import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";

export default function SecureDownload() {
  const { id } = useParams();
  const [paper, setPaper] = useState<any>(null);
  const [denied, setDenied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [shareEmail, setShareEmail] = useState("");

  function load() {
    api
      .get(`/papers/${id}`)
      .then((r) => setPaper(r.data.paper))
      .catch((e) => {
        if (e.response?.status === 403) {
          setDenied(true);
          setPaper(e.response.data.paper);
        } else setMsg("Failed to load paper");
      })
      .finally(() => setLoading(false));
  }
  useEffect(load, [id]);

  async function download(kind: "paper" | "answer_key") {
    try {
      const r = await api.get(`/papers/${id}/download?type=${kind}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${paper.subject_name || "paper"}_${kind}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setMsg("Download failed or access denied.");
    }
  }

  async function share() {
    try {
      await api.post(`/papers/${id}/share`, { email: shareEmail });
      setMsg(`Access granted to ${shareEmail}`);
      setShareEmail("");
    } catch (e: any) {
      setMsg(e.response?.data?.error || "Share failed");
    }
  }

  if (loading) return <Spinner label="Checking access…" />;

  if (denied)
    return (
      <div>
        <PageHeader title="Secure Download" />
        <div className="card max-w-md">
          <Alert kind="error">Access Denied</Alert>
          <p className="mt-3 text-sm text-slate-500">
            This question paper is encrypted and you are not authorized to view its contents.
          </p>
          <dl className="mt-3 text-sm text-slate-500">
            <p>Paper ID: {paper?.id}</p>
            <p>Encrypted: {String(paper?.encrypted)}</p>
          </dl>
        </div>
      </div>
    );

  return (
    <div>
      <PageHeader title="Secure Download" subtitle={paper?.subject_name} />
      {msg && <div className="mb-4"><Alert kind="info">{msg}</Alert></div>}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card space-y-2">
          <div className="flex gap-2">
            <span className="badge bg-green-100 text-green-700">Encrypted ✓</span>
            <span className="badge bg-green-100 text-green-700">Authorized Access ✓</span>
          </div>
          <dl className="mt-2 text-sm">
            <Row k="Paper ID" v={paper?.id} />
            <Row k="Total marks" v={paper?.total_marks} />
            <Row k="Questions" v={paper?.question_count} />
            <Row k="Algorithm" v={paper?.encryption?.algorithm} />
            <Row k="Created" v={new Date(paper?.created_at).toLocaleString()} />
          </dl>
          <div className="flex gap-2 pt-2">
            <button className="btn-primary" onClick={() => download("paper")}>
              Download Question Paper
            </button>
            <button className="btn-ghost" onClick={() => download("answer_key")}>
              Download Answer Key
            </button>
          </div>
          <p className="pt-2 text-xs text-slate-400">
            Files are decrypted on the server only for this request and streamed to you. The
            plaintext PDF is never stored.
          </p>
        </div>

        <div className="card space-y-2">
          <h3 className="font-medium">Grant access to another lecturer</h3>
          <input
            className="input"
            placeholder="lecturer email"
            value={shareEmail}
            onChange={(e) => setShareEmail(e.target.value)}
          />
          <button className="btn-ghost w-full" onClick={share} disabled={!shareEmail}>
            Share
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-1">
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-medium">{String(v ?? "—")}</dd>
    </div>
  );
}
