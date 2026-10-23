# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_nettoyage.py
# Version      : 1
# Date         : 22-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests du nettoyage des anciennes exécutions (src/core/nettoyage.py, T7.2).

Sans réseau : pur système de fichiers, via monkeypatch.chdir(tmp_path).
Couvre la sélection par âge, la protection de l'exécution courante, le
fail-safe sur les noms non reconnus, la simulation, les registres globaux,
et le bilan (compteurs + octets). Références : tests/plan_tests.md TU-94..TU-100.
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.core.nettoyage import (
    AGE_DEFAUT_JOURS,
    RACINES_SOUS_DOSSIERS,
    RACINE_LOGS,
    executions_a_supprimer,
    nettoyer_anciennes_executions,
)


def _id(date: datetime) -> str:
    return date.strftime("%Y%m%d_%H%M%S") + "_a1b2c3"


def _fabriquer_executions(tmp_path: Path, ids: list) -> None:
    """Crée les 4 familles de traces pour chaque id (dossiers + log)."""
    for id_execution in ids:
        for racine in RACINES_SOUS_DOSSIERS:
            dossier = tmp_path / racine / id_execution
            dossier.mkdir(parents=True)
            (dossier / "fichier.csv").write_text("données", encoding="utf-8")
        log = tmp_path / RACINE_LOGS / f"openDataAgent_{id_execution}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("log\n", encoding="utf-8")


@pytest.fixture
def maintenant():
    return datetime(2026, 10, 22, 12, 0, 0)


@pytest.fixture
def vielle():
    return datetime(2026, 9, 1, 10, 0, 0)


@pytest.fixture
def recente():
    return datetime(2026, 10, 20, 10, 0, 0)


def test_execution_ancienne_supprimee_sur_les_quatre_racines(tmp_path, monkeypatch, vielle, maintenant):
    # Réf. tests/plan_tests.md : TU-94
    monkeypatch.chdir(tmp_path)
    id_vieux = _id(vielle)
    _fabriquer_executions(tmp_path, [id_vieux])

    bilan = nettoyer_anciennes_executions(age_jours=30, maintenant=maintenant)
    assert bilan["statut"] == "succes"
    assert bilan["donnees"]["supprimes"] == [id_vieux]
    assert bilan["donnees"]["conserves"] == []
    for racine in RACINES_SOUS_DOSSIERS:
        assert not (tmp_path / racine / id_vieux).exists()
    assert not (tmp_path / RACINE_LOGS / f"openDataAgent_{id_vieux}.log").exists()


def test_execution_recente_conservee(tmp_path, monkeypatch, vielle, recente, maintenant):
    # Réf. tests/plan_tests.md : TU-95
    monkeypatch.chdir(tmp_path)
    ids = [_id(vielle), _id(recente)]
    _fabriquer_executions(tmp_path, ids)

    a_supprimer = executions_a_supprimer(
        30, racines=RACINES_SOUS_DOSSIERS, racine_logs=RACINE_LOGS, maintenant=maintenant
    )
    assert a_supprimer == [_id(vielle)]
    for racine in RACINES_SOUS_DOSSIERS:
        assert (tmp_path / racine / _id(recente)).is_dir()
    assert (tmp_path / RACINE_LOGS / f"openDataAgent_{_id(recente)}.log").is_file()


def test_execution_courante_toujours_protegee(tmp_path, monkeypatch, vielle, maintenant):
    # Réf. tests/plan_tests.md : TU-96
    monkeypatch.chdir(tmp_path)
    id_courant = _id(vielle)  # même un id "vieux" est protégé s'il est courant
    _fabriquer_executions(tmp_path, [id_courant])

    a_supprimer = executions_a_supprimer(
        30, id_execution_courante=id_courant,
        racines=RACINES_SOUS_DOSSIERS, racine_logs=RACINE_LOGS, maintenant=maintenant,
    )
    assert a_supprimer == []
    bilan = nettoyer_anciennes_executions(age_jours=30, id_execution_courante=id_courant)
    assert bilan["donnees"]["supprimes"] == []
    assert bilan["donnees"]["conserves"] == [id_courant]
    assert (tmp_path / "data" / "raw" / id_courant).is_dir()


def test_simulation_ne_supprime_rien(tmp_path, monkeypatch, vielle, maintenant):
    # Réf. tests/plan_tests.md : TU-97
    monkeypatch.chdir(tmp_path)
    id_vieux = _id(vielle)
    _fabriquer_executions(tmp_path, [id_vieux])

    bilan = nettoyer_anciennes_executions(age_jours=30, simulation=True, maintenant=maintenant)
    assert bilan["statut"] == "succes"
    assert bilan["donnees"]["simulation"] is True
    assert bilan["donnees"]["supprimes"] == [id_vieux]
    for racine in RACINES_SOUS_DOSSIERS:
        assert (tmp_path / racine / id_vieux).is_dir()
    assert (tmp_path / RACINE_LOGS / f"openDataAgent_{id_vieux}.log").is_file()


