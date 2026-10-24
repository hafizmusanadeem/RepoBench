import { NavLink } from "react-router-dom";
import { FlaskConical, GitCompare, LayoutDashboard, List, Plus } from "lucide-react";
import { cn } from "../../lib/utils";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/new", label: "New evaluation", icon: Plus, end: false },
  { to: "/evaluations", label: "Evaluations", icon: GitCompare, end: false },
  { to: "/runs", label: "Runs", icon: List, end: false },
] as const;

type SidebarProps = {
  onNavigate?: () => void;
};

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <aside className="flex h-full w-60 flex-col border-r border-line bg-sidebar">
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-panel">
          <FlaskConical className="h-4 w-4 text-accent" aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-semibold tracking-tight">Evaluation Lab</p>
          <p className="text-[11px] text-muted">Coding-agent observability</p>
        </div>
      </div>

      <nav className="flex flex-col gap-0.5 p-3" aria-label="Primary">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-raised text-fg"
                    : "text-muted hover:bg-panel hover:text-fg",
                )
              }
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
