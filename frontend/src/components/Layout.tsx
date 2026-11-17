import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const lecturerNav = [
  ["/dashboard", "Dashboard"],
  ["/subjects", "Subject Management"],
  ["/upload", "Upload Materials"],
  ["/lesson-plan", "Lesson Plan"],
  ["/analysis", "Previous Paper Analysis"],
  ["/pattern", "Pattern Selection"],
  ["/generate", "AI Question Generation"],
  ["/review", "Question Review"],
  ["/answers", "Answer Key"],
  ["/validation", "Validation Results"],
  ["/question-bank", "Question Bank"],
  ["/paper", "Generate Paper"],
  ["/papers", "Generated Papers"],
  ["/settings", "Settings"],
];

const adminNav = [
  ["/dashboard", "Dashboard"],
  ["/admin", "Admin Dashboard"],
  ["/users", "User Management"],
  ["/subjects", "Subject Management"],
  ["/upload", "Upload Materials"],
  ["/lesson-plan", "Lesson Plan"],
  ["/analysis", "Previous Paper Analysis"],
  ["/pattern", "Pattern Selection"],
  ["/generate", "AI Question Generation"],
  ["/review", "Question Review"],
  ["/answers", "Answer Key"],
  ["/validation", "Validation Results"],
  ["/question-bank", "Question Bank"],
  ["/paper", "Generate Paper"],
  ["/papers", "Generated Papers"],
  ["/audit", "Audit Logs"],
  ["/settings", "Settings"],
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const items = user?.role === "admin" ? adminNav : lecturerNav;

  const closeMobile = () => setMobileOpen(false);

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* Mobile top navigation header */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
        <div>
          <p className="text-sm font-bold text-brand-700">SecureExam AI</p>
          <p className="text-xs text-slate-400">Exam Question Paper System</p>
        </div>
        <button
          className="btn-ghost rounded p-1.5 text-slate-600"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle navigation"
        >
          {mobileOpen ? (
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </header>

      {/* Sidebar for desktop and mobile drawer */}
      <aside
        className={`${
          mobileOpen ? "flex" : "hidden"
        } w-full shrink-0 flex-col border-r border-slate-200 bg-white md:flex md:w-64`}
      >
        <div className="hidden border-b border-slate-200 px-5 py-4 md:block">
          <p className="text-sm font-semibold text-brand-700">SecureExam AI</p>
          <p className="text-xs text-slate-400">Question Paper Management</p>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {items.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              onClick={closeMobile}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-4 text-xs">
          <p className="font-medium text-slate-700">{user?.name}</p>
          <p className="text-slate-400">
            {user?.email} · <span className="badge bg-slate-100 text-slate-600">{user?.role}</span>
          </p>
          <button
            className="btn-ghost mt-3 w-full"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Logout
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-x-hidden p-6">
        <Outlet />
      </main>
    </div>
  );
}
