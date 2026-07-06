import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// vi.mock est hoisté → les variables partagées doivent passer par vi.hoisted.
const h = vi.hoisted(() => ({
  polled: {},
  post: vi.fn(() => Promise.resolve({})),
  put: vi.fn(() => Promise.resolve({})),
}));

vi.mock("../hooks/usePolling.js", () => ({
  usePolling: (path) => ({ data: h.polled[path], loading: false, error: null, reload: () => {} }),
}));

vi.mock("../api.js", () => ({
  api: { get: vi.fn(() => Promise.resolve({})), put: h.put, post: h.post },
  exportUrl: (p) => p,
  login: vi.fn(),
  fetchMe: vi.fn(() => Promise.resolve({ username: "erwann", role: "admin", plan: "pro" })),
  // Auth v2 : silent refresh au boot (null = pas de session) + liaisons.
  refreshSession: vi.fn(() => Promise.resolve(null)),
  logoutSession: vi.fn(),
  bindSession: vi.fn(),
  registerAccount: h.register ?? vi.fn(() => Promise.resolve({})),
  verifyEmail: vi.fn(() => Promise.resolve({})),
  forgotPassword: vi.fn(() => Promise.resolve({})),
  resetPassword: vi.fn(() => Promise.resolve({})),
}));

import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../AuthContext.jsx";
import Cockpit from "../pages/Cockpit.jsx";
import Settings from "../pages/Settings.jsx";
import Jobs from "../pages/Jobs.jsx";
import Sets from "../pages/Sets.jsx";
import Watchlist from "../pages/Watchlist.jsx";
import Restock from "../pages/Restock.jsx";
import Retailers from "../pages/Retailers.jsx";
import Calendar from "../pages/Calendar.jsx";
import SetExplorer from "../pages/SetExplorer.jsx";
import FlipRadar from "../pages/FlipRadar.jsx";
import Layout from "../components/Layout.jsx";
import App from "../App.jsx";

const wrap = (ui) => render(<MemoryRouter><AuthProvider>{ui}</AuthProvider></MemoryRouter>);

beforeEach(() => {
  h.post.mockClear();
  h.put.mockClear();
});

describe("Cockpit", () => {
  it("affiche les KPIs des données mockées", () => {
    h.polled["/cockpit"] = {
      kpis: { total_portfolio_value: 375, capital_invested: 80, cash_total: 295,
              realized_profit_net: 55, capital_rotation_rate: 0.5, cash_locked: 16.5,
              cash_active: 278.5, tax_provision: 12.3, operational_capital: 358.5 },
      tier: { current: 1, current_name: "T1", next: 2, capital_min: 150, capital_max: 300, progress: 0.5 },
      allocation: { stock_pct: 22, cash_pct: 78, target_stock_pct: null, target_cash_pct: null },
      pending_alerts: 3,
      history: [],
    };
    wrap(<Cockpit />);
    expect(screen.getByText("Cockpit")).toBeInTheDocument();
    expect(screen.getByText("Profit net réalisé")).toBeInTheDocument();
    expect(screen.getAllByText(/375\.00 €/).length).toBeGreaterThan(0);
  });
});

describe("Settings — bascule Pro", () => {
  it("appelle l'action atomique switch-pro après confirmation", async () => {
    h.polled["/settings"] = [
      { key: "poketrace_plan", value: "free", value_type: "string" },
      { key: "valuation_market", value: "US", value_type: "string" },
      { key: "fomo_freeze", value: "false", value_type: "bool" },
    ];
    vi.stubGlobal("confirm", vi.fn(() => true));
    wrap(<Settings />);
    fireEvent.click(screen.getByText("Passer en Pro"));
    await waitFor(() => expect(h.post).toHaveBeenCalled());
    expect(h.post.mock.calls[0][1]).toBe("/settings/switch-pro");
    expect(h.post.mock.calls[0][2]).toEqual({ to_pro: true });
  });
});

