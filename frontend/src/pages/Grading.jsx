import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { Card, Table, Badge, PageHeader, eur } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";

export default function Grading() {
  const { t } = useI18n();
  const { data: settings } = usePolling("/settings", { intervalSec: 120 });
  const { data: opps } = usePolling("/grading-opportunities");

  const flag = (settings || []).find((s) => s.key === "feature_grading_enabled");
  const enabled = flag ? flag.value === "true" : false;

  if (!enabled) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("nav.grading")} subtitle={t("grading.subtitle")} />
        <Card>
          <div className="py-8 text-center text-slate-500">
            <p className="text-lg">Module grading désactivé (mode prototype).</p>
            <p className="mt-2 text-sm">
              Le comparateur dépend des prix gradés (PokeTrace Pro). Active-le dans
              <b> Réglages → Passer en Pro</b> ou <code>feature_grading_enabled</code>.
              L'authenticité PSA (<code>verify-cert</code>) reste disponible dans tous les modes.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  const cols = [
    { key: "product_name", label: "Produit", render: (r) => (
        <div className="flex items-center gap-2.5">
          <ProductImage src={r.image_url} alt={r.product_name} seed={r.product_id} style={{ width: 30, height: 42 }} />
          <span className="font-medium">{r.product_name}</span>
        </div>
      ) },
    { key: "raw_value", label: "Valeur brute", render: (r) => eur(r.raw_value) },
    { key: "expected_net_weighted", label: "Espérance pondérée", render: (r) => eur(r.expected_net_weighted) },
    { key: "grading_cost", label: "Coût", render: (r) => eur(r.grading_cost) },
    { key: "grade_probability", label: "Probas grade", render: (r) =>
        r.grade_probability ? (
          <span className="text-xs text-slate-400">
            10:{r.grade_probability["10"]} / 9:{r.grade_probability["9"]} / ≤8:{r.grade_probability["le8"]}
          </span>
        ) : "—" },
    { key: "is_recommended", label: "Reco", render: (r) =>
        r.is_recommended ? <Badge severity="info">Recommandé</Badge> : <span className="text-slate-500">non</span> },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.grading")} subtitle={t("grading.subtitle")} />
      <div className="rounded border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
        Rappels : coût élevé (PSA ~80€ + logistique), capital immobilisé plusieurs mois, et le pop
        report surestime les hauts grades (biais de survie) — défaut conservateur. Plancher 100€.
      </div>
      <Card><Table columns={cols} rows={opps || []} empty={t("grading.empty")} /></Card>
    </div>
  );
}
