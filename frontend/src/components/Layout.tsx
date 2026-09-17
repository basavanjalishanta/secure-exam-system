import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const lecturerNav = [
  ["/dashboard", "Dashboard"],
  ["/subjects", "Subject Management"],
  ["/upload", "Upload Materials"],
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
  ["/question-bank", "Question Bank"],
  ["/papers", "Generated Papers"],
  ["/audit", "Audit Logs"],
  ["/settings", "Settings"],
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = user?.role === "admin" ? adminNav : lecturerNav;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="border-b border-slate-200 px-5 py-4">
          <p className="text-sm font-semibold text-brand-700">SecureExam AI</p>
          <p className="text-xs text-slate-400">Question Paper Management</p>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {items.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
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
