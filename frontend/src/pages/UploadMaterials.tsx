import { FormEvent, useEffect, useState } from "react";
import api from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import SubjectPicker from "../components/SubjectPicker";
import { useWorkflow } from "../context/WorkflowContext";

const TYPES = [
  ["syllabus", "Syllabus"],
  ["textbook", "Textbook"],
  ["notes", "Notes"],
  ["previous_paper", "Previous Question Paper"],
] as const;

export default function UploadMaterials() {
  const { subjectId } = useWorkflow();
  const [docs, setDocs] = useState<any[]>([]);
  const [type, setType] = useState("syllabus");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  function load() {
    if (!subjectId) return;
    setLoading(true);
    api.get(`/documents/${subjectId}`).then((r) => {
      setDocs(r.data.documents);
      setLoading(false);
    });
  }
  useEffect(load, [subjectId]);

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!subjectId || !file) return;
    setBusy(true);
    setMsg("");
    const fd = new FormData();
    fd.append("subject_id", subjectId);
    fd.append("type", type);
    fd.append("file", file);
    try {
      const r = await api.post("/documents/upload", fd);
      setMsg(`Uploaded "${r.data.document.filename}" — ${r.data.document.chunks_indexed} chunks indexed.`);
      setFile(null);
      load();
    } catch (err: any) {
      setMsg(err.response?.data?.error || "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await api.delete(`/documents/${id}`);
    load();
  }

  return (
    <div>
      <PageHeader title="Upload Materials" subtitle="PDF / DOCX / TXT — text is extracted, chunked and embedded for RAG" />
      <SubjectPicker />
      {!subjectId && <Alert kind="info">Select a subject to upload materials.</Alert>}

      {subjectId && (
        <div className="grid gap-6 lg:grid-cols-2">
          <form onSubmit={upload} className="card space-y-3">
            <h3 className="font-medium">Upload document</h3>
            <div>
              <label className="label">Document type</label>
              <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
                {TYPES.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">File</label>
              <input
                className="input"
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
              />
            </div>
            {msg && <Alert kind="info">{msg}</Alert>}
            <button className="btn-primary w-full" disabled={busy || !file}>
              {busy ? "Processing…" : "Upload & index"}
            </button>
          </form>

          <div className="card">
            <h3 className="mb-3 font-medium">Uploaded documents</h3>
            {loading ? (
              <Spinner />
            ) : (
              <ul className="space-y-2 text-sm">
                {docs.map((d) => (
                  <li key={d.id} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{d.filename}</span>
                      <button className="text-xs text-red-600 hover:underline" onClick={() => remove(d.id)}>
                        delete
                      </button>
                    </div>
                    <p className="text-xs text-slate-500">
                      {d.type} · {d.char_count} chars · {d.chunks_indexed ?? "?"} chunks
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-400">{d.preview}</p>
                  </li>
                ))}
                {docs.length === 0 && <li className="text-slate-400">Nothing uploaded yet.</li>}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
