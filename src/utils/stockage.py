# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : stockage.py
# Version      : 1
# Date         : 23-10-2026  (renommé de storage.py, T13.4)
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Stockage local des fichiers téléchargés (cf. docs/specs/stockage.md).

Arborescence : data/raw/<id_execution>/<id_ressource>_<nom>.<ext>.
L'id_execution (AAAAMMJJ_HHMMSS_<hash6>) isole chaque exécution et
permet de retrouver tous les fichiers d'une session.
"""
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def generer_id_execution() -> str:
    """Génère un identifiant d'exécution au format AAAAMMJJ_HHMMSS_<hash6>."""
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_court = uuid.uuid4().hex[:6]
    return f"{horodatage}_{hash_court}"


def nettoyer_nom_fichier(nom: str) -> str:
    """Nettoie un nom de fichier : séquences de caractères spéciaux
    remplacées par un seul tiret, sans tiret parasite autour de l'extension."""
    nettoye = re.sub(r"[^A-Za-z0-9._-]+", "-", nom.strip())
    nettoye = re.sub(r"-+(?=\.|$)", "", nettoye)
    return nettoye.strip("-") or "fichier"


def _nom_original_depuis_url(url: str) -> str:
    """Extrait le dernier segment de l'URL, sans query string."""
    chemin = urlparse(url).path
    return Path(chemin).name


def chemin_destination(
    id_execution: str,
    id_ressource: str,
    url: str,
    racine: Path = Path("data") / "raw",
) -> Path:
    """Construit le chemin de destination conforme a stockage.md.

    Format : data/raw/<id_execution>/<id_ressource>_<nom_fichier_original>.<ext>.
    Si l'URL n'a pas de nom exploitable, le nom retombe sur l'id seul.
    """
    nom_original = nettoyer_nom_fichier(_nom_original_depuis_url(url))
    prefixe = nettoyer_nom_fichier(id_ressource)
    if nom_original and nom_original != "fichier":
        nom_fichier = f"{prefixe}_{nom_original}"
    else:
        nom_fichier = prefixe
    return racine / nettoyer_nom_fichier(id_execution) / nom_fichier


def resoudre_collision(chemin: Path) -> Path:
    """Résout une collision de nom dans une même exécution (stockage.md §4).

    Si le chemin éxiste deja sur disque, un suffixe numérique est ajouté
    avant l'extension : fichier_1.csv, fichier_2.csv... Le premier chemin
    libre est retourné ; le fichier n'est jamais ecrasé.
    """
    if not chemin.exists():
        return chemin
    indice = 1
    while True:
        candidat = chemin.with_name(f"{chemin.stem}_{indice}{chemin.suffix}")
        if not candidat.exists():
            return candidat
        indice += 1


def lister_fichiers(id_execution: str, racine: Path = Path("data") / "raw") -> list:
    """Liste les fichiers acquis lors d'une exécution (stockage.md §3.1).

    Sert a retrouver tous les fichiers d'une session (synthese A4, CLI).
    Retourne une liste vide si l'exécution n'a aucun fichier.
    """
    repertoire = racine / nettoyer_nom_fichier(id_execution)
    if not repertoire.is_dir():
        return []
    # T10.8 : le manifeste d'acquisition n'est pas une donnée acquise.
    from src.core.manifeste import NOM_MANIFESTE

    return sorted(f for f in repertoire.iterdir() if f.is_file() and f.name != NOM_MANIFESTE)


def lister_acquisitions(id_execution: str, racine: Path = Path("data") / "raw") -> list:
    """Retourne les acquisitions manifestées d'une exécution (T10.8).

    Lit data/raw/<id_execution>/manifeste_acquisitions.json via le module
    manifeste (défensif : liste vide si absent ou illisible).
    """
    from src.core.manifeste import lire_manifeste

    manifeste = lire_manifeste(id_execution, racine)
    if not manifeste:
        return []
    return manifeste.get("acquisitions", [])
