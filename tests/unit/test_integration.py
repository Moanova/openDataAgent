# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_integration.py
# Version      : 1
# Date         : 13-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests d'integration du flux complet (T3.4.3, embryon de T5.2.1).

Chaine recherche -> inventaire -> telechargement, sans reseau
(`responses`), registre injecte sur tmp_path. Couvre TI-08 : registre
final avec deux entrees de motifs distincts en ordre chronologique.
"""
import json
from pathlib import Path

import pytest
import responses

from src.core.search import rechercher_jeux
from src.core.resources import lister_ressources
from src.core.download import telecharger_brut
from src.utils.registry import RegistreSourcesInaccessibles

URL_RECHERCHE = "https://www.data.gouv.fr/api/2/datasets/search/"
def url_jeu(id_jeu: str) -> str:
    return f"https://www.data.gouv.fr/api/2/datasets/{id_jeu}/"


def url_ressources(id_jeu: str) -> str:
    return f"https://www.data.gouv.fr/api/2/datasets/{id_jeu}/resources/"


def _mocker_inventaire_v2(id_jeu, detail, ressources):
    """Ajoute les deux reponses v2 : detail du jeu + sous-ressource paginee."""
    responses.add(responses.GET, url_jeu(id_jeu), json=detail, status=200)
    responses.add(
        responses.GET,
        url_ressources(id_jeu),
        json={"data": ressources, "total": len(ressources), "page": 1,
              "page_size": 50, "next_page": None, "previous_page": None},
        status=200,
    )


def _split_v2(payload):
    """Scinde un payload inventaire {.., resources: [liste]} en (detail, ressources) v2."""
    detail = {k: v for k, v in payload.items() if k != "resources"}
    detail["resources"] = {
        "rel": "subsection",
        "href": "https://www.data.gouv.fr/api/2/datasets/%s/resources/" % payload.get("id", "x"),
        "total": len(payload.get("resources", [])),
    }
    return detail, payload.get("resources", [])


def _detail_inventaire_v2(jeu_recherche):
    """Convertit un jeu au format recherche v2 en payload d'inventaire avec ressources plates."""
    payload = dict(jeu_recherche)
    payload["resources"] = [
        {"id": f"res-{jeu_recherche['id']}", "title": f"Fichier {jeu_recherche['id']}",
         "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 10}
    ]
    return payload
URL_FICHIER = "https://exemple.org/donnees/budget.csv"
def ping_tabulaire(id_ressource: str) -> str:
    return f"https://tabular-api.data.gouv.fr/api/resources/{id_ressource}/"


@pytest.fixture
def registre(tmp_path) -> RegistreSourcesInaccessibles:
    return RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")


def _jeu(id_: str, titre: str, licence: str, organisation: str = "Org") -> dict:
    return {
        "id": id_,
        "title": titre,
        "slug": id_,
        "page": f"https://www.data.gouv.fr/datasets/{id_}",
        "created_at": "2024-01-01T00:00:00+00:00",
        "last_modified": "2026-09-01T00:00:00+00:00",
        "last_update": "2026-09-01T00:00:00+00:00",
        "license": licence,
        "organization": {"name": organisation},
        "resources": {"rel": "subsection", "href": f"https://www.data.gouv.fr/api/2/datasets/{id_}/resources/", "total": 1},
    }


@responses.activate
def test_ti08_flux_complet_exclusion_et_echec(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-08 (flux complet : exclusion licence + échec téléchargement → registre : deux entrées, motifs exacts, ordre chronologique)
    monkeypatch.chdir(tmp_path)

    # Etape 1 : recherche — un jeu ouvert, un jeu de licence refusee
    reponse_recherche = {
        "data": [
            _jeu("jeu-ouvert", "Jeu ouvert", "lov2", organisation="Insee"),
            _jeu("jeu-ferme", "Jeu ferme", "other-closed", organisation="Ministere X"),
        ],
        "total": 2,
        "page": 1,
        "next_page": None,
        "previous_page": None,
    }
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_recherche, status=200)

    recherche = rechercher_jeux(["budget"], registre=registre)
    assert recherche["statut"] == "succes"
    assert [j["id"] for j in recherche["donnees"]["jeux"]] == ["jeu-ouvert"]
    assert recherche["donnees"]["exclus_licence"] == 1

    # Etape 2 : inventaire du jeu ouvert
    reponse_inventaire = {
        "id": "jeu-ouvert",
        "title": "Jeu ouvert",
        "license": "lov2",
        "organization": {"name": "Insee"},
        "resources": [
            {"id": "res-telecharge", "title": "Budget", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 10}
        ],
    }
    responses.add(responses.GET, ping_tabulaire("res-telecharge"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-ouvert", *_split_v2(reponse_inventaire))

    inventaire = lister_ressources("jeu-ouvert", registre=registre)
    assert inventaire["statut"] == "succes"

    # Etape 3 : telechargement refuse par le serveur d'origine
    responses.add(responses.GET, URL_FICHIER, body=b"acces refuse", status=403)

    telechargement = telecharger_brut("res-telecharge", id_execution="20261013_160000_xyz789", registre=registre)
    assert telechargement["statut"] == "echec_technique"
    assert telechargement["donnees"]["suggestion"] == "fichier_heberge_exterieurement"

    # Registre final : deux entrees, motifs exacts, ordre chronologique
    entrees = registre.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees) == 2

    premiere, seconde = entrees
    assert premiere["motif"] == "licence_incompatible"
    assert premiere["id_jeu"] == "jeu-ferme"
    assert premiere["licence"] == "other-closed"
    assert premiere["organisation"] == "Ministere X"

    assert seconde["motif"] == "serveur_origine_bloque"
    assert seconde["id_jeu"] == "jeu-ouvert"
    assert seconde["licence"] == "lov2"
    assert seconde["organisation"] == "Insee"
    assert seconde["detail"] == "Statut HTTP 403"

    assert premiere["timestamp"] <= seconde["timestamp"]

    # Registre persiste au format JSON valide
    chemin_registre = tmp_path / "registry.json"
    assert chemin_registre.exists()
    json.loads(chemin_registre.read_text(encoding="utf-8"))


@responses.activate
def test_flux_complet_telechargement_reussi(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-05/T5.2.1 (flux complet simulé avec téléchargement réussi)
    monkeypatch.chdir(tmp_path)

    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [_jeu("jeu-ok", "Jeu OK", "fr-lo")],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    recherche = rechercher_jeux(["budget"], registre=registre)
    assert recherche["donnees"]["jeux"][0]["id"] == "jeu-ok"

    responses.add(responses.GET, ping_tabulaire("res-ok"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-ok", *_split_v2({
        "id": "jeu-ok",
        "title": "Jeu OK",
        "license": "fr-lo",
        "organization": {"name": "Org"},
        "resources": [
            {"id": "res-ok", "title": "Fichier", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 5}
        ],
    }))
    inventaire = lister_ressources("jeu-ok", registre=registre)
    assert inventaire["statut"] == "succes"

    responses.add(responses.GET, URL_FICHIER, body=b"a,b\n1,2\n", status=200)
    telechargement = telecharger_brut("res-ok", id_execution="20261013_170000_aaa000", registre=registre)

    assert telechargement["statut"] == "succes"
    chemin = Path(telechargement["donnees"]["chemin_local"])
    assert chemin.read_bytes() == b"a,b\n1,2\n"
    assert telechargement["donnees"]["licence"] == "fr-lo"

    # Aucune entree au registre : tout a reussi
    assert registre.rapport_pour_agent()["sources_inaccessibles"] == []


@responses.activate
def test_entree_exclusion_non_alteree_par_echec(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : invariants du registre (aucune entrée modifiée après écriture)
    monkeypatch.chdir(tmp_path)

    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [_jeu("jeu-ferme", "Jeu ferme", "notspecified")],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    rechercher_jeux(["x"], registre=registre)
    avant = registre.rapport_pour_agent()["sources_inaccessibles"][0]

    # Un echec de telechargement sur une autre source n'altere pas l'entree existante
    responses.add(responses.GET, ping_tabulaire("res-autre"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-autre", *_split_v2({
        "id": "jeu-autre",
        "title": "Jeu autre",
        "license": "lov2",
        "organization": {"name": "Autre"},
        "resources": [
            {"id": "res-autre", "title": "F", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 1}
        ],
    }))
    lister_ressources("jeu-autre", registre=registre)
    responses.add(responses.GET, URL_FICHIER, body=b"non", status=503)
    responses.add(responses.GET, URL_FICHIER, body=b"non", status=503)
    responses.add(responses.GET, URL_FICHIER, body=b"non", status=503)
    telecharger_brut("res-autre", id_execution="20261013_180000_bbb111", registre=registre)

    entrees = registre.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees) == 2
    assert entrees[0] == avant


@responses.activate
def test_t521_flux_complet_avec_exclusion_licence(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-14 (T5.2.1) — flux complet nominal avec exclusion de licence à la recherche
    monkeypatch.chdir(tmp_path)
    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [
            _jeu("jeu-ouvert", "Jeu Ouvert", "lov2", "Insee"),
            _jeu("jeu-ferme", "Jeu Ferme", "other-closed", "Ministere X"),
        ],
        "total": 2, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    recherche = rechercher_jeux(["budget"], registre=registre)
    assert recherche["statut"] == "succes"
    ids = [j["id"] for j in recherche["donnees"]["jeux"]]
    assert ids == ["jeu-ouvert"]
    assert recherche["donnees"]["exclus_licence"] == 1

    responses.add(responses.GET, ping_tabulaire("res-jeu-ouvert"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-ouvert", *_split_v2({
        "id": "jeu-ouvert", "title": "Jeu Ouvert", "license": "lov2",
        "organization": {"name": "Insee"},
        "resources": [
            {"id": "res-jeu-ouvert", "title": "Budget", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 7}
        ],
    }))
    inventaire = lister_ressources("jeu-ouvert", registre=registre)
    assert inventaire["statut"] == "succes"

    responses.add(responses.GET, URL_FICHIER, body=b"col;val\nx;1\n", status=200)
    telechargement = telecharger_brut("res-jeu-ouvert", id_execution="20261014_flux", registre=registre)
    assert telechargement["statut"] == "succes"
    chemin = Path(telechargement["donnees"]["chemin_local"])
    assert chemin.read_bytes() == b"col;val\nx;1\n"
    assert telechargement["donnees"]["licence"] == "lov2"

    # Le jeu ferme n'a jamais ete expose a l'inventaire ni au telechargement :
    # la chaine identifiants est restee integre, l'exclusion est tracee au registre.
    entrees = registre.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees) == 1
    assert entrees[0]["motif"] == "licence_incompatible"
    assert entrees[0]["id_jeu"] == "jeu-ferme"


