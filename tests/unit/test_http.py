# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_http.py
# Version      : 1
# Date         : 12-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du client HTTP data.gouv.fr (src/utils/http.py, T3.1.1).

Couvre TU-15, TU-17 a TU-20 du plan de tests, sans reseau : la couche
HTTP est simulee avec `responses`.
"""
import json
from pathlib import Path

import pytest
import responses

from src.utils.http import appel_api, rechercher_jeux_api

REPERTOIRE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api"
URL_RECHERCHE = "https://www.data.gouv.fr/api/1/datasets/"


@pytest.fixture
def fixture_recherche() -> dict:
    with open(REPERTOIRE_FIXTURES / "recherche_jeux_reussite.json", encoding="utf-8") as flux:
        return json.load(flux)


@responses.activate
def test_succes_recherche_validee(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-15 (tri et fenetre_maj valides -> traduction correcte vers les paramètres API)
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    resultat = rechercher_jeux_api(["dette", "publique"], tri="vues", fenetre_maj="12_mois", limite=10, page=3)

    assert len(responses.calls) == 1
    requete = responses.calls[0].request
    assert "q=dette+publique" in requete.url
    assert "sort=-views" in requete.url
    assert "last_update_range=12_mois" in requete.url
    assert "page_size=10" in requete.url
    assert "page=3" in requete.url
    assert resultat.reussi
    assert resultat.donnees["total"] == 1


@responses.activate
def test_succes_parametres_defauts_omis(fixture_recherche):
    # Test annexe : sans référence directe dans tests/plan_tests.md
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    resultat = rechercher_jeux_api(["dette"])

    requete = responses.calls[0].request.url
    assert "sort" not in requete
    assert "last_update_range" not in requete
    assert resultat.reussi


@responses.activate
def test_erreur_500_echec_technique():
    # Réf. tests/plan_tests.md : TU-17 (erreur HTTP 500 -> statut echec_technique, pas d'exception)
    responses.add(responses.GET, URL_RECHERCHE, json={"erreur": "interne"}, status=500)

    resultat = rechercher_jeux_api(["dette"])

    assert not resultat.reussi
    assert resultat.statut == "echec_technique"
    assert resultat.status_code == 500


@responses.activate
def test_404_jeu_introuvable():
    # Réf. tests/plan_tests.md : TU-18 (jeu inexistant 404 -> statut jeu_introuvable)
    responses.add(responses.GET, "https://www.data.gouv.fr/api/1/datasets/inconnu/", json={"message": "not found"}, status=404)

    resultat = appel_api("/datasets/inconnu/")

    assert resultat.statut == "jeu_introuvable"
    assert resultat.status_code == 404


@responses.activate
def test_expiration_delai_echec_technique():
    # Réf. tests/plan_tests.md : TU-19 (expiration du délai -> echec_technique après les tentatives configurées)
    from requests.exceptions import ConnectTimeout

    for _ in range(3):
        responses.add(responses.GET, URL_RECHERCHE, body=ConnectTimeout("delai expire"))

    resultat = appel_api("/datasets/", nb_tentatives=3)

    assert not resultat.reussi
    assert resultat.statut == "echec_technique"
    assert len(responses.calls) == 3


@responses.activate
def test_429_puis_succes(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-20 (429 -> nouvelle tentative puis succès)
    responses.add(responses.GET, URL_RECHERCHE, json={}, status=429)
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    resultat = appel_api("/datasets/", params={"q": "dette"})

    assert resultat.reussi
    assert len(responses.calls) == 2


@responses.activate
def test_503_persistant_echec_technique():
    # Réf. tests/plan_tests.md : TU-20 (503 persistant -> echec_technique après les tentatives)
    for _ in range(3):
        responses.add(responses.GET, URL_RECHERCHE, json={}, status=503)

    resultat = appel_api("/datasets/", nb_tentatives=3)

    assert resultat.statut == "echec_technique"
    assert len(responses.calls) == 3


@responses.activate
def test_page_suivante_extraite_de_next_page(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-15 (pagination -> page_suivante extrait de l'URL next_page v1)
    donnees = json.loads(json.dumps(fixture_recherche))
    donnees["next_page"] = "https://www.data.gouv.fr/api/1/datasets/?q=dette&page=2&page_size=10"
    responses.add(responses.GET, URL_RECHERCHE, json=donnees, status=200)

    resultat = rechercher_jeux_api(["dette"])

    assert resultat.donnees["page_suivante"] == 2


@responses.activate
def test_page_suivante_nulle_sans_next_page(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-15 (pagination -> page_suivante null si derniere page)
    donnees = json.loads(json.dumps(fixture_recherche))
    donnees["next_page"] = None
    responses.add(responses.GET, URL_RECHERCHE, json=donnees, status=200)

    resultat = rechercher_jeux_api(["dette"])

    assert resultat.donnees["page_suivante"] is None


@responses.activate
def test_reponse_invalide_contre_schema_echec_propre():
    # Réf. tests/plan_tests.md : TU-37 (charge utile non conforme -> échec propre, sans exception)
    reponse_invalide = {"data": [], "page": 1}
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_invalide, status=200)

    resultat = rechercher_jeux_api(["dette"])

    assert resultat.statut == "echec_technique"
    assert "total" in (resultat.erreur or "")


@pytest.mark.parametrize("tri,sort_attendu", [
    ("recent", "-last_update"),
    ("vues", "-views"),
    ("reutilisations", "-reuses"),
])
@responses.activate
def test_tri_recents_et_reutilisations_traduits(fixture_recherche, tri, sort_attendu):
    # Régression : les clés de TRIS_API étaient accentuées ("récent", "réutilisations")
    # alors que l'enum vaut recent/reutilisations -> KeyError -> echec_technique
    # (constaté en trace agentique du 18/10/2026, 2 invocations perdues).
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)
    resultat = rechercher_jeux_api(["dette"], tri=tri, limite=10, page=1)
    assert resultat.reussi
    assert f"sort={sort_attendu}" in responses.calls[0].request.url
