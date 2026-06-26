import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ResumePage from "./ResumePage";
import { api } from "../api";

vi.mock("../api");

beforeEach(() => {
  vi.resetAllMocks();
});

it("lists resumes from the api", async () => {
  vi.mocked(api.listResumes).mockResolvedValue([
    { id: 1, filename: "cv.pdf", created_at: "2026-06-26T00:00:00" },
  ]);
  render(<ResumePage />);
  await waitFor(() => expect(screen.getByText("cv.pdf")).toBeInTheDocument());
});

it("shows an error when listing fails", async () => {
  vi.mocked(api.listResumes).mockRejectedValue(new Error("500: boom"));
  render(<ResumePage />);
  await waitFor(() => expect(screen.getByText(/500: boom/)).toBeInTheDocument());
});
