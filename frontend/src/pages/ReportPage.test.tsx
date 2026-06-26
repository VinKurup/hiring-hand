import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReportPage from "./ReportPage";
import { api } from "../api";
import type { Evaluation } from "../types";

vi.mock("../api");

const EVAL: Evaluation = {
  id: 9,
  resume_id: 1,
  visibility_score: 75,
  evidence_score: 60,
  role_profile: {
    title: "Senior Backend Engineer",
    job_count: 2,
    must_haves: [{ skill: "Python", category: "tech", frequency: 2 }],
  },
  match: {
    matches: [
      { skill: "Python", status: "strong", evidence: "5 yrs", claim_without_evidence: false },
      { skill: "Kubernetes", status: "missing", evidence: "none", claim_without_evidence: false },
    ],
    visibility_score: 75,
    evidence_score: 60,
  },
  recommendations: {
    build: [{ project: "k8s demo", stack: ["Go"], closes_gap: "Kubernetes" }],
    github: [{ action: "pin repo", closes_gap: "Kubernetes" }],
    learn: [{ skill: "Kubernetes", score_impact: "high" }],
  },
  created_at: "2026-06-26T00:00:00",
};

beforeEach(() => {
  vi.resetAllMocks();
});

it("runs an evaluation and renders scores, must-haves, and recommendations", async () => {
  vi.mocked(api.listResumes).mockResolvedValue([
    { id: 1, filename: "cv.pdf", created_at: "" },
  ]);
  vi.mocked(api.listEvaluations).mockResolvedValue([]);
  vi.mocked(api.createEvaluation).mockResolvedValue(EVAL);

  render(<ReportPage />);
  await waitFor(() => expect(screen.getByText("cv.pdf (#1)")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "Run evaluation" }));

  await waitFor(() => expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument());
  expect(api.createEvaluation).toHaveBeenCalledWith(1);
  expect(screen.getByText("75")).toBeInTheDocument();
  expect(screen.getAllByText("Kubernetes").length).toBeGreaterThan(0);
  expect(screen.getByText("k8s demo")).toBeInTheDocument();
});

it("surfaces a 422 error from the backend", async () => {
  vi.mocked(api.listResumes).mockResolvedValue([{ id: 1, filename: "cv.pdf", created_at: "" }]);
  vi.mocked(api.listEvaluations).mockResolvedValue([]);
  vi.mocked(api.createEvaluation).mockRejectedValue(new Error("422: No jobs marked included"));

  render(<ReportPage />);
  await waitFor(() => expect(screen.getByText("cv.pdf (#1)")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Run evaluation" }));
  await waitFor(() =>
    expect(screen.getByText(/No jobs marked included/)).toBeInTheDocument()
  );
});
