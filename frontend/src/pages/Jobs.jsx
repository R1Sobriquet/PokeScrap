import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { Card, Badge } from "../components/ui.jsx";

const JOB_LABELS = {
  "sync-tracked-sets": "Synchroniser les sets",
  "refresh-prices": "Rafraîchir les prix",
  "scan-movers": "Scanner les top movers",
  "evaluate-sales": "Évaluer les ventes",
  "kpi-snapshot": "Snapshot KPI",
};
const ORDER = ["sync-tracked-sets", "refresh-prices", "scan-movers", "evaluate-sales", "kpi-snapshot"];
const QUOTA_WARN = 200;  // > X produits suivis : risque de dépasser le quota Free (250/j)

function sevFor(status) {
  return status === "error" ? "critical" : status === "running" ? "warning" : "info";
}

export default function Jobs() {
  const { token } = useAuth();
  const { data, reload } = usePolling("/admin/jobs/recent", { intervalSec: 5 });
  const [msg, setMsg] = useState(null);

  const runs = data?.runs || [];
  const jobs = data?.jobs || ORDER;
  const watchlistCount = data?.watchlist_count ?? 0;
  const quotaLimit = data?.poketrace_daily_limit ?? 250;

  // Dernier run par job (runs déjà triés du plus récent au plus ancien).
  const lastByJob = {};
  for (const r of runs) if (!lastByJob[r.job_name]) lastByJob[r.job_name] = r;

  async function run(name) {
    setMsg(null);
    try {
      await api.post(token, `/admin/jobs/${name}/run`);
      setMsg(`Lancé : ${JOB_LABELS[name] || name}`);
      reload();
    } catch (e) {
      setMsg(e.message.includes("409") ? "Ce job est déjà en cours." : `Erreur : ${e.message}`);
    }
  }

  const ordered = ORDER.filter((j) => jobs.includes(j)).concat(jobs.filter((j) => !ORDER.includes(j)));

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Actions & Jobs</h1>
      {msg && <div className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm">{msg}</div>}

      <div className="grid gap-3 md:grid-cols-2">
        {ordered.map((name) => {
          const last = lastByJob[name];
          const running = last?.status === "running";
          return (
            <Card key={name} title={JOB_LABELS[name] || name}>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => run(name)}
                  disabled={running}
                  className={`rounded px-3 py-2 text-sm font-medium ${
                    running ? "cursor-not-allowed bg-slate-700 text-slate-400"
                            : "bg-info text-slate-900 hover:opacity-90"}`}
                >
                  {running ? "En cours…" : "Lancer"}
                </button>
                {last ? (
                  <div className="text-right text-xs text-slate-400">
                    <Badge severity={sevFor(last.status)}>{last.status}</Badge>
                    <div className="mt-1">{(last.finished_at || last.started_at || "").replace("T", " ").slice(0, 16)}</div>
                  </div>
                ) : <span className="text-xs text-slate-500">jamais lancé</span>}
              </div>
              {last?.summary && <p className="mt-2 text-xs text-slate-400">{last.summary}</p>}
              {last?.status === "error" && last?.error_text && (
                <p className="mt-2 text-xs text-critical">{last.error_text}</p>
              )}
              {name === "refresh-prices" && (
                <p className={`mt-2 text-xs ${watchlistCount > QUOTA_WARN ? "text-warning" : "text-slate-500"}`}>
                  {watchlistCount} produits suivis · quota Free {quotaLimit}/j
                  {watchlistCount > QUOTA_WARN ? " — risque de dépassement, fractionne." : ""}
                </p>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
