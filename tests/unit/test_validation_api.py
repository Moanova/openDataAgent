# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_validation_api.py
# Version      : 1
# Date         : 12-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de la validation des reponses API (T2.2).

Couvre TU-34 a TU-38 du plan de tests. Tous sans reseau : les charges
utiles proviennent de fixtures simulant des reponses reelles de
l'API data.gouv.fr (v1).
"""
import json
from pathlib import Path

import pytest

from src.contracts.validation_api import (
    REPERTOIRE_SCHEMAS,
    SCHEMAS_CONNUS,
    ResultatValidation,
    valider_json_brut,
    valider_reponse_api,
)

REPERTOIRE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api"


def charger_fixture(nom: str) -> dict:
    with open(REPERTOIRE_FIXTURES / nom, encoding="utf-8") as flux:
        return json.load(flux)


@pytest.fixture(scope="module")
def fixture_recherche() -> dict:
    return charger_fixture("recherche_jeux_reussite.json")


@pytest.fixture(scope="module")
def fixture_ressources() -> dict:
    return charger_fixture("lister_ressources_reussite.json")


# ---------------------------------------------------------------------------
# TU-34 : reponse reelle de recherche valide
# ---------------------------------------------------------------------------

def test_tu34_reponse_reelle_recherche_valide(fixture_recherche):
    resultat = valider_reponse_api("rechercher_jeux", fixture_recherche)
    assert resultat.valide
    assert resultat.erreurs == []
    assert resultat.statut == "succes"


# ---------------------------------------------------------------------------
# TU-35 : champ obligatoire absent
# ---------------------------------------------------------------------------

def test_tu35_champ_obligatoire_absent(fixture_recherche):
    donnees = json.loads(json.dumps(fixture_recherche))
    del donnees["total"]
    jeu = donnees["data"][0]
    del jeu["id"]

    resultat = valider_reponse_api("rechercher_jeux", donnees)
    assert not resultat.valide
    assert resultat.statut == "echec_technique"
    assert len(resultat.erreurs) == 2
    assert any("total" in e and "required" in e for e in resultat.erreurs)
    assert any("/data/0" in e for e in resultat.erreurs)


# ---------------------------------------------------------------------------
# TU-36 : type inattendu, chemin de l'erreur (JSON pointer)
# ---------------------------------------------------------------------------

def test_tu36_type_inattendu_chemin_erreur(fixture_recherche):
    # T11.3 : en v2, `resources` est une sous-ressource (rel/href/total) ;
    # le type inattendu est testé sur son champ `total`.
    donnees = json.loads(json.dumps(fixture_recherche))
    donnees["data"][0]["resources"]["total"] = "seize"

    resultat = valider_reponse_api("rechercher_jeux", donnees)
    assert not resultat.valide
    assert len(resultat.erreurs) == 1
    assert "/data/0/resources/total" in resultat.erreurs[0]


# ---------------------------------------------------------------------------
# TU-37 : charge utile vide / JSON invalide -> echec propre
# ---------------------------------------------------------------------------

def test_tu37_json_invalide_echec_propre():
    resultat = valider_json_brut("rechercher_jeux", "{pas du json")
    assert isinstance(resultat, ResultatValidation)
    assert not resultat.valide
    assert resultat.statut == "echec_technique"
    assert len(resultat.erreurs) == 1


def test_tu37_racine_non_objet_echec_propre():
    resultat = valider_json_brut("rechercher_jeux", "[1, 2, 3]")
    assert not resultat.valide
    assert resultat.statut == "echec_technique"


def test_tu37_charge_utile_vide():
    resultat = valider_reponse_api("rechercher_jeux", {})
    assert not resultat.valide
    assert resultat.statut == "echec_technique"
    assert any("total" in e for e in resultat.erreurs)


def test_tu37_schema_inconnu_echec_propre():
    resultat = valider_reponse_api("outil_inconnu", {})
    assert not resultat.valide
    assert resultat.statut == "echec_technique"
    assert "outil_inconnu" in resultat.erreurs[0]


# ---------------------------------------------------------------------------
# TU-38 : reponse reelle d'inventaire de ressources valide
# ---------------------------------------------------------------------------

def test_tu38_reponse_reelle_ressources_valide(fixture_ressources):
    resultat = valider_reponse_api("lister_ressources", fixture_ressources)
    assert resultat.valide
    assert resultat.erreurs == []
    assert resultat.statut == "succes"


# ---------------------------------------------------------------------------
# Tests annexes : coherence du repertoire des schemas
# ---------------------------------------------------------------------------

def test_schemas_connus_fichiers_presents():
    # Test annexe : sans référence directe dans tests/plan_tests.md
    for nom_fichier in SCHEMAS_CONNUS.values():
        assert (REPERTOIRE_SCHEMAS / nom_fichier).is_file()


def test_schemas_valides_en_draft_2020_12():
    # Test annexe : sans référence directe dans tests/plan_tests.md
    import jsonschema

    for nom_fichier in SCHEMAS_CONNUS.values():
        with open(REPERTOIRE_SCHEMAS / nom_fichier, encoding="utf-8") as flux:
            schema = json.load(flux)
        jsonschema.Draft202012Validator.check_schema(schema)
