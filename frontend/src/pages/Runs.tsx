import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { ResultBadge } from "../components/ui/Badge";
import { Select } from "../components/ui/Select";
import { EmptyState } from "../components/ui/EmptyState";
import { listAgents, listRuns, listTasks, type RunSummary, type TaskSummary } from "../lib/api";

export function Runs() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [agents, setAgents] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [task, setTask] = useState("all");
  const [agent, setAgent] = useState("all");
  const [result, setResult] = useState("all");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [runsData, tasksData, agentsData] = await Promise.all([
          listRuns(),
          listTasks(),
          listAgents(),
        ]);
        if (cancelled) return;
        setRuns(runsData);
        setTasks(tasksData);
        setAgents(agentsData);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load runs.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    return runs.filter((run) => {
      if (task !== "all" && run.taskId !== task) return false;
      if (agent !== "all" && run.agent !== agent) return false;
      if (result !== "all" && run.result !== result) return false;
      return true;
    });
  }, [runs, task, agent, result]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
        <p className="mt-1 text-sm text-muted">
          Filter historical evaluations by task, agent, and result.
        </p>
      </header>

      {error ? (
        <div
          role="alert"
          className="rounded-md border border-fail/30 bg-fail/10 px-4 py-3 text-sm text-fail"
        >
          Couldn't reach the backend: {error}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Select label="Task" value={task} onChange={(event) => setTask(event.target.value)}>
          <option value="all">All</option>
          {tasks.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id}
            </option>
          ))}
        </Select>
        <Select label="Agent" value={agent} onChange={(event) => setAgent(event.target.value)}>
          <option value="all">All</option>
          {agents.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
        <Select
          label="Result"
          value={result}
          onChange={(event) => setResult(event.target.value)}
        >
          <option value="all">All</option>
          <option value="PASS">PASS</option>
          <option value="FAIL">FAIL</option>
        </Select>
      </div>

      {!loading && filtered.length === 0 ? (
        <EmptyState
          title="No runs match these filters"
          detail="Clear a filter to see more evaluation history."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-raised/60 text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Task</th>
                  <th className="px-4 py-2.5 font-medium">Agent</th>
                  <th className="px-4 py-2.5 font-medium">Result</th>
                  <th className="px-4 py-2.5 font-medium">Tool Calls</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((run) => (
                  <tr
                    key={run.id}
                    tabIndex={0}
                    className="cursor-pointer border-b border-line last:border-0 hover:bg-raised/70"
                    onClick={() => navigate(`/runs/${run.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/runs/${run.id}`);
                      }
                    }}
                  >
                    <td className="px-4 py-2.5 font-mono text-[13px]">{run.taskId}</td>
                    <td className="px-4 py-2.5">{run.agent}</td>
                    <td className="px-4 py-2.5">
                      <ResultBadge result={run.result} status={run.status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">
                      {run.toolCallCount ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">
                      {run.duration ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">
                      {new Date(run.createdAt).toLocaleString()}
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
