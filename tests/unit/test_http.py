# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_http.py
# Version      : 2
# Date         : 18-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du client HTTP data.gouv.fr (src/utils/http.py, T3.1.1).

Couvre TU-15, TU-17 a TU-20 du plan de tests, sans reseau : la couche
HTTP est simulee avec `responses`. Version 2 (T11.3) : endpoints v2,
fenetre_maj depreciee, inventaire en sous-ressource paginee.
"""
import json
from pathlib import Path

import pytest
import responses

from src.utils.http import (
    PAGE_SIZE_INVENTAIRE,
    PLAFOND_PAGES_INVENTAIRE,
    appel_api,
    lister_ressources_api,
    rechercher_jeux_api,
)

REPERTOIRE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api"
URL_RECHERCHE = "https://www.data.gouv.fr/api/2/datasets/search/"
URL_RESSOURCES = "https://www.data.gouv.fr/api/2/datasets/62581fdf02e05e365ea227a1/resources/"


@pytest.fixture
def fixture_recherche() -> dict:
    with open(REPERTOIRE_FIXTURES / "recherche_jeux_reussite.json", encoding="utf-8") as flux:
        return json.load(flux)


@pytest.fixture
def fixture_inventaire() -> dict:
    with open(REPERTOIRE_FIXTURES / "lister_ressources_reussite.json", encoding="utf-8") as flux:
        return json.load(flux)


@responses.activate
def test_succes_recherche_validee(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-15 (tri valide -> traduction correcte vers les paramètres API v2)
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    resultat = rechercher_jeux_api(["dette", "publique"], tri="vues", limite=10, page=3)

    assert len(responses.calls) == 1
    requete = responses.calls[0].request
    assert "q=dette+publique" in requete.url
    assert "sort=-views" in requete.url
    assert "page_size=10" in requete.url
    assert "page=3" in requete.url
    assert resultat.reussi
    assert resultat.donnees["total"] == 235


@responses.activate
def test_fenetre_maj_ignoree_en_v2(fixture_recherche):
    # T11.3 : l'API v2 ne supporte pas last_update_range (400) ; le paramètre
    # est accepté pour compatibilité mais jamais traduit vers l'API.
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    resultat = rechercher_jeux_api(["dette"], tri="recent", fenetre_maj="12_mois", limite=10, page=1)

    requete = responses.calls[0].request.url
    assert "last_update_range" not in requete
    assert resultat.reussi


@responses.activate
def test_succes_parametres_defauts_omis(fixture_recherche):
    # Test annexe : sans référence directe dans tests/plan_tests.md
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    resultat = rechercher_jeux_api(["dette"])

    requete = responses.calls[0].request.url
    assert "sort" not in requete
    assert resultat.reussi


@responses.activate
def test_erreur_500_echec_technique():
    # Réf. tests/plan_tests.md : TU-17 (erreur HTTP 500 -> statut echec_technique, pas d'exception)
    responses.add(responses.GET, URL_RECHERCHE, json={"erreur": "interne"}, status=500)

    resultat = rechercher_jeux_api(["dette"])

    assert not resultat.reussi
    assert resultat.statut == "echec_technique"
    assert resultat.status_code == 500


@responses.activate
def test_404_jeu_introuvable():
    # Réf. tests/plan_tests.md : TU-18 (jeu inexistant 404 -> statut jeu_introuvable)
    responses.add(responses.GET, "https://www.data.gouv.fr/api/2/datasets/inconnu/", json={"message": "not found"}, status=404)

    resultat = appel_api("/datasets/inconnu/")

    assert resultat.statut == "jeu_introuvable"
    assert resultat.status_code == 404


@responses.activate
def test_expiration_delai_echec_technique():
    # Réf. tests/plan_tests.md : TU-19 (expiration du délai -> echec_technique après les tentatives configurées)
    from requests.exceptions import ConnectTimeout

    for _ in range(3):
        responses.add(responses.GET, URL_RECHERCHE, body=ConnectTimeout("delai expire"))

    resultat = appel_api("/datasets/search/", nb_tentatives=3)

    assert not resultat.reussi
    assert resultat.statut == "echec_technique"
    assert len(responses.calls) == 3


@responses.activate
def test_429_puis_succes(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-20 (429 -> nouvelle tentative puis succès)
    responses.add(responses.GET, URL_RECHERCHE, json={}, status=429)
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)

    resultat = appel_api("/datasets/search/", params={"q": "dette"})

    assert resultat.reussi
    assert len(responses.calls) == 2


@responses.activate
def test_503_persistant_echec_technique():
    # Réf. tests/plan_tests.md : TU-20 (503 persistant -> echec_technique après les tentatives)
    for _ in range(3):
        responses.add(responses.GET, URL_RECHERCHE, json={}, status=503)

    resultat = appel_api("/datasets/search/", nb_tentatives=3)

    assert resultat.statut == "echec_technique"
    assert len(responses.calls) == 3


@responses.activate
def test_page_suivante_extraite_de_next_page(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-15 (pagination -> page_suivante extrait de l'URL next_page v2)
    donnees = json.loads(json.dumps(fixture_recherche))
    donnees["next_page"] = "https://www.data.gouv.fr/api/2/datasets/search/?q=dette&page=2&page_size=10"
    responses.add(responses.GET, URL_RECHERCHE, json=donnees, status=200)

    resultat = rechercher_jeux_api(["dette"])

    assert resultat.donnees["page_suivante"] == 2


@responses.activate
def test_page_suivante_nulle_sans_next_page(fixture_recherche):
    # Réf. tests/plan_tests.md : TU-15 (pagination -> page_suivante null si derniere page)
    donnees = json.loads(json.dumps(fixture_recherche))
    donnees["next_page"] = None
    responses.add(responses.GET, URL_RECHERCHE, json=donnees, status=200)

    resultat = rechercher_jeux_api(["dette"])

    assert resultat.donnees["page_suivante"] is None


@responses.activate
def test_reponse_invalide_contre_schema_echec_propre():
    # Réf. tests/plan_tests.md : TU-37 (charge utile non conforme -> échec propre, sans exception)
    reponse_invalide = {"data": [], "page": 1}
    responses.add(responses.GET, URL_RECHERCHE, json=reponse_invalide, status=200)

    resultat = rechercher_jeux_api(["dette"])

    assert resultat.statut == "echec_technique"
    assert "total" in (resultat.erreur or "")


@pytest.mark.parametrize("tri,sort_attendu", [
    ("recent", "-last_update"),
    ("vues", "-views"),
    ("reutilisations", "-reuses"),
])
@responses.activate
def test_tri_recents_et_reutilisations_traduits(fixture_recherche, tri, sort_attendu):
    # Régression : les clés de TRIS_API étaient accentuées ("récént", "réutilisations")
    # alors que l'enum vaut recent/reutilisations -> KeyError -> echec_technique
    # (constaté en trace agentique du 18/10/2026, 2 invocations perdues).
    responses.add(responses.GET, URL_RECHERCHE, json=fixture_recherche, status=200)
    resultat = rechercher_jeux_api(["dette"], tri=tri, limite=10, page=1)
    assert resultat.reussi
    assert f"sort={sort_attendu}" in responses.calls[0].request.url


# ---------------------------------------------------------------------------
# T11.3 — Inventaire v2 : sous-ressource paginée (E2)
# ---------------------------------------------------------------------------


def _page_ressources(items, total, next_page=None):
    return {
        "data": items,
        "total": total,
        "page": 1,
        "page_size": PAGE_SIZE_INVENTAIRE,
        "next_page": next_page,
        "previous_page": None,
    }


def _ressource(n):
    return {
        "id": f"res-{n}",
        "title": f"ressource {n}",
        "url": f"https://static.data.gouv.fr/ressource-{n}.csv",
        "format": "csv",
        "mime": "text/csv",
        "filesize": 100,
        "filetype": "file",
    }


def _detail_jeu(nb_declare):
    return {
        "id": "62581fdf02e05e365ea227a1",
        "title": "Election présidentielle 2022",
        "slug": "election-presidentielle-2022",
        "page": "https://www.data.gouv.fr/fr/datasets/election-presidentielle-2022/",
        "created_at": "2022-04-14T15:21:35.194000+00:00",
        "last_modified": "2022-04-19T11:44:16.818000+00:00",
        "last_update": "2022-04-14T15:26:17.908000+00:00",
        "license": "fr-lo",
        "organization": {"name": "Ministère de l'intérieur", "badges": [{"kind": "public-service"}]},
        "resources": {"rel": "subsection", "href": URL_RESSOURCES, "total": nb_declare},
    }


@responses.activate
def test_inventaire_v2_deux_appels_et_payload_reconstitue():
    # T11.3 (E2) : détail v2 puis sous-ressource paginée ; le payload
    # reconstitué expose une liste `resources` plate au format attendu par le cœur.
    jeu = _detail_jeu(nb_declare=3)
    ressources = [_ressource(n) for n in range(3)]
    responses.add(responses.GET, "https://www.data.gouv.fr/api/2/datasets/62581fdf02e05e365ea227a1/", json=jeu, status=200)
    responses.add(responses.GET, URL_RESSOURCES, json=_page_ressources(ressources, 3, next_page=None), status=200)

    resultat = lister_ressources_api("62581fdf02e05e365ea227a1")

    assert len(responses.calls) == 2
    assert "page_size=%d" % PAGE_SIZE_INVENTAIRE in responses.calls[1].request.url
    assert "page=1" in responses.calls[1].request.url
    assert resultat.reussi
    assert isinstance(resultat.donnees["resources"], list)
    assert len(resultat.donnees["resources"]) == 3
    assert resultat.donnees["id"] == jeu["id"]
    assert resultat.donnees["last_update"] == "2022-04-14T15:26:17.908000+00:00"
    assert resultat.donnees["organization"]["name"] == "Ministère de l'intérieur"


@responses.activate
def test_inventaire_v2_boucle_sur_next_page():
    # T11.3 (E2, décision 3) : pagination arrêtée sur next_page absent —
    # 2 pages de ressources (50 + 10) itérées via next_page.
    jeu = _detail_jeu(nb_declare=60)
    page1 = _page_ressources([_ressource(n) for n in range(50)], 60,
                             next_page=URL_RESSOURCES + "?page=2&page_size=%d" % PAGE_SIZE_INVENTAIRE)
    page2 = _page_ressources([_ressource(n) for n in range(50, 60)], 60, next_page=None)
    responses.add(responses.GET, "https://www.data.gouv.fr/api/2/datasets/62581fdf02e05e365ea227a1/", json=jeu, status=200)
    responses.add(responses.GET, URL_RESSOURCES, json=page1, status=200)
    responses.add(responses.GET, URL_RESSOURCES, json=page2, status=200)

    resultat = lister_ressources_api("62581fdf02e05e365ea227a1")

    assert len(responses.calls) == 3
    assert "page=2" in responses.calls[2].request.url
    assert resultat.reussi
    assert len(resultat.donnees["resources"]) == 60


@responses.activate
def test_inventaire_v2_plafond_de_pages_anti_boucle():
    # T11.3 (E2) : garde anti-boucle — un next_page aberrant qui ne s'épuise
    # jamais déclenche le plafond et produit echec_technique explicite.
    jeu = _detail_jeu(nb_declare=1000)
    page_bouclante = _page_ressources([_ressource(0)], 1000,
                                      next_page=URL_RESSOURCES + "?page=2&page_size=%d" % PAGE_SIZE_INVENTAIRE)
    responses.add(responses.GET, "https://www.data.gouv.fr/api/2/datasets/62581fdf02e05e365ea227a1/", json=jeu, status=200)
    for _ in range(PLAFOND_PAGES_INVENTAIRE + 2):
        responses.add(responses.GET, URL_RESSOURCES, json=page_bouclante, status=200)

    resultat = lister_ressources_api("62581fdf02e05e365ea227a1")

    assert not resultat.reussi
    assert resultat.statut == "echec_technique"
    assert "plafond" in (resultat.erreur or "")
    assert len(responses.calls) == 1 + PLAFOND_PAGES_INVENTAIRE


@responses.activate
def test_inventaire_v2_404_jeu_introuvable():
    # T11.3 (E2) : le 404 du détail produit toujours jeu_introuvable
    # (pas de second appel vers la sous-ressource).
    responses.add(responses.GET, "https://www.data.gouv.fr/api/2/datasets/inconnu/", json={"message": "not found"}, status=404)

    resultat = lister_ressources_api("inconnu")

    assert resultat.statut == "jeu_introuvable"
    assert len(responses.calls) == 1


@responses.activate
def test_inventaire_v2_ressources_vides_reponse_valide():
    # T11.3 (E2) : jeu sans ressource (total 0) — liste vide, succès propre.
    jeu = _detail_jeu(nb_declare=0)
    responses.add(responses.GET, "https://www.data.gouv.fr/api/2/datasets/62581fdf02e05e365ea227a1/", json=jeu, status=200)
    responses.add(responses.GET, URL_RESSOURCES, json=_page_ressources([], 0, next_page=None), status=200)

    resultat = lister_ressources_api("62581fdf02e05e365ea227a1")

    assert resultat.reussi
    assert resultat.donnees["resources"] == []


# ---------------------------------------------------------------------------
# T7.1 — Réessai intelligent (22/10/2026) : TU-81..TU-90
# ---------------------------------------------------------------------------

import time as _time
from unittest.mock import patch as _patch

from src.utils.http import (
    DELAI_BASE_RETRY,
    DELAI_PLAFOND_RETRY,
    STATUTS_DEFINITIFS,
    _delai_retry,
    telecharger_fichier,
)


def test_tu81_retry_after_respecte():
    # TU-81 : 429 avec Retry-After: 5 -> le delai respecte la borne serveur
    with open(REPERTOIRE_FIXTURES / "recherche_jeux_reussite.json", encoding="utf-8") as f:
        payload = json.load(f)
    with _patch.object(_time, "sleep") as mock_sleep:
        with responses.mock:
            responses.add(responses.GET, URL_RECHERCHE, json={}, status=429,
                          headers={"Retry-After": "5"})
            responses.add(responses.GET, URL_RECHERCHE, json=payload, status=200)
            resultat = appel_api("/datasets/search/", params={"q": "dette"})
        assert resultat.reussi
        assert resultat.nb_tentatives == 2
        delai = mock_sleep.call_args[0][0]
        assert delai >= 5.0  # Retry-After respecte comme borne superieure


def test_tu82_backoff_exponentiel_avec_jitter_borne():
    # TU-82 : delai croissant, borne [0.75x, 1.25x] du backoff pur, plafond
    for tentative, attendu in [(1, DELAI_BASE_RETRY), (2, 2 * DELAI_BASE_RETRY), (3, 4 * DELAI_BASE_RETRY)]:
        for _ in range(50):
            d = _delai_retry(tentative)
            assert attendu * 0.75 <= d <= min(attendu * 1.25, DELAI_PLAFOND_RETRY * 1.25)
    # Plafond : jamais au-dela de DELAI_PLAFOND_RETRY * 1.25
    for _ in range(50):
        assert _delai_retry(20) <= DELAI_PLAFOND_RETRY * 1.25


@pytest.mark.parametrize("statut,motif", [(403, "acces_refuse"), (410, "ressource_supprimee"), (400, "requete_invalide")])
@responses.activate
def test_tu83_84_85_statuts_definitifs_sans_retry(statut, motif):
    # TU-83/84/85 : 403/410/400 -> 1 seul appel, motif explicite, pas de retry
    responses.add(responses.GET, URL_RECHERCHE, json={"message": "refus"}, status=statut)
    with _patch.object(_time, "sleep") as mock_sleep:
        resultat = appel_api("/datasets/search/", nb_tentatives=3)
    assert resultat.statut == "echec_technique"
    assert resultat.status_code == statut
    assert resultat.motif == motif
    assert resultat.nb_tentatives == 1
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


def _reponse_206_corps(corps: bytes):
    """Construit un body streaming dont iter_content produit `corps`."""
    import requests

    class _ReponseFausse:
        status_code = 206
        headers = {}

        def iter_content(self, chunk_size=8192):
            yield corps

        def close(self):
            pass

    return _ReponseFausse()


def test_tu86_reprise_range_sur_part_existant(tmp_path):
    # TU-86 : .part existant + 206 -> reprise a l'octet (header Range), contenu final complet
    destination = tmp_path / "fichier.csv"
    part = tmp_path / "fichier.csv.part"
    part.write_bytes(b"abcde")  # 5 octets deja telecharges
    corps_restant = b"fghij"

    with _patch("src.utils.http._SESSION") as mock_session:
        mock_session.get.return_value = _reponse_206_corps(corps_restant)
        resultat = telecharger_fichier("https://exemple.fr/fichier.csv", destination)

    assert resultat.reussi
    assert resultat.nb_tentatives == 1
    # Header Range envoye avec l'offset du .part
    _, kwargs = mock_session.get.call_args
    assert kwargs["headers"]["Range"] == "bytes=5-"
    # Contenu final = .part + suite
    assert destination.read_bytes() == b"abcdefghij"
    assert not part.exists()


def test_tu87_coupure_mid_stream_retry_et_part_conserve(tmp_path):
    # TU-87 : coupure mid-stream (ChunkedEncodingError) -> retry, .part conserve,
    # succes au 2e essai avec contenu complet
    import requests

    destination = tmp_path / "fichier.csv"

    class _ReponseCassee:
        status_code = 200
        headers = {}

        def iter_content(self, chunk_size=8192):
            yield b"abcde"
            raise requests.exceptions.ChunkedEncodingError("connexion coupee")

        def close(self):
            pass

    class _ReponseOK:
        status_code = 200
        headers = {}

        def iter_content(self, chunk_size=8192):
            yield b"abcde"
            yield b"fghij"

        def close(self):
            pass

    with _patch("src.utils.http._SESSION") as mock_session, _patch.object(_time, "sleep"):
        mock_session.get.side_effect = [_ReponseCassee(), _ReponseOK()]
        resultat = telecharger_fichier("https://exemple.fr/fichier.csv", destination)

    assert resultat.reussi
    assert resultat.nb_tentatives == 2
    assert destination.read_bytes() == b"abcdefghij"


def test_tu88_part_existant_reponse_200_ecrasement_propre(tmp_path):
    # TU-88 : .part existant + 200 (Range ignore) -> ecrasement, contenu = reponse seule
    destination = tmp_path / "fichier.csv"
    part = tmp_path / "fichier.csv.part"
    part.write_bytes(b"ancien contenu long")

    with _patch("src.utils.http._SESSION") as mock_session:
        reponse = _reponse_206_corps(b"nouveau")
        reponse.status_code = 200  # serveur ignore Range
        mock_session.get.return_value = reponse
        resultat = telecharger_fichier("https://exemple.fr/fichier.csv", destination)

    assert resultat.reussi
    assert destination.read_bytes() == b"nouveau"
    assert not part.exists()


@responses.activate
def test_tu89_echec_definitif_supprime_le_part(tmp_path):
    # TU-89 : 403 avec .part present -> .part supprime, aucun fichier final
    destination = tmp_path / "fichier.csv"
    part = tmp_path / "fichier.csv.part"
    part.write_bytes(b"donnees partielles")

    responses.add(responses.GET, "https://exemple.fr/fichier.csv", body=b"refus", status=403)
    with _patch.object(_time, "sleep"):
        resultat = telecharger_fichier("https://exemple.fr/fichier.csv", destination, nb_tentatives=3)

    assert resultat.statut == "echec_technique"
    assert resultat.motif == "acces_refuse"
    assert resultat.nb_tentatives == 1
    assert len(responses.calls) == 1  # pas de retry sur un 403
    assert not part.exists()
    assert not destination.exists()


def test_tu90_nb_tentatives_succes(tmp_path):
    # TU-90 : succes au 1er essai -> nb_tentatives=1 ; succes au 3e -> 3
    destination = tmp_path / "f.csv"
    with _patch("src.utils.http._SESSION") as mock_session, _patch.object(_time, "sleep"):
        import requests as _rq
        mock_session.get.side_effect = [
            _rq.exceptions.ConnectionError("ko"),
            _rq.exceptions.ConnectionError("ko"),
            _reponse_206_corps(b"ok"),
        ]
        # 3e reponse : statut 200 via _reponse_206_corps modifie
        reponse3 = _reponse_206_corps(b"ok")
        reponse3.status_code = 200
        mock_session.get.side_effect = [
            _rq.exceptions.ConnectionError("ko"),
            _rq.exceptions.ConnectionError("ko"),
            reponse3,
        ]
        resultat = telecharger_fichier("https://exemple.fr/f.csv", destination, nb_tentatives=3)
    assert resultat.reussi
    assert resultat.nb_tentatives == 3

    # Succes au 1er essai
    destination2 = tmp_path / "g.csv"
    with _patch("src.utils.http._SESSION") as mock_session:
        reponse = _reponse_206_corps(b"ok")
        reponse.status_code = 200
        mock_session.get.return_value = reponse
        resultat2 = telecharger_fichier("https://exemple.fr/g.csv", destination2)
    assert resultat2.reussi
    assert resultat2.nb_tentatives == 1
