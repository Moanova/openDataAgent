# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : query.py
# Version      : 1
# Date         : 13-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Interrogation d'une ressource indexée par l'API tabulaire (voie 1, T3.3.1).

Garde du contrat : jamais appelée sur une ressource non indexée
(api_tabulaire faux -> ressource_non_indexee, bascule vers
telecharger_brut) ni sur une ressource jamais delivrée par l'inventaire
(ressource_introuvable). Recommandation de volume au-dela du seuil
configure (5000 par defaut) : volume_eleve_telechargement_brut_suggere.
"""
import os
from typing import Any, Dict, Optional

from src.utils.logging import get_logger, bind_context, log_to_file
from src.utils.http import interroger_ressource_api, profil_ressource_api
from src.core.resources import inventaire

logger = get_logger("openDataAgent.core.query")

SEUIL_VOLUME_ELEVE_DEFAUT = 5000


def _seuil_volume_eleve() -> int:
    try:
        return int(os.environ.get("SEUIL_VOLUME_ELEVE", SEUIL_VOLUME_ELEVE_DEFAUT))
    except ValueError:
        return SEUIL_VOLUME_ELEVE_DEFAUT


def _colonnes_depuis_data(donnees: Dict[str, Any], id_ressource: str) -> list:
    """Colonnes depuis la première ligne ; repli sur profile/ si data vide."""
    lignes = donnees.get("data") or []
    if lignes and isinstance(lignes[0], dict):
        return list(lignes[0].keys())
    profil = profil_ressource_api(id_ressource)
    if profil.reussi:
        entetes = (profil.donnees.get("profile") or {}).get("header") or []
        return list(entetes)
    return []


def _page_suivante_depuis_links(liens: Optional[Dict[str, Any]]) -> Optional[int]:
    """Extrait le numéro de page depuis l'URL `links.next` (T3.3.2).

    L'API tabulaire renvoie une URL complète (...&page=2) ou null sur
    la dernière page ; retourne l'entier ou None.
    """
    from urllib.parse import urlparse, parse_qs

    next_url = (liens or {}).get("next")
    if not next_url:
        return None
    numero = parse_qs(urlparse(next_url).query).get("page")
    return int(numero[0]) if numero else None


def interroger_ressource(
    id_ressource: str,
    page: int = 1,
    taille_page: int = 20,
    filtre: Optional[Dict[str, Any]] = None,
    tri: Optional[Dict[str, Any]] = None,
    id_execution: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extrait des données d'une ressource indexée par l'API tabulaire.

    Args:
        id_ressource (str): Identifiant de la ressource, issu de `lister_ressources`.
        page (int): Page demandée (defaut 1).
        taille_page (int): Lignes par page (defaut 20, max 50).
        filtre (Optional[dict]): {colonne, valeur, operateur} - une colonne à la fois.
        tri (Optional[dict]): {colonne, ordre} - ordre croissant|decroissant.
        id_execution (Optional[str]): Identifiant unique pour tracer l'exécution.

    Returns:
        Dict[str, Any]: Résultat au format normalisé (statut/message/donnees).
    """
    if id_execution:
        bind_context(id_execution=id_execution)

    logger.info(
        "Appel de interroger_ressource",
        id_ressource=id_ressource,
        page=page,
        taille_page=taille_page,
    )
    log_to_file(
        "Appel de interroger_ressource",
        id_ressource=id_ressource,
        page=page,
        taille_page=taille_page,
    )

    if not id_ressource:
        logger.error("Erreur de paramètres : id_ressource est vide")
        return {
            "statut": "erreur_parametres",
            "message": "Le paramètre 'id_ressource' est obligatoire et ne peut être vide.",
            "donnees": {},
        }

    # Gardes du contrat : identifiant delivré par la chaine, puis indexation.
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
        logger.error("Ressource non indexee par l'API tabulaire", id_ressource=id_ressource)
        log_to_file("Ressource non indexee par l'API tabulaire", id_ressource=id_ressource)
        return {
            "statut": "ressource_non_indexee",
            "message": f"La ressource '{id_ressource}' n'est pas indexée par l'API tabulaire.",
            "donnees": {"suggestion": "basculer sur telecharger_brut"},
        }

    if taille_page < 1 or taille_page > 50:
        taille_page = 20
        logger.warning("taille_page ajustee a la valeur par defaut (20)", id_ressource=id_ressource)

    logger.debug("Appel HTTP à l'API tabulaire", id_ressource=id_ressource, page=page)
    log_to_file("Appel HTTP à l'API tabulaire", id_ressource=id_ressource, page=page)

    resultat = interroger_ressource_api(
        id_ressource=id_ressource,
        page=page,
        taille_page=taille_page,
        filtre=filtre,
        tri=tri,
    )

    if not resultat.reussi:
        logger.error(
            "Échec de l'appel à l'API tabulaire",
            statut=resultat.statut,
            erreur=resultat.erreur,
            id_ressource=id_ressource,
        )
        log_to_file(
            "Échec de l'appel à l'API tabulaire",
            statut=resultat.statut,
            erreur=resultat.erreur,
            id_ressource=id_ressource,
        )
        return {
            "statut": resultat.statut,
            "message": f"Échec de l'interrogation de '{id_ressource}' : {resultat.erreur or resultat.statut}",
            "donnees": {
                "suggestion": "basculer sur telecharger_brut" if resultat.statut == "ressource_non_indexee" else "réessayer",
                # T7.1 (E4) : nombre de tentatives de l'appel HTTP.
                "nb_tentatives": resultat.nb_tentatives,
                # T7.7 (E3) : motif T7.1 exposé pour le circuit breaker agentique.
                "motif": resultat.motif,
            },
        }

    donnees = resultat.donnees
    meta = donnees.get("meta") or {}
    total_lignes = meta.get("total", 0)
    lignes = donnees.get("data") or []
    colonnes = _colonnes_depuis_data(donnees, id_ressource)
    page_suivante = _page_suivante_depuis_links(donnees.get("links"))

    reponse: Dict[str, Any] = {
        "statut": "succes",
        "message": "",
        "donnees": {
            "total_lignes": total_lignes,
            "colonnes": colonnes,
            "lignes": lignes,
            "page": meta.get("page", page),
            "page_suivante": page_suivante,
            # T7.1 (E4) : nombre de tentatives de l'appel HTTP.
            "nb_tentatives": resultat.nb_tentatives,
        },
    }

    # Recommandation de volume (T3.3.3) : au-dela du seuil, suggerer
    # la bascule vers telecharger_brut.
    if total_lignes > _seuil_volume_eleve():
        reponse["donnees"]["recommandation"] = "volume_eleve_telechargement_brut_suggere"

    logger.info(
        "Interrogation terminée",
        id_ressource=id_ressource,
        total_lignes=total_lignes,
        lignes_retournees=len(lignes),
        colonnes=len(colonnes),
    )
    log_to_file(
        "Interrogation terminée",
        id_ressource=id_ressource,
        total_lignes=total_lignes,
        lignes_retournees=len(lignes),
        colonnes=len(colonnes),
    )

    return reponse
