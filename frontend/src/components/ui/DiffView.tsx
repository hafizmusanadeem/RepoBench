import { cn } from "../../lib/utils";

export function DiffView({ patch }: { patch: string | null | undefined }) {
  if (!patch) {
    return <p className="p-4 text-sm text-muted">No file changes were captured.</p>;
  }
  return (
    <pre className="overflow-x-auto p-3 font-mono text-[12px] leading-5">
      {patch.split("\n").map((line, i) => (
        <span
          key={i}
          className={cn(
            "block whitespace-pre",
            line.startsWith("+") && !line.startsWith("+++") && "bg-pass/10 text-pass",
            line.startsWith("-") && !line.startsWith("---") && "bg-fail/10 text-fail",
            (line.startsWith("@@") || line.startsWith("diff --git")) && "text-accent",
          )}
        >
          {line || " "}
        </span>
      ))}
    </pre>
  );
}