def test_registres_globaux_et_noms_inconnus_conserves(tmp_path, monkeypatch, vielle, maintenant):
    # Réf. tests/plan_tests.md : TU-98
    monkeypatch.chdir(tmp_path)
    id_vieux = _id(vielle)
    _fabriquer_executions(tmp_path, [id_vieux])
    # Registres globaux (fichiers plats sous data/, hors périmètre id_execution)
    registre = tmp_path / "data" / "registre_sources.json"
    registre.parent.mkdir(parents=True, exist_ok=True)
    registre.write_text("{}", encoding="utf-8")
    acceptations = tmp_path / "data" / "registre_acceptations.json"
    acceptations.write_text("{}", encoding="utf-8")
    # Dossier au nom non reconnu (fail-safe : jamais supprimé)
    dossier_inconnu = tmp_path / "data" / "raw" / "sauvegarde_manuelle"
    dossier_inconnu.mkdir(parents=True)
    (dossier_inconnu / "fichier.csv").write_text("x", encoding="utf-8")
    # Log au nom non reconnu
    logs = tmp_path / RACINE_LOGS
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "openDataAgent.log").write_text("log\n", encoding="utf-8")

    bilan = nettoyer_anciennes_executions(age_jours=30, maintenant=maintenant)
    assert bilan["donnees"]["supprimes"] == [id_vieux]
    assert "sauvegarde_manuelle" in bilan["donnees"]["conserves"]
    assert registre.is_file()
    assert acceptations.is_file()
    assert dossier_inconnu.is_dir()
    assert (logs / "openDataAgent.log").is_file()


def test_id_malforme_conserve(tmp_path, monkeypatch, maintenant):
    # Réf. tests/plan_tests.md : TU-99
    monkeypatch.chdir(tmp_path)
    dossier = tmp_path / "data" / "raw" / "20261301_999999_xyz"  # date invalide
    dossier.mkdir(parents=True)
    (dossier / "f.csv").write_text("x", encoding="utf-8")

    a_supprimer = executions_a_supprimer(
        1, racines=RACINES_SOUS_DOSSIERS, racine_logs=RACINE_LOGS, maintenant=maintenant
    )
    assert a_supprimer == []
    assert dossier.is_dir()


def test_bilan_compteurs_et_octets(tmp_path, monkeypatch, vielle, maintenant):
    # Réf. tests/plan_tests.md : TU-100
    monkeypatch.chdir(tmp_path)
    ids = [_id(vielle), _id(vielle + timedelta(days=1))]
    _fabriquer_executions(tmp_path, ids)
    # Fichier de taille connue dans l'un des dossiers raw
    (tmp_path / "data" / "raw" / ids[0] / "fichier.csv").write_text("12345", encoding="utf-8")

    bilan = nettoyer_anciennes_executions(age_jours=30, maintenant=maintenant)
    donnees = bilan["donnees"]
    assert donnees["supprimes"] == ids
    assert donnees["conserves"] == []
    # 'données' = 8 octets en utf-8 (é = 2), 'log\n' = 4 octets ; le fichier
    # écrasé vaut 5 octets au lieu de 8 pour ids[0]
    attendu = len(ids) * (8 * len(RACINES_SOUS_DOSSIERS) + 4) - 3
    assert donnees["octets_liberes"] == attendu
    assert donnees["erreurs"] == []
    assert donnees["age_jours"] == 30
    assert donnees["simulation"] is False


def test_age_invalide_retourne_erreur_parametres(tmp_path, monkeypatch):
    # Garde-fou de la fonction cœur (la CLI valide déjà via min=1)
    monkeypatch.chdir(tmp_path)
    bilan = nettoyer_anciennes_executions(age_jours=0)
    assert bilan["statut"] == "erreur_parametres"
    assert bilan["donnees"] == {}


def test_racines_inexistantes_ignorees(tmp_path, monkeypatch):
    # Aucune racine créée : bilan succès, rien à supprimer
    monkeypatch.chdir(tmp_path)
    bilan = nettoyer_anciennes_executions(age_jours=30)
    assert bilan["statut"] == "succes"
    assert bilan["donnees"]["supprimes"] == []


def test_constante_age_defaut():
    assert AGE_DEFAUT_JOURS == 30
