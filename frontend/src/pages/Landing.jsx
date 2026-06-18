import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme, THEMES } from "../ThemeContext.jsx";
import { useI18n } from "../i18n.jsx";
import PackModal from "../components/PackModal.jsx";

// Données marketing statiques (vitrine) reprises du design.
const TICKER = [
  ["EVOLVING SKIES BB", "$1,289", "▲15.8%", "green"],
  ["POKÉMON 151 UPC", "$159", "▲11.2%", "green"],
  ["PRISMATIC EVOLUTIONS ETB", "$98", "▲9.4%", "green"],
  ["CROWN ZENITH ETB", "$96", "▲6.1%", "green"],
  ["ASCENDED HEROES PREORDER", "$164", "▲21.3%", "green"],
  ["CELEBRATIONS UPC", "$214", "▼2.1%", "red"],
];

// Éventail de cartes (la centrale = grail "STRONG BUY").
const CARDS = [
  { name: "Crown Zenith", tag: "AI 86", grad: "linear-gradient(155deg, #0A3A4A, #2FB6C9 60%, #CFF6FF)",
    note: "◆ STEADY", price: "$96", delta: "▲ 6.1%", rot: -15, ty: 34, z: 1, w: 156, h: 214 },
  { name: "Pokémon 151", tag: "AI 87", grad: "linear-gradient(155deg, #7A1220, #F4585F 60%, #FFC2A8)",
    note: "◆ HIGH", price: "$159", delta: "▲ 11.2%", rot: -8, ty: 11, z: 2, w: 156, h: 214 },
  { name: "Umbreon VMAX", tag: "AI 99", grad: "linear-gradient(155deg, #1A1030, #5B3FA8 56%, #C9B8FF)",
    note: "★ GRAIL TIER", price: "$1,485", delta: "▲ 18.2%", rot: 0, ty: -10, z: 6, w: 174, h: 240, hero: true },
  { name: "Evolving Skies", tag: "AI 96", grad: "linear-gradient(155deg, #123B7A, #3D7BFF 60%, #8FD0FF)",
    note: "◆ VAULT", price: "$1,289", delta: "▲ 15.8%", rot: 8, ty: 11, z: 2, w: 156, h: 214 },
  { name: "Asc. Heroes", tag: "HYPE 93", grad: "linear-gradient(155deg, #6E2A08, #FF8A3D 58%, #FFE0B8)",
    note: "◆ BREAKOUT", price: "+140%", delta: "PREORDER", rot: 15, ty: 34, z: 1, w: 156, h: 214 },
];

const STATS = [
  ["12,438", "landing.stat.products"],
  ["164", "landing.stat.sets"],
  ["57", "landing.stat.signals"],
  ["88%", "landing.stat.confidence"],
];

const THEME_SWATCH = {
  dark: "#0A0D14",
  light: "#F4F6FA",
  holo: "conic-gradient(from 210deg, #5B8CFF, #B89CFF, #FFCB2E, #34E2A4, #5B8CFF)",
  ember: "linear-gradient(150deg, #FF8A3D, #FF5E54)",
};

function FanCard({ c }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate("/sets")}
      style={{
        flex: "none",
        marginLeft: c.z === 6 ? 0 : -46,
        transform: `rotate(${c.rot}deg) translateY(${c.ty}px)`,
        zIndex: c.z,
        cursor: "pointer",
        border: "none",
        background: "transparent",
        padding: 0,
        transition: "transform .28s cubic-bezier(.2,.9,.3,1)",
      }}
    >
      {c.hero && (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: -22,
            transform: "translateX(-50%) rotate(-4deg)",
            zIndex: 8,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 11px",
            borderRadius: 9,
            background: "linear-gradient(180deg, #FFD75A, #FFC91F)",
            color: "#1A1503",
            boxShadow: "0 10px 26px rgba(255,203,46,.45)",
            whiteSpace: "nowrap",
          }}
        >
          <span style={{ fontSize: 11 }}>★</span>
          <span className="font-mono" style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".06em" }}>
            STRONG BUY
          </span>
        </div>
      )}
      <div
        style={{
          position: "relative",
          width: c.w,
          height: c.h,
          borderRadius: 14,
          overflow: "hidden",
          background: c.grad,
          boxShadow: c.hero
            ? "0 36px 80px rgba(0,0,0,.62), 0 0 50px rgba(155,123,255,.4), 0 0 0 1px rgba(255,255,255,.24)"
            : "0 22px 46px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.16)",
        }}
      >
        <div style={{ position: "absolute", inset: 7, borderRadius: 9, border: "1px solid rgba(255,255,255,.24)" }} />
        <div style={{ position: "absolute", left: 12, right: 12, top: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11.5, fontWeight: 800, color: "#fff", textShadow: "0 1px 3px rgba(0,0,0,.5)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 96 }}>
            {c.name}
          </span>
          <span className="font-mono" style={{ fontSize: 8, fontWeight: 700, color: "#042A33", background: "#9BE9F5", padding: "2px 5px", borderRadius: 5 }}>
            {c.tag}
          </span>
        </div>
        <div style={{ position: "absolute", left: 12, right: 12, top: 35, height: c.hero ? 130 : 110, borderRadius: 7, border: "1px solid rgba(255,255,255,.26)", background: "repeating-linear-gradient(135deg, rgba(255,255,255,.16) 0 7px, rgba(255,255,255,0) 7px 14px), linear-gradient(160deg, rgba(0,0,0,.2), rgba(0,0,0,.04))" }} />
        <div className="font-mono" style={{ position: "absolute", left: 12, right: 12, bottom: 28, fontSize: 7.5, letterSpacing: ".1em", color: "#fff" }}>
          {c.note}
        </div>
        <div style={{ position: "absolute", left: 12, right: 12, bottom: 11, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="font-mono" style={{ fontSize: 11, fontWeight: 700, color: "#fff" }}>{c.price}</span>
          <span className="font-mono" style={{ fontSize: 9, fontWeight: 700, color: "#5EE3AC" }}>{c.delta}</span>
        </div>
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: "linear-gradient(110deg, transparent 36%, rgba(255,255,255,.32) 50%, transparent 64%)", backgroundSize: "220% 100%", animation: "pa-holo 5s linear infinite", mixBlendMode: "screen", opacity: 0.7 }} />
      </div>
    </button>
  );
}

