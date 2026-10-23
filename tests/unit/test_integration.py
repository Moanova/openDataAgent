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
    # Aucune ecriture pour la ressource refusee : un seul fichier de donnees
    # dans l'arborescence (T10.8 : le manifeste d'acquisition de la ressource
    # legitime precedemment telechargee est une sortie latérale attendue).
    fichiers = list((tmp_path / "data" / "raw").rglob("*"))
    fichiers_ecrits = [f for f in fichiers if f.is_file() and f.name != "manifeste_acquisitions.json"]
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


# ---------------------------------------------------------------------
# T11.1 — TI-18 : scénario multi-tours simulé (SDK Conversations simulé)
# ---------------------------------------------------------------------

def test_t118_scenario_multi_tours_simule(tmp_path, monkeypatch):
    # R\u00e9f. T11.1 TI-18 \u2014 exploration -> correction utilisateur -> raffinement
    # -> acquisition valid\u00e9e. L'API Conversations et le coeur sont simules.
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import src.agent.outils as module_outils
    from src.agent.agent import Agent
    from src.agent.boucle import cloturer_conversation, creer_conversation, tour_conversation
    from src.agent.journal import JournalConversation, lire_journal

    # --- Coeur simul\u00e9 : recherche, inventaire, t\u00e9l\u00e9chargement ---
    recherche = MagicMock(return_value={
        "statut": "succes", "message": "",
        "donnees": {"jeux": [{"id": "jeu-1", "titre": "Jeu 1", "licence": "lov2"}],
                    "total_trouves": 1, "exclus_licence": 0,
                    "page_courante": 1, "page_suivante": None},
    })
    inventaire = MagicMock(return_value={
        "statut": "succes", "message": "",
        "donnees": {"ressources": [{"id": "res-1", "titre": "fichier.csv", "classe": "fichier_tabulaire",
                                    "api_tabulaire": False, "format": "csv"}],
                    "indetermination": []},
    })
    telechargement = MagicMock(return_value={
        "statut": "succes", "message": "",
        "donnees": {"chemin_local": "data/raw/id_multi/res-1_fichier.csv", "format": "csv", "licence": "lov2"},
    })
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", recherche)
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "lister_ressources", inventaire)
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "telecharger_brut", telechargement)

    # --- Helpers \u00e9v\u00e9nements Conversations ---
    def evt_started(cid="conv-multi"):
        return SimpleNamespace(event="conversation.response.started",
                               data=SimpleNamespace(type="conversation.response.started", conversation_id=cid))

    def evt_msg(texte):
        return SimpleNamespace(event="message.output.delta",
                               data=SimpleNamespace(type="message.output.delta", id="m",
                                                     content={"type": "text", "text": texte}, role="assistant"))

    def evt_call(nom, args, cid="c1", output_index=0):
        return SimpleNamespace(event="function.call.delta",
                               data=SimpleNamespace(type="function.call.delta", id=f"fc-{cid}", name=nom,
                                                     tool_call_id=cid, arguments=json.dumps(args),
                                                     output_index=output_index))

    def evt_done():
        return SimpleNamespace(event="conversation.response.done",
                               data=SimpleNamespace(type="conversation.response.done",
                                                     usage=SimpleNamespace(total_tokens=10)))

    # --- Sc\u00e9nario : 3 tours ---
    # Tour 1 (exploration) : recherche + inventaire, synth\u00e8se = proposition
    # Tour 2 (correction) : l'utilisateur restreint, l'agent relance la recherche
    # Tour 3 (validation) : l'utilisateur valide, l'agent t\u00e9l\u00e9charge
    client = MagicMock()
    streams = [
        # Tour 1 : start_stream -> recherche + inventaire (2 tool_calls en un stream,
        #          puis append avec les r\u00e9sultats -> proposition)
        iter([evt_started(), evt_msg("Je recherche."), evt_call("rechercher_jeux", {"mots_cles": ["dette"]}, "c1"), evt_done()]),
        iter([evt_call("lister_ressources", {"id_jeu": "jeu-1"}, "c2"), evt_done()]),
        iter([evt_msg("Proposition : jeu-1, ressource res-1. Validez-vous ?"), evt_done()]),
        # Tour 2 : append_stream (message utilisateur) -> nouvelle recherche affin\u00e9e
        iter([evt_msg("Restreins aux donn\u00e9es r\u00e9centes."), evt_call("rechercher_jeux", {"mots_cles": ["dette", "2026"]}, "c3"), evt_done()]),
        iter([evt_msg("Jeu retenu : jeu-1. Confirmez l'acquisition ?"), evt_done()]),
        # Tour 3 : append_stream (validation) -> t\u00e9l\u00e9chargement
        iter([evt_msg("Oui, acquiert."), evt_call("telecharger_brut", {"id_ressource": "res-1"}, "c4"), evt_done()]),
        iter([evt_msg("Fichier acquis : data/raw/id_multi/res-1_fichier.csv (lov2)."), evt_done()]),
    ]
    client.beta.conversations.start_stream.side_effect = [streams[0]]
    client.beta.conversations.append_stream.side_effect = streams[1:]

    agent = Agent(client=client, agent_id="ag-multi", modele="m", outils=[], ephemere=True)
    journal = JournalConversation("id_multi", modele="m", prompt="empreinte", plafond=10, repertoire=tmp_path)
    conversation = creer_conversation(agent, "id_multi", plafond=10, journal=journal)

    r1 = tour_conversation(conversation, "cherche des donn\u00e9es sur la dette publique")
    assert r1["statut"] == "succes"
    assert r1["donnees"]["numero_tour"] == 1
    assert r1["donnees"]["nb_invocations"] == 2
    assert conversation.conversation_id == "conv-multi"

    r2 = tour_conversation(conversation, "restreins aux donn\u00e9es r\u00e9centes")
    assert r2["statut"] == "succes"
    assert r2["donnees"]["numero_tour"] == 2
    assert r2["donnees"]["nb_invocations"] == 1

    r3 = tour_conversation(conversation, "oui, acquiert res-1")
    assert r3["statut"] == "succes"
    assert r3["donnees"]["numero_tour"] == 3
    assert r3["donnees"]["nb_invocations"] == 1
    assert "acquis" in r3["donnees"]["synthese"].lower()

    cloturer_conversation(conversation, "succes")

    # --- V\u00e9rifications ---
    # Le coeur a \u00e9t\u00e9 invoqu\u00e9 dans l'ordre attendu, avec l'id_execution de la conversation
    recherche.assert_any_call(mots_cles=["dette"], id_execution="id_multi")
    recherche.assert_any_call(mots_cles=["dette", "2026"], id_execution="id_multi")
    inventaire.assert_called_once_with(id_jeu="jeu-1", id_execution="id_multi")
    telechargement.assert_called_once_with(id_ressource="res-1", id_execution="id_multi")
    assert recherche.call_count == 2

    # Le contexte serveur est conserv\u00e9 : un seul start_stream, le reste en append_stream
    assert client.beta.conversations.start_stream.call_count == 1
    assert client.beta.conversations.append_stream.call_count == 6
    # Chaque append_stream apr\u00e8s le premier tour porte le conversation_id
    for appel in client.beta.conversations.append_stream.call_args_list:
        assert appel.kwargs["conversation_id"] == "conv-multi"

    # Totaux de la conversation
    assert conversation.nb_tours == 3
    assert conversation.nb_invocations == 4

    # Journal multi-tours : 3 debut_tour, 3 fin_tour, 1 contexte, 1 fin
    enregistrements = lire_journal(journal.chemin)
    evenements = [e["event"] for e in enregistrements]
    assert evenements.count("debut_tour") == 3
    assert evenements.count("fin_tour") == 3
    assert evenements[0] == "contexte"
    assert evenements[-1] == "fin"
    assert enregistrements[-1]["nb_tours"] == 3
    assert enregistrements[-1]["nb_invocations"] == 4
    numeros = [e["numero_tour"] for e in enregistrements if e["event"] == "debut_tour"]
    assert numeros == [1, 2, 3]

    # La conversation a \u00e9t\u00e9 supprim\u00e9e c\u00f4t\u00e9 serveur
    client.beta.conversations.delete.assert_called_once_with(conversation_id="conv-multi")


