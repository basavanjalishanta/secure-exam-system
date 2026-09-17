"""Document processing: text extraction (PDF/DOCX/TXT), cleaning, chunking,
and lightweight unit/topic detection.
"""
import io
import re

from config import config


# ---------------- Text extraction ----------------
def extract_text(filename: str, raw_bytes: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == ".pdf":
        return _extract_pdf(raw_bytes)
    if ext == ".docx":
        return _extract_docx(raw_bytes)
    if ext == ".txt":
        return raw_bytes.decode("utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(raw_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw_bytes))
    pages_lines = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - a bad page shouldn't kill the upload
            text = ""
        pages_lines.append(text.splitlines())
    return _strip_repeated_boilerplate(pages_lines)


_DIGIT_RE = re.compile(r"\d+")


def _strip_repeated_boilerplate(pages_lines: list[list[str]]) -> str:
    """Drop lines that recur across many pages - college/dept name, faculty
    name, running chapter title, 'Page X of Y' footers - which have no
    sentence punctuation around them and otherwise pollute extracted text
    with junk that looks like real course content.
    """
    n_pages = len(pages_lines)
    if n_pages <= 1:
        return "\n".join("\n".join(lines) for lines in pages_lines)

    counts: dict[str, int] = {}
    for lines in pages_lines:
        seen_this_page = set()
        for line in lines:
            key = _DIGIT_RE.sub("#", line.strip().lower())
            if key and key not in seen_this_page:
                counts[key] = counts.get(key, 0) + 1
                seen_this_page.add(key)

    threshold = max(2, int(n_pages * 0.4))
    out_pages = []
    for lines in pages_lines:
        kept = []
        for line in lines:
            key = _DIGIT_RE.sub("#", line.strip().lower())
            if key and len(key) < 90 and counts.get(key, 0) >= threshold:
                continue  # repeated header/footer boilerplate
            kept.append(line)
        out_pages.append("\n".join(kept))
    return "\n".join(out_pages)


def _extract_docx(raw_bytes: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(raw_bytes))
    return "\n".join(p.text for p in document.paragraphs)


# ---------------- Cleaning ----------------
_WS_RE = re.compile(r"[ \t]+")
_MULTINL_RE = re.compile(r"\n{3,}")
_PAGE_NUM_RE = re.compile(r"^\s*(page\s*)?\d+\s*$", re.IGNORECASE)


def clean_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = _WS_RE.sub(" ", line).strip()
        if not line:
            lines.append("")
            continue
        if _PAGE_NUM_RE.match(line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    return _MULTINL_RE.sub("\n\n", cleaned).strip()


# ---------------- Unit / topic detection ----------------
_UNIT_RE = re.compile(
    r"\b(?:unit|module|chapter)\s*[-:]?\s*(\d+|[IVX]+)\b[ \t:.-]*(.{0,80})",
    re.IGNORECASE,
)

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


def detect_units(text: str) -> list[dict]:
    found = []
    for m in _UNIT_RE.finditer(text):
        token = m.group(1).upper()
        num = _ROMAN.get(token, None)
        if num is None:
            try:
                num = int(token)
            except ValueError:
                continue
        title = re.split(r"[\n\r]", m.group(2))[0].strip(" -:.")
        found.append({"unit": num, "title": title})
    # de-dup keeping first title seen
    seen = {}
    for f in found:
        seen.setdefault(f["unit"], f["title"])
    return [{"unit": u, "title": t} for u, t in sorted(seen.items())]


# ---------------- Chunking ----------------
def chunk_text(text: str, subject_units: list[int] | None = None) -> list[dict]:
    size = config.CHUNK_SIZE
    overlap = config.CHUNK_OVERLAP
    words = text.split()
    chunks: list[dict] = []
    i = 0
    step = max(1, size - overlap)
    # approximate: treat size as word count / ~5 chars per word
    words_per_chunk = max(80, size // 5)
    words_overlap = max(10, overlap // 5)
    step = max(1, words_per_chunk - words_overlap)
    while i < len(words):
        window = words[i : i + words_per_chunk]
        chunk_str = " ".join(window)
        unit = _guess_unit(chunk_str, subject_units)
        chunks.append({"text": chunk_str, "unit": unit, "index": len(chunks)})
        i += step
    return chunks


def _guess_unit(chunk: str, subject_units: list[int] | None) -> int | None:
    m = _UNIT_RE.search(chunk)
    if m:
        token = m.group(1).upper()
        return _ROMAN.get(token) or (int(token) if token.isdigit() else None)
    return None
