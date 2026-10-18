# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_extraction.py
# Version      : 1
# Date         : 15-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de l'extraction paginée (src/core/extraction.py, T10.7)."""
import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.core.resources as module_resources
from src.core.extraction import extraire_ressource


def inventaire_avec(ressources):
    module_resources._inventaire.clear()
    module_resources._inventaire.update(ressources)


@pytest.fixture(autouse=True)
def reinitialiser_inventaire():
    module_resources._inventaire.clear()
    yield
    module_resources._inventaire.clear()


def _reponse_api(lignes, total, page_suivante=None):
    liens = {"next": f"https://tabulaire/api/ressources/x/data/?page={page_suivante}"} if page_suivante else None
    return {
        "data": lignes,
        "meta": {"page": 1, "page_size": len(lignes) or 1, "total": total},
        "links": liens,
    }


def test_extraction_multi_pages_agregees(tmp_path, monkeypatch):
    # Réf. T10.7 — la pagination est conduite par le code : 3 pages agrégées en un CSV
    monkeypatch.chdir(tmp_path)
    inventaire_avec({"r1": {"id": "r1", "api_tabulaire": True, "licence": "lov2", "url": "https://example.fr/donnees.csv"}})
    pages = [
        _reponse_api([{"theme": "a"}, {"theme": "b"}], 5, page_suivante=2),
        _reponse_api([{"theme": "c"}], 5, page_suivante=3),
        _reponse_api([{"theme": "d"}, {"theme": "e"}], 5),
    ]
    resultat_appel = MagicMock()
    with patch("src.core.extraction.interroger_ressource_api", side_effect=[MagicMock(reussi=True, donnees=p) for p in pages]):
        reponse = extraire_ressource("r1", id_execution="flux", taille_page=2)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["total_lignes"] == 5
    assert reponse["donnees"]["lignes_ecrites"] == 5
    assert reponse["donnees"]["tronque"] is False
    assert reponse["donnees"]["licence"] == "lov2"
    chemin = Path(reponse["donnees"]["chemin_local"])
    assert chemin.exists()
    with chemin.open(encoding="utf-8") as flux:
        lignes = list(csv.DictReader(flux))
    assert [l["theme"] for l in lignes] == ["a", "b", "c", "d", "e"]


def test_extraction_ressource_jamais_vue():
    # Réf. T10.7 — convention 1 : identifiant non délivré refusé
    reponse = extraire_ressource("inconnue", id_execution="flux")
    assert reponse["statut"] == "ressource_introuvable"
    assert reponse["donnees"]["suggestion"] == "reprendre par l'inventaire"


def test_extraction_ressource_non_indexee():
    # Réf. T10.7 — garde du contrat : pas d'extraction brute en voie 1 fermée
    inventaire_avec({"r2": {"id": "r2", "api_tabulaire": False, "licence": "lov2", "url": "https://x.fr/f.csv"}})
    reponse = extraire_ressource("r2", id_execution="flux")
    assert reponse["statut"] == "ressource_non_indexee"
    assert reponse["donnees"]["suggestion"] == "basculer sur telecharger_brut"


def test_extraction_plafond_tronque(tmp_path, monkeypatch):
    # Réf. T10.7 — plafond atteint : succès partiel explicite, jamais d'échec silencieux
    monkeypatch.chdir(tmp_path)
    inventaire_avec({"r3": {"id": "r3", "api_tabulaire": True, "licence": "cc-by", "url": "https://x.fr/g.csv"}})
    grandes_pages = [_reponse_api([{"n": i} for i in range(100)], 450, page_suivante=2) for _ in range(2)]
    with patch("src.core.extraction.interroger_ressource_api", side_effect=[MagicMock(reussi=True, donnees=p) for p in grandes_pages]):
        reponse = extraire_ressource("r3", id_execution="flux", taille_page=100, plafond_lignes=150)
    assert reponse["statut"] == "succes"
    donnees = reponse["donnees"]
    assert donnees["tronque"] is True
    assert donnees["lignes_ecrites"] == 150
    assert donnees["total_lignes"] == 450
    assert "tronquée" in reponse["message"]


