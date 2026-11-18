import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { Subject } from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import SubjectPicker from "../components/SubjectPicker";
import { useWorkflow } from "../context/WorkflowContext";

interface LectureSession {
  sl_no: number;
  unit: number;
  topic: string;
  methodology: string;
  assessment_tool: string;
}

interface CourseOutcome {
  co: string;
  text: string;
  bloom: string;
  unit: number;
}

interface LessonPlanData {
  _id: string;
  subject_id: string;
  course_title: string;
  course_code: string;
  semester: number;
  section: string;
  academic_year: string;
  total_contact_hours: number;
  l_t_p: string;
  cie_marks: number;
  see_marks: number;
  faculty_name: string;
  designation: string;
  prerequisites: string[];
  course_objectives: string[];
  course_outcomes: CourseOutcome[];
  textbooks: any[];
  references: any[];
  lecture_schedule: LectureSession[];
  test_schedule: {
    test_1: string;
    test_2: string;
    quiz_1: string;
    quiz_2: string;
  };
  approved: boolean;
  status: string;
}

export default function LessonPlan() {
  const navigate = useNavigate();
  const { subjectId, setSubjectId } = useWorkflow();
  const [subject, setSubject] = useState<Subject | null>(null);
  const [plan, setPlan] = useState<LessonPlanData | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const [meta, setMeta] = useState({
    academic_year: "2024-25 (Odd)",
    section: "CSE 'A'",
    classes_per_week: 3,
    class_duration: "1 Hour",
    weeks_per_sem: 14,
    total_contact_hours: 42,
    l_t_p: "3-0-0",
    faculty_name: "Dr. A V Krishna Mohan",
    designation: "Assistant Professor",
  });

  function handleClassesPerWeekChange(classes: number) {
    const total = classes * meta.weeks_per_sem;
    setMeta({
      ...meta,
      classes_per_week: classes,
      total_contact_hours: total,
      l_t_p: `${classes}-0-0`,
    });
  }

  function handleTotalHoursChange(hours: number) {
    setMeta({
      ...meta,
      total_contact_hours: hours,
    });
  }

  const [showConfig, setShowConfig] = useState(false);

  function onSubject(s: Subject | null) {
    setSubject(s);
    if (s) {
      setSubjectId(s.id);
      loadPlan(s.id);
    } else {
      setPlan(null);
    }
  }

  async function loadPlan(sid: string) {
    setLoading(true);
    setErr("");
    try {
      const res = await api.get(`/lesson-plans/subject/${sid}`);
      setPlan(res.data.lesson_plan);
      if (res.data.lesson_plan) {
        const lp = res.data.lesson_plan;
        setMeta((prev) => ({
          ...prev,
          academic_year: lp.academic_year || prev.academic_year,
          section: lp.section || prev.section,
          classes_per_week: lp.classes_per_week || prev.classes_per_week,
          total_contact_hours: lp.total_contact_hours || prev.total_contact_hours,
          l_t_p: lp.l_t_p || prev.l_t_p,
          faculty_name: lp.faculty_name || prev.faculty_name,
          designation: lp.designation || prev.designation,
        }));
      }
    } catch (e: any) {
      setErr("Failed to load lesson plan.");
    } finally {
      setLoading(false);
    }
  }

  async function generatePlan() {
    if (!subjectId) return;
    setGenerating(true);
    setErr("");
    setMsg("");
    try {
      const res = await api.post("/lesson-plans/generate", {
        subject_id: subjectId,
        meta,
      });
      setPlan(res.data.lesson_plan);
      setMsg("Course Lesson Plan generated successfully following NBA/VTU OBE guidelines.");
    } catch (e: any) {
      setErr(e.response?.data?.error || "Lesson plan generation failed");
    } finally {
      setGenerating(false);
    }
  }

  async function approvePlan() {
    if (!plan) return;
    try {
      await api.post(`/lesson-plans/${plan._id}/approve`);
      setPlan({ ...plan, approved: true, status: "approved" });
      setMsg("Lesson Plan approved by Faculty In-Charge.");
    } catch (e: any) {
      setErr("Could not approve lesson plan");
    }
  }

  async function downloadPdf() {
    if (!plan) return;
    try {
      setMsg("Preparing PDF download...");
      const res = await api.get(`/lesson-plans/${plan._id}/export-pdf`, {
        responseType: "blob",
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `Course_Plan_${plan.course_code || "Subject"}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      setMsg("Course Plan PDF downloaded successfully.");
    } catch (e: any) {
      setErr("Failed to download Course Plan PDF. Check server connection.");
    }
  }

  function updateTopic(sl_no: number, newTopic: string) {
    if (!plan) return;
    const updated = plan.lecture_schedule.map((s) =>
      s.sl_no === sl_no ? { ...s, topic: newTopic } : s
    );
    setPlan({ ...plan, lecture_schedule: updated });
  }

  return (
    <div>
      <PageHeader
        title="Course Lesson Plan (OBE / NBA Standard)"
        subtitle="Outcome-Based Course Planning: Lecture Schedules, Course Outcomes, and Pedagogy"
      />
      <SubjectPicker onChange={onSubject} />

      {err && <Alert kind="error">{err}</Alert>}
      {msg && <Alert kind="success">{msg}</Alert>}

      {!subjectId && <Alert kind="info">Select a subject to view or generate its lesson plan.</Alert>}

      {loading && <Spinner label="Loading course plan..." />}

      {subject && !loading && (
        <div className="space-y-6 mt-4">
          {generating && (
            <div className="space-y-1">
              <Spinner label="Generating OBE course outcomes with local Ollama..." />
              <p className="text-sm text-slate-500">
                Local generation can take about a minute. Keep this page open while the plan is being created.
              </p>
            </div>
          )}
          {!plan ? (
            <div className="card space-y-4">
              <h3 className="font-semibold text-lg text-slate-800">Generate Structured Course Plan</h3>
              <p className="text-sm text-slate-600">
                The system extracts syllabus units, learning objectives, and allocated teaching hours to synthesize
                a comprehensive 42-hour lecture schedule aligned with OBE principles.
              </p>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <label className="label">Classes Per Week</label>
                  <select
                    className="input font-medium text-brand-700"
                    value={meta.classes_per_week}
                    onChange={(e) => handleClassesPerWeekChange(Number(e.target.value))}
                  >
                    <option value={3}>3 classes / week (Standard 42 Hours)</option>
                    <option value={4}>4 classes / week (Extended 56 Hours)</option>
                    <option value={5}>5 classes / week (Core 70 Hours)</option>
                  </select>
                </div>
                <div>
                  <label className="label">Class Duration</label>
                  <input
                    className="input bg-slate-50 text-slate-500"
                    readOnly
                    value="1 Hour per class"
                  />
                </div>
                <div>
                  <label className="label">Total Classes in Semester</label>
                  <input
                    className="input font-bold text-slate-800"
                    type="number"
                    value={meta.total_contact_hours}
                    onChange={(e) => handleTotalHoursChange(Number(e.target.value))}
                  />
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {meta.classes_per_week} classes/week × {meta.weeks_per_sem} weeks
                  </p>
                </div>
                <div>
                  <label className="label">L-T-P Structure</label>
                  <input
                    className="input font-mono"
                    value={meta.l_t_p}
                    onChange={(e) => setMeta({ ...meta, l_t_p: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Academic Year</label>
                  <input
                    className="input"
                    value={meta.academic_year}
                    onChange={(e) => setMeta({ ...meta, academic_year: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Section</label>
                  <input
                    className="input"
                    value={meta.section}
                    onChange={(e) => setMeta({ ...meta, section: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Faculty Name</label>
                  <input
                    className="input"
                    value={meta.faculty_name}
                    onChange={(e) => setMeta({ ...meta, faculty_name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Designation</label>
                  <input
                    className="input"
                    value={meta.designation}
                    onChange={(e) => setMeta({ ...meta, designation: e.target.value })}
                  />
                </div>
              </div>

              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                <b>Intelligent Topic Weighting:</b> The system analyzes topic difficulty and conceptual depth (e.g. Trees, Dynamic Memory, and Pointer Recursion allocate more hours; simpler foundations allocate fewer hours).
              </div>

              <div className="pt-2">
                <button
                  className="btn-primary"
                  onClick={generatePlan}
                  disabled={generating}
                >
                  {generating ? "Synthesizing Course Plan..." : "Generate Course Lesson Plan"}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Header / Actions Card */}
              <div className="card flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold text-slate-800">{plan.course_title}</h2>
                    <span className="badge bg-brand-50 text-brand-700 font-mono font-bold">
                      {plan.course_code}
                    </span>
                    {plan.approved ? (
                      <span className="badge bg-green-100 text-green-800">Approved</span>
                    ) : (
                      <span className="badge bg-amber-100 text-amber-800">Draft</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Semester {plan.semester} · {plan.section} · {plan.total_contact_hours} Contact Hours · Faculty: {plan.faculty_name}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button className="btn-ghost" onClick={downloadPdf}>
                    📄 Export Course Plan PDF
                  </button>
                  {!plan.approved && (
                    <button className="btn-primary" onClick={approvePlan}>
                      ✓ Approve Plan
                    </button>
                  )}
                  <button
                    className="btn-ghost"
                    onClick={() => setShowConfig(!showConfig)}
                  >
                    ⚙ Configure & Regenerate
                  </button>
                  <button
                    className="btn-primary"
                    onClick={() => navigate("/pattern")}
                  >
                    Proceed to Examination Pattern →
                  </button>
                </div>
              </div>

              {/* Collapsible Re-configuration Card */}
              {showConfig && (
                <div className="card space-y-4 border border-brand-200 bg-brand-50/20">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-800">Adjust Hours & Regenerate Course Plan</h3>
                    <button
                      className="text-xs text-slate-500 hover:text-slate-800"
                      onClick={() => setShowConfig(false)}
                    >
                      ✕ Close
                    </button>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div>
                      <label className="label">Classes Per Week</label>
                      <select
                        className="input font-medium text-brand-700"
                        value={meta.classes_per_week}
                        onChange={(e) => handleClassesPerWeekChange(Number(e.target.value))}
                      >
                        <option value={3}>3 classes / week (Standard 42 Hours)</option>
                        <option value={4}>4 classes / week (Extended 56 Hours)</option>
                        <option value={5}>5 classes / week (Core 70 Hours)</option>
                      </select>
                    </div>
                    <div>
                      <label className="label">Total Classes in Semester</label>
                      <input
                        className="input font-bold text-slate-800"
                        type="number"
                        value={meta.total_contact_hours}
                        onChange={(e) => handleTotalHoursChange(Number(e.target.value))}
                      />
                    </div>
                    <div>
                      <label className="label">L-T-P Structure</label>
                      <input
                        className="input font-mono"
                        value={meta.l_t_p}
                        onChange={(e) => setMeta({ ...meta, l_t_p: e.target.value })}
                      />
                    </div>
                  </div>

                  <button
                    className="btn-primary"
                    onClick={generatePlan}
                    disabled={generating}
                  >
                    {generating ? "Re-synthesizing Course Plan..." : "↺ Apply & Regenerate"}
                  </button>
                </div>
              )}

              {/* Course Outcomes & Objectives */}
              <div className="grid gap-6 md:grid-cols-2">
                <div className="card space-y-3">
                  <h3 className="font-semibold text-sm text-slate-700 uppercase tracking-wide">Course Objectives</h3>
                  <ul className="space-y-1.5 text-xs text-slate-600 list-disc list-inside">
                    {plan.course_objectives.map((obj, i) => (
                      <li key={i}>{obj}</li>
                    ))}
                  </ul>

                  <h3 className="font-semibold text-sm text-slate-700 uppercase tracking-wide pt-2">Prerequisites</h3>
                  <ul className="space-y-1 text-xs text-slate-600 list-disc list-inside">
                    {plan.prerequisites.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>

                <div className="card space-y-3">
                  <h3 className="font-semibold text-sm text-slate-700 uppercase tracking-wide">Course Outcomes (COs)</h3>
                  <div className="space-y-2">
                    {plan.course_outcomes.map((co) => (
                      <div key={co.co} className="text-xs bg-slate-50 p-2.5 rounded border border-slate-100">
                        <span className="font-bold text-brand-700">{co.co}:</span> {co.text}
                        <div className="mt-1 flex gap-2">
                          <span className="badge bg-white text-slate-500 border">Unit {co.unit}</span>
                          <span className="badge bg-brand-50 text-brand-600 border border-brand-200">Bloom: {co.bloom}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Detailed Lecture Schedule Table */}
              <div className="card space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-800">Lecture-by-Lecture Teaching Schedule (42 Hours)</h3>
                    <p className="text-xs text-slate-500">
                      Topic coverage distributed across syllabus units. You may click on any topic to edit inline.
                    </p>
                  </div>
                  <div className="text-xs text-slate-600 font-medium">
                    Total Sessions: <span className="text-brand-700 font-bold">{plan.lecture_schedule.length}</span>
                  </div>
                </div>

                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-100 text-slate-700 uppercase font-semibold">
                      <tr>
                        <th className="p-2.5 w-12 text-center">Sl</th>
                        <th className="p-2.5 w-20">Unit</th>
                        <th className="p-2.5">Topic / Subtopic</th>
                        <th className="p-2.5 w-44">Methodology</th>
                        <th className="p-2.5 w-44">Assessment Tool</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {plan.lecture_schedule.map((s) => (
                        <tr key={s.sl_no} className="hover:bg-slate-50/80 transition-colors">
                          <td className="p-2.5 text-center font-bold text-slate-500">{s.sl_no}</td>
                          <td className="p-2.5 font-medium text-brand-700">Unit {s.unit}</td>
                          <td className="p-2.5">
                            <input
                              className="w-full bg-transparent hover:bg-white focus:bg-white border-b border-transparent focus:border-brand-500 px-1 py-0.5 outline-none text-slate-800"
                              value={s.topic}
                              onChange={(e) => updateTopic(s.sl_no, e.target.value)}
                            />
                          </td>
                          <td className="p-2.5 text-slate-500">{s.methodology}</td>
                          <td className="p-2.5 text-slate-500">{s.assessment_tool}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Milestone Schedule */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-wrap gap-6 text-xs text-slate-700">
                  <div><b>Test 1:</b> {plan.test_schedule.test_1}</div>
                  <div><b>Test 2:</b> {plan.test_schedule.test_2}</div>
                  <div><b>Quiz 1 & 2:</b> {plan.test_schedule.quiz_1}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