# ---------------------------------------------------------------------------
# T7.1 — Réessai intelligent (22/10/2026) : TI-19, TI-20
# ---------------------------------------------------------------------------

@responses.activate
def test_ti19_telechargement_503_puis_succes(registre, tmp_path, monkeypatch):
    # TI-19 : flux telecharger_brut — 1er appel 503 puis succès -> fichier complet,
    # nb_tentatives=2, registre vide (succès = pas de consignation).
    import time as _time
    from unittest.mock import patch as _patch

    monkeypatch.chdir(tmp_path)

    responses.add(responses.GET, ping_tabulaire("res-t19"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-t19", *_split_v2({
        "id": "jeu-t19",
        "title": "Jeu T19",
        "license": "lov2",
        "organization": {"name": "Org"},
        "resources": [
            {"id": "res-t19", "title": "Fichier", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 9}
        ],
    }))
    inventaire = lister_ressources("jeu-t19", registre=registre)
    assert inventaire["statut"] == "succes"

    responses.add(responses.GET, URL_FICHIER, body=b"indisponible", status=503)
    responses.add(responses.GET, URL_FICHIER, body=b"a,b\n1,2\n", status=200)
    with _patch.object(_time, "sleep"):
        telechargement = telecharger_brut("res-t19", id_execution="20261022_100000_t19x", registre=registre)

    assert telechargement["statut"] == "succes"
    assert telechargement["donnees"]["nb_tentatives"] == 2
    chemin = Path(telechargement["donnees"]["chemin_local"])
    assert chemin.read_bytes() == b"a,b\n1,2\n"
    assert registre.rapport_pour_agent()["sources_inaccessibles"] == []


