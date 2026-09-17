import { FormEvent, useEffect, useState } from "react";
import api from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";

export default function UserManagement() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "lecturer" });

  function load() {
    api.get("/users").then((r) => {
      setUsers(r.data.users);
      setLoading(false);
    });
  }
  useEffect(load, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setMsg("");
    try {
      await api.post("/users", form);
      setForm({ name: "", email: "", password: "", role: "lecturer" });
      load();
      setMsg("User created.");
    } catch (err: any) {
      setMsg(err.response?.data?.error || "Failed");
    }
  }

  async function patch(id: string, body: any) {
    await api.patch(`/users/${id}`, body);
    load();
  }
  async function del(id: string) {
    if (!confirm("Delete this user?")) return;
    await api.delete(`/users/${id}`);
    load();
  }

  if (loading) return <Spinner label="Loading users…" />;

  return (
    <div>
      <PageHeader title="User Management" subtitle="Add/remove users and assign roles" />
      {msg && <div className="mb-4"><Alert kind="info">{msg}</Alert></div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <form onSubmit={create} className="card space-y-3">
          <h3 className="font-medium">Add user</h3>
          {(["name", "email", "password"] as const).map((f) => (
            <div key={f}>
              <label className="label capitalize">{f}</label>
              <input
                className="input"
                type={f === "password" ? "password" : "text"}
                value={(form as any)[f]}
                onChange={(e) => setForm({ ...form, [f]: e.target.value })}
                required
              />
            </div>
          ))}
          <div>
            <label className="label">Role</label>
            <select
              className="input"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="lecturer">Lecturer</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button className="btn-primary w-full">Create</button>
        </form>

        <div className="card lg:col-span-2">
          <h3 className="mb-3 font-medium">All users ({users.length})</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2">Name</th>
                  <th className="py-2">Email</th>
                  <th className="py-2">Role</th>
                  <th className="py-2">Active</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-slate-100">
                    <td className="py-2">{u.name}</td>
                    <td className="py-2">{u.email}</td>
                    <td className="py-2">
                      <select
                        className="rounded border border-slate-300 px-1 text-xs"
                        value={u.role}
                        onChange={(e) => patch(u.id, { role: e.target.value })}
                      >
                        <option value="lecturer">lecturer</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td className="py-2">
                      <input
                        type="checkbox"
                        checked={u.active !== false}
                        onChange={(e) => patch(u.id, { active: e.target.checked })}
                      />
                    </td>
                    <td className="py-2">
                      <button className="text-xs text-red-600 hover:underline" onClick={() => del(u.id)}>
                        delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
