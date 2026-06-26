import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ResumeListItem } from "../types";

export default function ResumePage() {
  const [resumes, setResumes] = useState<ResumeListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setResumes(await api.listResumes());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadResume(file);
      if (fileRef.current) fileRef.current.value = "";
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Resume</h1>

      <div className="flex items-center gap-2">
        <input ref={fileRef} type="file" accept="application/pdf" className="text-sm" />
        <button
          onClick={onUpload}
          disabled={uploading}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <ul className="divide-y rounded border bg-white">
        {resumes.length === 0 && <li className="p-3 text-sm text-slate-500">No resumes yet.</li>}
        {resumes.map((r) => (
          <li key={r.id} className="flex justify-between p-3 text-sm">
            <span>{r.filename}</span>
            <span className="text-slate-400">#{r.id}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
