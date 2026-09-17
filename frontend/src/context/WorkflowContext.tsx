import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { Pattern, Question } from "../services/api";

interface WorkflowState {
  subjectId: string;
  setSubjectId: (id: string) => void;
  pattern: Pattern | null;
  setPattern: (p: Pattern | null) => void;
  questions: Question[];
  setQuestions: (q: Question[]) => void;
  validation: any;
  setValidation: (v: any) => void;
  reset: () => void;
}

const Ctx = createContext<WorkflowState>(null as unknown as WorkflowState);
const KEY = "workflow-state";

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const saved = (() => {
    try {
      return JSON.parse(sessionStorage.getItem(KEY) || "{}");
    } catch {
      return {};
    }
  })();

  const [subjectId, setSubjectId] = useState<string>(saved.subjectId || "");
  const [pattern, setPattern] = useState<Pattern | null>(saved.pattern || null);
  const [questions, setQuestions] = useState<Question[]>(saved.questions || []);
  const [validation, setValidation] = useState<any>(saved.validation || null);

  useEffect(() => {
    sessionStorage.setItem(KEY, JSON.stringify({ subjectId, pattern, questions, validation }));
  }, [subjectId, pattern, questions, validation]);

  return (
    <Ctx.Provider
      value={{
        subjectId,
        setSubjectId,
        pattern,
        setPattern,
        questions,
        setQuestions,
        validation,
        setValidation,
        reset: () => {
          setPattern(null);
          setQuestions([]);
          setValidation(null);
        },
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export const useWorkflow = () => useContext(Ctx);
