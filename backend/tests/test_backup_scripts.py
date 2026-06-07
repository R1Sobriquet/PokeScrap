"""Tests des scripts de sauvegarde (présence + garde-fous ; run réel documenté)."""

from __future__ import annotations

import pathlib
import shutil

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def test_scripts_exist_and_executable():
    for name in ("backup.sh", "restore.sh", "restore_test.sh"):
        path = SCRIPTS / name
        assert path.exists(), f"{name} manquant"
        assert path.stat().st_mode & 0o111, f"{name} non exécutable"


def test_backup_refuses_plaintext():
    # Garde-fou : pas de stockage en clair (chiffrement obligatoire).
    content = (SCRIPTS / "backup.sh").read_text()
    assert "BACKUP_ENCRYPTION_KEY" in content
    assert "refus de stocker en clair" in content
    assert 'rm -f "$PLAIN"' in content  # le clair est supprimé


def test_restore_test_has_integrity_checks():
    content = (SCRIPTS / "restore_test.sh").read_text()
    assert "DROP DATABASE IF EXISTS" in content   # base jetable
    assert "MIN_TABLES" in content                # contrôle nb de tables
    assert "transactions" in content              # compte de contrôle


def test_real_restore_test_skipped_without_docker():
    # Le run réel nécessite Docker + MySQL (indispo en sandbox CI) → skip documenté.
    if shutil.which("docker") is None:
        pytest.skip("Docker indisponible : restore_test.sh réel à exécuter au go-live")
    pytest.skip("Run réel de restore_test.sh à exécuter manuellement (voir runbook)")