@responses.activate
def test_ti20_telechargement_503_persistant_a_retenter(registre, tmp_path, monkeypatch):
    # TI-20 : flux telecharger_brut — 503 x 3 -> echec_technique, registre consigné
    # a_retenter, nb_tentatives=3.
    import time as _time
    from unittest.mock import patch as _patch

    monkeypatch.chdir(tmp_path)

    responses.add(responses.GET, ping_tabulaire("res-t20"), json={"links": []}, status=200)
    _mocker_inventaire_v2("jeu-t20", *_split_v2({
        "id": "jeu-t20",
        "title": "Jeu T20",
        "license": "lov2",
        "organization": {"name": "Org"},
        "resources": [
            {"id": "res-t20", "title": "Fichier", "url": URL_FICHIER, "format": "csv", "mime": "text/csv", "filesize": 9}
        ],
    }))
    inventaire = lister_ressources("jeu-t20", registre=registre)
    assert inventaire["statut"] == "succes"

    for _ in range(3):
        responses.add(responses.GET, URL_FICHIER, body=b"indisponible", status=503)
    with _patch.object(_time, "sleep"):
        telechargement = telecharger_brut("res-t20", id_execution="20261022_100000_t20x", registre=registre)

    assert telechargement["statut"] == "echec_technique"
    assert telechargement["donnees"]["nb_tentatives"] == 3
    assert len(responses.calls) >= 3  # 3 tentatives effectuees

    entrees = registre.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees) == 1
    assert entrees[0]["statut_reprise"] == "a_retenter"
    assert entrees[0]["motif"] == "serveur_origine_bloque"

    # Aucune écriture partielle conservée après épuisement des tentatives transitoires
    # (le .part est conservé pour une reprise ultérieure — comportement T7.1 E3)


# ---------------------------------------------------------------------------
# T7.2 — Nettoyage des anciennes exécutions (22/10/2026) : TI-21
# ---------------------------------------------------------------------------

