import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { Card, Table } from "../components/ui.jsx";

const BREAKERS = ["fomo_freeze", "pe_reprint_ended", "pe_stock_declining", "speculation_flag"];

export default function Settings() {
  const { token } = useAuth();
  const { data, reload } = usePolling("/settings", { intervalSec: 120 });
  const [drafts, setDrafts] = useState({});
  const settings = data || [];
  const byKey = Object.fromEntries(settings.map((s) => [s.key, s]));

  async function setValue(key, value) {
    await api.put(token, `/settings/${key}`, { value: String(value) });
    reload();
  }
  async function toggle(key) {
    const cur = byKey[key]?.value === "true";
    await setValue(key, cur ? "false" : "true");
  }
  async function switchPro() {
    if (!confirm("Passer en mode Pro ? Met à jour plan/marché/grading/historique/quotas. Prend effet au prochain run de job.")) return;
    await api.post(token, "/settings/switch-pro", { to_pro: true });
    reload();
  }

  const cols = [
    { key: "key", label: "Clé" },
    { key: "value_type", label: "Type", render: (r) => <span className="text-xs text-slate-500">{r.value_type}</span> },
    { key: "value", label: "Valeur", render: (r) => (
        <input
          className="w-48 rounded bg-slate-800 px-2 py-1 text-sm"
          defaultValue={r.value}
          onChange={(e) => setDrafts((d) => ({ ...d, [r.key]: e.target.value }))}
        />
      ) },
    { key: "save", label: "", render: (r) => (
        <button className="text-info text-sm"
                onClick={() => setValue(r.key, drafts[r.key] ?? r.value)}>Enregistrer</button>
      ) },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Réglages</h1>

      <div className="grid gap-3 md:grid-cols-2">
        <Card title="Disjoncteurs">
          <div className="space-y-2">
            {BREAKERS.map((key) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-sm">{key}</span>
                <button
                  onClick={() => toggle(key)}
                  className={`rounded px-3 py-1 text-xs ${
                    byKey[key]?.value === "true" ? "bg-critical text-white" : "bg-slate-700 text-slate-300"
                  }`}
                >
                  {byKey[key]?.value === "true" ? "ACTIF" : "inactif"}
                </button>
              </div>
            ))}
            {byKey["fomo_freeze"]?.value === "true" && (
              <p className="text-xs text-warning">
                Gel FOMO actif (portée : {byKey["fomo_scope"]?.value || "global"}).
              </p>
            )}
          </div>
        </Card>

        <Card title="Mode données">
          <p className="mb-2 text-sm text-slate-400">
            Plan actuel : <b>{byKey["poketrace_plan"]?.value || "?"}</b> · marché{" "}
            <b>{byKey["valuation_market"]?.value || "?"}</b>
          </p>
          <button onClick={switchPro} className="rounded bg-info px-3 py-2 text-sm font-medium text-slate-900">
            Passer en Pro
          </button>
          <p className="mt-2 text-xs text-slate-500">Atomique, confirmé ; effectif au prochain run de job.</p>
        </Card>
      </div>

      <Card title="Table settings (édition typée)">
        <Table columns={cols} rows={settings} empty="Aucun réglage" />
      </Card>
    </div>
  );
}
