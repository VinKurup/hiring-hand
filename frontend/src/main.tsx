import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import "./index.css";
import App from "./App";
import ResumePage from "./pages/ResumePage";
import JobsPage from "./pages/JobsPage";
import ReportPage from "./pages/ReportPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/resume" replace /> },
      { path: "resume", element: <ResumePage /> },
      { path: "jobs", element: <JobsPage /> },
      { path: "report", element: <ReportPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
