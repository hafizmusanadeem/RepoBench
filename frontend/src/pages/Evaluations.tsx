import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { listEvaluations, type EvaluationSummary } from "../lib/api";

export function Evaluations() {
  const navigate = useNavigate();
  const [items, setItems] = useState<EvaluationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEvaluations().then(setItems).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Evaluations</h1>
        <p className="mt-1 text-sm text-muted">Each evaluation compares agents on one task.</p>
      </header>
      {error ? <p className="text-sm text-fail">Couldn't reach the backend: {error}</p> : null}
      {items.length === 0 && !error ? (
        <EmptyState title="No evaluations yet" detail="Start one from New evaluation." />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-raised/60 text-xs text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Title</th>
                  <th className="px-4 py-2.5 font-medium">Repository</th>
                  <th className="px-4 py-2.5 font-medium">Agents</th>
                  <th className="px-4 py-2.5 font-medium">Progress</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((e) => (
                  <tr key={e.id} tabIndex={0} className="cursor-pointer border-b border-line last:border-0 hover:bg-raised/70"
                    onClick={() => navigate(`/evaluations/${e.id}`)}
                    onKeyDown={(ev) => { if (ev.key === "Enter") navigate(`/evaluations/${e.id}`); }}>
                    <td className="px-4 py-2.5">{e.title}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{e.repoUrl?.replace(/^https?:\/\//, "") ?? e.benchmarkTaskId}</td>
                    <td className="px-4 py-2.5 text-muted">{e.agents.length}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{e.doneCount}/{e.runCount}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone={e.status === "error" ? "fail" : e.status === "complete" ? "pass" : "neutral"}>{e.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
