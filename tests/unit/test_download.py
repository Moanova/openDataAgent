# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_download.py
# Version      : 1
# Date         : 13-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du telechargement brut (src/core/download.py, T3.4.1).

Sans reseau (`responses`). L'inventaire requis par le contrat est
peuple via un appel simule a lister_ressources (chaine TI-05).
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import responses

from src.core.download import telecharger_brut
from src.core.resources import lister_ressources
from src.utils.registry import RegistreSourcesInaccessibles
from src.utils.storage import chemin_destination, nettoyer_nom_fichier

URL_JEU = "https://www.data.gouv.fr/api/1/datasets/jeu-t/"
URL_FICHIER = "https://exemple.fr/donnees/budget-2024.csv"


@pytest.fixture
def registre(tmp_path) -> RegistreSourcesInaccessibles:
    return RegistreSourcesInaccessibles(chemin=tmp_path / "registry.json")


@pytest.fixture
def inventaire_peuple(registre, tmp_path):
    """Peuple l'inventaire via un appel simule a lister_ressources (chaine TI-05)."""
    reponse_api = {
        "id": "jeu-t",
        "title": "Jeu T",
        "license": "lov2",
        "resources": [
            {
                "id": "res-1",
                "title": "Budget 2024",
                "url": URL_FICHIER,
                "format": "csv",
                "mime": "text/csv",
                "filesize": 100,
            }
        ],
    }
    with patch("src.core.resources.est_indexee_api_tabulaire", return_value=False), responses.mock:
        responses.add(responses.GET, URL_JEU, json=reponse_api, status=200)
        lister_ressources("jeu-t", registre=registre)
    return reponse_api


