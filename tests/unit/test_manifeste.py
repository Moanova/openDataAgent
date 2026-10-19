# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_manifeste.py
# Version      : 1
# Date         : 19-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests du manifeste d'acquisition (src/core/manifeste.py, T10.8).

Sans réseau : le manifeste est pur système de fichiers. Couvre le
round-trip, l'additivité, l'atomicité, la défense en lecture et
l'anti-doublon.
"""
import json
from pathlib import Path

import pytest

from src.core.manifeste import (
    NOM_MANIFESTE,
    _chemin_manifeste,
    _ecrire,
    consigner_demande,
    enregistrer_acquisition,
    lire_manifeste,
)


@pytest.fixture
def racine(tmp_path) -> Path:
    return tmp_path / "data" / "raw"


def _entree(fichier, **kwargs):
    base = {
        "fichier": fichier,
        "voie": "telechargement",
        "id_ressource": "res-1",
        "id_jeu": "jeu-1",
        "titre_jeu": "Jeu Un",
        "organisation": "Insee",
        "licence": "fr-lo",
    }
    base.update(kwargs)
    return base


def test_round_trip_ecriture_lecture(racine):
    # T10.8 : une acquisition écrite est relue à l'identique.
    enregistrer_acquisition("exec-1", _entree("fichier.csv"), racine=racine)
    manifeste = lire_manifeste("exec-1", racine=racine)
    assert manifeste is not None
    assert manifeste["id_execution"] == "exec-1"
    assert len(manifeste["acquisitions"]) == 1
    assert manifeste["acquisitions"][0]["fichier"] == "fichier.csv"
    assert manifeste["acquisitions"][0]["titre_jeu"] == "Jeu Un"
    assert manifeste["acquisitions"][0]["horodatage"]


def test_additivite_deux_acquisitions(racine):
    # T10.8 : deux acquisitions successives -> deux entrées, aucune altération.
    enregistrer_acquisition("exec-1", _entree("fichier-a.csv"), racine=racine)
    enregistrer_acquisition("exec-1", _entree("fichier-b.csv", voie="extraction", tronque=True), racine=racine)
    manifeste = lire_manifeste("exec-1", racine=racine)
    assert len(manifeste["acquisitions"]) == 2
    voies = {a["fichier"]: a["voie"] for a in manifeste["acquisitions"]}
    assert voies["fichier-a.csv"] == "telechargement"
    assert voies["fichier-b.csv"] == "extraction"


def test_anti_doublon_meme_fichier(racine):
    # T10.8 : un même fichier ne figure pas deux fois.
    enregistrer_acquisition("exec-1", _entree("fichier.csv"), racine=racine)
    enregistrer_acquisition("exec-1", _entree("fichier.csv"), racine=racine)
    manifeste = lire_manifeste("exec-1", racine=racine)
    assert len(manifeste["acquisitions"]) == 1


def test_ecriture_atomique_pas_de_part_residuel(racine):
    # T10.8 : écriture via .part renommé ; aucun résidu.
    enregistrer_acquisition("exec-1", _entree("fichier.csv"), racine=racine)
    repertoire = racine / "exec-1"
    noms = [f.name for f in repertoire.iterdir()]
    assert noms == [NOM_MANIFESTE]
    assert not (repertoire / (NOM_MANIFESTE + ".part")).exists()


def test_lecture_defensive_absent(racine):
    # T10.8 : manifeste absent -> None, pas d'exception.
    assert lire_manifeste("exec-inconnue", racine=racine) is None


def test_lecture_defensive_invalide(racine):
    # T10.8 : JSON invalide -> None + warning, pas d'exception.
    chemin = _chemin_manifeste("exec-1", racine)
    chemin.parent.mkdir(parents=True)
    chemin.write_text("{pas du json", encoding="utf-8")
    assert lire_manifeste("exec-1", racine=racine) is None


def test_consigner_demande_en_tete(racine):
    # T10.8 : la demande utilisateur figure en en-tête du manifeste.
    consigner_demande("exec-1", "résultats des élections présidentielles", racine=racine)
    manifeste = lire_manifeste("exec-1", racine=racine)
    assert manifeste["demande"] == "résultats des élections présidentielles"
    assert manifeste["generé_le"]
    assert manifeste["acquisitions"] == []


def test_consigner_demande_preserve_acquisitions(racine):
    # T10.8 : re-consigner la demande n'écrase pas les acquisitions.
    enregistrer_acquisition("exec-1", _entree("fichier.csv"), racine=racine)
    consigner_demande("exec-1", "demande ultérieure", racine=racine)
    manifeste = lire_manifeste("exec-1", racine=racine)
    assert manifeste["demande"] == "demande ultérieure"
    assert len(manifeste["acquisitions"]) == 1


def test_echec_ecriture_warning_sans_exception(racine):
    # T10.8 : un échec d'écriture ne lève jamais (l'acquisition prime).
    # racine est un fichier (pas un répertoire) -> mkdir échoue -> False.
    chemin_fichier = racine
    chemin_fichier.parent.mkdir(parents=True, exist_ok=True)
    chemin_fichier.write_text("blocage", encoding="utf-8")
    ok = _ecrire(_chemin_manifeste("exec-1", chemin_fichier), {"acquisitions": []})
    assert ok is False


# ---------------------------------------------------------------------------
# T10.8 — Branchement des voies, enrichissement E0, CLI
# ---------------------------------------------------------------------------

import responses
from unittest.mock import patch

from src.core.download import telecharger_brut
from src.core.extraction import extraire_ressource
from src.core.resources import lister_ressources
from src.utils.registry import RegistreSourcesInaccessibles

URL_FICHIER = "https://exemple.org/donnees/budget.csv"
URL_JEU = "https://www.data.gouv.fr/api/2/datasets/jeu-m/"
URL_RESSOURCES = "https://www.data.gouv.fr/api/2/datasets/jeu-m/resources/"


def _mocker_inventaire(id_jeu="jeu-m", titre_jeu="Jeu Manifeste"):
    """Mocke l'inventaire v2 (détail + sous-ressource) avec une ressource indexée."""
    detail = {
        "id": id_jeu,
        "title": titre_jeu,
        "page": f"https://www.data.gouv.fr/datasets/{id_jeu}",
        "license": "fr-lo",
        "organization": {"name": "Insee", "badges": []},
        "last_update": "2026-01-01T00:00:00+00:00",
        "resources": {"rel": "subsection", "href": URL_RESSOURCES, "total": 1},
    }
    ressources = [{"id": "res-m", "title": "Fichier budget", "url": URL_FICHIER,
                   "format": "csv", "mime": "text/csv", "filesize": 10}]
    responses.add(responses.GET, URL_JEU, json=detail, status=200)
    responses.add(
        responses.GET,
        URL_RESSOURCES,
        json={"data": ressources, "total": 1, "page": 1, "page_size": 50,
              "next_page": None, "previous_page": None},
        status=200,
    )
    return detail, ressources


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_telechargement_succedant_ecrit_entree_manifeste(mock_indexee, tmp_path, monkeypatch):
    # T10.8 (E2) : téléchargement réussi -> entrée voie telechargement avec
    # titre_jeu/url_jeu (E0) et mention d'attribution.
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    monkeypatch.chdir(tmp_path)
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    _mocker_inventaire()
    lister_ressources("jeu-m", registre=registre)

    responses.add(responses.GET, URL_FICHIER, body=b"a,b\n1,2\n", status=200)
    reponse = telecharger_brut("res-m", id_execution="exec-t", registre=registre)

    assert reponse["statut"] == "succes"
    manifeste = lire_manifeste("exec-t", racine=tmp_path / "data" / "raw")
    assert manifeste is not None
    entree = manifeste["acquisitions"][0]
    assert entree["voie"] == "telechargement"
    assert entree["fichier"] == "res-m_budget.csv"
    assert entree["titre_jeu"] == "Jeu Manifeste"
    assert entree["url_jeu"].endswith("jeu-m")
    assert entree["organisation"] == "Insee"
    assert entree["licence"] == "fr-lo"


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_telechargement_echoue_aucune_entree(mock_indexee, tmp_path, monkeypatch):
    # T10.8 (E2) : échec du téléchargement -> aucune entrée au manifeste.
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    monkeypatch.chdir(tmp_path)
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    _mocker_inventaire()
    lister_ressources("jeu-m", registre=registre)

    responses.add(responses.GET, URL_FICHIER, body=b"refuse", status=403)
    reponse = telecharger_brut("res-m", id_execution="exec-t", registre=registre)

    assert reponse["statut"] == "echec_technique"
    assert lire_manifeste("exec-t", racine=tmp_path / "data" / "raw") is None


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=True)
def test_extraction_succedante_ecrit_entree_manifeste(mock_indexee, tmp_path, monkeypatch):
    # T10.8 (E2) : extraction réussie -> entrée voie extraction avec
    # tronque et nb_lignes.
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    monkeypatch.chdir(tmp_path)
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    _mocker_inventaire()
    lister_ressources("jeu-m", registre=registre)

    responses.add(
        responses.GET,
        "https://tabular-api.data.gouv.fr/api/resources/res-m/data/",
        json={"data": [{"a": "1"}], "meta": {"page": 1, "page_size": 100, "total": 1},
              "links": {"next": None}},
        status=200,
    )
    reponse = extraire_ressource("res-m", id_execution="exec-t")

    assert reponse["statut"] == "succes"
    manifeste = lire_manifeste("exec-t", racine=tmp_path / "data" / "raw")
    entree = manifeste["acquisitions"][0]
    assert entree["voie"] == "extraction"
    assert entree["titre_jeu"] == "Jeu Manifeste"
    assert entree["tronque"] is False
    assert entree["nb_lignes"] == 1


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=True)
def test_extraction_non_indexee_aucune_entree(mock_indexee, tmp_path, monkeypatch):
    # T10.8 (E2) : garde du contrat (non indexée) -> aucun fichier, aucun manifeste.
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    monkeypatch.chdir(tmp_path)
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    detail, _ = _mocker_inventaire()
    # inventaire peuplé, puis on déclare la ressource non indexée pour l'extraction
    lister_ressources("jeu-m", registre=registre)
    module_resources._inventaire["res-m"]["api_tabulaire"] = False

    reponse = extraire_ressource("res-m", id_execution="exec-t")

    assert reponse["statut"] == "ressource_non_indexee"
    assert lire_manifeste("exec-t", racine=tmp_path / "data" / "raw") is None


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_jeu_courant_porte_titre_et_url(mock_indexee, tmp_path):
    # T10.8 (E0) : _jeu_courant retient titre et URL du jeu ; la ressource
    # normalisée les dénormalise (titre_jeu, url_jeu).
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    _mocker_inventaire(titre_jeu="Titre Étalons")
    lister_ressources("jeu-m", registre=registre)

    ressource = module_resources._inventaire["res-m"]
    assert ressource["titre_jeu"] == "Titre Étalons"
    assert ressource["url_jeu"].endswith("/jeu-m")


