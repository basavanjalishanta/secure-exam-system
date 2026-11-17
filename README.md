# Secure Examination Question Paper Management System (AI)

A full-stack web application that helps lecturers automatically generate structured
examination question papers and answer keys from **syllabus, textbooks, notes and
previous-year question papers**, using a Retrieval-Augmented Generation (RAG) pipeline
with a local LLaMA-compatible LLM.

The system combines AI question generation, previous-paper pattern analysis, automatic
exam-pattern selection, answer-key generation, a validation engine, semantic duplicate
detection, a MongoDB question bank, ReportLab PDF generation, **AES-256 encryption of
generated papers**, JWT authentication and role-based access control.

> Uploaded examination material never leaves your machine. The AI service talks only to a
> **local** LLaMA-compatible endpoint (or a bundled offline mock provider for testing).

---

## 1. Technology stack

| Layer            | Tech |
|------------------|------|
| Frontend         | React, TypeScript, Tailwind CSS, React Router, Axios, Vite |
| Backend          | Python, Flask, REST APIs |
| Database         | MongoDB |
| AI               | LLaMA-compatible local LLM (OpenAI-style API), RAG, embedding/vector search |
| Security         | JWT, bcrypt, AES-256-GCM, `.env` secrets, role-based authorization, audit logs |
| PDF              | ReportLab |
| Doc processing   | PDF / DOCX / TXT extraction, cleaning, chunking, embeddings |

---

## 2. Project structure

```
secure-exam-system/
├── backend/
│   ├── app.py                 # Flask app factory + blueprints + /api/health
│   ├── config.py              # all config from environment variables
│   ├── requirements.txt
│   ├── seed.py                # sample data (DBMS, 5 units, 2 previous papers)
│   ├── Dockerfile
│   ├── data/                  # sample syllabus / notes / previous papers (.txt)
│   ├── routes/                # auth, users, subjects, documents, pattern,
│   │                          # questions, answers, validation, papers,
│   │                          # question_bank, misc (audit + dashboard)
│   ├── services/              # ai_service, rag_service, pattern_service,
│   │                          # validation_service, pdf_service,
│   │                          # encryption_service, document_service
│   ├── models/db.py           # Mongo connection + collections + indexes
│   ├── utils/                 # security (JWT/bcrypt/guards), audit, serialization
│   ├── uploads/               # raw uploaded files
│   └── encrypted_papers/      # AES-256 ciphertext blobs (no plaintext PDFs)
├── frontend/
│   ├── src/
│   │   ├── components/        # Layout, ProtectedRoute, SubjectPicker, ui
│   │   ├── pages/             # 20 pages (see below)
│   │   ├── services/api.ts    # Axios instance + typed helpers
│   │   ├── hooks/ context/    # AuthContext, WorkflowContext
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── .env.example
├── docker-compose.yml
├── API.md                     # complete API documentation
└── README.md
```

---

## 3. Prerequisites