def test_chaine_inventaire_telechargement(inventaire_peuple, registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-05 (chaîne inventaire → téléchargement → fichier écrit, statut succes, chemin et format exacts)
    monkeypatch.chdir(tmp_path)
    with responses.mock:
        responses.add(responses.GET, URL_FICHIER, body=b"col1,col2\na,b\n", status=200)
        reponse = telecharger_brut("res-1", id_execution="20261013_120000_abc123", registre=registre)

    assert reponse["statut"] == "succes"
    chemin = Path(reponse["donnees"]["chemin_local"])
    assert chemin.exists()
    assert chemin.read_bytes() == b"col1,col2\na,b\n"
    assert chemin.name == "res-1_budget-2024.csv"
    assert chemin.parent.name == "20261013_120000_abc123"
    assert chemin.parent.parent.name == "raw"
    assert reponse["donnees"]["format"] == "csv"
    assert reponse["donnees"]["licence"] == "lov2"


def test_sans_inventaire_prealable(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-06 (sans inventaire préalable → ressource_introuvable, aucune écriture disque)
    monkeypatch.chdir(tmp_path)
    reponse = telecharger_brut("res-jamais-vue", registre=registre)

    assert reponse["statut"] == "ressource_introuvable"
    assert reponse["donnees"]["suggestion"] == "reprendre par l'inventaire"
    assert not (tmp_path / "data").exists()


def test_refus_serveur_registre_et_aucune_ecriture(inventaire_peuple, registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TI-07 (refus serveur → echec_technique, registre motif serveur_origine_bloque, aucune écriture partielle)
    monkeypatch.chdir(tmp_path)
    with responses.mock:
        responses.add(responses.GET, URL_FICHIER, body=b"acces refuse", status=403)
        reponse = telecharger_brut("res-1", id_execution="20261013_120000_def456", registre=registre)

    assert reponse["statut"] == "echec_technique"
    assert reponse["donnees"]["suggestion"] == "fichier_heberge_exterieurement"

    entrees = registre.rapport_pour_agent()["sources_inaccessibles"]
    assert len(entrees) == 1
    assert entrees[0]["motif"] == "serveur_origine_bloque"
    assert entrees[0]["url"] == URL_FICHIER
    assert entrees[0]["licence"] == "lov2"

    # Aucune ecriture partielle : ni fichier ni .part
    raw = tmp_path / "data" / "raw"
    assert not raw.exists() or not any(raw.rglob("*"))


def test_erreur_reseau_echec_propre(inventaire_peuple, registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TB-05 simulé (échec réseau → échec propre, registre alimenté, pas de crash)
    from requests.exceptions import ConnectionError as ErreurConnexion

    monkeypatch.chdir(tmp_path)
    with responses.mock:
        for _ in range(3):
            responses.add(responses.GET, URL_FICHIER, body=ErreurConnexion("injoignable"))
        reponse = telecharger_brut("res-1", id_execution="20261013_120000_ghi789", registre=registre)

    assert reponse["statut"] == "echec_technique"
    assert len(registre.rapport_pour_agent()["sources_inaccessibles"]) == 1


def test_429_puis_succes(inventaire_peuple, registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-20 transposé au téléchargement (429 → reprise puis succès)
    monkeypatch.chdir(tmp_path)
    with responses.mock:
        responses.add(responses.GET, URL_FICHIER, body=b"", status=429)
        responses.add(responses.GET, URL_FICHIER, body=b"donnees completes", status=200)
        reponse = telecharger_brut("res-1", id_execution="20261013_120000_jkl012", registre=registre)

    assert reponse["statut"] == "succes"
    assert Path(reponse["donnees"]["chemin_local"]).read_bytes() == b"donnees completes"


def test_nom_fichier_nettoye():
    # Test annexe : URL avec caractères spéciaux → nom de fichier valide
    chemin = chemin_destination("exec-1", "res-x", "https://exemple.fr/données/budget 2024!.csv")
    assert chemin.name == "res-x_budget-2024.csv"


def test_url_sans_nom_exploitable():
    # Test annexe : URL sans segment final exploitable → nom retombé sur l'id
    chemin = chemin_destination("exec-1", "res-y", "https://api.exemple.fr/v1/data/DD_CNA_APU_CSV_FR")
    assert chemin.name == "res-y_DD_CNA_APU_CSV_FR"


def test_id_execution_distincts(inventaire_peuple, registre, tmp_path, monkeypatch):
    # Test annexe : deux exécutions → deux arborescences, aucun écrasement
    monkeypatch.chdir(tmp_path)
    with responses.mock:
        responses.add(responses.GET, URL_FICHIER, body=b"premiere", status=200)
        premiere = telecharger_brut("res-1", id_execution="20261013_120000_aaa111", registre=registre)
        responses.add(responses.GET, URL_FICHIER, body=b"seconde", status=200)
        seconde = telecharger_brut("res-1", id_execution="20261013_130000_bbb222", registre=registre)

    assert premiere["donnees"]["chemin_local"] != seconde["donnees"]["chemin_local"]
    assert Path(premiere["donnees"]["chemin_local"]).read_bytes() == b"premiere"
    assert Path(seconde["donnees"]["chemin_local"]).read_bytes() == b"seconde"


def test_collision_meme_execution_suffixe_numerique(inventaire_peuple, registre, tmp_path, monkeypatch):
    # Réf. docs/specs/stockage.md §4 (même nom dans une même exécution → suffixe numérique, jamais d'écrasement)
    monkeypatch.chdir(tmp_path)
    with responses.mock:
        responses.add(responses.GET, URL_FICHIER, body=b"copie-1", status=200)
        premiere = telecharger_brut("res-1", id_execution="20261013_140000_ccc333", registre=registre)
        responses.add(responses.GET, URL_FICHIER, body=b"copie-2", status=200)
        seconde = telecharger_brut("res-1", id_execution="20261013_140000_ccc333", registre=registre)
        responses.add(responses.GET, URL_FICHIER, body=b"copie-3", status=200)
        troisieme = telecharger_brut("res-1", id_execution="20261013_140000_ccc333", registre=registre)

    assert premiere["donnees"]["chemin_local"].endswith("res-1_budget-2024.csv")
    assert seconde["donnees"]["chemin_local"].endswith("res-1_budget-2024_1.csv")
    assert troisieme["donnees"]["chemin_local"].endswith("res-1_budget-2024_2.csv")

    # Aucune perte : les trois copies coexistent avec leur contenu
    assert Path(premiere["donnees"]["chemin_local"]).read_bytes() == b"copie-1"
    assert Path(seconde["donnees"]["chemin_local"]).read_bytes() == b"copie-2"
    assert Path(troisieme["donnees"]["chemin_local"]).read_bytes() == b"copie-3"


def test_lister_fichiers_execution(inventaire_peuple, registre, tmp_path, monkeypatch):
    # Réf. docs/specs/stockage.md §3.1 (retrouver tous les fichiers d'une session)
    from src.utils.storage import lister_fichiers

    monkeypatch.chdir(tmp_path)
    with responses.mock:
        responses.add(responses.GET, URL_FICHIER, body=b"a", status=200)
        telecharger_brut("res-1", id_execution="20261013_150000_ddd444", registre=registre)

    fichiers = lister_fichiers("20261013_150000_ddd444")
    assert len(fichiers) == 1
    assert fichiers[0].name == "res-1_budget-2024.csv"

    assert lister_fichiers("execution_inexistante") == []


# ---------------------------------------------------------------------
# Formats non tabulaires (T5.1.5) : chaine inventaire -> telechargement
# -> persistance, pour ZIP, GeoJSON, JSON, SHP, PDF.
# ---------------------------------------------------------------------

import io
import zipfile


def _contenu_zip():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("donnees.csv", "col1,col2\na,b\n")
    return tampon.getvalue()


CONTENUS_FORMATS = {
    "zip": _contenu_zip(),
    "geojson": json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [2.35, 48.85]}, "properties": {"nom": "Paris"}}]}).encode("utf-8"),
    "json": json.dumps({"cle": "valeur", "liste": [1, 2, 3]}).encode("utf-8"),
    "shp": bytes([0x00, 0x00, 0x27, 0x0A, 0xFF, 0xFE, 0x0D, 0x0A, 0x1A, 0x00]),
    "pdf": b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF",
}

