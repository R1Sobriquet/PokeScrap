// Squelettes de chargement (pattern Robinhood/Linear) : la page annonce sa
// structure au lieu d'un texte « Chargement… ». Shimmer désactivé si
// prefers-reduced-motion (voir index.css).

export function Skeleton({ w = "100%", h = 14, r = 8, className = "", style }) {
  return (
    <div
      aria-hidden="true"
      className={`pa-skeleton ${className}`}
      style={{ width: w, height: h, borderRadius: r, ...style }}
    />
  );
}

const panel = { background: "var(--panel)", border: "1px solid var(--border)" };

function GaugeSkeleton() {
  return (
    <div className="rounded-2xl p-5" style={panel}>
      <Skeleton w={110} h={10} />
      <Skeleton w={140} h={26} style={{ marginTop: 14 }} />
      <Skeleton w="100%" h={6} r={3} style={{ marginTop: 16 }} />
    </div>
  );
}

// Reprend la structure réelle du Cockpit : hero deal + 4 jauges + 2 panneaux.
export function CockpitSkeleton() {
  return (
    <div className="space-y-8" role="status" aria-label="Chargement du cockpit">
      <div>
        <Skeleton w={190} h={26} />
        <Skeleton w={300} h={12} style={{ marginTop: 10 }} />
      </div>
      <div className="rounded-2xl p-6" style={panel}>
        <div className="grid items-center gap-6 md:grid-cols-[360px_1fr]">
          <Skeleton w="100%" h={280} r={16} />
          <div>
            <Skeleton w={160} h={10} />
            <Skeleton w={260} h={22} style={{ marginTop: 12 }} />
            <div className="mt-5 flex gap-5">
              <Skeleton w={70} h={30} /><Skeleton w={70} h={30} /><Skeleton w={70} h={30} />
            </div>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <GaugeSkeleton /><GaugeSkeleton /><GaugeSkeleton /><GaugeSkeleton />
      </div>
      <div className="grid gap-3.5 lg:grid-cols-2">
        <Skeleton w="100%" h={220} r={16} />
        <Skeleton w="100%" h={220} r={16} />
      </div>
    </div>
  );
}

// Squelette générique (fallback Suspense des routes + pages tabulaires).
export function PageSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Chargement">
      <div>
        <Skeleton w={220} h={26} />
        <Skeleton w={340} h={12} style={{ marginTop: 10 }} />
      </div>
      <div className="overflow-hidden rounded-2xl p-4" style={panel}>
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="flex items-center gap-4 py-3">
            <Skeleton w={34} h={44} r={6} />
            <Skeleton w="38%" h={13} />
            <Skeleton w="14%" h={13} />
            <Skeleton w="10%" h={13} />
            <Skeleton w="12%" h={13} />
          </div>
        ))}
      </div>
    </div>
  );
}