- **Python 3.11 or 3.12** (3.10+ works; some pinned wheels lag on 3.13/3.14)
- **Node.js 18+**
- **MongoDB 6/7** running locally, or a MongoDB Atlas connection string
- *(optional)* a local LLaMA-compatible server — [Ollama](https://ollama.com),
  `llama.cpp` server, [vLLM](https://github.com/vllm-project/vllm) or LM Studio.
  Without one, the app runs with the offline **mock** AI provider.

---

## 4. Setup

### 4.1 Clone & configure secrets

```bash
cd secure-exam-system
cp .env.example backend/.env
```

Edit `backend/.env` and set at least:

```bash
FLASK_SECRET_KEY=<random string>
JWT_SECRET=<random string>
MONGO_URI=mongodb://localhost:27017
# 32-byte AES key, base64 encoded:
AES_KEY_B64=<python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())">
```

Generate the AES key:

```bash
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
```

### 4.2 Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                       # creates sample data + prints demo credentials
python app.py                        # http://localhost:5000
```

`seed.py` prints the generated admin/lecturer passwords **once** — copy them.
Set `SEED_ADMIN_PASSWORD` / `SEED_LECTURER_PASSWORD` in `.env` first if you want fixed ones.

### 4.3 Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev                          # http://localhost:5173
```

### 4.4 Docker (alternative)

```bash
cp .env.example backend/.env         # fill in secrets first
docker compose up --build
# then, in another shell:
docker compose exec backend python seed.py
```

---

## 5. Using a real local LLaMA model

The app never calls a hosted API. Point it at a local OpenAI-compatible server:

```bash
# example: Ollama
ollama pull llama3
ollama serve                         # exposes http://localhost:11434/v1
```

In `backend/.env`:

```bash
AI_PROVIDER=llama
LLAMA_BASE_URL=http://localhost:11434/v1
LLAMA_MODEL=llama3
# optionally use the same server for embeddings:
EMBEDDING_PROVIDER=llama
EMBEDDING_MODEL=nomic-embed-text
```

Embedding options:
- `hash` – deterministic local fallback, zero extra dependencies (default)
- `sentence-transformers` – `pip install sentence-transformers`, runs a local model
- `llama` – uses the local server's `/embeddings` endpoint

The **mock** provider (`AI_PROVIDER=mock`) is for development/testing only. It does **not**
hardcode a question list — it composes questions and answers from the retrieved context
passages using Bloom-aware templates so the full pipeline can run offline.

---

## 6. Application workflow (as implemented)

1. Lecturer logs in.
2. Creates / selects a subject (e.g. *Database Management Systems*, 5 units).
3. Uploads syllabus, textbook, notes, previous question papers (PDF/DOCX/TXT).
4. Backend extracts text → cleans → chunks → embeds → stores in the `chunks` vector store.
5. **Previous Paper Analysis** – question counts, marks, types, unit distribution, repeated
   questions, frequently-asked topics, difficulty, section structure.
6. **Pattern Selection** – auto-select a pattern derived from the analysis, or pick one
   manually (Standard 2/6/10, 10+5+5, 8+6+6, 50-mark internal, …).
7. **AI Question Generation** – per pattern slot: RAG retrieval (unit-filtered) → LLM →
   structured JSON question (text, unit, topic, marks, difficulty, Bloom level, type) →
   semantic duplicate check → accept.
8. **Answer Key** – RAG retrieval from textbook/notes → answer whose depth scales with marks.
9. **Validation** – total marks, section structure, unit coverage, marks balance, question
   format, duplicate/similar questions, missing units, invalid format, hallucination
   (context-support score). *Fix Automatically* regenerates flagged questions.
10. **Duplicate detection** – cosine similarity of embeddings vs the question bank and the
    current paper; near-duplicates are rejected and regenerated.
11. **Question Bank** – every validated question stored with its embedding and `usage_count`.
12. **Generate Paper** – ReportLab builds a university-style question paper + answer key.
13. **Security** – both PDFs are encrypted with **AES-256-GCM**; only the ciphertext +
    metadata (nonce, algorithm, owner, permissions) is stored. Plaintext PDFs are never
    persisted. Downloads are decrypted on the fly for authorized users only; others get
    **Access Denied**.
14. **Audit logging** – every security-relevant action is written to `audit_logs`.

---

## 7. Frontend pages

Login · Register · Dashboard (lecturer) · Admin Dashboard · Subject Management ·
Upload Materials · Previous Paper Analysis · Pattern Selection · AI Question Generation ·
Question Review (editable cards, regenerate/delete) · Answer Key · Validation Results ·
Question Bank · Generate Paper · Generated Papers · Secure Download · User Management ·
Audit Logs · Settings.

---

## 8. User roles

**Admin** – add/remove users, assign lecturer/admin roles, manage subjects, view system
activity & audit logs, view generated-paper metadata, manage the question bank, monitor
generation history.

**Lecturer** – register/login, upload materials, analyze previous papers, generate a
question paper and answer key, review/regenerate/validate questions, create the PDF,
encrypt it, view/download authorized papers and answer keys, share access with another
lecturer.

---

## 9. Database

MongoDB collections: `users`, `subjects`, `documents`, `chunks` (vector store),
`question_bank`, `question_papers`, `generated_questions`, `answers` (reserved),
`exam_patterns` (reserved), `audit_logs`.
Indexes are created automatically on startup (`models/db.ensure_indexes`).
See `API.md` for document shapes.

### Reset / re-seed

```bash
python seed.py --reset      # drops all collections, then re-creates the sample data
```

### Utility scripts

```bash
python manage_users.py list
python manage_users.py set-password admin@example.edu "NewPass123!"   # lost the seeded password
python manage_users.py promote lecturer@example.edu                    # make an existing user admin
python manage_users.py create-admin "Jane Doe" jane@example.edu "Pass123!"

python reindex_subject.py <subject_id>   # re-run extraction/chunking/embedding for files
                                          # still in uploads/, without re-uploading them
                                          # (use after a document_service fix or config change)
```

---

## 10. Security checklist

- [x] JWT bearer authentication, 12h expiry, secret from `.env`
- [x] bcrypt password hashing (cost 12)
- [x] Role-based authorization decorators (`admin_required`, `lecturer_required`)
- [x] AES-256-GCM encryption of generated papers + answer keys
- [x] Plaintext PDFs never written to disk
- [x] Per-paper access-control list; unauthorized access returns *Access Denied*
- [x] All secrets via environment variables; `.env.example` provided; `.env` git-ignored
- [x] File-type + size validation on upload
- [x] Audit log for login, uploads, generation, validation, paper creation, downloads,
      access-denied events, user/role changes
- [x] Uploaded material is only sent to a local LLM, never to an external API

---

## 11. Tests

Two offline check scripts are included for reference and can be re-created from the repo
history; the shipped project is verified with an in-memory MongoDB covering the full
workflow (upload → analyze → generate → answer → validate → paper → encrypt → download →
access control → audit).

---

## 12. Sample data

`python seed.py` loads **Database Management Systems (BCS401)** with 5 units and two
previous question papers (May 2023, Nov 2022), so the system is testable immediately.


## Email two-step login verification

Login now uses two factors: (1) the user's email and password, then (2) a six-digit OTP sent to that email. The API issues the JWT only after the OTP is verified. OTPs expire after five minutes and are limited to five incorrect attempts.

Configure Gmail SMTP in `backend/.env` (do not use your normal Gmail password):

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=yourgmail@gmail.com
SMTP_PASSWORD=your-16-character-google-app-password
SMTP_FROM_EMAIL=yourgmail@gmail.com
EMAIL_OTP_TTL_MINUTES=5
```

To create a Gmail App Password, enable 2-Step Verification on the Google account, then open Google Account > Security > 2-Step Verification > App passwords. Generate an app password and paste it into `SMTP_PASSWORD` (remove spaces). App passwords may not be available for some managed or protected Google accounts.

Restart the Flask backend after editing `backend/.env`. During login, enter the password first, then enter the code received in the registered email inbox (check Spam/Junk too). If mail delivery fails, verify the SMTP username, App Password, and outbound SMTP access. The OTP endpoint is `POST /api/auth/verify-otp`.
