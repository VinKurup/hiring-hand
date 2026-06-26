import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JobsPage from "./JobsPage";
import { api } from "../api";

vi.mock("../api");

beforeEach(() => {
  vi.resetAllMocks();
});

it("lists jobs and toggles included via the api", async () => {
  vi.mocked(api.listJobs).mockResolvedValue([
    { id: 1, label: "Backend", description: "d", included: true, created_at: "" },
  ]);
  vi.mocked(api.updateJob).mockResolvedValue({
    id: 1, label: "Backend", description: "d", included: false, created_at: "",
  });

  render(<JobsPage />);
  await waitFor(() => expect(screen.getByText("Backend")).toBeInTheDocument());

  const toggle = screen.getByLabelText("included-1");
  await userEvent.click(toggle);
  expect(api.updateJob).toHaveBeenCalledWith(1, { included: false });
});

it("creates a job from the form", async () => {
  vi.mocked(api.listJobs).mockResolvedValue([]);
  vi.mocked(api.createJob).mockResolvedValue({
    id: 2, label: "L", description: "D", included: true, created_at: "",
  });

  render(<JobsPage />);
  await waitFor(() => expect(screen.getByText(/No jobs yet/)).toBeInTheDocument());

  await userEvent.type(screen.getByPlaceholderText("Label (e.g. Senior Backend @ Acme)"), "L");
  await userEvent.type(screen.getByPlaceholderText("Paste the job description…"), "D");
  await userEvent.click(screen.getByRole("button", { name: "Add job" }));

  expect(api.createJob).toHaveBeenCalledWith("L", "D");
});
