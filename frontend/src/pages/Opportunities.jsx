import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { Card, Table, Badge, eur, pct } from "../components/ui.jsx";

const FLAG_LABELS = { anti_pump: "Anti-pump", illiquid: "Illiquidité", fomo: "FOMO" };

export default function Opportunities() {
  const [tab, setTab] = useState("active");
  const { data } = usePolling("/opportunities");
  const rows = data || [];

  const active = rows.filter((r) => ["new", "flagged", "watch"].includes(r.status));
  const blocked = rows.filter((r) => r.status === "blocked");

  function motifs(flags) {
    if (!flags) return "—";
    const active = Object.entries(flags)
      .filter(([k, v]) => v === true && FLAG_LABELS[k])
      .map(([k]) => FLAG_LABELS[k]);
    if (flags.ratio_block) active.push("Ratio > 50 %");
    if (flags.cash_block) active.push("Garde-fou cash");
    if (flags.buy_reason === "ir_absolute_floor") active.push("Plancher IR");
    return active.length ? active.join(", ") : "—";
  }

  const cols = [
    { key: "raw_title", label: "Annonce", render: (r) => (
        <a href={r.url} target="_blank" rel="noreferrer" className="text-info hover:underline">{r.raw_title}</a>
      ) },
    { key: "platform", label: "Plateforme" },
    { key: "acquisition_cost_total", label: "Coût", render: (r) => eur(r.acquisition_cost_total) },
    { key: "estimated_resale_value", label: "Revente nette", render: (r) => eur(r.estimated_resale_value) },
    { key: "ratio_pct", label: "Ratio", render: (r) => pct(r.ratio_pct) },
  ];
  const blockedCols = [
    { key: "raw_title", label: "Annonce" },
    { key: "ratio_pct", label: "Ratio", render: (r) => pct(r.ratio_pct) },
    { key: "motifs", label: "Motif du blocage", render: (r) => <Badge severity="warning">{motifs(r.filter_flags)}</Badge> },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Opportunités</h1>
      <div className="flex gap-2">
        <Tab active={tab === "active"} onClick={() => setTab("active")}>Actives ({active.length})</Tab>
        <Tab active={tab === "blocked"} onClick={() => setTab("blocked")}>Bloquées ({blocked.length})</Tab>
      </div>
      <Card>
        {tab === "active" ? (
          <Table columns={cols} rows={active} empty="Aucune opportunité active" />
        ) : (
          <Table columns={blockedCols} rows={blocked} empty="Aucune annonce bloquée" />
        )}
      </Card>
    </div>
  );
}

function Tab({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-3 py-1 text-sm ${active ? "bg-slate-700 text-white" : "bg-slate-900 text-slate-400"}`}
    >
      {children}
    </button>
  );
}
