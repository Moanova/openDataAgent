# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_resources.py
# Version      : 1
# Date         : 13-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de l'inventaire des ressources (src/core/resources.py, T3.2.1).

Sans reseau (`responses`), reponses simulees a partir de la fixture reelle.
"""
import json
from pathlib import Path

import pytest
import responses

from unittest.mock import patch

from src.core.resources import inventaire, lister_ressources
from src.utils.registry import RegistreSourcesInaccessibles

REPERTOIRE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api"
URL_JEU = "https://www.data.gouv.fr/api/2/datasets/67660551c8588734a16a6a60/"


def _split_fixture_v2(fixture):
    """Scinde la fixture v2 reconstituée : detail (resources en subsection) + liste plate."""
    detail = {k: v for k, v in fixture.items() if k != "resources"}
    detail["resources"] = {
        "rel": "subsection",
        "href": "https://www.data.gouv.fr/api/2/datasets/%s/resources/" % fixture["id"],
        "total": len(fixture["resources"]),
    }
    return detail, fixture["resources"]


def _mocker_jeu_v2(id_jeu, detail, ressources):
    """Ajoute les deux réponses v2 : détail du jeu + sous-ressource paginée."""
    import responses as _responses
    base = "https://www.data.gouv.fr/api/2/datasets/"
    _responses.add(_responses.GET, base + id_jeu + "/", json=detail, status=200)
    _responses.add(
        _responses.GET,
        base + id_jeu + "/resources/",
        json={"data": ressources, "total": len(ressources), "page": 1,
              "page_size": 50, "next_page": None, "previous_page": None},
        status=200,
    )



@pytest.fixture
def fixture_ressources() -> dict:
    with open(REPERTOIRE_FIXTURES / "lister_ressources_reussite.json", encoding="utf-8") as flux:
        return json.load(flux)


@pytest.fixture
def registre(tmp_path) -> RegistreSourcesInaccessibles:
    return RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_inventaire_complet(mock_indexee, fixture_ressources, registre):
    # Réf. tests/plan_tests.md : TI-01 (chaîne recherche → inventaire → inventaire complet, métadonnées enregistrées)
    _mocker_jeu_v2("67660551c8588734a16a6a60", *_split_fixture_v2(fixture_ressources))

    reponse = lister_ressources("67660551c8588734a16a6a60", registre=registre)

    assert reponse["statut"] == "succes"
    ressources = reponse["donnees"]["ressources"]
    assert len(ressources) == len(fixture_ressources["resources"])
    premiere = ressources[0]
    assert premiere["id"] == fixture_ressources["resources"][0]["id"]
    assert premiere["titre"] == fixture_ressources["resources"][0]["title"]
    assert premiere["url"] == fixture_ressources["resources"][0]["url"]
    assert premiere["taille_octets"] == fixture_ressources["resources"][0]["filesize"]
    # Classification T3.2.2 : la fixture (format csv, mime text/csv) est tabulaire
    assert premiere["classe"] == "fichier_tabulaire"
    assert premiere["api_tabulaire"] is False
    # Metadonnees enregistrees dans l'inventaire (invariant du contrat)
    assert premiere["id"] in inventaire()


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_hebergement_plateforme_depuis_filetype(mock_indexee, fixture_ressources, registre):
    # Test annexe : sans référence directe dans tests/plan_tests.md
    donnees = json.loads(json.dumps(fixture_ressources))
    donnees["resources"][0]["filetype"] = "file"
    donnees["resources"][1]["filetype"] = "remote" if len(donnees["resources"]) > 1 else None
    _mocker_jeu_v2("67660551c8588734a16a6a60", *_split_fixture_v2(donnees))

    reponse = lister_ressources("67660551c8588734a16a6a60", registre=registre)

    ressources = reponse["donnees"]["ressources"]
    assert ressources[0]["heberge_sur_plateforme"] is True
    if len(ressources) > 1:
        assert ressources[1]["heberge_sur_plateforme"] is False


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_indetermination_vide_apres_classification(mock_indexee, fixture_ressources, registre):
    # Réf. tests/plan_tests.md : TU-05/TU-07 via le flux (ressources classées -> indetermination vide)
    # Fixture v2 (T11.3) : seules les ressources classables sont retenues ; la ressource
    # `txt` de la capture réelle est inclassable et alimente l'indétermination (comportement
    # conforme au contrat, couvert par test_ressource_inclassable_dans_indetermination).
    detail, ressources = _split_fixture_v2(fixture_ressources)
    detail["resources"]["total"] = 2
    _mocker_jeu_v2("67660551c8588734a16a6a60", detail, [r for r in ressources if r.get("format") != "txt"])

    reponse = lister_ressources("67660551c8588734a16a6a60", registre=registre)

    assert reponse["donnees"]["indetermination"] == []
    classes = {r["classe"] for r in reponse["donnees"]["ressources"]}
    assert "indetermine" not in classes


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_ressource_inclassable_dans_indetermination(mock_indexee, registre):
    # Réf. tests/plan_tests.md : TU-10 (ressource inclassable -> remontée dans indetermination)
    reponse_api = {
        "id": "jeu-x",
        "title": "Jeu X",
        "resources": [
            {
                "id": "res-inconnue",
                "title": "Fichier mystere",
                "url": "https://exemple.fr/donnees",
                "format": "docx",
                "mime": None,
                "filesize": 100,
            }
        ],
    }
    _mocker_jeu_v2("jeu-x", *_split_fixture_v2(reponse_api))

    reponse = lister_ressources("jeu-x", registre=registre)

    ressources = reponse["donnees"]["ressources"]
    assert ressources[0]["classe"] == "indetermine"
    assert reponse["donnees"]["indetermination"] == ["res-inconnue"]


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_coherence_inclusion_exclusion_indetermination(mock_indexee, registre):
    # Réf. tests/plan_tests.md : TU-10/TU-11 (invariants de cohérence de la réponse)
    reponse_api = {
        "id": "jeu-mixte",
        "title": "Jeu mixte",
        "resources": [
            {"id": "res-csv", "title": "Donnees CSV", "url": "https://exemple.fr/d.csv", "format": "csv", "mime": "text/csv", "filesize": 10},
            {"id": "res-mystere", "title": "Fichier mystere", "url": "https://exemple.fr/donnees", "format": "docx", "mime": None, "filesize": 20},
            {"id": "res-zip", "title": "Archive", "url": "https://exemple.fr/a.zip", "format": "zip", "mime": None, "filesize": 30},
            {"id": "res-nu", "title": "Fichier sans metadonnees", "url": "https://exemple.fr/f", "format": None, "mime": None, "filesize": None},
        ],
    }
    _mocker_jeu_v2("jeu-mixte", *_split_fixture_v2(reponse_api))

    reponse = lister_ressources("jeu-mixte", registre=registre)
    donnees = reponse["donnees"]
    par_id = {r["id"]: r for r in donnees["ressources"]}

    # Inclusion : tout id de indetermination est dans ressources, classe indetermine
    for id_ in donnees["indetermination"]:
        assert id_ in par_id
        assert par_id[id_]["classe"] == "indetermine"

    # Exclusion : toute ressource classee est absente de indetermination
    for id_, res in par_id.items():
        if res["classe"] != "indetermine":
            assert id_ not in donnees["indetermination"]

    assert donnees["indetermination"] == ["res-mystere", "res-nu"]


@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_indetermination_autoportante_pour_agent(mock_indexee, registre):
    # Réf. tests/plan_tests.md : TU-11 (l'agent A3 dispose du titre et de l'URL sans appel d'outil supplémentaire)
    reponse_api = {
        "id": "jeu-a3",
        "title": "Jeu A3",
        "resources": [
            {"id": "res-a", "title": "Ressource A", "url": "https://exemple.fr/a", "format": "bin", "mime": None, "filesize": 1},
        ],
    }
    _mocker_jeu_v2("jeu-a3", *_split_fixture_v2(reponse_api))

    reponse = lister_ressources("jeu-a3", registre=registre)
    donnees = reponse["donnees"]
    par_id = {r["id"]: r for r in donnees["ressources"]}

    for id_ in donnees["indetermination"]:
        assert par_id[id_]["titre"]
        assert par_id[id_]["url"]


@responses.activate
def test_jeu_introuvable_404(registre):
    # Réf. tests/plan_tests.md : TI-02 (identifiant jamais délivré → jeu_introuvable, aucune écriture au registre)
    responses.add(responses.GET, URL_JEU, json={"message": "not found"}, status=404)

    reponse = lister_ressources("67660551c8588734a16a6a60", registre=registre)

    assert reponse["statut"] == "jeu_introuvable"
    assert reponse["donnees"]["suggestion"] == "reprendre à rechercher_jeux"
    assert registre.rapport_pour_agent()["sources_inaccessibles"] == []


def test_id_jeu_vide(registre):
    # Réf. tests/plan_tests.md : TU-12 (paramètre obligatoire vide → erreur_parametres, jamais d'appel HTTP)
    reponse = lister_ressources("", registre=registre)
    assert reponse["statut"] == "erreur_parametres"


@responses.activate
def test_reponse_invalide_echec_propre(registre):
    # Réf. tests/plan_tests.md : TU-37 (charge utile non conforme → échec propre, sans exception)
    reponse_invalide = {"id": "abc", "resources": "pas une liste"}
    responses.add(responses.GET, URL_JEU, json=reponse_invalide, status=200)

    reponse = lister_ressources("67660551c8588734a16a6a60", registre=registre)

    assert reponse["statut"] == "echec_technique"


# ---------------------------------------------------------------------
# T10.2 : sérialisation additive de l'inventaire (persistance CLI)
# ---------------------------------------------------------------------

@responses.activate
@patch("src.core.resources.est_indexee_api_tabulaire", return_value=False)
def test_decharger_charger_round_trip(mock_indexee, fixture_ressources, registre):
    # Réf. T10.2 — dump/rechargement sans perte, métadonnées complètes
    import src.core.resources as module
    module._inventaire.clear()
    _mocker_jeu_v2("67660551c8588734a16a6a60", *_split_fixture_v2(fixture_ressources))
    lister_ressources("67660551c8588734a16a6a60", registre=registre)

    dump = module.decharger_inventaire()
    assert set(dump.keys()) == set(module.inventaire().keys())
    premiere_id = fixture_ressources["resources"][0]["id"]
    assert dump[premiere_id]["licence"] == fixture_ressources["license"]
    assert dump[premiere_id]["id_jeu"] == "67660551c8588734a16a6a60"

    module._inventaire.clear()
    assert module.inventaire() == {}
    module.charger_inventaire(dump)
    assert module.inventaire() == dump


def test_charger_inventaire_enrichissement_cumulatif():
    # Réf. T10.2 — la fusion n'écrase pas les entrées existantes
    import src.core.resources as module
    module._inventaire.clear()
    module._inventaire["r1"] = {"id": "r1", "licence": "lov2"}
    ajoutees = module.charger_inventaire({
        "r1": {"id": "r1", "licence": "ecrasee"},
        "r2": {"id": "r2", "licence": "cc-by"},
    })
    assert ajoutees == 1
    assert module.inventaire()["r1"]["licence"] == "lov2"
    assert module.inventaire()["r2"]["licence"] == "cc-by"
    module._inventaire.clear()
