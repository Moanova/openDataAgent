# -*- coding: utf-8 -*-
"""Tests du réalignement linguistique des modules internes (T13.4) — TU-135..TU-138.

Vérifie que les 6 modules renommés sont importables sous leur nouveau nom,
que les anciens noms ne le sont plus, que le chemin par défaut du registre
est `data/registre_sources.json`, et que les noms de loggers sont réalignés.
"""
import importlib
import logging
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# TU-135 — Les 6 modules renommés sont importables sous leur nouveau nom
# ---------------------------------------------------------------------------

MODULES_RENOMMES = [
    "src.core.recherche",
    "src.core.telechargement",
    "src.core.interrogation",
    "src.utils.journalisation",
    "src.utils.registre_sources",
    "src.utils.stockage",
]

MODULES_ANCIENS = [
    "src.core.search",
    "src.core.download",
    "src.core.query",
    "src.utils.logging",
    "src.utils.registry",
    "src.utils.storage",
]


@pytest.mark.parametrize("module", MODULES_RENOMMES)
def test_tu135_module_renomme_importable(module):
    # TU-135 : chaque module renommé s'importe sous son nouveau nom.
    importlib.import_module(module)


@pytest.mark.parametrize("module", MODULES_ANCIENS)
def test_tu135b_ancien_module_plus_importable(module):
    # TU-135 (suite) : les anciens noms de modules ne sont plus importables.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


# ---------------------------------------------------------------------------
# TU-136 — Chemin par défaut du registre : data/registre_sources.json
# ---------------------------------------------------------------------------

def test_tu136_chemin_registre_par_defaut():
    # TU-136 : le registre des sources inaccessibles pointe par défaut sur
    # data/registre_sources.json (renommé de data/registry.json, T13.4).
    from src.utils.registre_sources import RegistreSourcesInaccessibles

    registre = RegistreSourcesInaccessibles()
    assert registre.chemin == Path("data") / "registre_sources.json"


# ---------------------------------------------------------------------------
# TU-137 — Noms de loggers réalignés
# ---------------------------------------------------------------------------

def test_tu137_loggers_realignes():
    # TU-137 : les loggers des modules renommés portent le nouveau nom.
    from src.utils.journalisation import get_logger

    attendus = {
        "openDataAgent.core.recherche",
        "openDataAgent.core.telechargement",
        "openDataAgent.core.interrogation",
        "openDataAgent.utils.registre_sources",
    }
    for nom in attendus:
        logger = get_logger(nom)
        stdlib = logging.getLogger(nom)
        assert stdlib.name == nom
        assert logger is not None


def test_tu137b_anciens_loggers_absents_du_code():
    # TU-137 (suite) : aucun fichier source ne référence les anciens loggers.
    import subprocess

    resultat = subprocess.run(
        [
            "grep", "-rn",
            "openDataAgent.core.search\\|openDataAgent.core.download\\|"
            "openDataAgent.core.query\\|openDataAgent.utils.registry\\|"
            "openDataAgent.utils.logging\\|openDataAgent.utils.storage",
            "src/", "--include=*.py",
        ],
        capture_output=True,
        text=True,
    )
    residus = [
        ligne for ligne in resultat.stdout.splitlines()
        if "__pycache__" not in ligne
        and "recherche" not in ligne and "telechargement" not in ligne
        and "interrogation" not in ligne and "registre_sources" not in ligne
        and "journalisation" not in ligne and "stockage" not in ligne
    ]
    assert residus == [], f"Résidus d'anciens loggers : {residus}"


# ---------------------------------------------------------------------------
# TU-138 — Les fichiers de tests renommés existent sous leur nouveau nom
# ---------------------------------------------------------------------------

def test_tu138_fichiers_tests_renommes():
    # TU-138 : les 5 fichiers de tests renommés existent, les anciens non.
    racine_tests = Path(__file__).parent
    nouveaux = [
        "test_recherche.py",
        "test_telechargement.py",
        "test_interrogation.py",
        "test_journalisation.py",
        "test_registre_sources.py",
    ]
    anciens = [
        "test_search.py",
        "test_download.py",
        "test_query.py",
        "test_logging.py",
        "test_registry.py",
    ]
    for nom in nouveaux:
        assert (racine_tests / nom).is_file(), f"Fichier renommé absent : {nom}"
    for nom in anciens:
        assert not (racine_tests / nom).exists(), f"Ancien fichier encore présent : {nom}"
