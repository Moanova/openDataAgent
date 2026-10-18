# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : extraction.py
# Version      : 1
# Date         : 15-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Extraction paginée d'une ressource indexée vers le stockage local (T10.7).

Maillon B5->B7 du schéma de conception : la voie 1 (API tabulaire)
matérialise ici les données sur disque, en CSV, sous data/raw/, au même
endroit que la voie 2. La pagination est conduite par le code (le
consommateur n'a pas à paginer), avec un plafond de sécurité sur le
nombre de lignes extraites ; l'atteinte du plafond produit un succès
partiel explicite (troncature signalée), jamais un échec silencieux.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.resources import inventaire
from src.core.licences_descriptif import mention_attribution
from src.utils.http import interroger_ressource_api
from src.utils.logging import get_logger, bind_context, log_to_file
from src.utils.storage import chemin_destination, resoudre_collision

logger = get_logger("openDataAgent.core.extraction")

PLAFOND_EXTRACTION_DEFAUT = 10_000
TAILLE_PAGE_EXTRACTION_DEFAUT = 100


def _plafond_lignes() -> int:
    """Plafond de sécurité configurable par PLAFOND_EXTRACTION."""
    try:
        return int(os.environ.get("PLAFOND_EXTRACTION", PLAFOND_EXTRACTION_DEFAUT))
    except ValueError:
        return PLAFOND_EXTRACTION_DEFAUT


def _page_suivante(liens: Optional[Dict[str, Any]]) -> Optional[int]:
    """Extrait le numéro de page depuis links.next (URL complète ou numéro)."""
    if not liens:
        return None
    suivante = liens.get("next")
    if suivante is None:
        return None
    if isinstance(suivante, int):
        return suivante
    marqueur = "page="
    if marqueur in suivante:
        valeur = suivante.split(marqueur)[1].split("&")[0]
        if valeur.isdigit():
            return int(valeur)
    return None


def extraire_ressource(
    id_ressource: str,
    id_execution: Optional[str] = None,
    taille_page: int = TAILLE_PAGE_EXTRACTION_DEFAUT,
    plafond_lignes: Optional[int] = None,
) -> Dict[str, Any]:
    """Extrait une ressource indexée par l'API tabulaire vers un CSV local.

    Conduit la pagination de bout en bout (l'appelant n'a pas à paginer),
    agrège les lignes et écrit le résultat en data/raw/<id_execution>/.
    Gardes du contrat : identifiant délivré par la chaîne (convention 1),
    ressource indexée par l'API tabulaire.

    Args:
        id_ressource : Identifiant de la ressource, issu de lister_ressources.
        id_execution : Identifiant unique pour tracer l'exécution.
        taille_page : Lignes demandées par page à l'API (défaut 100).
        plafond_lignes : Nombre maximum de lignes extraites ; atteint, le
            fichier est tronqué et le succès est partiel (truncation signalée).
            Défaut : variable d'environnement PLAFOND_EXTRACTION (10 000).

    Returns:
        Dict[str, Any]: Résultat au format normalisé (statut/message/donnees).
    """
    if id_execution:
        bind_context(id_execution=id_execution)
    plafond = plafond_lignes if plafond_lignes is not None else _plafond_lignes()
    logger.info("Appel de extraire_ressource", id_ressource=id_ressource, plafond_lignes=plafond)
    log_to_file("Appel de extraire_ressource", id_ressource=id_ressource, plafond_lignes=plafond)

    if not id_ressource:
        logger.error("Erreur de paramètres : id_ressource est vide")
        return {
            "statut": "erreur_parametres",
            "message": "Le paramètre 'id_ressource' est obligatoire et ne peut être vide.",
            "donnees": {},
        }

    # Gardes du contrat : identifiant délivré par la chaîne, puis indexation.
    metadonnees = inventaire().get(id_ressource)
    if metadonnees is None:
        logger.error("Ressource jamais vue par l'inventaire", id_ressource=id_ressource)
        log_to_file("Ressource jamais vue par l'inventaire", id_ressource=id_ressource)
        return {
            "statut": "ressource_introuvable",
            "message": f"L'identifiant '{id_ressource}' n'a jamais été délivré par lister_ressources au cours du flux courant.",
            "donnees": {"suggestion": "reprendre par l'inventaire"},
        }
    if not metadonnees.get("api_tabulaire"):
        logger.error("Ressource non indexée par l'API tabulaire", id_ressource=id_ressource)
        log_to_file("Ressource non indexée par l'API tabulaire", id_ressource=id_ressource)
        return {
            "statut": "ressource_non_indexee",
            "message": f"La ressource '{id_ressource}' n'est pas indexée par l'API tabulaire.",
            "donnees": {"suggestion": "basculer sur telecharger_brut"},
        }

    if taille_page < 1:
        taille_page = TAILLE_PAGE_EXTRACTION_DEFAUT
        logger.warning("taille_page ajustée à la valeur par défaut", id_ressource=id_ressource)

    # Boucle de pagination : agrégation des lignes jusqu'à épuisement ou plafond.
    lignes: List[Dict[str, Any]] = []
    colonnes: List[str] = []
    total_lignes = 0
    page = 1
    tronque = False
    while True:
        logger.debug("Page d'extraction", id_ressource=id_ressource, page=page)
        resultat = interroger_ressource_api(
            id_ressource=id_ressource,
            page=page,
            taille_page=taille_page,
        )
        if not resultat.reussi:
            logger.error(
                "Échec de l'appel à l'API tabulaire",
                statut=resultat.statut,
                erreur=resultat.erreur,
                id_ressource=id_ressource,
                page=page,
            )
            log_to_file(
                "Échec de l'appel à l'API tabulaire",
                statut=resultat.statut,
                erreur=resultat.erreur,
                id_ressource=id_ressource,
                page=page,
            )
            return {
                "statut": resultat.statut,
                "message": f"Échec de l'extraction de '{id_ressource}' en page {page} : {resultat.erreur or resultat.statut}",
                "donnees": {"suggestion": "réessayer"},
            }
        donnees = resultat.donnees
        meta = donnees.get("meta") or {}
        total_lignes = meta.get("total", 0)
        page_lignes = donnees.get("data") or []
        if page == 1:
            # Colonnes déduites de la première page, ordre de l'API conservé.
            for ligne in page_lignes:
                colonnes = list(ligne.keys())
                break
        lignes.extend(page_lignes)
        if len(lignes) >= plafond:
            lignes = lignes[:plafond]
            tronque = True
            break
        suivante = _page_suivante(donnees.get("links"))
        if suivante is None:
            break
        page = suivante

    # Écriture du CSV pivot (data/raw/, même racine que la voie 2).
    identifiant = id_execution or ""
    destination = chemin_destination(
        id_execution=identifiant,
        id_ressource=id_ressource,
        url=metadonnees.get("url") or "",
    ).with_suffix(".csv")
    destination = resoudre_collision(destination)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="") as flux:
            if colonnes:
                ecrivain = csv.DictWriter(flux, fieldnames=colonnes, extrasaction="ignore")
                ecrivain.writeheader()
                ecrivain.writerows(lignes)
            else:
                flux.write("")
    except OSError as erreur:
        logger.error("Échec d'écriture du CSV", erreur=str(erreur), chemin=str(destination))
        log_to_file("Échec d'écriture du CSV", erreur=str(erreur), chemin=str(destination))
        return {
            "statut": "echec_technique",
            "message": f"Impossible d'écrire l'extraction vers '{destination}' : {erreur}",
            "donnees": {"suggestion": "réessayer"},
        }

    resultat_mention = mention_attribution(
        organisation=metadonnees.get("organisation"),
        licence=metadonnees.get("licence"),
        derniere_maj=metadonnees.get("derniere_maj"),
        licence_conditionnelle=bool(metadonnees.get("licence_conditionnelle", False)),
    )
    logger.info(
        "Extraction terminée",
        id_ressource=id_ressource,
        chemin=str(destination),
        total_lignes=total_lignes,
        lignes_ecrites=len(lignes),
        tronque=tronque,
    )
    log_to_file(
        "Extraction terminée",
        id_ressource=id_ressource,
        chemin=str(destination),
        total_lignes=total_lignes,
        lignes_ecrites=len(lignes),
        tronque=tronque,
    )
    message_sortie = "" if not tronque else \
        f"Extraction tronquée au plafond de {plafond} lignes ({total_lignes} lignes au total)."
    if resultat_mention["statut"] != "succes":
        message_sortie = (message_sortie + " " if message_sortie else "") + resultat_mention["message"]
    return {
        "statut": "succes",
        "message": message_sortie,
        "donnees": {
            "chemin_local": str(destination),
            "total_lignes": total_lignes,
            "lignes_ecrites": len(lignes),
            "colonnes": colonnes,
            "tronque": tronque,
            "licence": metadonnees.get("licence") or "",
            "licence_conditionnelle": bool(metadonnees.get("licence_conditionnelle", False)),
            "mention_attribution": resultat_mention["donnees"].get("mention"),
        },
    }