MIMES_FORMATS = {
    "zip": "application/zip",
    "geojson": "application/geo+json",
    "json": "application/json",
    "shp": "application/octet-stream",
    "pdf": "application/pdf",
}


def _inventaire_avec_ressource(registre, tmp_path, id_ressource, titre, url, format_ressource, mime):
    reponse_api = {
        "id": "jeu-f",
        "title": "Jeu Formats",
        "license": "lov2",
        "resources": [
            {"id": id_ressource, "title": titre, "url": url, "format": format_ressource, "mime": mime, "filesize": None}
        ],
    }
    url_jeu = URL_JEU.replace("jeu-t", "jeu-f")
    with patch("src.core.resources.est_indexee_api_tabulaire", return_value=False), responses.mock:
        responses.add(responses.GET, url_jeu, json=reponse_api, status=200)
        lister_ressources("jeu-f", registre=registre)
    return reponse_api


@pytest.mark.parametrize("format_ressource", ["zip", "geojson", "json", "shp", "pdf"])
def test_format_non_tabulaire_chaine_complete(format_ressource, registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-40..TU-44 (section 3.9) — persistance octet-octet, chemin valide, format retourné
    monkeypatch.chdir(tmp_path)
    url = f"https://exemple.fr/donnees/parcelles.{format_ressource}"
    _inventaire_avec_ressource(registre, tmp_path, "res-nt", f"Parcelles {format_ressource}", url, format_ressource, MIMES_FORMATS[format_ressource])
    contenu = CONTENUS_FORMATS[format_ressource]
    with responses.mock:
        responses.add(responses.GET, url, body=contenu, status=200)
        reponse = telecharger_brut("res-nt", id_execution="20261014_formats", registre=registre)
    assert reponse["statut"] == "succes", reponse
    chemin = Path(reponse["donnees"]["chemin_local"])
    assert chemin.exists()
    assert chemin.read_bytes() == contenu
    assert chemin.parent.name == "20261014_formats"
    assert reponse["donnees"]["format"] == format_ressource
    assert reponse["donnees"]["licence"] == "lov2"


def test_zip_telecharge_est_une_archive_valide(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-40 (section 3.9) — intégrité de l'archive écrite
    monkeypatch.chdir(tmp_path)
    url = "https://exemple.fr/donnees/parcelles.zip"
    _inventaire_avec_ressource(registre, tmp_path, "res-zip", "Parcelles ZIP", url, "zip", "application/zip")
    with responses.mock:
        responses.add(responses.GET, url, body=CONTENUS_FORMATS["zip"], status=200)
        reponse = telecharger_brut("res-zip", id_execution="20261014_zip", registre=registre)
    chemin = Path(reponse["donnees"]["chemin_local"])
    with zipfile.ZipFile(chemin) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == ["donnees.csv"]
        assert archive.read("donnees.csv") == b"col1,col2\na,b\n"


def test_geojson_telecharge_est_du_json_valide(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-41 (section 3.9) — parsing du GeoJSON écrit
    monkeypatch.chdir(tmp_path)
    url = "https://exemple.fr/donnees/quartiers.geojson"
    _inventaire_avec_ressource(registre, tmp_path, "res-gj", "Quartiers GeoJSON", url, "geojson", "application/geo+json")
    with responses.mock:
        responses.add(responses.GET, url, body=CONTENUS_FORMATS["geojson"], status=200)
        reponse = telecharger_brut("res-gj", id_execution="20261014_gj", registre=registre)
    chemin = Path(reponse["donnees"]["chemin_local"])
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert contenu["type"] == "FeatureCollection"
    assert len(contenu["features"]) == 1
    assert contenu["features"][0]["geometry"]["type"] == "Point"


def test_mime_zip_format_inconnu(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-45 (section 3.9) — le mime application/zip suffit à l'acquisition
    monkeypatch.chdir(tmp_path)
    url = "https://exemple.fr/donnees/archive-mystere"
    _inventaire_avec_ressource(registre, tmp_path, "res-mk", "Archive mystere", url, "format inconnu", "application/zip")
    with responses.mock:
        responses.add(responses.GET, url, body=CONTENUS_FORMATS["zip"], status=200)
        reponse = telecharger_brut("res-mk", id_execution="20261014_mk", registre=registre)
    assert reponse["statut"] == "succes"
    assert Path(reponse["donnees"]["chemin_local"]).read_bytes() == CONTENUS_FORMATS["zip"]


def test_contenu_binaire_non_utf8(registre, tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-46 (section 3.9) — octets invalides en UTF-8 : aucune erreur de décodage
    monkeypatch.chdir(tmp_path)
    url = "https://exemple.fr/donnees/binaire.shp"
    contenu = bytes([0x89, 0x50, 0x4E, 0x47, 0xFF, 0xFE, 0x80, 0x9F, 0xC3, 0x28])
    _inventaire_avec_ressource(registre, tmp_path, "res-bin", "Binaire SHP", url, "shp", "application/octet-stream")
    with responses.mock:
        responses.add(responses.GET, url, body=contenu, status=200)
        reponse = telecharger_brut("res-bin", id_execution="20261014_bin", registre=registre)
    assert reponse["statut"] == "succes"
    assert Path(reponse["donnees"]["chemin_local"]).read_bytes() == contenu


@responses.activate
def test_mention_attribution_dans_telechargement(registre, tmp_path, monkeypatch):
    # Réf. T7.5 : la mention d'attribution suit le fichier jusqu'à la visualisation
    from src.core.resources import inventaire
    inventaire().clear() if False else None
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    module_resources._inventaire["res-1"] = {
        "id": "res-1",
        "id_jeu": "jeu-t",
        "organisation": "Ministère de l'Économie",
        "titre": "Budget 2024",
        "format": "csv",
        "url": "https://static.data.gouv.fr/res-1.csv",
        "licence": "lov2",
        "licence_conditionnelle": False,
        "derniere_maj": "2026-09-30T16:42:11.000000+00:00",
    }
    responses.add(responses.GET, "https://static.data.gouv.fr/res-1.csv", body="a;b\n1;2\n", status=200)
    monkeypatch.chdir(tmp_path)
    reponse = telecharger_brut("res-1", registre=registre)
    assert reponse["statut"] == "succes"
    donnees = reponse["donnees"]
    assert donnees["licence"] == "lov2"
    assert donnees["licence_conditionnelle"] is False
    mention = donnees["mention_attribution"]
    assert mention is not None
    assert "Ministère de l'Économie" in mention
    assert "Licence Ouverte / Open Licence 2.0 (Etalab)" in mention
    assert "2026-09-30" in mention


@responses.activate
def test_mention_nulle_pour_licence_a_verifier(registre, tmp_path, monkeypatch):
    # other-open : jamais devinée — mention null, téléchargement réussi
    import src.core.resources as module_resources
    module_resources._inventaire.clear()
    module_resources._inventaire["res-2"] = {
        "id": "res-2",
        "id_jeu": "jeu-u",
        "organisation": "Association X",
        "titre": "Jeu U",
        "format": "csv",
        "url": "https://static.data.gouv.fr/res-2.csv",
        "licence": "other-open",
        "licence_conditionnelle": False,
        "derniere_maj": None,
    }
    responses.add(responses.GET, "https://static.data.gouv.fr/res-2.csv", body="a;b\n1;2\n", status=200)
    monkeypatch.chdir(tmp_path)
    reponse = telecharger_brut("res-2", registre=registre)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["mention_attribution"] is None
    assert reponse["message"] != ""  # message explicite de vérification