function FeatureCard({ kicker, title, desc, link, accent, onClick }) {
  return (
    <div
      className="rounded-2xl border p-6 transition-transform hover:-translate-y-1"
      style={{ borderColor: "var(--border)", background: "var(--panel)" }}
    >
      <div className="font-mono text-[10px] uppercase tracking-[0.16em]" style={{ color: accent }}>
        {kicker}
      </div>
      <div className="mt-2.5 text-lg font-bold">{title}</div>
      <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--muted)" }}>{desc}</p>
      <button
        onClick={onClick}
        className="mt-3.5 border-none bg-transparent text-sm font-semibold"
        style={{ color: "var(--blue-soft)", cursor: "pointer" }}
      >
        {link}
      </button>
    </div>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  const [packOpen, setPackOpen] = useState(false);
  const launch = () => navigate("/cockpit");

  return (
    <div style={{ minHeight: "100vh", overflow: "hidden" }}>
      <PackModal open={packOpen} onClose={() => setPackOpen(false)} />
      {/* Hero */}
      <div style={{ position: "relative", minHeight: "100vh", display: "flex", flexDirection: "column" }}>
        <div style={{ position: "absolute", inset: 0, background: "var(--hero-overlay)", pointerEvents: "none" }} />

        {/* Top bar */}
        <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "22px 44px" }}>
          <div className="flex items-center gap-2.5">
            <div style={{ width: 26, height: 26, borderRadius: "50%", background: "conic-gradient(from 210deg, #3D7BFF, #9B7BFF, #FFCB2E, #34D399, #3D7BFF)", boxShadow: "inset 0 0 0 5px var(--bg), 0 0 18px rgba(155,123,255,.5)" }} />
            <div className="text-lg font-extrabold tracking-tight">
              Poké<span style={{ color: "var(--logo-accent)" }}>Alpha</span>
            </div>
          </div>
          <div className="flex items-center gap-3.5">
            <div className="flex items-center gap-1.5 rounded-full border p-1.5" style={{ borderColor: "var(--glass-border)", background: "var(--glass-bg)" }}>
              {THEMES.map((th) => (
                <button
                  key={th}
                  onClick={() => setTheme(th)}
                  title={t(`theme.${th}`)}
                  style={{ width: 18, height: 18, borderRadius: "50%", background: THEME_SWATCH[th], cursor: "pointer", border: "1px solid var(--border-hover)", outline: theme === th ? "2px solid var(--blue)" : "none", outlineOffset: 1 }}
                />
              ))}
            </div>
            <button
              onClick={launch}
              className="rounded-xl px-4.5 py-2.5 text-sm font-semibold backdrop-blur"
              style={{ border: "1px solid var(--glass-border)", background: "var(--glass-bg)", color: "var(--text)", cursor: "pointer", padding: "9px 18px" }}
            >
              {t("landing.cta.launch")}
            </button>
          </div>
        </div>

        {/* Hero content */}
        <div style={{ position: "relative", flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", maxWidth: 1180, margin: "0 auto", padding: "18px 40px 150px", boxSizing: "border-box" }}>
          <div className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5" style={{ border: "1px solid rgba(155,123,255,.35)", background: "rgba(155,123,255,.1)" }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--violet)", animation: "pa-pulse 2s infinite" }} />
            <span className="font-mono" style={{ fontSize: 11, letterSpacing: ".16em", color: "var(--violet-text)" }}>{t("landing.badge")}</span>
          </div>
          <h1 style={{ margin: "22px 0 0", fontSize: 60, lineHeight: 1.05, fontWeight: 800, letterSpacing: "-0.03em", maxWidth: 660 }}>
            {t("landing.titlePre")}
            <span style={{ background: "linear-gradient(100deg, #FFD75A 5%, #FF9D5C 38%, #9B7BFF 75%, #3D7BFF 100%)", backgroundSize: "230% 100%", animation: "pa-holo 6s linear infinite", WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              {t("landing.titleHi")}
            </span>
            {t("landing.titlePost")}
          </h1>
          <p style={{ margin: "20px 0 0", fontSize: 18, lineHeight: 1.55, color: "var(--muted2)", maxWidth: 588 }}>
            {t("landing.subtitle")}
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={launch}
              className="text-ink"
              style={{ padding: "16px 30px", borderRadius: 14, border: "none", background: "linear-gradient(180deg, #FFD75A, #FFC91F)", fontSize: 16.5, fontWeight: 700, cursor: "pointer", boxShadow: "0 10px 34px rgba(255,203,46,.35)" }}
            >
              {t("landing.cta.explore")}
            </button>
            <button
              onClick={() => setPackOpen(true)}
              className="inline-flex items-center gap-2"
              style={{ padding: "16px 26px", borderRadius: 14, border: "1px solid var(--glass-border)", background: "var(--glass-bg)", color: "var(--text)", fontSize: 16.5, fontWeight: 600, cursor: "pointer", backdropFilter: "blur(10px)" }}
            >
              <span style={{ filter: "drop-shadow(0 0 6px rgba(255,203,46,.6))" }}>⚡</span> {t("pack.cta")}
            </button>
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-7 font-mono text-xs" style={{ color: "var(--muted)" }}>
            {STATS.map(([val, key]) => (
              <div key={key}>
                <div style={{ color: "var(--text)", fontWeight: 700, fontSize: 21 }}>{val}</div>
                <div style={{ marginTop: 3 }}>{t(key)}</div>
              </div>
            ))}
          </div>

          <div className="mt-14 inline-flex items-center gap-2">
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)", animation: "pa-pulse 1.6s infinite" }} />
            <span className="font-mono" style={{ fontSize: 10.5, letterSpacing: ".18em", color: "var(--muted)" }}>{t("landing.movers")}</span>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "center", marginTop: 22, minHeight: 250 }}>
            {CARDS.map((c) => (
              <div key={c.name} style={{ position: "relative" }}>
                <FanCard c={c} />
              </div>
            ))}
          </div>
        </div>

        {/* Ticker */}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, borderTop: "1px solid var(--line)", background: "var(--ticker-bg)", backdropFilter: "blur(10px)", overflow: "hidden", padding: "13px 0" }}>
          <div style={{ display: "flex", gap: 48, width: "max-content", animation: "pa-ticker 32s linear infinite" }} className="font-mono text-xs whitespace-nowrap">
            {[...TICKER, ...TICKER].map(([name, price, delta, color], i) => (
              <span key={i} style={{ color: "var(--muted2)" }}>
                {name} <span style={{ color: "var(--text)" }}>{price}</span>{" "}
                <span style={{ color: color === "red" ? "var(--red)" : "var(--green)" }}>{delta}</span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Feature trio */}
      <div style={{ position: "relative", padding: "80px 44px 90px", maxWidth: 1180, margin: "0 auto" }}>
        <div className="text-center">
          <div className="font-mono text-[11px] tracking-[0.18em]" style={{ color: "var(--violet-text)" }}>
            {t("landing.section.terminal")}
          </div>
          <h2 className="mx-auto mt-3.5 max-w-[620px] text-4xl font-extrabold tracking-tight">
            {t("landing.section.title")}
          </h2>
        </div>
        <div className="mt-10 grid grid-cols-1 gap-3.5 md:grid-cols-3">
          <FeatureCard
            kicker={t("landing.feature.future.kicker")}
            title={t("landing.feature.future.title")}
            desc={t("landing.feature.future.desc")}
            link={t("landing.feature.future.link")}
            accent="var(--violet-text)"
            onClick={() => navigate("/future")}
          />
          <FeatureCard
            kicker={t("landing.feature.analyzer.kicker")}
            title={t("landing.feature.analyzer.title")}
            desc={t("landing.feature.analyzer.desc")}
            link={t("landing.feature.analyzer.link")}
            accent="var(--green-text)"
            onClick={() => navigate("/analyzer")}
          />
          <FeatureCard
            kicker={t("landing.feature.portfolio.kicker")}
            title={t("landing.feature.portfolio.title")}
            desc={t("landing.feature.portfolio.desc")}
            link={t("landing.feature.portfolio.link")}
            accent="var(--gold)"
            onClick={() => navigate("/portefeuille")}
          />
        </div>
      </div>
    </div>
  );
}
