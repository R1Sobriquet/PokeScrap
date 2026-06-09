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
  api: { get: vi.fn(), put: h.put, post: h.post },
  exportUrl: (p) => p,
  login: vi.fn(),
  fetchMe: vi.fn(),
}));

import { AuthProvider } from "../AuthContext.jsx";
import Cockpit from "../pages/Cockpit.jsx";
import Settings from "../pages/Settings.jsx";
import Jobs from "../pages/Jobs.jsx";
import Sets from "../pages/Sets.jsx";
import Watchlist from "../pages/Watchlist.jsx";
import App from "../App.jsx";

const wrap = (ui) => render(<AuthProvider>{ui}</AuthProvider>);

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

describe("Auth", () => {
  it("protège les routes : non connecté → écran de login", () => {
    render(<App />);
    expect(screen.getByText("Se connecter")).toBeInTheDocument();
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
