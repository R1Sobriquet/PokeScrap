import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { Card, Table, Badge, eur, pct } from "../components/ui.jsx";

const EMPTY = { name: "", set_slug: "", min_value_eur: "5", include_single: true, include_sealed: true };

export default function Sets() {
  const { token } = useAuth();
  const { data: sets, reload } = usePolling("/tracked-sets", { intervalSec: 120 });
  const { data: movers } = usePolling("/movers");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  async function toggle(s) {
    await api.put(token, `/tracked-sets/${s.id}`, { is_active: !s.is_active });
    reload();
  }

  async function remove(s) {
    if (!confirm(`Supprimer le set « ${s.name} » ?`)) return;
    await api.del(token, `/tracked-sets/${s.id}`);
    reload();
  }

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (!form.set_slug.trim()) return setErr("Le slug est requis.");
    if (Number(form.min_value_eur) < 0) return setErr("La valeur min doit être ≥ 0.");
    try {
      await api.post(token, "/tracked-sets", {
        set_slug: form.set_slug.trim(), name: form.name.trim() || form.set_slug.trim(),
        min_value_eur: Number(form.min_value_eur) || 0,
        include_single: form.include_single, include_sealed: form.include_sealed,
      });
      setForm(EMPTY);
      setShowForm(false);
      reload();
    } catch (e2) {
      setErr(e2.message.includes("409") ? "Ce set est déjà suivi." : `Erreur : ${e2.message}`);
    }
  }

  const setCols = [
    { key: "name", label: "Set" },
    { key: "set_slug", label: "Slug", render: (s) => <span className="text-xs text-slate-500">{s.set_slug}</span> },
    { key: "min_value_eur", label: "Valeur min", render: (s) => eur(s.min_value_eur) },
    { key: "types", label: "Types", render: (s) => (
        <span className="space-x-1">
          {s.include_single && <Badge>single</Badge>}
          {s.include_sealed && <Badge severity="warning">sealed</Badge>}
        </span>
      ) },
    { key: "is_active", label: "Actif", render: (s) => (
        <button onClick={() => toggle(s)}
          className={`rounded px-3 py-1 text-xs ${s.is_active ? "bg-info text-slate-900" : "bg-slate-700 text-slate-300"}`}>
          {s.is_active ? "ON" : "off"}
        </button>
      ) },
    { key: "del", label: "", render: (s) => (
        <button onClick={() => remove(s)} className="text-xs text-critical hover:underline">Supprimer</button>
      ) },
  ];

  const moverCols = [
    { key: "name", label: "Produit" },
    { key: "set_slug", label: "Set", render: (m) => <span className="text-xs text-slate-500">{m.set_slug}</span> },
    { key: "rise_pct", label: "Hausse 7j/30j", render: (m) => (
        <span className={m.rise_pct >= 0 ? "text-info" : "text-critical"}>{pct(m.rise_pct)}</span>
      ) },
    { key: "volume", label: "Volume", render: (m) => m.volume ?? "—" },
    { key: "price", label: "Prix", render: (m) => eur(m.price) },
    { key: "score", label: "Score", render: (m) => (m.score != null ? m.score.toFixed(3) : "—") },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Sets suivis & Top movers</h1>

      <Card title="Sets cibles (auto-watchlist)"
            right={<button onClick={() => setShowForm((v) => !v)}
              className="rounded bg-info px-3 py-1 text-sm font-medium text-slate-900">+ Ajouter un set cible</button>}>
        {showForm && (
          <form onSubmit={submit} className="mb-4 grid gap-2 rounded border border-slate-800 p-3 md:grid-cols-2">
            <label className="text-xs">Nom
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.name} onChange={set("name")} />
            </label>
            <label className="text-xs">Slug (ex. prismatic-evolutions)
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.set_slug} onChange={set("set_slug")} />
            </label>
            <label className="text-xs">Valeur min (€)
              <input type="number" min="0" step="1" className="mt-1 w-full rounded bg-slate-800 px-2 py-1"
                     value={form.min_value_eur} onChange={set("min_value_eur")} />
            </label>
            <div className="flex items-end gap-4 text-xs">
              <label className="flex items-center gap-1"><input type="checkbox" checked={form.include_single} onChange={set("include_single")} /> singles</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={form.include_sealed} onChange={set("include_sealed")} /> sealed</label>
            </div>
            {err && <p className="text-xs text-critical md:col-span-2">{err}</p>}
            <div className="md:col-span-2">
              <button type="submit" className="rounded bg-info px-3 py-1 text-sm font-medium text-slate-900">Ajouter</button>
            </div>
          </form>
        )}
        <Table columns={setCols} rows={sets || []} empty="Aucun set suivi" />
        <p className="mt-2 text-xs text-slate-500">
          Le job <code>sync-tracked-sets</code> peuple la watchlist (source=auto) sans
          écraser tes ajouts manuels. Respecte le quota PokeTrace (1×/jour).
        </p>
      </Card>

      <Card title="Top movers — le radar SIGNALE, il n'achète pas">
        <Table columns={moverCols} rows={movers || []}
               empty="Aucun mover (volume insuffisant ou pas d'historique)" />
        <p className="mt-2 text-xs text-slate-500">
          Hausse confirmée par le volume ; les achats restent soumis aux garde-fous
          (50 %, anti-pump, anti-FOMO, cash).
        </p>
      </Card>
    </div>
  );
}