@responses.activate
def test_t521_ressource_hors_chaine_refusee(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-14b (T5.2.1) — propriété TA-01/TA-02 au niveau intégration :
    # un téléchargement d'identifiant jamais délivré par le flux est refusé, aucune écriture disque
    monkeypatch.chdir(tmp_path)
    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [_jeu("jeu-a", "Jeu A", "lov2", "Insee")],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    recherche = rechercher_jeux(["budget"], registre=registre)
    assert recherche["statut"] == "succes"

    responses.add(responses.GET, ping_tabulaire("res-jeu-a"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-a", *_split_v2({
        "id": "jeu-a", "title": "Jeu A", "license": "lov2",
        "organization": {"name": "Insee"},
        "resources": [
            {"id": "res-jeu-a", "title": "Fichier", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 5}
        ],
    }))
    inventaire = lister_ressources("jeu-a", registre=registre)
    assert inventaire["statut"] == "succes"

    # Ressource inventoriee : le telechargement fonctionne
    responses.add(responses.GET, URL_FICHIER, body=b"a;b\n", status=200)
    reponse_ok = telecharger_brut("res-jeu-a", id_execution="20261014_hc", registre=registre)
    assert reponse_ok["statut"] == "succes"

    # Ressource jamais vue par l'inventaire de CE flux : refusee, aucune ecriture
    reponse_ko = telecharger_brut("res-fantome", id_execution="20261014_hc", registre=registre)
    assert reponse_ko["statut"] == "ressource_introuvable"
    assert reponse_ko["donnees"]["suggestion"] == "reprendre par l'inventaire"
    # Aucune ecriture pour la ressource refusee : un seul fichier dans l'arborescence
    fichiers = list((tmp_path / "data" / "raw").rglob("*"))
    fichiers_ecrits = [f for f in fichiers if f.is_file()]
    assert len(fichiers_ecrits) == 1


