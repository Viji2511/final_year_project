import { Link, useLocation } from "react-router-dom";
import { FlaskConical, Play, BarChart3 } from "lucide-react";

const links = [
  { to: "/",        label: "Dashboard", icon: BarChart3 },
  { to: "/run",     label: "Run",       icon: Play },
  { to: "/results", label: "Results",   icon: FlaskConical },
];

export default function Navbar() {
  const { pathname } = useLocation();

  return (
    <nav className="border-b border-white/10 bg-[#0d1530]/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-brand flex items-center justify-center">
            <FlaskConical size={14} className="text-white" />
          </div>
          <span className="font-bold text-white tracking-tight">MRep</span>
          <span className="text-xs text-slate-400 ml-1 hidden sm:block">
            Multimodal Reproduction Pipeline
          </span>
        </div>

        <div className="flex items-center gap-1">
          {links.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === to
                  ? "bg-brand text-white"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <Icon size={14} />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}