import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { useI18n } from "../i18n.jsx";
import { Card, Table, PageHeader } from "../components/ui.jsx";

const EMPTY = { product_name: "", set_name: "", product_type: "", release_date: "", preorder_date: "", source_note: "" };

export default function Calendar() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { data: releases, reload } = usePolling("/releases", { intervalSec: 120 });
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (!form.product_name.trim()) return setErr("Le nom du produit est requis.");
    try {
      await api.post(token, "/releases", { ...form, product_name: form.product_name.trim() });
      setForm(EMPTY);
      reload();
    } catch (e2) {
      setErr(e2.message.includes("400") ? "Vérifie les dates (AAAA-MM-JJ)." : `Erreur : ${e2.message}`);
    }
  }

  async function remove(r) {
    if (!confirm(`Supprimer « ${r.product_name} » ?`)) return;
    await api.del(token, `/releases/${r.id}`);
    reload();
  }

  const cols = [
    { key: "product_name", label: "Produit" },
    { key: "set_name", label: "Set", render: (r) => <span className="text-xs text-slate-500">{r.set_name || "—"}</span> },
    { key: "product_type", label: "Type", render: (r) => r.product_type || "—" },
    { key: "preorder_date", label: "Précommande", render: (r) => r.preorder_date || "—" },
    { key: "release_date", label: "Sortie", render: (r) => r.release_date || "—" },
    { key: "del", label: "", render: (r) => (
        <button onClick={() => remove(r)} className="text-xs text-critical hover:underline">Supprimer</button>
      ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.calendrier")} subtitle={t("calendar.subtitle")} />

      <Card title="Ajouter une sortie (curation manuelle)">
        <form onSubmit={submit} className="grid gap-2 md:grid-cols-3">
          <label className="text-xs">Produit
            <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.product_name} onChange={set("product_name")} />
          </label>
          <label className="text-xs">Set
            <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.set_name} onChange={set("set_name")} />
          </label>
          <label className="text-xs">Type (etb/display/coffret…)
            <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.product_type} onChange={set("product_type")} />
          </label>
          <label className="text-xs">Précommande (AAAA-MM-JJ)
            <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.preorder_date} onChange={set("preorder_date")} />
          </label>
          <label className="text-xs">Sortie (AAAA-MM-JJ)
            <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.release_date} onChange={set("release_date")} />
          </label>
          <label className="text-xs">Note source
            <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={form.source_note} onChange={set("source_note")} />
          </label>
          {err && <p className="text-xs text-critical md:col-span-3">{err}</p>}
          <div className="md:col-span-3">
            <button type="submit" className="rounded bg-info px-3 py-1 text-sm font-medium text-ink">Ajouter</button>
          </div>
        </form>
      </Card>

      <Card title="Sorties à venir">
        <Table columns={cols} rows={releases || []} empty="Aucune sortie planifiée" />
      </Card>
    </div>
  );
}