describe("Flip Radar — tri + tiroir de détail", () => {
  const OPPS = [
    { offer_id: 1, title: "Cheap Box", retailer: "Fnac", stock_state: "in_stock",
      retail_price: 10, market_value: 20, net_upside_pct: 50, est_profit: 5,
      verdict: "BUY", verdict_tone: "buy", url: "https://a/x" },
    { offer_id: 2, title: "Pricey Box", retailer: "Cultura", stock_state: "in_stock",
      retail_price: 99, market_value: 150, net_upside_pct: 30, est_profit: 20,
      verdict: "FAIR", verdict_tone: "fair", url: "https://b/y" },
  ];

  it("trie par prix au clic (desc puis asc)", () => {
    h.polled["/retail/opportunities"] = OPPS;
    wrap(<FlipRadar />);
    const rowTitles = () =>
      screen.getAllByRole("button").filter((b) => /voir le détail/.test(b.getAttribute("aria-label") || ""))
        .map((b) => b.getAttribute("aria-label"));
    fireEvent.click(screen.getByText("PRIX (MSRP)"));
    expect(rowTitles()[0]).toMatch(/Pricey Box/); // desc au 1er clic
    fireEvent.click(screen.getByText("PRIX (MSRP)"));
    expect(rowTitles()[0]).toMatch(/Cheap Box/); // asc au 2e clic
  });

  it("ouvre le tiroir de détail au clic sur une ligne", () => {
    h.polled["/retail/opportunities"] = OPPS;
    wrap(<FlipRadar />);
    fireEvent.click(screen.getByLabelText(/Cheap Box — voir le détail/));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog.textContent).toContain("Cheap Box");
    expect(dialog.textContent).toContain("10.00 €"); // MSRP dans le tiroir
  });
});

describe("Layout — shell", () => {
  it("rend skip-link, nav scindée (PokéStock FR) et bouton tutoriel", () => {
    h.polled["/alerts?status=pending"] = [];
    wrap(<Layout />);
    expect(screen.getByText("Aller au contenu")).toBeInTheDocument();
    expect(screen.getByText("PokéStock FR")).toBeInTheDocument(); // groupe scindé
    expect(screen.getByLabelText("Rejouer le tutoriel")).toBeInTheDocument();
    expect(screen.getByLabelText("Ouvrir la navigation")).toBeInTheDocument(); // hamburger mobile
  });

  it("masque la nav d'exploitation aux non-admins", () => {
    h.polled["/alerts?status=pending"] = [];
    wrap(<Layout />); // AuthProvider sans profil → rôle "user"
    expect(screen.queryByText("Actions & Jobs")).not.toBeInTheDocument();
    expect(screen.queryByText("Détaillants")).not.toBeInTheDocument();
    expect(screen.getByText("Watchlist")).toBeInTheDocument(); // nav user intacte
  });
});

describe("Auth", () => {
  it("protège les routes : non connecté → écran de login", async () => {
    // "/" est la landing publique ; une route protégée redirige vers le login
    // (après le silent refresh du boot, résolu à null par le mock).
    window.history.pushState({}, "", "/cockpit");
    render(<App />);
    expect(await screen.findByText("Se connecter")).toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });

  it("inscription : formulaire complet + lien retour connexion", () => {
    window.history.pushState({}, "", "/register");
    render(<App />);
    expect(screen.getByText("Créer mon compte")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });
});

describe("Landing", () => {
  it("affiche la landing publique sur /", () => {
    window.history.pushState({}, "", "/");
    render(<App />);
    // Langue par défaut FR.
    expect(screen.getByText("Lancer l'app")).toBeInTheDocument();
    expect(screen.getByText("Explorer le marché")).toBeInTheDocument();
  });
});

describe("Actions & Jobs", () => {
  it("rend les boutons, désactive un job en cours, et lance un job", async () => {
    h.polled["/admin/jobs/recent"] = {
      jobs: ["sync-tracked-sets", "refresh-prices", "scan-movers", "evaluate-sales", "kpi-snapshot"],
      runs: [
        { id: 2, job_name: "sync-tracked-sets", status: "running", started_at: "2026-06-05T12:00:00" },
        { id: 1, job_name: "kpi-snapshot", status: "done", finished_at: "2026-06-05T11:01:00",
          summary: "snapshot 2026-06-05" },
      ],
      watchlist_count: 240,
      poketrace_daily_limit: 250,
    };
    wrap(<Jobs />);

    // Les 5 actions sont rendues.
    expect(screen.getByText("Synchroniser les sets")).toBeInTheDocument();
    expect(screen.getByText("Rafraîchir les prix")).toBeInTheDocument();
    // Le job en cours affiche "En cours…" et son bouton est désactivé.
    const running = screen.getByText("En cours…");
    expect(running).toBeDisabled();
    // Avertissement quota (240 > 200) présent.
    expect(screen.getByText(/risque de dépassement/)).toBeInTheDocument();

    // Lancer un job appelle l'endpoint run.
    fireEvent.click(screen.getAllByText("Lancer")[0]);
    await waitFor(() => expect(h.post).toHaveBeenCalled());
    expect(h.post.mock.calls[0][1]).toMatch(/^\/admin\/jobs\/.+\/run$/);
  });
});

describe("Sets — ajout d'un set cible", () => {
  it("ouvre le formulaire, valide le slug requis, puis POST", async () => {
    h.polled["/tracked-sets"] = [
      { id: 1, name: "PE", set_slug: "pe", min_value_eur: 5, include_single: true, include_sealed: true, is_active: true },
    ];
    h.polled["/movers"] = [];
    wrap(<Sets />);

    fireEvent.click(screen.getByText("+ Ajouter un set cible"));
    // slug vide → message de validation, pas d'appel.
    fireEvent.click(screen.getByText("Ajouter"));
    expect(screen.getByText(/slug est requis/i)).toBeInTheDocument();
    expect(h.post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Slug/i), { target: { value: "151" } });
    fireEvent.click(screen.getByText("Ajouter"));
    await waitFor(() => expect(h.post).toHaveBeenCalled());
    expect(h.post.mock.calls[0][1]).toBe("/tracked-sets");
  });
});

