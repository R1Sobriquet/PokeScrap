"""Modèle ML Future Radar (scikit-learn).

``features`` : extraction de features identiques à l'entraînement et au service
(parité train/serve). ``dataset`` : construit (features, cibles) depuis l'historique
réel ``price_snapshots``. ``scorer`` : entraîne / persiste / charge / prédit.
"""
