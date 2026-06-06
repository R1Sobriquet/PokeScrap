# Jalon 6 — Pré-vol : robustesse aux changements de structure

## Posture

Scraping **poli, faible débit, listings publics**. Aucun contournement anti-bot
(pas de CAPTCHA solving, pas d'anti-fingerprint, pas de proxies d'évasion). Si une
plateforme bloque (CAPTCHA / 403 / mur DataDome) → on **s'arrête** sur cette
plateforme, on émet `tech_error`, on applique un backoff. On ne lutte pas.

## Sélecteurs externalisés (aucun en dur)

Tous les sélecteurs CSS vivent dans **`scraper/selectors.yaml`**, par plateforme :
`search_url`, `container`, `title`, `price`, `shipping`, `location`, `link`,
`external_id_attr` (optionnel ; sinon l'id est extrait du href), `base_url`.

Le code (`app/scraping/parser.py`) ne contient **aucun** sélecteur : il reçoit le
bloc de la plateforme et applique `BeautifulSoup.select`.

## Hypothèse de structure retenue

> ⚠️ Les sélecteurs de `selectors.yaml` sont une **hypothèse de départ
> best-effort** (la mémoire d'entraînement est probablement périmée). Ils
> **doivent être vérifiés sur le HTML réel** avant le premier vrai run.

- **Vinted** : grille de cartes `div.feed-grid__item`, lien `a[href*='/items/']`
  (l'id = plus longue suite de chiffres du href), prix `…--price-text`.
- **LeBoncoin** : cartes `article[data-test-id='ad']`, lien `a[href*='/ad/']`,
  prix `[data-test-id='price']`.

## Détection de casse bruyante

`parse_listings` renvoie `ParseResult(broken=True, reason=…)` si :
- **0 conteneur** là où on attend des résultats, ou
- plus de **`selector_break_threshold`%** (défaut 30) des cartes n'ont ni titre ni
  prix.

Dans ce cas l'orchestration (`scrape_sourcing`) émet une alerte `tech_error`
« sélecteurs à mettre à jour, plateforme X » **au lieu d'insérer du vide**.

## Comment mettre à jour `selectors.yaml`

1. Récupérer le HTML d'une page de recherche réelle (DevTools → Copy outerHTML, ou
   `page.content()`), le sauver en fixture.
2. Identifier le conteneur d'une annonce, puis les sélecteurs relatifs
   (titre/prix/port/localisation/lien).
3. Mettre à jour le bloc plateforme dans `scraper/selectors.yaml` (rien d'autre à
   toucher : aucun sélecteur n'est en dur dans le code).
4. Vérifier avec une fixture via `tests/test_scraper_parser.py` (ajouter/มettre à
   jour une fixture si la structure a changé).

## Architecture & isolation

- Le **fetch Playwright** (`scraper/fetch.py`) vit dans le conteneur scraper
  (sortant uniquement, `restart: unless-stopped`). Le **parsing est pur**
  (`app/scraping/`), donc testable sur fixtures sans navigateur.
- `scrape_sourcing` est **best-effort** : toute exception d'un provider est captée
  (→ `tech_error`), **jamais propagée**. Une panne du scraper n'affecte ni les
  prix ni les KPIs (conteneurs distincts).
- **PII minimale** : on ne stocke pas l'identité du vendeur ; seulement une
  localisation grossière. Rétention courte (`sourcing_retention_days`, défaut 90).