def test_lister_acquisitions_via_storage(tmp_path):
    # T10.8 (E4) : lister_acquisitions lit le manifeste (liste vide si absent).
    from src.utils.storage import lister_acquisitions

    assert lister_acquisitions("exec-x", racine=tmp_path / "data" / "raw") == []
    enregistrer_acquisition("exec-x", _entree("f.csv"), racine=tmp_path / "data" / "raw")
    acquisitions = lister_acquisitions("exec-x", racine=tmp_path / "data" / "raw")
    assert len(acquisitions) == 1
    assert acquisitions[0]["fichier"] == "f.csv"


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", side_effect=[True, True])
def test_ti_deux_voies_un_manifeste(mock_indexee, tmp_path, monkeypatch):
    # TI T10.8 : voie 1 (extraction) puis voie 2 (téléchargement) dans la même
    # exécution -> un manifeste unique, deux entrées distinctes et ordonnées.
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    monkeypatch.chdir(tmp_path)
    registre = RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")
    _mocker_inventaire()
    lister_ressources("jeu-m", registre=registre)

    # voie 1 : extraction (ressource indexée : premier ping True)
    responses.add(
        responses.GET,
        "https://tabular-api.data.gouv.fr/api/resources/res-m/data/",
        json={"data": [{"a": "1"}], "meta": {"page": 1, "page_size": 100, "total": 1},
              "links": {"next": None}},
        status=200,
    )
    reponse_ex = extraire_ressource("res-m", id_execution="exec-2v")
    assert reponse_ex["statut"] == "succes"

    # voie 2 : téléchargement brut (ping indexée True retourné par le mock, ignoré ici)
    responses.add(responses.GET, URL_FICHIER, body=b"a,b\n1,2\n", status=200)
    reponse_dl = telecharger_brut("res-m", id_execution="exec-2v", registre=registre)
    assert reponse_dl["statut"] == "succes"

    manifeste = lire_manifeste("exec-2v", racine=tmp_path / "data" / "raw")
    assert manifeste is not None
    acquisitions = manifeste["acquisitions"]
    assert len(acquisitions) == 2
    assert [a["voie"] for a in acquisitions] == ["extraction", "telechargement"]
    assert acquisitions[0]["nb_lignes"] == 1
    assert "tronque" not in acquisitions[1]
    # fichiers distincts : le CSV extrait et le fichier brut coexistent
    assert acquisitions[0]["fichier"] != acquisitions[1]["fichier"]