def test_extraction_plafond_defaut_environnement(tmp_path, monkeypatch):
    # Réf. T10.7 — plafond par défaut configurable via PLAFOND_EXTRACTION
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLAFOND_EXTRACTION", "3")
    inventaire_avec({"r4": {"id": "r4", "api_tabulaire": True, "licence": "lov2", "url": "https://x.fr/h.csv"}})
    pages = [_reponse_api([{"n": i} for i in range(3)], 10, page_suivante=2), _reponse_api([{"n": 3}], 10)]
    with patch("src.core.extraction.interroger_ressource_api", side_effect=[MagicMock(reussi=True, donnees=p) for p in pages]):
        reponse = extraire_ressource("r4", id_execution="flux", taille_page=3)
    assert reponse["donnees"]["lignes_ecrites"] == 3
    assert reponse["donnees"]["tronque"] is True


def test_extraction_collision_fichier(tmp_path, monkeypatch):
    # Réf. T10.7 — ré-extraction dans la même exécution : suffixe, jamais d'écrasement
    monkeypatch.chdir(tmp_path)
    inventaire_avec({"r5": {"id": "r5", "api_tabulaire": True, "licence": "lov2", "url": "https://x.fr/i.csv"}})
    page = _reponse_api([{"theme": "a"}], 1)
    with patch("src.core.extraction.interroger_ressource_api", return_value=MagicMock(reussi=True, donnees=page)):
        premiere = extraire_ressource("r5", id_execution="flux")
        seconde = extraire_ressource("r5", id_execution="flux")
    assert premiere["statut"] == seconde["statut"] == "succes"
    assert Path(premiere["donnees"]["chemin_local"]) != Path(seconde["donnees"]["chemin_local"])
    assert Path(premiere["donnees"]["chemin_local"]).exists()
    assert Path(seconde["donnees"]["chemin_local"]).exists()


def test_extraction_echec_http_page_2(tmp_path, monkeypatch):
    # Réf. T10.7 — échec en cours de pagination : statut de l'échec, aucune écriture
    monkeypatch.chdir(tmp_path)
    inventaire_avec({"r6": {"id": "r6", "api_tabulaire": True, "licence": "lov2", "url": "https://x.fr/j.csv"}})
    page1 = MagicMock(reussi=True, donnees=_reponse_api([{"theme": "a"}], 3, page_suivante=2))
    echec = MagicMock(reussi=False, statut="echec_technique", erreur="coupure", donnees=None)
    with patch("src.core.extraction.interroger_ressource_api", side_effect=[page1, echec]):
        reponse = extraire_ressource("r6", id_execution="flux")
    assert reponse["statut"] == "echec_technique"
    assert not (tmp_path / "data" / "raw").exists() or not list((tmp_path / "data" / "raw").rglob("*.csv"))


def test_mention_attribution_dans_extraction(tmp_path, monkeypatch):
    # Réf. T7.5 — la mention d'attribution suit le fichier jusqu'à la visualisation (voie 1)
    monkeypatch.chdir(tmp_path)
    inventaire_avec({
        "r1": {
            "id": "r1", "api_tabulaire": True, "licence": "lov2",
            "licence_conditionnelle": False,
            "organisation": "Insee",
            "derniere_maj": "2026-01-15",
            "url": "https://example.fr/donnees.csv",
        }
    })
    page = _reponse_api([{"theme": "a"}], 1)
    with patch("src.core.extraction.interroger_ressource_api",
               side_effect=[MagicMock(reussi=True, donnees=page)]):
        reponse = extraire_ressource("r1", id_execution="flux", taille_page=10)
    assert reponse["statut"] == "succes"
    donnees = reponse["donnees"]
    assert donnees["licence"] == "lov2"
    assert donnees["licence_conditionnelle"] is False
    mention = donnees["mention_attribution"]
    assert mention is not None
    assert "Insee" in mention
    assert "Licence Ouverte / Open Licence 2.0 (Etalab)" in mention
    assert "2026-01-15" in mention


def test_mention_nulle_pour_licence_a_verifier_extraction(tmp_path, monkeypatch):
    # Réf. T7.5 — other-open : jamais devinée, mention null, extraction réussie
    monkeypatch.chdir(tmp_path)
    inventaire_avec({
        "r1": {
            "id": "r1", "api_tabulaire": True, "licence": "other-open",
            "licence_conditionnelle": False,
            "organisation": "Association X",
            "derniere_maj": None,
            "url": "https://example.fr/donnees.csv",
        }
    })
    page = _reponse_api([{"theme": "a"}], 1)
    with patch("src.core.extraction.interroger_ressource_api",
               side_effect=[MagicMock(reussi=True, donnees=page)]):
        reponse = extraire_ressource("r1", id_execution="flux", taille_page=10)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["mention_attribution"] is None
    assert reponse["message"] != ""
