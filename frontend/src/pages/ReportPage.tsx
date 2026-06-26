import { useEffect, useState } from "react";
import { api } from "../api";
import type { Evaluation, MatchStatus, ResumeListItem } from "../types";

const STATUS_CLASS: Record<MatchStatus, string> = {
  strong: "bg-green-100 text-green-800",
  weak: "bg-amber-100 text-amber-800",
  missing: "bg-red-100 text-red-800",
};

function ScoreCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border bg-white p-3 text-center">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function Result({ ev }: { ev: Evaluation }) {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{ev.role_profile.title}</h2>

      <div className="grid grid-cols-2 gap-3">
        <ScoreCard label="Visibility (recruiter/ATS)" value={ev.visibility_score} />
        <ScoreCard label="Evidence (hiring manager)" value={ev.evidence_score} />
      </div>

      <div className="rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="border-b text-left text-slate-500">
            <tr>
              <th className="p-2">Must-have</th>
              <th className="p-2">Status</th>
              <th className="p-2">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {ev.match.matches.map((m) => (
              <tr key={m.skill} className="border-b last:border-0 align-top">
                <td className="p-2 font-medium">
                  {m.skill}
                  {m.claim_without_evidence && (
                    <span className="ml-1 text-xs text-red-600">(unbacked claim)</span>
                  )}
                </td>
                <td className="p-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${STATUS_CLASS[m.status]}`}>
                    {m.status}
                  </span>
                </td>
                <td className="p-2 text-slate-600">{m.evidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-3">
        <section>
          <h3 className="font-semibold">Build</h3>
          <ul className="list-disc pl-5 text-sm">
            {ev.recommendations.build.map((b, i) => (
              <li key={i}>
                <span className="font-medium">{b.project}</span>{" "}
                <span className="text-slate-500">[{b.stack.join(", ")}]</span> — {b.closes_gap}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="font-semibold">GitHub</h3>
          <ul className="list-disc pl-5 text-sm">
            {ev.recommendations.github.map((g, i) => (
              <li key={i}>{g.action} — <span className="text-slate-500">{g.closes_gap}</span></li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="font-semibold">Learn</h3>
          <ul className="list-disc pl-5 text-sm">
            {ev.recommendations.learn.map((l, i) => (
              <li key={i}>
                {l.skill} <span className="text-slate-500">({l.score_impact} impact)</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

export default function ReportPage() {
  const [resumes, setResumes] = useState<ResumeListItem[]>([]);
  const [resumeId, setResumeId] = useState<number | null>(null);
  const [current, setCurrent] = useState<Evaluation | null>(null);
  const [history, setHistory] = useState<Evaluation[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listResumes().then((rs) => {
      setResumes(rs);
      if (rs.length > 0) setResumeId(rs[0].id);
    }).catch((e) => setError((e as Error).message));
  }, []);

  useEffect(() => {
    if (resumeId == null) return;
    api.listEvaluations(resumeId).then(setHistory).catch((e) => setError((e as Error).message));
  }, [resumeId]);

  async function run() {
    if (resumeId == null) return;
    setRunning(true);
    setError(null);
    try {
      const ev = await api.createEvaluation(resumeId);
      setCurrent(ev);
      setHistory(await api.listEvaluations(resumeId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Report</h1>

      <div className="flex items-center gap-2">
        <select
          aria-label="resume"
          className="rounded border px-2 py-1 text-sm"
          value={resumeId ?? ""}
          onChange={(e) => setResumeId(Number(e.target.value))}
        >
          {resumes.length === 0 && <option value="">No resumes — upload one first</option>}
          {resumes.map((r) => (
            <option key={r.id} value={r.id}>
              {r.filename} (#{r.id})
            </option>
          ))}
        </select>
        <button
          onClick={run}
          disabled={running || resumeId == null}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {running ? "Running…" : "Run evaluation"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {current && <Result ev={current} />}

      {history.length > 0 && (
        <div className="text-sm text-slate-500">
          <h3 className="font-semibold text-slate-700">History</h3>
          <ul className="list-disc pl-5">
            {history.map((h) => (
              <li key={h.id}>
                #{h.id} — visibility {h.visibility_score}, evidence {h.evidence_score}{" "}
                <span className="text-slate-400">({h.created_at})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
