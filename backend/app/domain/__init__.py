"""MOTEUR DE RÈGLES — fonctions pures, zéro I/O.

Tout le métier des jalons suivants (règle des 50 %, filtres anti-pump/anti-FOMO,
moteur de vente 25/50/25, scoring d'opportunité, paliers, grading pondéré, KPIs…)
vivra ici.

Règle non négociable :

* **Fonctions pures, type-hintées.** Elles reçoivent des dataclasses / DTO et
  renvoient des décisions.
* **Aucun accès base, aucun réseau, aucune horloge cachée.** Tout ce dont une
  fonction a besoin lui est passé en argument (y compris les constantes lues via
  ``get_setting`` côté application, et l'instant courant si pertinent).

Cette discipline rend le moteur testable en isolation et indépendant des sources
de données (mode prototype US gratuit vs réel EU payant).

Vide au Jalon 1 — prêt pour le Jalon 2+.
"""
