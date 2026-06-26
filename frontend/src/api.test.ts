import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "./api";

function mockFetchOnce(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    statusText: "x",
    json: async () => body,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("api client", () => {
  it("listJobs GETs /api/jobs and returns parsed json", async () => {
    const fetchMock = mockFetchOnce([{ id: 1, label: "a", description: "d", included: true, created_at: "" }]);
    vi.stubGlobal("fetch", fetchMock);
    const jobs = await api.listJobs();
    expect(fetchMock).toHaveBeenCalledWith("/api/jobs", undefined);
    expect(jobs[0].label).toBe("a");
  });

  it("createJob POSTs JSON body", async () => {
    const fetchMock = mockFetchOnce({ id: 5, label: "L", description: "D", included: true, created_at: "" });
    vi.stubGlobal("fetch", fetchMock);
    const job = await api.createJob("L", "D");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ label: "L", description: "D" });
    expect(job.id).toBe(5);
  });

  it("createEvaluation POSTs resume_id and returns the evaluation", async () => {
    const fetchMock = mockFetchOnce({
      id: 9, resume_id: 1, visibility_score: 70, evidence_score: 60,
      role_profile: { title: "T", job_count: 1, must_haves: [] },
      match: { matches: [], visibility_score: 70, evidence_score: 60 },
      recommendations: { build: [], github: [], learn: [] },
      created_at: "",
    });
    vi.stubGlobal("fetch", fetchMock);
    const ev = await api.createEvaluation(1);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/evaluations");
    expect(JSON.parse(opts.body)).toEqual({ resume_id: 1 });
    expect(ev.visibility_score).toBe(70);
  });

  it("throws with the backend detail on non-ok", async () => {
    const fetchMock = mockFetchOnce({ detail: "No jobs marked included" }, false, 422);
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.createEvaluation(1)).rejects.toThrow("422: No jobs marked included");
  });
});
