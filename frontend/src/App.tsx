import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { WorkflowProvider } from "./context/WorkflowContext";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import AdminDashboard from "./pages/AdminDashboard";
import SubjectManagement from "./pages/SubjectManagement";
import UploadMaterials from "./pages/UploadMaterials";
import PreviousPaperAnalysis from "./pages/PreviousPaperAnalysis";
import PatternSelection from "./pages/PatternSelection";
import QuestionGeneration from "./pages/QuestionGeneration";
import QuestionReview from "./pages/QuestionReview";
import AnswerKey from "./pages/AnswerKey";
import ValidationResults from "./pages/ValidationResults";
import QuestionBank from "./pages/QuestionBank";
import GeneratePaper from "./pages/GeneratePaper";
import GeneratedPapers from "./pages/GeneratedPapers";
import SecureDownload from "./pages/SecureDownload";
import UserManagement from "./pages/UserManagement";
import AuditLogs from "./pages/AuditLogs";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <ProtectedRoute>
            <WorkflowProvider>
              <Layout />
            </WorkflowProvider>
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/admin" element={<ProtectedRoute roles={["admin"]}><AdminDashboard /></ProtectedRoute>} />
        <Route path="/users" element={<ProtectedRoute roles={["admin"]}><UserManagement /></ProtectedRoute>} />
        <Route path="/audit" element={<ProtectedRoute roles={["admin"]}><AuditLogs /></ProtectedRoute>} />
        <Route path="/subjects" element={<SubjectManagement />} />
        <Route path="/upload" element={<UploadMaterials />} />
        <Route path="/analysis" element={<PreviousPaperAnalysis />} />
        <Route path="/pattern" element={<PatternSelection />} />
        <Route path="/generate" element={<QuestionGeneration />} />
        <Route path="/review" element={<QuestionReview />} />
        <Route path="/answers" element={<AnswerKey />} />
        <Route path="/validation" element={<ValidationResults />} />
        <Route path="/question-bank" element={<QuestionBank />} />
        <Route path="/paper" element={<GeneratePaper />} />
        <Route path="/papers" element={<GeneratedPapers />} />
        <Route path="/papers/:id" element={<SecureDownload />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
