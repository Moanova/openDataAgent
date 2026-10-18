# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_licence.py
# Version      : 2
# Date         : 15-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du filtre de licence (src/core/licence.py, T3.1.2 + T7.5-A).

Couvre TU-01 a TU-04 du plan de tests ainsi que l'evolution T7.5
chantier A : elargissement du referentiel, parametrage JSON et
licences conditionnelles selon le type d'organisation.
"""

import json

import pytest

from src.core import licence as module_licence
from src.core.licence import (
    charger_politique,
    licence_est_acceptable,
    reinitialiser_politique,
)


@pytest.fixture(autouse=True)
def _politique_fraiche():
    reinitialiser_politique()
    yield
    reinitialiser_politique()


@pytest.mark.parametrize("licence", [
    "lov2",
    "fr-lo",
    "odc-odbl",
    "odc-by",
    "odc-pddl",
    "cc-by",
    "cc-by-sa",
    "cc-zero",
    "other-open",
    "other-attribution",
    "other-pd",
])
def test_licences_acceptees(licence):
    # Ref. tests/plan_tests.md : TU-01 (licences acceptees -> Vrai pour chacune)
    assert licence_est_acceptable(licence) is True


@pytest.mark.parametrize("licence", [
    "other-closed",
    "commercial",
])
def test_licences_exclues(licence):
    # Ref. tests/plan_tests.md : TU-02 (licences exclues -> Faux pour chacune)
    assert licence_est_acceptable(licence) is False


def test_licence_absente_nulle_vide():
    # Ref. tests/plan_tests.md : TU-03 (licence absente, nulle, chaine vide -> Faux)
    assert licence_est_acceptable(None) is False
    assert licence_est_acceptable("") is False


@pytest.mark.parametrize("licence,attendu", [
    ("LOV2", True),
    ("  FR-LO  ", True),
    (" CC-ZERO ", True),
    ("  CC-BY  ", True),
    (" Other-Open ", True),
    ("  ODC-BY  ", True),
    ("  NotSpecified  ", False),
    ("OTHER-CLOSED", False),
])
def test_casse_et_espaces_parasites(licence, attendu):
    # Ref. tests/plan_tests.md : TU-04 (casse et espaces parasites)
    assert licence_est_acceptable(licence) is attendu


def test_notspecified_refuse_sans_type_organisation():
    # Ref. tests/plan_tests.md : TU-41 (licence conditionnelle sans type -> Faux)
    assert licence_est_acceptable("notspecified") is False


@pytest.mark.parametrize("type_organisation", [
    "service_public",
    "collectivite_territoriale",
])
def test_notspecified_accepte_organisation_publique(type_organisation):
    # Ref. tests/plan_tests.md : TU-41 (notspecified + organisation publique -> Vrai)
    assert licence_est_acceptable("notspecified", type_organisation) is True


def test_notspecified_refuse_organisation_privee():
    # Ref. tests/plan_tests.md : TU-41 (notspecified + entreprise/association -> Faux)
    assert licence_est_acceptable("notspecified", "entreprise") is False
    assert licence_est_acceptable("notspecified", "association") is False


def test_notspecified_refuse_type_inconnu():
    # Ref. tests/plan_tests.md : TU-41 (type d'organisation inconnu -> Faux)
    assert licence_est_acceptable("notspecified", "societe_secrete") is False


def test_licence_incompatible_refusee_meme_publique():
    # Invariant : une licence declaree incompatible n'est jamais contournee,
    # meme pour un etablissement public.
    assert licence_est_acceptable("other-closed", "service_public") is False
    assert licence_est_acceptable("commercial", "collectivite_territoriale") is False


def test_licence_acceptee_independante_du_type():
    # Une licence acceptee l'est quel que soit le type d'organisation.
    assert licence_est_acceptable("lov2", "entreprise") is True


def test_type_organisation_insensible_casse():
    assert licence_est_acceptable("notspecified", "  Service_Public  ") is True


def test_charger_politique_fichier_valide(tmp_path):
    # Ref. tests/plan_tests.md : TU-40 (parametrage JSON)
    chemin = tmp_path / "politique.json"
    chemin.write_text(json.dumps({
        "data.gouv.fr": {
            "licences_acceptees": ["lov2", "cc-by"],
            "licences_conditionnelles": {"notspecified": ["service_public"]},
        }
    }), encoding="utf-8")
    politique = charger_politique(chemin)
    assert politique["licences_acceptees"] == frozenset({"lov2", "cc-by"})
    assert politique["licences_conditionnelles"]["notspecified"] == frozenset({"service_public"})
    assert licence_est_acceptable("odc-odbl", politique=politique) is False
    assert licence_est_acceptable("lov2", politique=politique) is True


def test_charger_politique_fichier_absent(tmp_path):
    # Comportement sur : fichier absent -> politique par defaut integree.
    politique = charger_politique(tmp_path / "inexistant.json")
    assert politique["licences_acceptees"] == module_licence.LICENCES_ACCEPTES_DEFAUT


def test_charger_politique_fichier_invalide(tmp_path):
    # Comportement sur : JSON invalide -> politique par defaut, sans exception.
    chemin = tmp_path / "politique.json"
    chemin.write_text("{invalide", encoding="utf-8")
    politique = charger_politique(chemin)
    assert politique["licences_acceptees"] == module_licence.LICENCES_ACCEPTES_DEFAUT


def test_charger_politique_source_absente(tmp_path):
    # Comportement sur : cle de source absente -> politique par defaut.
    chemin = tmp_path / "politique.json"
    chemin.write_text(json.dumps({"eurostat": {"licences_acceptees": ["cc-by"]}}), encoding="utf-8")
    politique = charger_politique(chemin)
    assert politique["licences_acceptees"] == module_licence.LICENCES_ACCEPTES_DEFAUT


def test_charger_politique_mal_formee(tmp_path):
    # Comportement sur : champs mal types -> politique par defaut.
    chemin = tmp_path / "politique.json"
    chemin.write_text(json.dumps({
        "data.gouv.fr": {"licences_acceptees": "lov2"}
    }), encoding="utf-8")
    politique = charger_politique(chemin)
    assert politique["licences_acceptees"] == module_licence.LICENCES_ACCEPTES_DEFAUT


def test_politique_config_par_defaut_coherente():
    # La politique embarquee (fichier absent) couvre le referentiel elargi.
    politique = module_licence._politique_defaut()
    for code in ("odc-by", "odc-pddl", "other-attribution", "other-pd"):
        assert code in politique["licences_acceptees"]
    assert "notspecified" in politique["licences_conditionnelles"]
