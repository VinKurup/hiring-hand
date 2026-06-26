import type { ResumeListItem, ResumeDetail, Job, Evaluation } from "./types";

const BASE = "/api";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    let detail: string = res.statusText;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

function jsonBody(data: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
}

export const api = {
  listResumes: () => req<ResumeListItem[]>("/resumes"),
  getResume: (id: number) => req<ResumeDetail>(`/resumes/${id}`),
  uploadResume: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<ResumeListItem>("/resumes", { method: "POST", body: fd });
  },

  listJobs: () => req<Job[]>("/jobs"),
  createJob: (label: string, description: string) =>
    req<Job>("/jobs", jsonBody({ label, description })),
  updateJob: (id: number, patch: Partial<Pick<Job, "label" | "description" | "included">>) =>
    req<Job>(`/jobs/${id}`, { ...jsonBody(patch), method: "PATCH" }),
  deleteJob: (id: number) => req<{ deleted: number }>(`/jobs/${id}`, { method: "DELETE" }),

  createEvaluation: (resume_id: number) =>
    req<Evaluation>("/evaluations", jsonBody({ resume_id })),
  listEvaluations: (resume_id: number) =>
    req<Evaluation[]>(`/evaluations?resume_id=${resume_id}`),
};
