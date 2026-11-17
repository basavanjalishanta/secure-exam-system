import { useEffect, useState } from "react";
import api, { Subject } from "../services/api";
import { useWorkflow } from "../context/WorkflowContext";

export default function SubjectPicker({ onChange }: { onChange?: (s: Subject | null) => void }) {
  const { subjectId, setSubjectId } = useWorkflow();
  const [subjects, setSubjects] = useState<Subject[]>([]);

  useEffect(() => {
    api.get("/subjects").then((r) => setSubjects(r.data.subjects));
  }, []);

  useEffect(() => {
    onChange?.(subjects.find((s) => s.id === subjectId) || null);
  }, [subjectId, subjects]);

  return (
    <div className="mb-5">
      <label className="label">Active subject</label>
      <select className="input max-w-md" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
        <option value="">— select a subject —</option>
        {subjects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} ({s.code})
          </option>
        ))}
      </select>
    </div>
  );
}
