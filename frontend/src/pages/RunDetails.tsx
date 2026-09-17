import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Check, X } from "lucide-react";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ResultBadge, StatusBadge } from "../components/ui/Badge";
import { cn } from "../lib/utils";
import { getRun, type RunDetail, type ToolCall } from "../lib/api";

const POLL_INTERVAL_MS = 3000;

export function RunDetails() {
  const { runId } = useParams();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function load() {
      try {
        const data = await getRun(runId!);
        if (cancelled) return;
        setRun(data);
        setSelectedId((current) => current ?? data.transcript[0]?.id);
        setError(null);
        // Still running: keep polling so the transcript fills in live and
        // the badge flips to PASS/FAIL/ERROR without a manual refresh.
        if (data.status === "running") {
          timer = setTimeout(load, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load run.");
        }
      }
    }

    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [runId]);

  const selected = useMemo(
    () => run?.transcript.find((item) => item.id === selectedId) ?? run?.transcript[0],
    [run, selectedId],
  );

  if (error) {
    return (
      <div className="space-y-4">
        <BackLink />
        <EmptyState title="Couldn't load this run" detail={error} />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="space-y-4">
        <BackLink />
        <EmptyState title="Loading…" detail={`Fetching run ${runId ?? ""}.`} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <BackLink />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Run #{run.id.slice(0, 8)}</h1>
          <ResultBadge result={run.result} status={run.status} />
        </div>
        {run.status === "error" && run.errorMessage ? (
          <p className="mt-2 text-sm text-fail">{run.errorMessage}</p>
        ) : null}
      </div>

      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-line bg-panel px-4 py-3 text-sm md:grid-cols-4">
        <Meta label="Task" value={run.taskId} mono />
        <Meta label="Agent" value={run.agent} />
        <Meta label="Duration" value={run.duration ?? "—"} mono />
        <Meta
          label="Tool Calls"
          value={run.toolCallCount != null ? String(run.toolCallCount) : "—"}
          mono
        />
      </dl>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <Card className="overflow-hidden">
          <h2 className="border-b border-line px-4 py-3 text-sm font-medium">
            Transcript
          </h2>
          {run.transcript.length === 0 ? (
            <div className="p-4">
              <EmptyState
                title={run.status === "running" ? "Run in progress" : "No tool calls recorded"}
                detail={
                  run.status === "running"
                    ? "The agent is still working. This page refreshes automatically."
                    : "This run didn't produce any tool calls."
                }
              />
            </div>
          ) : (
            <ol className="divide-y divide-line">
              {run.transcript.map((item) => {
                const isActive = item.id === selected?.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className={cn(
                        "flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-raised/70",
                        isActive && "bg-raised",
                      )}
                    >
                      <span className="w-6 font-mono text-xs text-muted">
                        {String(item.step).padStart(2, "0")}
                      </span>
                      <span className="flex-1 font-mono text-[13px]">{item.tool}</span>
                      {item.status === "Success" ? (
                        <Check className="h-4 w-4 text-pass" aria-label="Success" />
                      ) : (
                        <X className="h-4 w-4 text-fail" aria-label="Failed" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </Card>

        <Card className="overflow-hidden">
          <h2 className="border-b border-line px-4 py-3 text-sm font-medium">
            Tool Call Details
          </h2>
          {selected ? (
            <ToolCallDetails call={selected} />
          ) : (
            <div className="p-4">
              <EmptyState
                title="No tool call selected"
                detail="Choose an item from the transcript."
              />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/runs"
      className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Runs
    </Link>
  );
}

function Meta({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={cn("mt-0.5", mono && "font-mono text-[13px]")}>{value}</dd>
    </div>
  );
}

function ToolCallDetails({ call }: { call: ToolCall }) {
  return (
    <div className="space-y-5 p-4">
      <Detail label="Tool" value={call.tool} mono />

      <div>
        <p className="mb-1.5 text-xs uppercase tracking-wide text-muted">Arguments</p>
        <ArgumentsView call={call} />
      </div>

      <div>
        <p className="mb-1.5 text-xs uppercase tracking-wide text-muted">Output</p>
        <pre className="overflow-x-auto rounded-md border border-line bg-canvas p-3 font-mono text-[12px] leading-5 text-fg">
          {call.error ?? call.output ?? "—"}
        </pre>
      </div>

      <Detail label="Duration" value={call.duration} mono />
      <div>
        <p className="mb-1.5 text-xs uppercase tracking-wide text-muted">Status</p>
        <StatusBadge status={call.status} />
      </div>
    </div>
  );
}

// The agent's real tools (see agents/coding_agent.py): bash, text_editor,
// think, plus the react() agent's own submit tool. This renders each
// shape a bit more readably than a raw JSON dump; anything unrecognized
// still falls back to pretty-printed JSON below.
function ArgumentsView({ call }: { call: ToolCall }) {
  const args = call.arguments;

  if (call.tool === "bash" && typeof args.command === "string") {
    return (
      <pre className="overflow-x-auto rounded-md border border-line bg-canvas p-3 font-mono text-[12px]">
        {args.command}
      </pre>
    );
  }

  if (call.tool === "text_editor") {
    const command = typeof args.command === "string" ? args.command : undefined;
    const path = typeof args.path === "string" ? args.path : undefined;

    if (command === "str_replace") {
      return (
        <div className="space-y-2 rounded-md border border-line bg-canvas p-3">
          <p className="font-mono text-[12px] text-muted">{path}</p>
          <pre className="overflow-x-auto font-mono text-[12px] leading-5">
            <span className="block text-fail">- {String(args.old_str ?? "")}</span>
            <span className="mt-1 block text-pass">+ {String(args.new_str ?? "")}</span>
          </pre>
        </div>
      );
    }

    return (
      <div className="space-y-2 rounded-md border border-line bg-canvas p-3">
        <p className="font-mono text-[12px] text-muted">
          {command}
          {path ? ` ${path}` : ""}
        </p>
        {typeof args.file_text === "string" ? (
          <pre className="overflow-x-auto font-mono text-[12px] leading-5">
            {args.file_text}
          </pre>
        ) : null}
      </div>
    );
  }

  if (call.tool === "think" && typeof args.thought === "string") {
    return (
      <pre className="overflow-x-auto rounded-md border border-line bg-canvas p-3 font-mono text-[12px] leading-5">
        {args.thought}
      </pre>
    );
  }

  return (
    <pre className="overflow-x-auto rounded-md border border-line bg-canvas p-3 font-mono text-[12px]">
      {JSON.stringify(args, null, 2)}
    </pre>
  );
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="mb-1 text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={cn("text-sm", mono && "font-mono text-[13px]")}>{value}</p>
    </div>
  );
}
