import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, ResultBadge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ComparePanel } from "../components/ComparePanel";
import { getEvaluation, getRecommendation, type EvaluationDetail as Detail, type Recommendation } from "../lib/api";

const POLL_MS = 4000;
type Weights = { success: number; cost: number; time: number };
type Point = { agent: string; x: number; y: number };

const money = (v: number | null) => (v == null ? "—" : `$${v.toFixed(2)}`);
const secs = (v: number | null) => (v == null ? "—" : `${Math.round(v)}s`);

export function EvaluationDetail() {
  const { evaluationId } = useParams();
  const navigate = useNavigate();
  const [ev, setEv] = useState<Detail | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [w, setW] = useState<Weights>({ success: 70, cost: 15, time: 15 });
  const [xAxis, setXAxis] = useState<"cost" | "time">("time");

  const active = ev ? ev.status === "building" || ev.status === "running" : true;
  const doneCount = ev?.doneCount ?? 0;

  useEffect(() => {
    if (!evaluationId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const data = await getEvaluation(evaluationId!);
        if (cancelled) return;
        setEv(data);
        setError(null);
        if (data.status === "building" || data.status === "running") timer = setTimeout(load, POLL_MS);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load.");
      }
    }
    load();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [evaluationId]);

  // Recompute the recommendation when weights change or another run finishes.
  useEffect(() => {
    if (!evaluationId) return;
    getRecommendation(evaluationId, w).then(setRec).catch(() => undefined);
  }, [evaluationId, w, doneCount, active]);

  const points: Point[] = useMemo(() => {
    if (!rec) return [];
    return rec.stats.flatMap((s) => {
      const x = xAxis === "cost" ? s.medianCostUsd : s.medianDurationS;
      return x == null || s.n === 0 ? [] : [{ agent: s.agent, x, y: Math.round(s.successRate * 100) }];
    });
  }, [rec, xAxis]);

  if (error) return <EmptyState title="Couldn't load this evaluation" detail={error} />;
  if (!ev) return <EmptyState title="Loading…" detail="Fetching evaluation." />;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/evaluations" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />Evaluations
        </Link>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">{ev.title}</h1>
        <p className="mt-1 text-sm text-muted">
          {ev.doneCount}/{ev.runCount} runs finished · {ev.status === "building" ? "building the sandbox image…" : ev.status}
          {ev.repoCommit ? (
            <span className="ml-2 font-mono text-xs" title={ev.repoCommit}>commit {ev.repoCommit.slice(0, 8)}</span>
          ) : null}
        </p>
        {ev.errorMessage ? <pre className="mt-2 overflow-x-auto text-xs text-fail">{ev.errorMessage}</pre> : null}
      </div>

      <Card className="space-y-3 p-5">
        <h2 className="text-sm font-medium">Recommendation</h2>
        {rec?.bestAgent ? (
          <>
            <p className="text-lg font-semibold">
              {rec.bestAgent}
              <Badge className="ml-3" tone={rec.confidence === "high" ? "pass" : "neutral"}>{rec.confidence} confidence</Badge>
            </p>
            <p className="max-w-prose text-sm text-muted">{rec.summary}</p>
          </>
        ) : (
          <p className="text-sm text-muted">{rec?.summary ?? "Waiting for the first finished run."}</p>
        )}
        <div className="grid gap-4 pt-2 sm:grid-cols-3">
          {(["success", "cost", "time"] as const).map((k) => (
            <label key={k} className="flex flex-col gap-1 text-xs text-muted">
              Weight: {k} ({w[k]})
              <input type="range" min={0} max={100} value={w[k]} onChange={(e) => setW({ ...w, [k]: Number(e.target.value) })} />
            </label>
          ))}
        </div>
      </Card>

      {rec && rec.stats.length > 0 ? (
        <Card className="overflow-hidden">
          <h2 className="border-b border-line px-4 py-3 text-sm font-medium">Leaderboard</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-raised/60 text-xs text-muted">
                <tr>
                  {["Agent", "Passed", "95% range", "Median time", "Median cost", "Broke tests", "Votes (W-L-T)", "Score"].map((h) => (
                    <th key={h} className="px-4 py-2.5 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rec.stats.map((s) => (
                  <tr key={s.agent} className="border-b border-line last:border-0">
                    <td className="px-4 py-2.5">{s.agent}{s.agent === rec.bestAgent ? <Badge className="ml-2" tone="pass">best</Badge> : null}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px]">{s.passes}/{s.n}{s.errors ? <span className="text-fail"> +{s.errors} err</span> : null}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{Math.round(s.ciLow * 100)}–{Math.round(s.ciHigh * 100)}%</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{secs(s.medianDurationS)}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{money(s.medianCostUsd)}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{Math.round(s.regressionRate * 100)}%</td>
                    <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{s.wins}-{s.losses}-{s.ties}</td>
                    <td className="px-4 py-2.5 font-mono text-[13px]">{s.score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {points.length > 0 ? (
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium">Success rate vs {xAxis === "cost" ? "cost" : "time"}</h2>
            <div className="flex gap-3 text-xs text-muted">
              {(["time", "cost"] as const).map((k) => (
                <label key={k} className="flex items-center gap-1">
                  <input type="radio" name="x" checked={xAxis === k} onChange={() => setXAxis(k)} />{k}
                </label>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#30363d" />
              <XAxis type="number" dataKey="x" name={xAxis} stroke="#8b949e" tick={{ fontSize: 12 }} />
              <YAxis type="number" dataKey="y" name="Success %" domain={[0, 100]} stroke="#8b949e" tick={{ fontSize: 12 }} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={({ active: on, payload }) => {
                  const p = on ? (payload?.[0]?.payload as Point | undefined) : undefined;
                  return p ? (
                    <div className="rounded-md border border-line bg-panel px-3 py-2 text-xs">
                      <p className="font-medium">{p.agent}</p>
                      <p className="text-muted">{p.y}% passed · {xAxis === "cost" ? `$${p.x.toFixed(2)}` : `${Math.round(p.x)}s`}</p>
                    </div>
                  ) : null;
                }}
              />
              <Scatter data={points} fill="#4493f8" />
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
      ) : null}

      <Card className="overflow-hidden">
        <h2 className="border-b border-line px-4 py-3 text-sm font-medium">Runs</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line bg-raised/60 text-xs text-muted">
              <tr>
                {["Agent", "#", "Result", "Time", "Cost", "Changes"].map((h) => (
                  <th key={h} className="px-4 py-2.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ev.runs.map((r) => (
                <tr key={r.id} tabIndex={0} className="cursor-pointer border-b border-line last:border-0 hover:bg-raised/70"
                  onClick={() => navigate(`/runs/${r.id}`)}
                  onKeyDown={(e) => { if (e.key === "Enter") navigate(`/runs/${r.id}`); }}>
                  <td className="px-4 py-2.5">{r.agent}</td>
                  <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{r.epoch}</td>
                  <td className="px-4 py-2.5">
                    {r.status === "queued" ? <Badge>QUEUED</Badge> : <ResultBadge result={r.result} status={r.status} />}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{r.duration ?? "—"}</td>
                  <td className="px-4 py-2.5 font-mono text-[13px] text-muted">{money(r.costUsd)}</td>
                  <td className="px-4 py-2.5 font-mono text-[13px] text-muted">
                    {r.filesChanged != null ? `${r.filesChanged} files +${r.additions} −${r.deletions}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Compare two runs</h2>
        <ComparePanel evaluationId={ev.id} runs={ev.runs} />
      </section>
    </div>
  );
}
