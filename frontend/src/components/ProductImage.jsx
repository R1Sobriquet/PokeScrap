import { useState } from "react";

// Dégradés "art de carte" repris du design — fallback quand aucune image réelle.
const ARTS = [
  "linear-gradient(155deg, #1A1030, #5B3FA8 56%, #C9B8FF)",
  "linear-gradient(155deg, #0A3A4A, #2FB6C9 60%, #CFF6FF)",
  "linear-gradient(155deg, #7A1220, #F4585F 60%, #FFC2A8)",
  "linear-gradient(155deg, #123B7A, #3D7BFF 60%, #8FD0FF)",
  "linear-gradient(155deg, #6E2A08, #FF8A3D 58%, #FFE0B8)",
  "linear-gradient(155deg, #0E4D43, #34D399 60%, #C7F9E5)",
  "linear-gradient(155deg, #4A3A0E, #E0B45C 55%, #FFF0C2)",
];

export function gradientFor(seed = "") {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return ARTS[h % ARTS.length];
}

function initials(seed = "") {
  return String(seed)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

// Vignette produit : image réelle (PokeTrace / JSON-LD détaillant) avec repli
// gracieux sur un dégradé déterministe + initiales si l'image manque ou casse.
export default function ProductImage({ src, alt = "", seed, className = "", style = {}, rounded = 10, showInitials = true }) {
  const [broken, setBroken] = useState(false);
  const grad = gradientFor(seed || alt);
  const useImg = src && !broken;
  return (
    <div
      className={className}
      style={{
        background: grad,
        overflow: "hidden",
        borderRadius: rounded,
        position: "relative",
        flex: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        ...style,
      }}
    >
      {useImg ? (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          onError={() => setBroken(true)}
          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
        />
      ) : (
        showInitials && (
          <span style={{ fontWeight: 800, color: "rgba(255,255,255,.92)", fontSize: "min(42%, 22px)", textShadow: "0 1px 6px rgba(0,0,0,.4)" }}>
            {initials(alt || seed)}
          </span>
        )
      )}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: "linear-gradient(160deg, rgba(255,255,255,.12), transparent 40%)" }} />
    </div>
  );
}
