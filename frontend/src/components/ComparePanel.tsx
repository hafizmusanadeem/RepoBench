import { useEffect, useState } from "react";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import { DiffView } from "./ui/DiffView";
import { Select } from "./ui/Select";
import { createVote, getRun, type RunDetail, type RunSummary } from "../lib/api";

// Side-by-side patches for two runs, with optional blind voting. UX modelled on
// SWE-Agent-Arena (github.com/Software-Engineering-Arena/SWE-Agent-Arena).
export function ComparePanel({ evaluationId, runs }: { evaluationId: string; runs: RunSummary[] }) {
  const finished = runs.filter((r) => r.status === "success");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [blind, setBlind] = useState(true);
  const [voted, setVoted] = useState(false);
  const [detailA, setDetailA] = useState<RunDetail | null>(null);
  const [detailB, setDetailB] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setVoted(false);
    setDetailA(null);
    if (a) getRun(a).then(setDetailA).catch((e: Error) => setError(e.message));
  }, [a]);
  useEffect(() => {
    setVoted(false);
    setDetailB(null);
    if (b) getRun(b).then(setDetailB).catch((e: Error) => setError(e.message));
  }, [b]);

  if (finished.length < 2) {
    return <p className="text-sm text-muted">Comparing needs at least two finished runs.</p>;
  }

  const label = (r: RunSummary) =>
    blind && !voted ? `Run ${r.id.slice(0, 6)}` : `${r.agent} · #${r.epoch ?? 1} · ${r.result ?? "—"}`;

  async function vote(winner: "a" | "b" | "tie") {
    try {
      await createVote(evaluationId, { runA: a, runB: b, winner });
      setVoted(true);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vote failed.");
    }
  }

  const options = (
    <>
      <option value="">Choose a run</option>
      {finished.map((r) => (
        <option key={r.id} value={r.id}>
          {label(r)}
        </option>
      ))}
    </>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Select label="Left" value={a} onChange={(e) => setA(e.target.value)}>{options}</Select>
        <Select label="Right" value={b} onChange={(e) => setB(e.target.value)}>{options}</Select>
        <label className="flex items-center gap-2 pb-2 text-sm text-muted">
          <input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />
          Hide agent names until I vote
        </label>
      </div>

      {a && b && a !== b ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {[detailA, detailB].map((d, i) => (
              <Card key={i} className="overflow-hidden">
                <div className="border-b border-line px-4 py-2 text-xs text-muted">
                  {d ? `${d.filesChanged ?? 0} files · +${d.additions ?? 0} −${d.deletions ?? 0}` : "Loading…"}
                </div>
                <DiffView patch={d?.patch} />
              </Card>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted">Which change is better?</span>
            <Button disabled={voted} onClick={() => vote("a")}>Left</Button>
            <Button disabled={voted} onClick={() => vote("b")}>Right</Button>
            <Button variant="ghost" disabled={voted} onClick={() => vote("tie")}>Tie</Button>
            {voted ? <span className="text-sm text-pass">Vote saved.</span> : null}
          </div>
        </>
      ) : null}
      {error ? <p className="text-sm text-fail">{error}</p> : null}
    </div>
  );
}
