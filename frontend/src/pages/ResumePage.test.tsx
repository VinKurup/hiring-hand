import { render, screen } from "@testing-library/react";
import ResumePage from "./ResumePage";

test("renders placeholder", () => {
  render(<ResumePage />);
  expect(screen.getByText("placeholder")).toBeInTheDocument();
});
