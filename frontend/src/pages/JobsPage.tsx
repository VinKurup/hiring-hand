import { useEffect, useState } from "react";
import { api } from "../api";
import type { Job } from "../types";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setJobs(await api.listJobs());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function addJob() {
    if (!label.trim() || !description.trim()) return;
    try {
      await api.createJob(label.trim(), description.trim());
      setLabel("");
      setDescription("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function toggle(job: Job) {
    try {
      await api.updateJob(job.id, { included: !job.included });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove(id: number) {
    try {
      await api.deleteJob(id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Jobs</h1>

      <div className="space-y-2 rounded border bg-white p-3">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label (e.g. Senior Backend @ Acme)"
          className="w-full rounded border px-2 py-1 text-sm"
        />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Paste the job description…"
          rows={5}
          className="w-full rounded border px-2 py-1 text-sm"
        />
        <button
          onClick={addJob}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white"
        >
          Add job
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <ul className="divide-y rounded border bg-white">
        {jobs.length === 0 && <li className="p-3 text-sm text-slate-500">No jobs yet.</li>}
        {jobs.map((job) => (
          <li key={job.id} className="flex items-center justify-between gap-3 p-3 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                aria-label={`included-${job.id}`}
                checked={job.included}
                onChange={() => toggle(job)}
              />
              <span className={job.included ? "" : "text-slate-400 line-through"}>{job.label}</span>
            </label>
            <button onClick={() => remove(job.id)} className="text-red-600 hover:underline">
              delete
            </button>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-500">
        Only checked (included) jobs are used when you run a report.
      </p>
    </div>
  );
}
