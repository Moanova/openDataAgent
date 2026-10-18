# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_search.py
# Version      : 1
# Date         : 12-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du flux complet rechercher_jeux (src/core/search.py, T3.1.4).

Sans reseau (`responses`) : couvre le filtre de licence, la consignation
au registre et la reponse normalisee. Reponse HTTP simulee a partir de
la fixture reelle de recherche.
"""
import json
from pathlib import Path

import pytest
import responses

from src.core.search import rechercher_jeux
from src.utils.registry import RegistreSourcesInaccessibles
from src.utils.registre_acceptations import RegistreAcceptationsConditionnelles

REPERTOIRE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api"
URL_RECHERCHE = "https://www.data.gouv.fr/api/1/datasets/"


@pytest.fixture
def fixture_recherche() -> dict:
    with open(REPERTOIRE_FIXTURES / "recherche_jeux_reussite.json", encoding="utf-8") as flux:
        return json.load(flux)


@pytest.fixture
def registre(tmp_path) -> RegistreSourcesInaccessibles:
    return RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")


def _jeu(id_: str, licence_id: str, organisation: str = "Insee", badges: list = None) -> dict:
    return {
        "id": id_,
        "title": f"Jeu {id_}",
        "slug": f"jeu-{id_}",
        "page": f"https://www.data.gouv.fr/datasets/jeu-{id_}",
        "created_at": "2020-07-15T09:21:35.147000+00:00",
        "last_modified": "2026-09-30T16:42:11.000000+00:00",
        "license": licence_id,
        "organization": {"name": organisation, "badges": badges or []},
        "resources": [{"id": "res1", "title": "Fichier CSV", "url": "https://static.data.gouv.fr/res1.csv"}],
    }


def test_mots_cles_vide_erreur_parametres(registre):
    # Réf. tests/plan_tests.md : TU-12 (mots_cles vide -> erreur_parametres, jamais d'appel HTTP)
    reponse = rechercher_jeux([], registre=registre)
    assert reponse["statut"] == "erreur_parametres"
    assert reponse["donnees"] == {}


@responses.activate
def test_limite_hors_bornes_corrigee(fixture_recherche, registre):
    # Réf. tests/plan_tests.md : TU-14 (limite au-delà du maximum -> corrigée, pas d'exception)
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    reponse = rechercher_jeux(["dette"], limite=50, registre=registre)

    assert reponse["statut"] == "succes"
    assert "page_size=10" in responses.calls[0].request.url


@responses.activate
def test_filtre_licence_et_registre(registre):
    # Réf. tests/plan_tests.md : invariant CA-1 (aucun jeu de licence incompatible dans jeux)
    # + TU-21 (exclusion juridique consignée au registre)
    reponse_api = {
        "data": [
            _jeu("ouvert1", "lov2"),
            _jeu("ferme1", "other-closed"),
            _jeu("ferme2", "notspecified"),
            _jeu("ouvert2", "cc-by"),
        ],
        "total": 4,
        "page": 1,
        "next_page": "https://www.data.gouv.fr/api/1/datasets/?q=dette&page=2&page_size=10",
        "previous_page": None,
    }
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_api, status=200)

    reponse = rechercher_jeux(["dette"], registre=registre)

    assert reponse["statut"] == "succes"
    ids = [j["id"] for j in reponse["donnees"]["jeux"]]
    assert ids == ["ouvert1", "ouvert2"]
    assert reponse["donnees"]["exclus_licence"] == 2
    assert reponse["donnees"]["total_trouves"] == 4

    rapports = registre.rapport_pour_agent()["sources_inaccessibles"]
    assert len(rapports) == 2
    motifs = {e["id_jeu"]: e["motif"] for e in rapports}
    assert motifs == {"ferme1": "licence_incompatible", "ferme2": "licence_incompatible"}


@responses.activate
def test_pagination_page_suivante_et_invariant(registre):
    # Réf. tests/plan_tests.md : invariant (un jeu exclu n'est jamais retourné par une pagination ultérieure)
    # + T3.1.5 (page_courante / page_suivante exposés)
    page1 = {
        "data": [_jeu("ferme1", "other-closed"), _jeu("ouvert1", "lov2")],
        "total": 3,
        "page": 1,
        "next_page": "https://www.data.gouv.fr/api/1/datasets/?q=dette&page=2&page_size=2",
        "previous_page": None,
    }
    page2 = {
        "data": [_jeu("ferme2", "notspecified"), _jeu("ouvert3", "fr-lo")],
        "total": 3,
        "page": 2,
        "next_page": None,
        "previous_page": "https://www.data.gouv.fr/api/1/datasets/?q=dette&page=1&page_size=2",
    }
    responses.add(responses.GET, URL_RECHERCHE, json=page1, status=200)
    responses.add(responses.GET, URL_RECHERCHE, json=page2, status=200)

    premiere = rechercher_jeux(["dette"], limite=2, page=1, registre=registre)
    assert premiere["donnees"]["page_courante"] == 1
    assert premiere["donnees"]["page_suivante"] == 2
    assert [j["id"] for j in premiere["donnees"]["jeux"]] == ["ouvert1"]

    seconde = rechercher_jeux(["dette"], limite=2, page=2, registre=registre)
    assert seconde["donnees"]["page_courante"] == 2
    assert seconde["donnees"]["page_suivante"] is None
    assert [j["id"] for j in seconde["donnees"]["jeux"]] == ["ouvert3"]

    tous_les_ids = {j["id"] for r in (premiere, seconde) for j in r["donnees"]["jeux"]}
    assert "ferme1" not in tous_les_ids and "ferme2" not in tous_les_ids
    assert len(registre.rapport_pour_agent()["sources_inaccessibles"]) == 2


@responses.activate
def test_licence_absente_exclue(fixture_recherche, registre):
    # Réf. tests/plan_tests.md : TU-03 via le flux (licence absente -> comportement sûr par défaut)
    donnees = json.loads(json.dumps(fixture_recherche))
    donnees["data"][0]["license"] = None
    responses.add(responses.GET, URL_RECHERCHE, json=donnees, status=200)

    reponse = rechercher_jeux(["dette"], registre=registre)

    assert reponse["donnees"]["jeux"] == []
    assert reponse["donnees"]["exclus_licence"] == 1
    assert registre.rapport_pour_agent()["sources_inaccessibles"][0]["licence"] == "notspecified"


@responses.activate
def test_succes_aucune_exclusion(fixture_recherche, registre):
    # Réf. tests/plan_tests.md : TI-14 (succès -> total_trouves, jeux_retournes, exclus_licence exacts)
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    reponse = rechercher_jeux(["dette", "publique"], tri="vues", limite=10, registre=registre)

    assert reponse["statut"] == "succes"
    assert reponse["message"] == ""
    assert reponse["donnees"]["total_trouves"] == 1
    assert reponse["donnees"]["exclus_licence"] == 0
    assert reponse["donnees"]["jeux"][0]["licence"] == "lov2"
    assert registre.rapport_pour_agent()["sources_inaccessibles"] == []


@responses.activate
def test_echec_http_500_echec_technique(registre):
    # Réf. tests/plan_tests.md : TU-17 (erreur HTTP 500 -> echec_technique, pas d'exception)
    responses.add(responses.GET, URL_RECHERCHE, json={"erreur": "interne"}, status=500)

    reponse = rechercher_jeux(["dette"], registre=registre)

    assert reponse["statut"] == "echec_technique"
    assert reponse["donnees"]["suggestion"] == "réessayer"
    assert registre.rapport_pour_agent()["sources_inaccessibles"] == []


@pytest.fixture
def registre_acceptations(tmp_path):
    return RegistreAcceptationsConditionnelles(chemin=tmp_path / "registre_acceptations.json")


@responses.activate
def test_notspecified_producteur_public_accepte_conditionnel(registre, registre_acceptations):
    # Réf. tests/plan_tests.md : TU-60 (notspecified + badge public-service -> accepté, marqué, consigné)
    reponse_api = {
        "data": [
            _jeu("mairie1", "notspecified", "Ville de Paris",
                 badges=[{"kind": "local-authority"}, {"kind": "certified"}]),
            _jeu("ouvert1", "lov2"),
        ],
        "total": 2,
        "page": 1,
        "next_page": None,
        "previous_page": None,
    }
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_api, status=200)
    reponse = rechercher_jeux(["dette"], registre=registre, registre_acceptations=registre_acceptations)
    assert reponse["statut"] == "succes"
    ids = [j["id"] for j in reponse["donnees"]["jeux"]]
    assert ids == ["mairie1", "ouvert1"]
    marquage = {j["id"]: j["licence_conditionnelle"] for j in reponse["donnees"]["jeux"]}
    assert marquage == {"mairie1": True, "ouvert1": False}
    assert reponse["donnees"]["acceptes_licence_conditionnelle"] == 1
    assert reponse["donnees"]["exclus_licence"] == 0
    acceptations = registre_acceptations.rapport_pour_agent()["acceptations_conditionnelles"]
    assert len(acceptations) == 1
    entree = acceptations[0]
    assert entree["motif"] == "licence_absente_producteur_public"
    assert entree["id_jeu"] == "mairie1"
    assert entree["type_organisation"] == "collectivite_territoriale"
    # le registre des sources inaccessibles n'est pas alimenté
    assert registre.rapport_pour_agent()["sources_inaccessibles"] == []


@responses.activate
def test_notspecified_service_public_accepte(registre, registre_acceptations):
    # Badge public-service -> service_public (TU-60)
    reponse_api = {
        "data": [_jeu("etalab1", "notspecified", "Etalab", badges=[{"kind": "public-service"}])],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_api, status=200)
    reponse = rechercher_jeux(["etalab"], registre=registre, registre_acceptations=registre_acceptations)
    assert reponse["donnees"]["acceptes_licence_conditionnelle"] == 1
    assert reponse["donnees"]["jeux"][0]["licence_conditionnelle"] is True


@responses.activate
def test_notsspecified_sans_badge_exclu(registre, registre_acceptations):
    # Organisation sans badge type -> considérée privée -> exclusion (TU-60, comportement sûr)
    reponse_api = {
        "data": [
            _jeu("prive1", "notspecified", "Entreprise X", badges=[{"kind": "certified"}]),
        ],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_api, status=200)
    reponse = rechercher_jeux(["données"], registre=registre, registre_acceptations=registre_acceptations)
    assert reponse["donnees"]["jeux"] == []
    assert reponse["donnees"]["exclus_licence"] == 1
    assert registre.rapport_pour_agent()["sources_inaccessibles"][0]["motif"] == "licence_incompatible"
    assert registre_acceptations.rapport_pour_agent()["acceptations_conditionnelles"] == []


@responses.activate
def test_licence_incompatible_producteur_public_exclu(registre, registre_acceptations):
    # Invariant : une licence incompatible explicite n'est jamais contournée, même public
    reponse_api = {
        "data": [
            _jeu("ferme1", "other-closed", "Ministère X", badges=[{"kind": "public-service"}]),
        ],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_api, status=200)
    reponse = rechercher_jeux(["dette"], registre=registre, registre_acceptations=registre_acceptations)
    assert reponse["donnees"]["jeux"] == []
    assert registre.rapport_pour_agent()["sources_inaccessibles"][0]["motif"] == "licence_incompatible"


def test_registre_acceptations_persiste_et_antidoublon(tmp_path):
    # Invariant du registre dédié : persistance entre instances, anti-doublon
    from src.utils.registre_acceptations import RegistreAcceptationsConditionnelles
    chemin = tmp_path / "registre_acceptations.json"
    r1 = RegistreAcceptationsConditionnelles(chemin=chemin)
    r1.consigner_acceptation_conditionnelle(
        id_jeu="mairie1", organisation="Ville de Paris",
        type_organisation="collectivite_territoriale",
        licence="notspecified", url="https://example.org",
    )
    r1.sauvegarder()
    r2 = RegistreAcceptationsConditionnelles(chemin=chemin)
    assert r2.id_deja_consigne("mairie1") is True
    assert r2.id_deja_consigne("autre") is False
    assert r2.rapport_pour_agent()["acceptations_conditionnelles"][0]["id_jeu"] == "mairie1"