def test_ti21_nettoyage_flux_complet(tmp_path, monkeypatch):
    # TI-21 : scénario de nettoyage sur arborescence réelle — une exécution
    # ancienne (toutes traces) est supprimée, une récente et l'exécution
    # courante sont conservées ; registres globaux intacts.
    from datetime import datetime as _dt, timedelta as _td
    from src.core.nettoyage import (
        RACINES_SOUS_DOSSIERS,
        RACINE_LOGS,
        nettoyer_anciennes_executions,
    )

    monkeypatch.chdir(tmp_path)
    maintenant = _dt(2026, 10, 22, 12, 0, 0)
    ids = {
        "vieux": (maintenant - _td(days=60)).strftime("%Y%m%d_%H%M%S") + "_t21a",
        "recent": (maintenant - _td(days=2)).strftime("%Y%m%d_%H%M%S") + "_t21b",
        "courant": (maintenant - _td(days=90)).strftime("%Y%m%d_%H%M%S") + "_t21c",
    }
    for id_execution in ids.values():
        for racine in RACINES_SOUS_DOSSIERS:
            dossier = tmp_path / racine / id_execution
            dossier.mkdir(parents=True)
            (dossier / "fichier.csv").write_text("x", encoding="utf-8")
        log = tmp_path / RACINE_LOGS / f"openDataAgent_{id_execution}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("log\n", encoding="utf-8")
    registre = tmp_path / "data" / "registry.json"
    registre.write_text("{}", encoding="utf-8")

    bilan = nettoyer_anciennes_executions(
        age_jours=30, id_execution_courante=ids["courant"], maintenant=maintenant
    )

    assert bilan["statut"] == "succes"
    assert bilan["donnees"]["supprimes"] == [ids["vieux"]]
    assert set(bilan["donnees"]["conserves"]) == {ids["recent"], ids["courant"]}
    assert not (tmp_path / "data" / "raw" / ids["vieux"]).exists()
    assert not (tmp_path / RACINE_LOGS / f"openDataAgent_{ids['vieux']}.log").exists()
    assert (tmp_path / "data" / "raw" / ids["recent"]).is_dir()
    assert (tmp_path / "data" / "raw" / ids["courant"]).is_dir()
    assert registre.is_file()


# ---------------------------------------------------------------------
# T11.4 : memoire cross-session via consulter_registre
# ---------------------------------------------------------------------

@responses.activate
def test_ti26_consulter_registre_memoire_cross_session(tmp_path, monkeypatch):
    # Ref. tests/plan_tests.md : TI-26 (T11.4) — une entree consignee par une
    # execution est visible via consulter_registre dans une execution suivante
    # (memoire cross-session), sans aucune re-ecriture du registre.
    from src.core.registre import consulter_registre

    monkeypatch.chdir(tmp_path)
    chemin_registre = tmp_path / "registry.json"

    # --- Execution 1 : exclusion de licence consignee et sauvegardee
    registre_1 = RegistreSourcesInaccessibles(chemin=chemin_registre)
    responses.add(responses.GET, URL_RECHERCHE, json={
        "data": [_jeu("jeu-ferme", "Jeu Ferme", "other-closed", "Ministere X")],
        "total": 1, "page": 1, "next_page": None, "previous_page": None,
    }, status=200)
    recherche = rechercher_jeux(["budget"], registre=registre_1)
    assert recherche["statut"] == "succes"
    assert recherche["donnees"]["exclus_licence"] == 1

    # --- Execution 2 : nouvelle instance sur le meme chemin, lecture seule
    registre_2 = RegistreSourcesInaccessibles(chemin=chemin_registre)
    reponse = consulter_registre(registre=registre_2)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["total"] == 1
    entree = reponse["donnees"]["sources_inaccessibles"][0]
    assert entree["id_jeu"] == "jeu-ferme"
    assert entree["motif"] == "licence_incompatible"
    assert entree["statut_reprise"] == "definitif"

    # Lecture seule : le fichier registre n'a pas ete re-ecrit ni altere
    contenu = json.loads(chemin_registre.read_text(encoding="utf-8"))
    assert len(contenu["sources_inaccessibles"]) == 1
