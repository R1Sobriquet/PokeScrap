"""Anti-détection LÉGÈRE + diagnostic de blocage (parties pures, testables).

Posture : pas de course à l'armement (ni proxies résidentiels, ni solveur de
captcha). On se limite à masquer les signaux d'automation évidents, un UA/locale
réalistes, un rythme lent — et surtout un **diagnostic précis** quand une source
bloque (403 ? captcha ? mur DataDome ?).
"""

from __future__ import annotations

# UA réaliste et récent (Chrome desktop).
REALISTIC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Script injecté avant chargement : masque navigator.webdriver et signaux évidents.
STEALTH_INIT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR','fr','en-US','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = window.chrome || { runtime: {} };
"""

# Marqueurs de pages anti-bot (recherche insensible à la casse dans le HTML).
DATADOME_MARKERS = ("datadome", "geo.captcha-delivery.com", "dd_cookie", "captcha-delivery")
CAPTCHA_MARKERS = ("recaptcha", "hcaptcha", "px-captcha", "g-recaptcha",
                   "are you a human", "verifying you are human", "challenge-platform")


def classify_block(status: int | None, html: str | None) -> str | None:
    """Renvoie la cause de blocage, ou ``None`` si la page semble exploitable.

    Distingue : ``http_403`` / ``http_429`` (refus immédiat), ``datadome`` (mur
    DataDome), ``captcha`` (recaptcha/hcaptcha/PerimeterX).
    """
    if status in (403, 429):
        return f"http_{status}"
    low = (html or "").lower()
    if any(m in low for m in DATADOME_MARKERS):
        return "datadome"
    if any(m in low for m in CAPTCHA_MARKERS):
        return "captcha"
    return None
