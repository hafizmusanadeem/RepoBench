import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";
import { createRun, listAgents, listTasks, type TaskSummary } from "../lib/api";

export function NewEvaluation() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [agents, setAgents] = useState<string[]>([]);
  const [task, setTask] = useState("");
  const [agent, setAgent] = useState("");
  const [maxToolCalls, setMaxToolCalls] = useState("20");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [tasksData, agentsData] = await Promise.all([listTasks(), listAgents()]);
        if (cancelled) return;
        setTasks(tasksData);
        setAgents(agentsData);
        setTask((current) => current || tasksData[0]?.id || "");
        setAgent((current) => current || agentsData[0] || "");
        setLoadError(null);
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Failed to load tasks and agents.");
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!task || !agent) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const run = await createRun({
        taskId: task,
        agent,
        maxToolCalls: Number(maxToolCalls) || 20,
      });
      // Jump straight to the run's transcript; it polls while running.
      navigate(`/runs/${run.id}`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to start the evaluation.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">New Evaluation</h1>
        <p className="mt-1 text-sm text-muted">
          Configure and launch a coding-agent run against RepoBench.
        </p>
      </header>

      {loadError ? (
        <div
          role="alert"
          className="rounded-md border border-fail/30 bg-fail/10 px-4 py-3 text-sm text-fail"
        >
          Couldn't reach the backend: {loadError}
        </div>
      ) : (
        <Card className="p-5">
          <form className="space-y-5" onSubmit={handleSubmit}>
            <Select label="Task" value={task} onChange={(event) => setTask(event.target.value)}>
              {tasks.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.id} — {item.title}
                </option>
              ))}
            </Select>

            <Select
              label="Agent"
              value={agent}
              onChange={(event) => setAgent(event.target.value)}
            >
              {agents.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>

            <label className="flex flex-col gap-1.5 text-sm" htmlFor="max-tool-calls">
              <span className="text-muted">Max Tool Calls</span>
              <input
                id="max-tool-calls"
                type="number"
                min={1}
                max={200}
                value={maxToolCalls}
                onChange={(event) => setMaxToolCalls(event.target.value)}
                className="h-9 rounded-md border border-line bg-canvas px-3 font-mono text-fg hover:border-muted focus:border-accent"
              />
            </label>

            <Button type="submit" disabled={submitting || !task || !agent}>
              {submitting ? "Starting…" : "Run Evaluation"}
            </Button>
          </form>
        </Card>
      )}

      {submitError ? (
        <div
          role="alert"
          className="rounded-md border border-fail/30 bg-fail/10 px-4 py-3 text-sm text-fail"
        >
          {submitError}
        </div>
      ) : null}
    </div>
  );
}