describe("PokéStock FR — Veille restock", () => {
  it("affiche les offres watchées et ajoute une offre par URL", async () => {
    h.polled["/retail/offers?watched=true"] = [
      { id: 1, title: "ETB Pokémon", retailer: "Cultura", stock_state: "in_stock",
        price: 59.99, url: "https://c/p/etb.html", last_changed_at: "2026-06-16T10:00:00" },
    ];
    wrap(<Restock />);
    expect(screen.getByText("ETB Pokémon")).toBeInTheDocument();
    expect(screen.getByText("✅ En stock")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/cultura\.com/i), {
      target: { value: "https://www.cultura.com/p/x.html" },
    });
    fireEvent.click(screen.getByText("Ajouter à la veille"));
    await waitFor(() => expect(h.post).toHaveBeenCalled());
    expect(h.post.mock.calls[0][1]).toBe("/retail/offers");
  });
});

describe("PokéStock FR — Détaillants", () => {
  it("affiche le circuit breaker et bascule l'activation", async () => {
    h.polled["/retail/retailers"] = [
      { id: 1, code: "fnac", name: "Fnac", enabled: false, offers: 3,
        error_count: 5, circuit_open: true, is_active: true },
    ];
    wrap(<Retailers />);
    expect(screen.getByText("Fnac")).toBeInTheDocument();
    expect(screen.getByText(/ouvert \(5 err\)/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("ON"));
    await waitFor(() => expect(h.put).toHaveBeenCalled());
    expect(h.put.mock.calls[0][1]).toBe("/retail/retailers/1");
  });
});

describe("PokéStock FR — Calendrier", () => {
  it("valide le nom requis puis POST une sortie", async () => {
    h.polled["/releases"] = [];
    wrap(<Calendar />);
    fireEvent.click(screen.getByText("Ajouter"));
    expect(screen.getByText(/nom du produit est requis/i)).toBeInTheDocument();
    expect(h.post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/^Produit/i), { target: { value: "ETB Prismatic" } });
    fireEvent.click(screen.getByText("Ajouter"));
    await waitFor(() => expect(h.post).toHaveBeenCalled());
    expect(h.post.mock.calls[0][1]).toBe("/releases");
  });
});

describe("Set Explorer", () => {
  it("affiche les sets suivis avec le nombre de movers", () => {
    h.polled["/tracked-sets"] = [
      { id: 1, name: "Prismatic Evolutions", set_slug: "prismatic-evolutions", is_active: true },
    ];
    h.polled["/movers"] = [
      { product_id: 9, name: "Umbreon ex", set_slug: "prismatic-evolutions", rise_pct: 12.5, price: 1400 },
    ];
    wrap(<SetExplorer />);
    expect(screen.getByText("Prismatic Evolutions")).toBeInTheDocument();
    expect(screen.getByText("prismatic-evolutions")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // 1 mover
  });
});

describe("Watchlist — ajout manuel", () => {
  it("rend le formulaire et affiche 'aucun résultat' sur 404", async () => {
    h.polled["/watchlist"] = [];
    h.polled["/alerts?status=pending"] = [];
    h.post.mockRejectedValueOnce(new Error("API 404 sur /watchlist"));
    wrap(<Watchlist />);

    fireEvent.click(screen.getByText("+ Ajouter une carte/produit"));
    fireEvent.change(screen.getByLabelText(/Recherche PokeTrace/i), { target: { value: "Inexistant" } });
    fireEvent.click(screen.getByText("Ajouter"));

    await waitFor(() => expect(h.post).toHaveBeenCalled());
    expect(h.post.mock.calls[0][1]).toBe("/watchlist");
    expect(h.post.mock.calls[0][2].search).toBe("Inexistant");
    expect(await screen.findByText(/Aucun produit trouvé pour cette recherche/i)).toBeInTheDocument();
  });
});
