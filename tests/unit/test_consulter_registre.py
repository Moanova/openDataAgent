# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_consulter_registre.py
# Version      : 1
# Date         : 22-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de l'outil `consulter_registre` (src/core/registre.py, T11.4).

Refs tests/plan_tests.md : TU-114 a TU-119. Sans reseau : le registre est
un registre temporaire (`tmp_path` de pytest) injecte explicitement.
"""
import json

import src.agent.outils as module_outils
from src.agent.outils import executer_outil
from src.core.registre import DERNIERE_N_DEFAUT, consulter_registre
from src.utils.registry import RegistreSourcesInaccessibles


def _registre_peuple(tmp_path, nb_licence=2, nb_technique=3):
    """Registre temporaire avec des exclusions de licence et des echecs techniques."""
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    for i in range(nb_licence):
        registre.consigner_exclusion_juridique(
            id_jeu=f"jeu-lic-{i}",
            organisation="Org",
            licence="other-closed",
            url=f"https://data.gouv.fr/jeu/jeu-lic-{i}",
        )
    for i in range(nb_technique):
        registre.consigner_echec_technique(
            id_jeu=f"jeu-tech-{i}",
            organisation="Org",
            licence="lov2",
            url=f"https://hote.example/fichier-{i}.csv",
            detail="503 apres tentatives",
            statut_reprise="a_retenter" if i == 0 else "definitif",
        )
    return registre


def test_tu114_registre_absent_rapport_vide(tmp_path):
    # TU-114 : registre absent -> succes, liste vide, total=0 (jamais d'exception).
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    reponse = consulter_registre(registre=registre)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["sources_inaccessibles"] == []
    assert reponse["donnees"]["total"] == 0
    assert reponse["donnees"]["nb_retournees"] == 0


def test_tu115_limite_derniere_n(tmp_path):
    # TU-115 : derniere_n retourne les N entrees les plus recentes ;
    # total reflete la taille reelle du registre, hors limite.
    registre = _registre_peuple(tmp_path, nb_licence=2, nb_technique=3)
    reponse = consulter_registre(derniere_n=2, registre=registre)
    assert reponse["statut"] == "succes"
    entrees = reponse["donnees"]["sources_inaccessibles"]
    assert len(entrees) == 2
    assert reponse["donnees"]["nb_retournees"] == 2
    assert reponse["donnees"]["total"] == 5
    # Les plus recentes : ordre chronologique conserve (les 2 dernieres consignations)
    assert entrees[-1]["id_jeu"] == "jeu-tech-2"
    assert entrees[0]["id_jeu"] == "jeu-tech-1"


def test_tu115b_limite_superieure_au_total(tmp_path):
    # TU-115 (suite) : derniere_n >= total -> toutes les entrees, nb_retournees = total.
    registre = _registre_peuple(tmp_path, nb_licence=2, nb_technique=3)
    reponse = consulter_registre(derniere_n=100, registre=registre)
    assert reponse["donnees"]["nb_retournees"] == 5
    assert reponse["donnees"]["total"] == 5


def test_tu116_filtre_motif(tmp_path):
    # TU-116 : filtre motif -> seules les entrees correspondantes ; total hors filtre.
    registre = _registre_peuple(tmp_path, nb_licence=2, nb_technique=3)
    reponse = consulter_registre(motif="licence_incompatible", registre=registre)
    entrees = reponse["donnees"]["sources_inaccessibles"]
    assert reponse["statut"] == "succes"
    assert {e["motif"] for e in entrees} == {"licence_incompatible"}
    assert len(entrees) == 2
    assert reponse["donnees"]["total"] == 5


def test_tu117_filtre_et_limite_combines(tmp_path):
    # TU-117 : filtre puis limite (les N plus recentes parmi le motif filtre).
    registre = _registre_peuple(tmp_path, nb_licence=2, nb_technique=3)
    reponse = consulter_registre(derniere_n=2, motif="serveur_origine_bloque", registre=registre)
    entrees = reponse["donnees"]["sources_inaccessibles"]
    assert {e["motif"] for e in entrees} == {"serveur_origine_bloque"}
    assert len(entrees) == 2
    assert entrees[0]["id_jeu"] == "jeu-tech-1"
    assert entrees[1]["id_jeu"] == "jeu-tech-2"
    assert reponse["donnees"]["total"] == 5


def test_tu118_statut_reprise_expose(tmp_path):
    # TU-118 : statut_reprise expose (a_retenter / definitif) ; entree sans
    # champ (exclusion de licence) -> defaut definitif (comportement TU-93).
    registre = _registre_peuple(tmp_path, nb_licence=1, nb_technique=2)
    reponse = consulter_registre(derniere_n=3, registre=registre)
    entrees = reponse["donnees"]["sources_inaccessibles"]
    statuts = {e["id_jeu"]: e["statut_reprise"] for e in entrees}
    assert statuts["jeu-tech-0"] == "a_retenter"
    assert statuts["jeu-tech-1"] == "definitif"
    assert statuts["jeu-lic-0"] == "definitif"  # exclusion juridique : pas de champ -> defaut


def test_tu119_dispatch_agent_lecture_seule(tmp_path, monkeypatch):
    # TU-119 : dispatch agent — validation Pydantic (champs inconnus ignores),
    # id_execution injecte, registre inchange apres l'appel (lecture seule).
    registre = _registre_peuple(tmp_path, nb_licence=1, nb_technique=1)
    registre.sauvegarder()
    avant = json.loads((tmp_path / "registry.json").read_text(encoding="utf-8"))
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "consulter_registre",
                        lambda **kwargs: consulter_registre(registre=registre, **kwargs))

    reponse = executer_outil(
        "consulter_registre",
        {"derniere_n": 1, "champ_inconnu": "ignore", "motif": "licence_incompatible"},
        "id_test",
    )
    assert reponse["statut"] == "succes"
    entrees = reponse["donnees"]["sources_inaccessibles"]
    assert len(entrees) == 1
    assert entrees[0]["motif"] == "licence_incompatible"
    # Lecture seule : le fichier registre est byte-identique
    apres = json.loads((tmp_path / "registry.json").read_text(encoding="utf-8"))
    assert apres == avant


def test_tu119b_parametres_invalides(tmp_path):
    # TU-119 (suite) : derniere_n < 1 ou motif inconnu -> erreur_parametres.
    registre = _registre_peuple(tmp_path)
    assert consulter_registre(derniere_n=0, registre=registre)["statut"] == "erreur_parametres"
    assert consulter_registre(motif="motif_inconnu", registre=registre)["statut"] == "erreur_parametres"


def test_derniere_n_defaut(tmp_path):
    # Test annexe : la constante de defaut vaut 20 et s'applique sans argument.
    assert DERNIERE_N_DEFAUT == 20
    registre = _registre_peuple(tmp_path, nb_licence=10, nb_technique=15)
    reponse = consulter_registre(registre=registre)
    assert reponse["donnees"]["nb_retournees"] == 20
    assert reponse["donnees"]["total"] == 25
