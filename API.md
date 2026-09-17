# API Documentation

Base URL: `http://localhost:5000/api`

Auth: send `Authorization: Bearer <JWT>` on every protected endpoint.
Roles: `lecturer` endpoints also accept `admin`; `admin` endpoints require the admin role.

| Symbol | Meaning |
|--------|---------|
| 🔓 | public |
| 🔑 | any authenticated user |
| 👨‍🏫 | lecturer or admin |
| 🛡️ | admin only |

---

## Auth

### 🔓 POST `/auth/register`
Body: `{ "name", "email", "password" (>=8) }`
The **first** account created on a fresh system becomes `admin`; all later
self-registrations are `lecturer`.
→ `201 { "token", "user" }`

### 🔓 POST `/auth/login`
Body: `{ "email", "password" }` → `200 { "token", "user" }` / `401`

### 🔑 POST `/auth/logout`
Stateless — client discards the token. Audited. → `200`

### 🔑 GET `/auth/me` → `{ "user" }`

---

## Users (🛡️)

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/users` | — | list all users |
| POST | `/users` | `{name,email,password,role}` | create user |
| PATCH | `/users/:id` | `{role?, active?, password?}` | update |
| DELETE | `/users/:id` | — | cannot delete self |

---

## Subjects (👨‍🏫; DELETE is 🛡️)

| Method | Path | Body |
|--------|------|------|
| GET | `/subjects` | — |
| GET | `/subjects/:id` | — (includes `counts`, `pattern_analysis`, `selected_pattern`) |
| POST | `/subjects` | `{name, code, semester, units:[{unit,title}]}` |
| PATCH | `/subjects/:id` | `{name?, semester?, units?}` |
| DELETE | `/subjects/:id` | — (also removes its documents + chunks) |

---

## Documents (👨‍🏫)

### POST `/documents/upload` — `multipart/form-data`
Fields: `subject_id`, `type` (`syllabus|textbook|notes|previous_paper`), `file` (`.pdf/.docx/.txt`)
Extracts text → cleans → chunks → embeds → indexes. → `201 { document }`

### GET `/documents/:subject_id` → `{ documents:[…] }` (preview only, no full text)

### DELETE `/documents/:document_id` → removes the doc and its chunks

---

## Pattern (👨‍🏫)

### GET `/pattern/defaults` → `{ patterns:[…] }`
Built-in patterns: Standard 2/6/10, 10+5+5, 8+6+6, 50-mark internal.

### POST `/pattern/analyze`
Body: `{ subject_id }` — analyzes all uploaded `previous_paper` docs.
→ `{ analysis: { papers_analyzed, questions_found, marks_distribution,
question_type_distribution, difficulty_distribution, unit_distribution_percent,
frequently_asked_topics, repeated_questions, section_structure, suggested_pattern } }`

### POST `/pattern/select`
Body: `{ subject_id, mode: "auto"|"manual", pattern? }`
Persists `selected_pattern` on the subject. → `{ pattern, mode }`

---

## Questions (👨‍🏫)

### POST `/questions/generate`
Body:
```json
{
  "subject_id": "…",
  "pattern": { … },              // optional; falls back to subject.selected_pattern
  "units": [1,2,3,4,5],          // optional
  "unit_weights": {"unit_1":0.2},// optional; default from pattern analysis
  "difficulty": "Medium",        // optional override
  "bloom_level": "Understand"    // optional override
}
```
For each pattern slot: RAG retrieval (unit-filtered) → LLM → JSON question → duplicate
check. → `{ generation_id, pattern, questions:[…], provider }`

Each question:
```json
{
  "section": "B", "question": "…", "unit": 4, "topic": "Normalization",
  "marks": 6, "difficulty": "Medium", "bloom_level": "Understand",
  "question_type": "Theory", "source": ["textbook (unit 4, score 0.72)"],
  "source_context": "…", "similarity_score": 0.31, "duplicate": false,
  "matched_question": null, "index": 10
}
```

### POST `/questions/regenerate`
Body: `{ subject_id, question, existing_questions?:[…], topic_hint? }`
→ `{ question }` (a fresh non-duplicate question for the same slot)

---

## Answers (👨‍🏫)

### POST `/answers/generate`
Body: `{ subject_id, questions:[…] }`
RAG retrieval from textbook/notes; answer depth scales with marks
(2 → key points, 6 → definition+explanation+example, 10 → detailed + diagram note).
→ `{ questions:[… + answer, answer_support, answer_sources] }`

---

## Validation (👨‍🏫)

### POST `/validation/validate`
Body: `{ subject_id, pattern, questions:[…] }`
Checks: total marks, section structure, unit coverage, marks balance, question format,
semantic duplicates within the paper, repeats vs question bank, hallucination
(context-support score), difficulty spread.
→ `{ validation: { valid, checks:[{check,ok,detail}], errors:[{type,message,question_index?}], summary } }`

### POST `/validation/fix`
Body: `{ subject_id, pattern, questions:[…] }`
Regenerates every question flagged with a `question_index` and re-validates.
→ `{ questions:[…], fixed_indexes:[…], validation }`

---

## Papers

### 👨‍🏫 POST `/papers/generate`
Body: `{ subject_id, pattern, questions:[…], meta:{college_name,exam_name,date,time,instructions[]} }`
- builds question-paper PDF + answer-key PDF (ReportLab)
- encrypts both with AES-256-GCM; stores ciphertext + metadata only
- stores validated questions in the question bank
→ `201 { paper: { id, subject_name, total_marks, question_count, encrypted,
encryption:{paper:{algorithm,size_bytes},answer_key:{…}}, questions_added_to_bank } }`

### 👨‍🏫 POST `/papers/:id/encrypt`
Returns encryption status. → `{ paper_id, encrypted, algorithm, plaintext_stored:false }`

### 🔑 GET `/papers`
Lecturer: own + shared papers. Admin: all. → `{ papers:[metadata…] }`

### 🔑 GET `/papers/:id`
Authorized → full metadata. Unauthorized → `403 { paper:{…minimal}, message:"Access Denied" }`

### 👨‍🏫 POST `/papers/:id/share`
Body: `{ email }` — grants another lecturer access (owner/admin only). → `{ message }`

### 🔑 GET `/papers/:id/download?type=paper|answer_key`
Decrypts on the fly for authorized users; streams `application/pdf`.
Unauthorized → `403 Access Denied` (audited).

---

## Question Bank (👨‍🏫)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/question-bank?subject_id=&unit=&difficulty=&search=` | list (max 500) |
| POST | `/question-bank` | `{subject_id, question, …}` — rejects near-duplicates (`409`) |
| DELETE | `/question-bank/:id` | remove |

---

## Audit & Dashboard

### 🛡️ GET `/audit-logs?action=&limit=` → `{ logs:[…] }`

### 🔑 GET `/dashboard/stats`
→ `{ stats:{total_subjects,total_questions,generated_papers,uploaded_documents},
difficulty_distribution, unit_coverage, question_type_distribution,
recent_activity:[…], generation_history:[…] }`

### 🔓 GET `/health` → `{ status, mongo, ai_provider }`

---

## Error format

All errors: `{ "error": "message" }` with an appropriate HTTP status
(`400` bad request, `401` unauthenticated, `403` forbidden / Access Denied,
`404` not found, `409` conflict, `413` file too large, `422` unprocessable, `500`).
