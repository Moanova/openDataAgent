# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_licences_descriptif.py
# Version      : 1
# Date         : 15-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du registre descriptif des licences (src/core/licences_descriptif.py, T7.5).

Couvre le registre des propriétés, les prédicats partie 2, l'échec
propre sur licence inconnue/à vérifier et la génération de mention
d'attribution.
"""

import pytest

from src.core.licences_descriptif import (
    PROPRIETES_LICENCES,
    attribution_requise,
    mention_attribution,
    partage_a_l_identique_requis,
    produit_derive_permissif_autorise,
    propriete_licence,
)


@pytest.mark.parametrize("licence", sorted(PROPRIETES_LICENCES))
def test_toute_licence_du_registre_accessible(licence):
    resultat = propriete_licence(licence)
    assert resultat["statut"] == "succes"
    for cle in ("nom", "attribution_requise", "partage_a_l_identique_requis", "usage_commercial_autorise", "a_verifier"):
        assert cle in resultat["donnees"]


@pytest.mark.parametrize("licence", [None, "", "licence-inconnue", "CC-BY-NC"])
def test_licence_inconnue_echec_propre(licence):
    resultat = propriete_licence(licence)
    assert resultat["statut"] == "licence_inconnue"
    assert resultat["donnees"] == {}


@pytest.mark.parametrize("licence", ["other-open", "other-attribution", "other-pd", "notspecified"])
def test_licences_a_verifier_jamais_devinees(licence):
    resultat = propriete_licence(licence)
    assert resultat["statut"] == "succes"
    assert resultat["donnees"]["a_verifier"] is True
    assert resultat["donnees"]["attribution_requise"] is None
    assert resultat["donnees"]["partage_a_l_identique_requis"] is None


def test_predicats_attribution():
    assert attribution_requise("lov2") is True
    assert attribution_requise("cc-by") is True
    assert attribution_requise("cc-zero") is False
    assert attribution_requise("odc-pddl") is False
    assert attribution_requise("other-open") is None
    assert attribution_requise("notspecified") is None
    assert attribution_requise("licence-inconnue") is None


def test_predicats_partage_a_l_identique():
    assert partage_a_l_identique_requis("odc-odbl") is True
    assert partage_a_l_identique_requis("cc-by-sa") is True
    assert partage_a_l_identique_requis("lov2") is False
    assert partage_a_l_identique_requis("other-open") is None


def test_predicat_produit_derive_permissif():
    # Copyleft : produit dérivé permissif interdit
    assert produit_derive_permissif_autorise("odc-odbl") is False
    assert produit_derive_permissif_autorise("cc-by-sa") is False
    # Permissives : autorisé
    assert produit_derive_permissif_autorise("lov2") is True
    assert produit_derive_permissif_autorise("cc-by") is True
    assert produit_derive_permissif_autorise("cc-zero") is True
    # À vérifier / inconnue : jamais deviné
    assert produit_derive_permissif_autorise("other-open") is None
    assert produit_derive_permissif_autorise("notspecified") is None
    assert produit_derive_permissif_autorise("licence-inconnue") is None


def test_mention_attribution_licence_standard():
    resultat = mention_attribution("Insee", "lov2", derniere_maj="2026-01-15")
    assert resultat["statut"] == "succes"
    mention = resultat["donnees"]["mention"]
    assert "Insee" in mention
    assert "Licence Ouverte / Open Licence 2.0 (Etalab)" in mention
    assert "2026-01-15" in mention
    assert resultat["donnees"]["attribution_requise"] is True


def test_mention_attribution_partage_identique():
    resultat = mention_attribution("Ville de Paris", "odc-odbl")
    assert resultat["statut"] == "succes"
    assert "partage a l'identique" in resultat["donnees"]["mention"]


def test_mention_courtoisie_cc_zero():
    # Décision concepteur : mention de courtoisie pour cc-zero / odc-pddl
    resultat = mention_attribution("Etalab", "cc-zero")
    assert resultat["statut"] == "succes"
    mention = resultat["donnees"]["mention"]
    assert "courtoisie" in mention
    assert resultat["donnees"]["attribution_requise"] is False


def test_mention_courtoisie_odc_pddl():
    resultat = mention_attribution("Etalab", "odc-pddl")
    assert resultat["statut"] == "succes"
    assert "courtoisie" in resultat["donnees"]["mention"]


@pytest.mark.parametrize("licence", ["other-open", "other-attribution", "other-pd", "notspecified"])
def test_mention_a_verifier_jamais_devinee(licence):
    resultat = mention_attribution("Organisation", licence)
    assert resultat["statut"] == "licence_a_verifier"
    assert resultat["donnees"]["mention"] is None
    assert "verifier" in resultat["donnees"]["suggestion"]


def test_mention_licence_inconnue():
    resultat = mention_attribution("Organisation", "cc-by-nc")
    assert resultat["statut"] == "licence_inconnue"
    assert resultat["donnees"]["mention"] is None


def test_mention_conditionnelle_avertissement():
    # notspecified accepté par dérogation → statut a_verifier (mention null)
    # Le marquage conditionnel ne change pas ce statut : jamais deviné.
    resultat = mention_attribution("Mairie", "notspecified", licence_conditionnelle=True)
    assert resultat["statut"] == "licence_a_verifier"
    assert resultat["donnees"]["mention"] is None


def test_mention_licence_connue_mais_marquee_conditionnelle():
    # Cas défensif : marquage conditionnel sur une licence connue
    # (ne devrait pas arriver : le filtre ne marque que notspecified).
    resultat = mention_attribution("Mairie", "lov2", licence_conditionnelle=True)
    assert resultat["statut"] == "succes"
    assert "Avertissement" in resultat["donnees"]["mention"]


def test_mention_sans_date_ni_organisation():
    resultat = mention_attribution(None, "cc-by", derniere_maj=None)
    assert resultat["statut"] == "succes"
    assert "source inconnue" in resultat["donnees"]["mention"]


def test_mention_insensible_casse():
    assert mention_attribution("Insee", "LOV2")["statut"] == "succes"
    assert mention_attribution("Insee", "  ODC-ODBL ")["statut"] == "succes"
