import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";
import { cn } from "../lib/utils";
import {
  createEvaluation, createRepo, getRepo, listAgentInfo, listTasks, updateRepoProfile,
  type AgentInfo, type Profile, type Repo, type TaskKind, type TaskSummary,
} from "../lib/api";

const KINDS: { value: TaskKind; label: string }[] = [
  { value: "bug", label: "Fix a bug (error or stack trace)" },
  { value: "failing_test", label: "Make a failing test pass" },
  { value: "feature", label: "Build a feature" },
  { value: "refactor", label: "Refactor" },
];

const inputCls =
  "w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-fg hover:border-muted focus:border-accent";

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="text-muted">{label}</span>
      {children}
      {hint ? <span className="text-xs text-muted">{hint}</span> : null}
    </label>
  );
}

export function NewEvaluation() {
  const navigate = useNavigate();
  const [source, setSource] = useState<"repo" | "benchmark">("repo");

  const [repoUrl, setRepoUrl] = useState("");
  const [repoRef, setRepoRef] = useState("");
  const [repo, setRepo] = useState<Repo | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [cloning, setCloning] = useState(false);

  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [benchTask, setBenchTask] = useState("");
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [picked, setPicked] = useState<string[]>([]);

  const [kind, setKind] = useState<TaskKind>("bug");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [errorLog, setErrorLog] = useState("");
  const [verifyCommand, setVerifyCommand] = useState("");
  const [judge, setJudge] = useState(false);
  const [epochs, setEpochs] = useState("3");
  const [maxToolCalls, setMaxToolCalls] = useState("60");

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([listTasks(), listAgentInfo()])
      .then(([t, a]) => {
        setTasks(t);
        setBenchTask(t[0]?.id ?? "");
        setAgents(a);
        setPicked(a.slice(0, 1).map((x) => x.id));
      })
      .catch((e: Error) => setError(`Couldn't reach the backend: ${e.message}`));
  }, []);

  const repoId = repo?.id;
  const repoStatus = repo?.status;
  useEffect(() => {
    if (!repoId || repoStatus !== "cloning") return;
    const timer = setInterval(() => {
      getRepo(repoId)
        .then((r) => {
          setRepo(r);
          if (r.status === "ready") setProfile(r.profile);
        })
        .catch(() => undefined);
    }, 2000);
    return () => clearInterval(timer);
  }, [repoId, repoStatus]);

  async function handleClone() {
    setCloning(true);
    setError(null);
    try {
      const r = await createRepo({ url: repoUrl, ref: repoRef || undefined });
      setRepo(r);
      setProfile(r.profile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add the repository.");
    } finally {
      setCloning(false);
    }
  }

  function patchProfile(p: Partial<Profile>) {
    setProfile((cur) => (cur ? { ...cur, ...p } : cur));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (source === "repo") {
        if (!repo || !profile) throw new Error("Add a repository first.");
        await updateRepoProfile(repo.id, profile); // persists edits + regenerates the Dockerfile
      }
      const ev = await createEvaluation({
        repoId: source === "repo" ? repo?.id : undefined,
        benchmarkTaskId: source === "benchmark" ? benchTask : undefined,
        kind, title, description, errorLog, verifyCommand,
        agents: picked,
        epochs: Number(epochs) || 1,
        maxToolCalls: Number(maxToolCalls) || 60,
        judge,
      });
      navigate(`/evaluations/${ev.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start the evaluation.");
      setSubmitting(false);
    }
  }

  const isBugKind = kind === "bug" || kind === "failing_test";
  const ready = source === "benchmark" ? !!benchTask : repo?.status === "ready" && !!profile;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">New evaluation</h1>
        <p className="mt-1 text-sm text-muted">
          Run several coding agents on the same task and find out which one works best for a repository.
        </p>
      </header>

      <div className="flex gap-2">
        {(["repo", "benchmark"] as const).map((s) => (
          <Button key={s} variant={source === s ? "primary" : "ghost"} onClick={() => setSource(s)}>
            {s === "repo" ? "My repository" : "Built-in benchmark task"}
          </Button>
        ))}
      </div>

      <form className="space-y-6" onSubmit={handleSubmit}>
        {source === "repo" ? (
          <>
            <Card className="space-y-4 p-5">
              <h2 className="text-sm font-medium">Repository</h2>
              <Field label="Git URL" hint="https://… or git@… The full history is cloned.">
                <input className={inputCls} value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://github.com/owner/name" />
              </Field>
              <Field label="Branch, tag or commit (optional)">
                <input className={inputCls} value={repoRef} onChange={(e) => setRepoRef(e.target.value)} />
              </Field>
              <Button disabled={cloning || !repoUrl || repo?.status === "cloning"} onClick={handleClone}>
                {repo?.status === "cloning" ? "Cloning…" : "Clone and detect setup"}
              </Button>
              {repo?.status === "error" ? <p className="text-sm text-fail">{repo.errorMessage}</p> : null}
            </Card>

            {repo?.status === "ready" && profile ? (
              <Card className="space-y-4 p-5">
                <h2 className="text-sm font-medium">
                  Detected setup: {profile.language}
                  <span className="ml-2 font-mono text-xs text-muted">{repo.commit?.slice(0, 8)}</span>
                </h2>
                {profile.notes.map((n) => (
                  <p key={n} className="text-xs text-muted">{n}</p>
                ))}
                <Field label="Base image">
                  <input className={cn(inputCls, "font-mono")} value={profile.baseImage} onChange={(e) => patchProfile({ baseImage: e.target.value })} />
                </Field>
                <Field label="Install command" hint="Runs once when the image is built, with network access.">
                  <textarea rows={3} className={cn(inputCls, "font-mono")} value={profile.installCommand} onChange={(e) => patchProfile({ installCommand: e.target.value })} />
                </Field>
                <Field label="Test command" hint="Used to catch regressions. Failures that already exist before the agent starts are not counted against it.">
                  <input className={cn(inputCls, "font-mono")} value={profile.testCommand} onChange={(e) => patchProfile({ testCommand: e.target.value })} />
                </Field>
                <Field label="Build command (optional)" hint="For reference only; the scorer uses the test command, not this.">
                  <input className={cn(inputCls, "font-mono")} value={profile.buildCommand} onChange={(e) => patchProfile({ buildCommand: e.target.value })} />
                </Field>
                <Field label="Lint command (optional)" hint="For reference only; not used in scoring.">
                  <input className={cn(inputCls, "font-mono")} value={profile.lintCommand} onChange={(e) => patchProfile({ lintCommand: e.target.value })} />
                </Field>
              </Card>
            ) : null}

            <Card className="space-y-4 p-5">
              <h2 className="text-sm font-medium">Task</h2>
              <Select label="Type" value={kind} onChange={(e) => setKind(e.target.value as TaskKind)}>
                {KINDS.map((k) => (
                  <option key={k.value} value={k.value}>{k.label}</option>
                ))}
              </Select>
              <Field label="Title (optional)">
                <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} />
              </Field>
              <Field label={kind === "feature" ? "Feature description" : "Description"}>
                <textarea rows={4} className={inputCls} value={description} onChange={(e) => setDescription(e.target.value)} />
              </Field>
              {isBugKind ? (
                <Field label="Error output or stack trace">
                  <textarea rows={5} className={cn(inputCls, "font-mono")} value={errorLog} onChange={(e) => setErrorLog(e.target.value)} />
                </Field>
              ) : null}
              <Field
                label={isBugKind ? "Command that must pass when fixed" : "Command that must pass (optional)"}
                hint={isBugKind ? "For example a failing test. It must fail on the current code." : undefined}
              >
                <input className={cn(inputCls, "font-mono")} value={verifyCommand} onChange={(e) => setVerifyCommand(e.target.value)} />
              </Field>
              {kind === "feature" ? (
                <label className="flex items-center gap-2 text-sm text-muted">
                  <input type="checkbox" checked={judge} onChange={(e) => setJudge(e.target.checked)} />
                  Also have a model review the diff against the description
                </label>
              ) : null}
            </Card>
          </>
        ) : (
          <Card className="p-5">
            <Select label="Task" value={benchTask} onChange={(e) => setBenchTask(e.target.value)}>
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>{t.id} — {t.title}</option>
              ))}
            </Select>
          </Card>
        )}

        <Card className="space-y-4 p-5">
          <h2 className="text-sm font-medium">Agents to compare</h2>
          <div className="space-y-2">
            {agents.map((a) => (
              <label key={a.id} className={`flex items-center gap-2 text-sm${a.available ? "" : " text-muted"}`}>
                <input
                  type="checkbox"
                  disabled={!a.available}
                  title={a.available ? undefined : a.reason ?? "Unavailable"}
                  checked={picked.includes(a.id)}
                  onChange={(e) => setPicked((cur) => (e.target.checked ? [...cur, a.id] : cur.filter((x) => x !== a.id)))}
                />
                <span>{a.label}</span>
                {a.available ? null : (
                  <span className="text-xs text-muted">— unavailable: {a.reason ?? "not configured"}</span>
                )}
              </label>
            ))}
            {agents.length === 0 ? <p className="text-sm text-muted">No agents configured. See backend/README.md.</p> : null}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Repeats per agent" hint="3 or more gives a usable median.">
              <input type="number" min={1} max={10} className={cn(inputCls, "font-mono")} value={epochs} onChange={(e) => setEpochs(e.target.value)} />
            </Field>
            <Field label="Max messages per run">
              <input type="number" min={1} max={500} className={cn(inputCls, "font-mono")} value={maxToolCalls} onChange={(e) => setMaxToolCalls(e.target.value)} />
            </Field>
          </div>
        </Card>

        {error ? (
          <div role="alert" className="rounded-md border border-fail/30 bg-fail/10 px-4 py-3 text-sm text-fail">{error}</div>
        ) : null}

        <Button type="submit" disabled={submitting || !ready || picked.length === 0}>
          {submitting ? "Starting…" : "Run evaluation"}
        </Button>
      </form>
    </div>
  );
}