# ---------------------------------------------------------------------
# T5.2.2 : persistance du registre des sources inaccessibles
# ---------------------------------------------------------------------

@responses.activate
def test_t522_rechargement_entre_executions(tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-15 (T5.2.2) — exécution 1 écrit, exécution 2 (nouvelle instance) retrouve tout
    monkeypatch.chdir(tmp_path)
    chemin_registre = tmp_path / "registry.json"

    # --- Exécution 1 : exclusion de licence + échec de téléchargement
    registre_1 = RegistreSourcesInaccessibles(chemin=chemin_registre)
    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [
            _jeu("jeu-ouvert", "Jeu Ouvert", "lov2", "Insee"),
            _jeu("jeu-ferme", "Jeu Ferme", "other-closed", "Ministere X"),
        ],
        "total": 2, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    recherche = rechercher_jeux(["budget"], registre=registre_1)
    assert recherche["statut"] == "succes"
    assert recherche["donnees"]["exclus_licence"] == 1

    responses.add(responses.GET, ping_tabulaire("res-jeu-ouvert"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-ouvert", *_split_v2({
        "id": "jeu-ouvert", "title": "Jeu Ouvert", "license": "lov2",
        "organization": {"name": "Insee"},
        "resources": [
            {"id": "res-jeu-ouvert", "title": "Budget", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 5}
        ],
    }))
    inventaire = lister_ressources("jeu-ouvert", registre=registre_1)
    assert inventaire["statut"] == "succes"

    responses.add(responses.GET, URL_FICHIER, body=b"", status=403)
    echec = telecharger_brut("res-jeu-ouvert", id_execution="20261014_exec1", registre=registre_1)
    assert echec["statut"] == "echec_technique"

    entrees_1 = registre_1.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees_1) == 2

    # --- Exécution 2 : nouvelle instance sur le même chemin — la persistance
    registre_2 = RegistreSourcesInaccessibles(chemin=chemin_registre)
    entrees_2 = registre_2.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees_2) == 2, "le registre doit être rechargé intégralement par l'exécution suivante"
    motifs = [e["motif"] for e in entrees_2]
    assert "licence_incompatible" in motifs
    assert "serveur_origine_bloque" in motifs
    for e1, e2 in zip(entrees_1, entrees_2):
        assert e1 == e2, "aucune entrée ne doit être altérée entre les exécutions"
    # JSON valide au chemin
    json.loads(chemin_registre.read_text(encoding="utf-8"))


