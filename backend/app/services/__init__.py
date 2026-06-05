"""Services applicatifs : ingestion, lecture, seeding.

Couche d'orchestration entre les adapters (I/O externe) et la base. Contient de
la mécanique de données, **pas de logique de décision** (celle-ci vivra dans
``domain/`` à partir du Jalon 3).
"""
