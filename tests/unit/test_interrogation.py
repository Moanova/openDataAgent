# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_query.py
# Version      : 1
# Date         : 13-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de l'interrogation tabulaire (src/core/query.py, T3.3.1).

Sans reseau (`responses`), fixture reelle capturee de l'API tabulaire
(films CNC). L'inventaire requis par le contrat est peuple par un appel
simule avec api_tabulaire vrai.
"""
import json
from pathlib import Path

import pytest
import responses

from src.core.interrogation import interroger_ressource
from src.core.resources import lister_ressources

REPERTOIRE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api"
URL_TABULAIRE = "https://tabular-api.data.gouv.fr/api"
RID = "1c5075ec-7ce1-49cb-ab89-94f507812daf"


@pytest.fixture
def fixture_tabulaire() -> dict:
    with open(REPERTOIRE_FIXTURES / "interroger_ressource_reussite.json", encoding="utf-8") as flux:
        return json.load(flux)


def _peupler_inventaire(api_tabulaire: bool = True) -> None:
    """Peuple l'inventaire avec une ressource interrogeable (simulation)."""
    reponse_api = {
        "id": "jeu-cnc",
        "title": "Films sortis en salle",
        "license": "lov2",
        "organization": {"name": "CNC"},
        "resources": [
            {"id": RID, "title": "Films", "url": "https://static.data.gouv.fr/films.csv", "format": "csv", "mime": "text/csv", "filesize": 100}
        ],
    }
    detail = {k: v for k, v in reponse_api.items() if k != "resources"}
    detail["resources"] = {
        "rel": "subsection",
        "href": "https://www.data.gouv.fr/api/2/datasets/jeu-cnc/resources/",
        "total": len(reponse_api["resources"]),
    }
    with responses.mock:
        responses.add(
            responses.GET,
            f"{URL_TABULAIRE}/resources/{RID}/",
            json={"created_at": "2023-01-01", "url": "x", "links": []},
            status=200 if api_tabulaire else 404,
        )
        responses.add(
            responses.GET,
            "https://www.data.gouv.fr/api/2/datasets/jeu-cnc/",
            json=detail,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://www.data.gouv.fr/api/2/datasets/jeu-cnc/resources/",
            json={"data": reponse_api["resources"], "total": 1, "page": 1,
                  "page_size": 50, "next_page": None, "previous_page": None},
            status=200,
        )
        lister_ressources("jeu-cnc")


def test_extraction_paginee(fixture_tabulaire):
    # Réf. tests/plan_tests.md : TI-03 (chaîne inventaire → interrogation : extraction paginée conforme, colonnes détectées)
    _peupler_inventaire(api_tabulaire=True)
    with responses.mock:
        responses.add(
            responses.GET,
            f"{URL_TABULAIRE}/resources/{RID}/data/",
            json=fixture_tabulaire,
            status=200,
        )
        reponse = interroger_ressource(RID, page=1, taille_page=3)

    assert reponse["statut"] == "succes"
    donnees = reponse["donnees"]
    assert donnees["total_lignes"] == 95764
    assert len(donnees["lignes"]) == 3
    assert "Titre" in donnees["colonnes"]
    assert donnees["page"] == 1
    # Volume eleve (95764 > 5000) -> recommandation presente
    assert donnees["recommandation"] == "volume_eleve_telechargement_brut_suggere"


def test_recommandation_absente_sous_seuil():
    # Réf. tests/plan_tests.md : TI-09 (volume sous le seuil -> pas de recommandation)
    _peupler_inventaire(api_tabulaire=True)
    petite_reponse = {
        "data": [{"Titre": "Un film", "Production": "CNC"}],
        "links": None,
        "meta": {"page": 1, "page_size": 20, "total": 74},
    }
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=petite_reponse, status=200)
        reponse = interroger_ressource(RID)

    assert reponse["statut"] == "succes"
    assert "recommandation" not in reponse["donnees"]
    assert reponse["donnees"]["total_lignes"] == 74


def test_recommandation_seuil_configurable(monkeypatch):
    # Réf. tests/plan_tests.md : TI-09 (seuil configurable)
    _peupler_inventaire(api_tabulaire=True)
    reponse_api = {
        "data": [{"a": 1}],
        "meta": {"page": 1, "page_size": 20, "total": 100},
    }
    monkeypatch.setenv("SEUIL_VOLUME_ELEVE", "50")
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=reponse_api, status=200)
        reponse = interroger_ressource(RID)

    assert reponse["donnees"]["recommandation"] == "volume_eleve_telechargement_brut_suggere"


def test_traduction_filtre_et_tri():
    # Réf. tests/plan_tests.md : TU-15 transposé (traduction des arguments vers les paramètres API)
    _peupler_inventaire(api_tabulaire=True)
    reponse_api = {"data": [], "meta": {"page": 1, "page_size": 20, "total": 0}}
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=reponse_api, status=200)
        interroger_ressource(
            RID,
            filtre={"colonne": "Production", "valeur": "20th Century Fox", "operateur": "exact"},
            tri={"colonne": "Date", "ordre": "decroissant"},
        )
        url = responses.calls[0].request.url

    assert "Production__exact=20th+Century+Fox" in url
    assert "Date__sort=desc" in url
    assert "page_size=20" in url


