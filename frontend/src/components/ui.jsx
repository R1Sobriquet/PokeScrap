// Petits composants UI réutilisables (denses, fonctionnels) — réskinés sur le
// design PokéAlpha. Le palette Tailwind (slate/info/warning/critical) est adossé
// aux variables de thème, donc ces primitives basculent sur les 4 thèmes.

// En-tête de page « terminal » : gros titre + sous-titre mono, pastille et slot
// d'action optionnels. Standardise le haut de chaque écran.
export function PageHeader({ title, subtitle, badge, right }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {badge && (
          <div
            className="mb-2.5 inline-flex items-center gap-2 rounded-full px-3 py-1 font-mono text-[9.5px] uppercase tracking-[0.14em] text-slate-500"
            style={{ border: "1px solid var(--border2)", background: "var(--panel2)" }}
          >
            {badge}
          </div>
        )}
        <h1 className="text-[26px] font-extrabold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-[620px] text-sm text-slate-500">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

// Classes/style partagés pour les champs de formulaire (look terminal).
export const inputCls = "rounded-lg border px-2.5 py-1.5 text-sm text-slate-100 outline-none";
export const inputStyle = { borderColor: "var(--border2)", background: "var(--panel2)" };

export function Card({ title, children, right }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4 transition-colors">
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between">
          {title && (
            <h3 className="font-mono text-xs font-medium uppercase tracking-wider text-slate-500">
              {title}
            </h3>
          )}
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function Kpi({ label, value, sub }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
      <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-2xl font-bold text-slate-100">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

const SEV = {
  info: "bg-info/15 text-info border-info/40",
  warning: "bg-warning/15 text-warning border-warning/40",
  critical: "bg-critical/15 text-critical border-critical/40",
};

export function Badge({ children, severity = "info" }) {
  return (
    <span
      className={`inline-block rounded-md border px-2 py-0.5 font-mono text-xs ${SEV[severity] || SEV.info}`}
    >
      {children}
    </span>
  );
}

export function Table({ columns, rows, empty = "Aucune donnée" }) {
  if (!rows || rows.length === 0) {
    return <div className="py-6 text-center text-sm text-slate-500">{empty}</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 font-mono text-xs uppercase tracking-wide text-slate-500">
            {columns.map((c) => (
              <th key={c.key} className="px-2 py-2 font-medium">{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id ?? i} className="border-b border-slate-800/60 hover:bg-slate-800/40">
              {columns.map((c) => (
                <td key={c.key} className="px-2 py-2 text-slate-200">
                  {c.render ? c.render(row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function eur(v) {
  return v === null || v === undefined ? "—" : `${Number(v).toFixed(2)} €`;
}

export function pct(v) {
  return v === null || v === undefined ? "—" : `${Number(v).toFixed(1)} %`;
}
