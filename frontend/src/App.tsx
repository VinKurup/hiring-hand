import { NavLink, Outlet } from "react-router-dom";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded ${isActive ? "bg-slate-800 text-white" : "text-slate-700 hover:bg-slate-200"}`;

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <nav className="mx-auto flex max-w-3xl gap-2 p-3">
          <span className="mr-4 self-center font-semibold">resume-booster</span>
          <NavLink to="/resume" className={linkClass}>Resume</NavLink>
          <NavLink to="/jobs" className={linkClass}>Jobs</NavLink>
          <NavLink to="/report" className={linkClass}>Report</NavLink>
        </nav>
      </header>
      <main className="mx-auto max-w-3xl p-4">
        <Outlet />
      </main>
    </div>
  );
}
