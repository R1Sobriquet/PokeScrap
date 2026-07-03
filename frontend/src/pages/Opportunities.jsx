import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { Card, Table, Badge, PageHeader, eur, pct } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";

const FLAG_LABELS = { anti_pump: "Anti-pump", illiquid: "Illiquidité", fomo: "FOMO" };

export default function Opportunities() {
  const { t } = useI18n();
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
        <div className="flex items-center gap-2.5">
          <ProductImage src={r.image_url} alt={r.raw_title} seed={r.url || r.raw_title} style={{ width: 30, height: 42 }} />
          <a href={r.url} target="_blank" rel="noreferrer" className="text-info hover:underline">{r.raw_title}</a>
        </div>
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
      <PageHeader title={t("nav.opportunites")} subtitle={t("opportunities.subtitle")} />
      <div className="flex gap-2">
        <Tab active={tab === "active"} onClick={() => setTab("active")}>Actives ({active.length})</Tab>
        <Tab active={tab === "blocked"} onClick={() => setTab("blocked")}>Bloquées ({blocked.length})</Tab>
      </div>
      <Card>
        {tab === "active" ? (
          <Table columns={cols} rows={active} empty={t("opps.empty.active")} />
        ) : (
          <Table columns={blockedCols} rows={blocked} empty={t("opps.empty.blocked")} />
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