def test_ressource_non_indexee():
    # Réf. tests/plan_tests.md : TI-04 (ressource non indexée → ressource_non_indexee, suggestion bascule telecharger_brut)
    _peupler_inventaire(api_tabulaire=False)
    reponse = interroger_ressource(RID)

    assert reponse["statut"] == "ressource_non_indexee"
    assert reponse["donnees"]["suggestion"] == "basculer sur telecharger_brut"


def test_ressource_jamais_inventoriee():
    # Réf. tests/plan_tests.md : convention transversale n°1 (identifiant jamais délivré -> refusé)
    reponse = interroger_ressource("rid-jamais-vu")

    assert reponse["statut"] == "ressource_introuvable"
    assert reponse["donnees"]["suggestion"] == "reprendre par l'inventaire"


def test_taille_page_hors_bornes():
    # Réf. tests/plan_tests.md : TU-14 transposé (taille_page au-delà du maximum -> corrigée, pas d'exception)
    _peupler_inventaire(api_tabulaire=True)
    reponse_api = {"data": [], "meta": {"page": 1, "page_size": 20, "total": 0}}
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=reponse_api, status=200)
        interroger_ressource(RID, taille_page=500)
        url = responses.calls[0].request.url

    assert "page_size=20" in url


def test_404_api_tabulaire_bascule():
    # Réf. tests/plan_tests.md : TI-04 (404 de l'API tabulaire -> bascule vers telecharger_brut)
    _peupler_inventaire(api_tabulaire=True)
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json={"error": "not found"}, status=404)
        reponse = interroger_ressource(RID)

    assert reponse["statut"] == "ressource_non_indexee"
    assert reponse["donnees"]["suggestion"] == "basculer sur telecharger_brut"


def test_erreur_500_echec_propre():
    # Réf. tests/plan_tests.md : TU-17 transposé (erreur HTTP 500 -> echec_technique, pas d'exception)
    _peupler_inventaire(api_tabulaire=True)
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json={}, status=500)
        reponse = interroger_ressource(RID)

    assert reponse["statut"] == "echec_technique"
    assert reponse["donnees"]["suggestion"] == "réessayer"


def test_colonnes_repli_profile_si_data_vide():
    # Test annexe : data vide -> colonnes via profile/ (repli)
    _peupler_inventaire(api_tabulaire=True)
    vide = {"data": [], "meta": {"page": 5, "page_size": 20, "total": 3}}
    profil = {"profile": {"header": ["Titre", "Réalisation", "Production"]}}
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=vide, status=200)
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/profile/", json=profil, status=200)
        reponse = interroger_ressource(RID, page=5)

    assert reponse["donnees"]["colonnes"] == ["Titre", "Réalisation", "Production"]
    assert reponse["donnees"]["total_lignes"] == 3


def test_page_suivante_extraite_de_links_next():
    # Réf. tests/plan_tests.md : TI-03/T3.3.2 (pagination -> page_suivante extrait de links.next)
    _peupler_inventaire(api_tabulaire=True)
    page1 = {
        "data": [{"Titre": "A"}, {"Titre": "B"}, {"Titre": "C"}],
        "links": {"next": f"{URL_TABULAIRE}/resources/{RID}/data/?page=2&page_size=3", "prev": None},
        "meta": {"page": 1, "page_size": 3, "total": 7},
    }
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=page1, status=200)
        reponse = interroger_ressource(RID, page=1, taille_page=3)

    assert reponse["donnees"]["page"] == 1
    assert reponse["donnees"]["page_suivante"] == 2


def test_page_suivante_nulle_derniere_page():
    # Réf. tests/plan_tests.md : TI-03/T3.3.2 (dernière page -> page_suivante null)
    _peupler_inventaire(api_tabulaire=True)
    derniere = {
        "data": [{"Titre": "G"}],
        "links": {"next": None, "prev": f"{URL_TABULAIRE}/resources/{RID}/data/?page=2&page_size=3"},
        "meta": {"page": 3, "page_size": 3, "total": 7},
    }
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=derniere, status=200)
        reponse = interroger_ressource(RID, page=3, taille_page=3)

    assert reponse["donnees"]["page"] == 3
    assert reponse["donnees"]["page_suivante"] is None


def test_colonne_filtre_inexistante_erreur_actionnable():
    # Réf. tests/plan_tests.md : T3.3.2 (filtre sur colonne inexistante -> échec propre, message API propagé)
    _peupler_inventaire(api_tabulaire=True)
    erreur_api = {
        "errors": [
            {"code": "7310d", "title": "Database error",
             "detail": {"code": "42703", "message": "column fb86.ColonneInexistante does not exist"}}
        ]
    }
    with responses.mock:
        responses.add(responses.GET, f"{URL_TABULAIRE}/resources/{RID}/data/", json=erreur_api, status=500)
        reponse = interroger_ressource(
            RID,
            filtre={"colonne": "ColonneInexistante", "valeur": "x", "operateur": "exact"},
        )

    assert reponse["statut"] == "echec_technique"
    assert "does not exist" in reponse["message"]
