import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  // Question generation runs a local LLM sequentially per pattern slot -
  // a full 20-question paper can take several minutes on CPU-only hardware.
  timeout: 1800000, // 30 minutes
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && !location.pathname.startsWith("/login")) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default api;

// ---- typed helpers ----
export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "lecturer";
  active?: boolean;
  created_at?: string;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  semester: number;
  units: { unit: number; title: string }[];
  selected_pattern?: Pattern;
  pattern_analysis?: any;
  counts?: Record<string, number>;
}

export interface PatternSection {
  section: string;
  count: number;
  marks_each: number;
  total: number;
}
export interface Pattern {
  name: string;
  sections: PatternSection[];
  total_marks: number;
  format?: string;
  units?: number;
  sub_parts?: number[];
  marks_per_question?: number;
}

export interface Question {
  index?: number;
  section?: string;
  question: string;
  unit: number;
  topic: string;
  marks: number;
  difficulty: string;
  bloom_level: string;
  question_type: string;
  full_question_num?: number;
  sub_part?: string;
  is_or?: boolean;
  bl?: number;
  co?: number;
  po?: number;
  pso?: number;
  source?: string[];
  source_context?: string;
  similarity_score?: number;
  duplicate?: boolean;
  matched_question?: string | null;
  answer?: string;
  answer_support?: number;
  answer_sources?: string[];
}

export function questionPaperNumber(question: Question, index: number): string {
  const subPart = question.sub_part?.trim().replace(/[()]/g, "");
  const number =
    question.full_question_num != null
      ? `Q${String(question.full_question_num).padStart(2, "0")}`
      : `Q${(question.index ?? index) + 1}`;
  return subPart ? `${number}(${subPart})` : number;
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  verifyOtp: (email: string, otp: string) =>
    api.post("/auth/verify-otp", { email, otp }),
  register: (name: string, email: string, password: string) =>
    api.post("/auth/register", { name, email, password }),
  me: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
};
