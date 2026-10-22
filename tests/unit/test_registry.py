# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_registry.py
# Version      : 1
# Date         : 12-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du registre des sources inaccessibles (src/utils/registry.py, T3.1.3).

Couvre TU-21 a TU-24 du plan de tests, avec un registre temporaire
(`tmp_path` de pytest) pour ne pas toucher au disque de production.
"""
import json

from src.utils.registry import RegistreSourcesInaccessibles


def test_consignation_exclusion_juridique(tmp_path):
    # Réf. tests/plan_tests.md : TU-21 (entrée complète : horodatage, motif, id_jeu, organisation, licence, url, detail)
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    entree = registre.consigner_exclusion_juridique(
        id_jeu="abc123",
        organisation="Ministere X",
        licence="other-closed",
        url="https://data.gouv.fr/jeu/abc123",
        detail="Licence non ouverte",
    )
    assert entree["motif"] == "licence_incompatible"
    assert entree["id_jeu"] == "abc123"
    assert entree["organisation"] == "Ministere X"
    assert entree["licence"] == "other-closed"
    assert entree["url"] == "https://data.gouv.fr/jeu/abc123"
    assert entree["detail"] == "Licence non ouverte"
    assert entree["timestamp"]


def test_sauvegarde_puis_rechargement(tmp_path):
    # Réf. tests/plan_tests.md : TU-22 (sauvegarde puis rechargement -> contenu préservé, JSON valide)
    chemin = tmp_path / "registry.json"
    registre = RegistreSourcesInaccessibles(chemin=chemin)
    registre.consigner_exclusion_juridique(
        id_jeu="abc123",
        organisation="Ministere X",
        licence="other-closed",
        url="https://data.gouv.fr/jeu/abc123",
    )
    registre.sauvegarder()

    relu = RegistreSourcesInaccessibles(chemin=chemin)
    contenu = relu.rapport_pour_agent()
    assert len(contenu["sources_inaccessibles"]) == 1
    assert contenu["sources_inaccessibles"][0]["id_jeu"] == "abc123"

    with open(chemin, encoding="utf-8") as flux:
        json.load(flux)


def test_rapport_pour_agent_copie(tmp_path):
    # Réf. tests/plan_tests.md : TU-23 (rapport_pour_agent -> copie ; modifier la copie n'altère pas le registre)
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    registre.consigner_exclusion_juridique(
        id_jeu="abc123",
        organisation="Org",
        licence="notspecified",
        url="https://data.gouv.fr/jeu/abc123",
    )
    rapport = registre.rapport_pour_agent()
    rapport["sources_inaccessibles"].clear()

    assert len(registre.rapport_pour_agent()["sources_inaccessibles"]) == 1


def test_registre_preexistant_non_ecrase(tmp_path):
    # Réf. tests/plan_tests.md : TU-24 (registre préexistant -> entrées antérieures chargées et non écrasées)
    chemin = tmp_path / "registry.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    anterieur = {
        "sources_inaccessibles": [
            {
                "timestamp": "2026-10-10T14:30:22+00:00",
                "motif": "licence_incompatible",
                "id_jeu": "vieux",
                "organisation": "Org",
                "licence": "other-closed",
                "url": "https://data.gouv.fr/jeu/vieux",
                "detail": "Licence non ouverte",
            }
        ]
    }
    chemin.write_text(json.dumps(anterieur), encoding="utf-8")

    registre = RegistreSourcesInaccessibles(chemin=chemin)
    registre.consigner_exclusion_juridique(
        id_jeu="nouveau",
        organisation="Org2",
        licence="notspecified",
        url="https://data.gouv.fr/jeu/nouveau",
    )
    registre.sauvegarder()

    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    ids = [e["id_jeu"] for e in contenu["sources_inaccessibles"]]
    assert ids == ["vieux", "nouveau"]


def test_fichier_invalide_registre_vide(tmp_path):
    # Test annexe : sans référence directe dans tests/plan_tests.md
    chemin = tmp_path / "registry.json"
    chemin.write_text("{pas du json", encoding="utf-8")

    registre = RegistreSourcesInaccessibles(chemin=chemin)
    assert registre.rapport_pour_agent()["sources_inaccessibles"] == []


# ---------------------------------------------------------------------------
# T7.1 (E5) — statut_reprise : TU-91..TU-93
# ---------------------------------------------------------------------------

from src.utils.registry import REPRISE_A_RETENTER, REPRISE_DEFINITIF


def test_tu91_echec_transitoire_marque_a_retenter(tmp_path):
    # TU-91 : échec transitoire épuisé -> registre consigné statut_reprise=a_retenter
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    entree = registre.consigner_echec_technique(
        id_jeu="jeu-1",
        organisation="Org",
        licence="lov2",
        url="https://exemple.fr/fichier.csv",
        detail="Statut HTTP 503",
        statut_reprise=REPRISE_A_RETENTER,
    )
    assert entree["statut_reprise"] == "a_retenter"
    assert entree["motif"] == "serveur_origine_bloque"


def test_tu92_echec_definitif_marque_definitif(tmp_path):
    # TU-92 : échec définitif (403) -> registre consigné statut_reprise=definitif
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    entree = registre.consigner_echec_technique(
        id_jeu="jeu-1",
        organisation="Org",
        licence="lov2",
        url="https://exemple.fr/fichier.csv",
        detail="Statut HTTP 403",
        statut_reprise=REPRISE_DEFINITIF,
    )
    assert entree["statut_reprise"] == "definitif"


def test_tu93_lecture_entree_sans_statut_reprise_defaut_definitif(tmp_path):
    # TU-93 : rétrocompatibilité — entrée sans statut_reprise lue comme definitif
    chemin = tmp_path / "registry.json"
    anterieur = {
        "sources_inaccessibles": [
            {
                "timestamp": "2026-10-10T14:30:22+00:00",
                "motif": "serveur_origine_bloque",
                "id_jeu": "vieux",
                "organisation": "Org",
                "licence": "lov2",
                "url": "https://exemple.fr/vieux.csv",
                "detail": "Statut HTTP 503",
            },
            {
                "timestamp": "2026-10-11T14:30:22+00:00",
                "motif": "licence_incompatible",
                "id_jeu": "vieux2",
                "organisation": "Org",
                "licence": "other-closed",
                "url": "https://exemple.fr/vieux2",
                "detail": "Licence non ouverte",
            },
        ]
    }
    chemin.write_text(json.dumps(anterieur), encoding="utf-8")

    registre = RegistreSourcesInaccessibles(chemin=chemin)
    rapport = registre.rapport_pour_agent()["sources_inaccessibles"]

    assert len(rapport) == 2
    # Entrée technique sans champ -> défaut definitif
    assert rapport[0]["statut_reprise"] == "definitif"
    # Exclusion de licence sans champ -> défaut definitif aussi
    assert rapport[1]["statut_reprise"] == "definitif"

    # Le disque n'est pas réécrit (pas de sauvegarde implicite)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert "statut_reprise" not in contenu["sources_inaccessibles"][0]