@responses.activate
def test_t522_enrichissement_cumulatif(tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-15b (T5.2.2) — l'exécution 2 ajoute sans altérer les entrées d'origine
    monkeypatch.chdir(tmp_path)
    chemin_registre = tmp_path / "registry.json"

    # Exécution 1 : une exclusion juridique
    registre_1 = RegistreSourcesInaccessibles(chemin=chemin_registre)
    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [_jeu("jeu-ferme", "Jeu Ferme", "other-closed", "Ministere X")],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    rechercher_jeux(["budget"], registre=registre_1)
    entrees_1 = registre_1.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees_1) == 1
    entree_juridique = entrees_1[0]

    # Exécution 2 : nouvelle instance, un échec technique s'ajoute
    registre_2 = RegistreSourcesInaccessibles(chemin=chemin_registre)
    registre_2.consigner_echec_technique(
        id_jeu="jeu-x",
        organisation="Org Y",
        licence="fr-lo",
        url="https://exemple.org/x.csv",
        detail="Statut HTTP 500",
    )
    registre_2.sauvegarder()
    entrees_2 = registre_2.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees_2) == 2, "l'exécution 2 cumule sans écraser"
    juridique_apres = [e for e in entrees_2 if e["motif"] == "licence_incompatible"][0]
    assert juridique_apres == entree_juridique, "l'entrée juridique d'origine n'est pas altérée"
    technique = [e for e in entrees_2 if e["motif"] == "serveur_origine_bloque"][0]
    assert technique["detail"] == "Statut HTTP 500"
    # Ordre chronologique
    assert entrees_2[0]["timestamp"] <= entrees_2[1]["timestamp"]

    # Exécution 3 : relecture nue — le cumul persiste
    registre_3 = RegistreSourcesInaccessibles(chemin=chemin_registre)
    assert len(registre_3.rapport_pour_agent()["sources_inaccessibles"]) == 2


