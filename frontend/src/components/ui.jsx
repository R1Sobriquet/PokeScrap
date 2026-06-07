// Petits composants UI réutilisables (denses, fonctionnels).

export function Card({ title, children, right }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h3 className="text-sm font-semibold text-slate-300">{title}</h3>}
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function Kpi({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-slate-100">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

const SEV = {
  info: "bg-info/20 text-info border-info/40",
  warning: "bg-warning/20 text-warning border-warning/40",
  critical: "bg-critical/20 text-critical border-critical/40",
};

export function Badge({ children, severity = "info" }) {
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs ${SEV[severity] || SEV.info}`}>
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
          <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
            {columns.map((c) => (
              <th key={c.key} className="px-2 py-2">{c.label}</th>
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
