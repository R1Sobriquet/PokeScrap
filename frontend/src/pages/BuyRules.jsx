import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { useI18n } from "../i18n.jsx";
import { Card, Table, Badge, PageHeader, eur } from "../components/ui.jsx";

const EMPTY = { scope: "offer", scope_value: "", max_price: "", max_quantity: "1", is_enabled: false };
const ATT_SEV = { carted: "info", dry_run: "warning", blocked: "critical", skipped: "warning" };

export default function BuyRules() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { data: rules, reload } = usePolling("/buy-rules", { intervalSec: 60 });
  const { data: attempts } = usePolling("/buy-attempts", { intervalSec: 30 });
  const { data: settings, reload: reloadSettings } = usePolling("/settings", { intervalSec: 60 });
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState(null);

  const byKey = Object.fromEntries((settings || []).map((s) => [s.key, s.value]));
  const killOn = byKey["assisted_buy_enabled"] === "true";
  const dryOn = byKey["assisted_buy_dry_run"] === "true";
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  async function setting(key, value) {
    await api.put(token, `/settings/${key}`, { value: String(value) });
    reloadSettings();
  }
  async function toggleRule(r) {
    await api.put(token, `/buy-rules/${r.id}`, { is_enabled: !r.is_enabled });
    reload();
  }
  async function remove(r) {
    if (!confirm("Supprimer cette règle d'achat ?")) return;
    await api.del(token, `/buy-rules/${r.id}`);
    reload();
  }
  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (!form.scope_value.trim()) return setErr("scope_value requis (id d'offre ou type produit).");
    if (Number(form.max_price) <= 0) return setErr("Plafond prix > 0 requis.");
    try {
      await api.post(token, "/buy-rules", {
        scope: form.scope, scope_value: form.scope_value.trim(),
        max_price: Number(form.max_price), max_quantity: Number(form.max_quantity) || 1,
        is_enabled: form.is_enabled,
      });
      setForm(EMPTY);
      reload();
    } catch (e2) {
      setErr(`Erreur : ${e2.message}`);
    }
  }

  const ruleCols = [
    { key: "scope", label: "Scope", render: (r) => <span className="font-mono text-xs">{r.scope}</span> },
    { key: "scope_value", label: "Valeur", render: (r) => <span className="font-mono text-xs text-slate-400">{r.scope_value}</span> },
    { key: "max_price", label: "Plafond prix", render: (r) => eur(r.max_price) },
    { key: "max_quantity", label: "Qté max", render: (r) => r.max_quantity },
    { key: "is_enabled", label: "Actif", render: (r) => (
        <button onClick={() => toggleRule(r)}
          className={`rounded px-3 py-1 text-xs ${r.is_enabled ? "bg-info text-ink" : "bg-slate-700 text-slate-300"}`}>
          {r.is_enabled ? "ON" : "off"}
        </button>
      ) },
    { key: "del", label: "", render: (r) => <button onClick={() => remove(r)} className="text-xs text-critical hover:underline">Supprimer</button> },
  ];

  const attCols = [
    { key: "offer_id", label: "Offre #", render: (a) => a.offer_id },
    { key: "status", label: "Statut", render: (a) => <Badge severity={ATT_SEV[a.status] || "info"}>{a.status}</Badge> },
    { key: "reason", label: "Motif", render: (a) => <span className="text-xs text-slate-500">{a.reason || "—"}</span> },
    { key: "cart_url", label: "Panier", render: (a) => a.cart_url
        ? <a href={a.cart_url} target="_blank" rel="noreferrer" className="text-xs text-info hover:underline">ouvrir</a> : "—" },
    { key: "created_at", label: "Quand", render: (a) => <span className="font-mono text-[10px] text-slate-600">{(a.created_at || "").replace("T", " ").slice(5, 16)}</span> },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.buyrules")} subtitle="Carting assisté + deep-link panier. TU finalises toujours le paiement + 3DS." badge="POKÉSTOCK FR · ASSISTÉ" />

      <div className="rounded-xl border px-4 py-3 text-sm" style={{ borderColor: "var(--border2)", background: "var(--panel2)" }}>
        ⚠️ Aucun paiement automatisé, aucune donnée de paiement stockée. On ajoute au panier (sur ta session connectée) et on t'envoie le lien — c'est tout.
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Card title="Kill-switch global">
          <div className="flex items-center justify-between">
            <span className="text-sm">Achat assisté</span>
            <button onClick={() => setting("assisted_buy_enabled", !killOn)}
              className={`rounded px-3 py-1 text-xs ${killOn ? "bg-info text-ink" : "bg-critical text-white"}`}>
              {killOn ? "ACTIF" : "COUPÉ"}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">Coupe instantanément tout le carting assisté.</p>
        </Card>
        <Card title="Mode dry-run">
          <div className="flex items-center justify-between">
            <span className="text-sm">Simulation (aucun carting réel)</span>
            <button onClick={() => setting("assisted_buy_dry_run", !dryOn)}
              className={`rounded px-3 py-1 text-xs ${dryOn ? "bg-warning text-ink" : "bg-slate-700 text-slate-300"}`}>
              {dryOn ? "DRY-RUN" : "réel"}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">En dry-run : alerte + lien simulés, rien n'est ajouté au panier.</p>
        </Card>
      </div>

      <Card title="Règles d'achat (allow-list)"
            right={<span className="font-mono text-[10px] text-slate-500">rien hors règle active n'est carté</span>}>
        <form onSubmit={submit} className="mb-4 grid gap-2 rounded border border-slate-800 p-3 md:grid-cols-5">
          <label className="text-xs">Scope
            <select className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.scope} onChange={set("scope")}>
              <option value="offer">offer</option>
              <option value="product_type">product_type</option>
            </select>
          </label>
          <label className="text-xs">Valeur (id offre / type)
            <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.scope_value} onChange={set("scope_value")} />
          </label>
          <label className="text-xs">Plafond prix €
            <input type="number" min="0" step="1" className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.max_price} onChange={set("max_price")} />
          </label>
          <label className="text-xs">Qté max
            <input type="number" min="1" step="1" className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.max_quantity} onChange={set("max_quantity")} />
          </label>
          <div className="flex items-end gap-2">
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={form.is_enabled} onChange={set("is_enabled")} /> actif</label>
            <button type="submit" className="rounded bg-info px-3 py-1 text-sm font-medium text-ink">Ajouter</button>
          </div>
          {err && <p className="text-xs text-critical md:col-span-5">{err}</p>}
        </form>
        <Table columns={ruleCols} rows={rules || []} empty="Aucune règle (rien ne sera carté)." />
      </Card>

      <Card title="Journal des tentatives (audit)">
        <Table columns={attCols} rows={attempts || []} empty="Aucune tentative." />
      </Card>
    </div>
  );
}