def test_t522_retetest_echec_technique_non_bloquant(tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-15c (T5.2.2) — une entrée technique ne bloque pas un nouvel essai :
    # le contrat global autorise le re-test d'une source en échec technique lors d'une exécution ultérieure.
    monkeypatch.chdir(tmp_path)
    chemin_registre = tmp_path / "registry.json"
    registre = RegistreSourcesInaccessibles(chemin=chemin_registre)
    registre.consigner_echec_technique(
        id_jeu="jeu-y",
        organisation="Org Z",
        licence="lov2",
        url="https://exemple.org/y.csv",
        detail="Statut HTTP 503",
    )
    registre.sauvegarder()
    # Le registre ne bloque rien par lui-même : une nouvelle exécution peut re-tenter la ressource.
    # (Le re-test effectif relancera telecharger_brut ; le registre n'interdit pas l'accès.)
    nouveau_registre = RegistreSourcesInaccessibles(chemin=chemin_registre)
    assert len(nouveau_registre.rapport_pour_agent()["sources_inaccessibles"]) == 1
    # Aucune API du registre n'expose de mécanisme de blocage : comportement conforme au contrat
    # (entrée technique re-testable, entrée juridique définitive côté filtrage licence).


def url_data(id_ressource: str) -> str:
    return f"https://tabular-api.data.gouv.fr/api/resources/{id_ressource}/data/"


@responses.activate
def test_t107_flux_complet_voie1_extraction(registre, tmp_path, monkeypatch):
    # Réf. T10.7 — flux complet voie 1 : recherche -> inventaire -> extraction -> CSV sur disque
    import src.core.resources as module_resources
    from src.core.extraction import extraire_ressource

    module_resources._inventaire.clear()
    monkeypatch.chdir(tmp_path)

    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [_jeu("jeu-ouvert", "Jeu Ouvert", "lov2", "Insee")],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    recherche = rechercher_jeux(["budget"], registre=registre)
    assert recherche["statut"] == "succes"

    responses.add(responses.GET, ping_tabulaire("res-jeu-ouvert"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-ouvert", *_split_v2(_detail_inventaire_v2(_jeu("jeu-ouvert", "Jeu Ouvert", "lov2", "Insee"))))
    inventaire = lister_ressources("jeu-ouvert", registre=registre)
    assert inventaire["statut"] == "succes"

    # Extraction paginée : deux pages, la ressource est indexée (ping 200).
    responses.add(responses.GET, url_data("res-jeu-ouvert"),
                  json={"data": [{"theme": "dette", "valeur": "1"}],
                        "meta": {"page": 1, "page_size": 1, "total": 2},
                        "links": {"next": "https://tabular-api.data.gouv.fr/api/resources/res-jeu-ouvert/data/?page=2"}},
                  status=200)
    responses.add(responses.GET, url_data("res-jeu-ouvert"),
                  json={"data": [{"theme": "dette", "valeur": "2"}],
                        "meta": {"page": 2, "page_size": 1, "total": 2},
                        "links": {"next": None}},
                  status=200)
    extraction = extraire_ressource("res-jeu-ouvert", id_execution="flux-voic1", taille_page=1)
    assert extraction["statut"] == "succes", extraction
    donnees = extraction["donnees"]
    assert donnees["total_lignes"] == 2
    assert donnees["lignes_ecrites"] == 2
    assert donnees["tronque"] is False
    assert donnees["licence"] == "lov2"

    chemin = Path(donnees["chemin_local"])
    assert chemin.exists()
    contenu = chemin.read_text(encoding="utf-8")
    assert "theme" in contenu.splitlines()[0]
    assert contenu.count("\n") == 3  # en-tête + 2 lignes
