# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : download.py
# Version      : 1
# Date         : 13-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Telechargement brut d'une ressource non indexée (voie 2, T3.4.1).

L'URL n'est jamais prise en argument : elle est résolue par le code à
partir des métadonnées enregistrées lors de l'inventaire (invariant du
contrat telecharger_brut). Chaque téléchargement est independant ; le
registre est alimenté même en cas d'echec.
"""
from typing import Any, Dict, Optional

from src.utils.logging import get_logger, bind_context, log_to_file
from src.utils.http import telecharger_fichier
from src.utils.storage import generer_id_execution, chemin_destination, resoudre_collision
from src.utils.registry import RegistreSourcesInaccessibles
from src.core.resources import inventaire
from src.core.licences_descriptif import mention_attribution
from src.core.manifeste import enregistrer_acquisition

logger = get_logger("openDataAgent.core.download")

_registre_par_defaut = RegistreSourcesInaccessibles()


def telecharger_brut(
    id_ressource: str,
    id_execution: Optional[str] = None,
    registre: Optional[RegistreSourcesInaccessibles] = None,
) -> Dict[str, Any]:
    """
    Télécharge une ressource dans son état brut vers le stockage local.

    Args:
        id_ressource (str): Identifiant de la ressource, issu de `lister_ressources`.
        id_execution (Optional[str]): Identifiant unique pour tracer l'exécution.
        registre (Optional[RegistreSourcesInaccessibles]): Registre des sources
            inaccessibles ; par defaut, l'instance globale sur data/registry.json.

    Returns:
        Dict[str, Any]: Resultat au format normalise (statut/message/donnees).
    """
    if registre is None:
        registre = _registre_par_defaut

    if id_execution:
        bind_context(id_execution=id_execution)

    logger.info("Appel de telecharger_brut", id_ressource=id_ressource)
    log_to_file("Appel de telecharger_brut", id_ressource=id_ressource)

    if not id_ressource:
        logger.error("Erreur de paramètres : id_ressource est vide")
        return {
            "statut": "erreur_parametres",
            "message": "Le paramètre 'id_ressource' est obligatoire et ne peut être vide.",
            "donnees": {},
        }

    # Resolution de l'URL depuis l'inventaire (jamais en argument).
    metadonnees = inventaire().get(id_ressource)
    if metadonnees is None:
        logger.error("Ressource jamais vue par l'inventaire", id_ressource=id_ressource)
        log_to_file("Ressource jamais vue par l'inventaire", id_ressource=id_ressource)
        return {
            "statut": "ressource_introuvable",
            "message": f"L'identifiant '{id_ressource}' n'a jamais été délivré par lister_ressources au cours du flux courant.",
            "donnees": {"suggestion": "reprendre par l'inventaire"},
        }

    url = metadonnees["url"]
    identifiant = id_execution or generer_id_execution()
    destination = resoudre_collision(chemin_destination(identifiant, id_ressource, url))

    logger.debug("Téléchargement en flux", url=url, destination=str(destination))
    log_to_file("Téléchargement en flux", url=url, destination=str(destination))

    resultat = telecharger_fichier(url, destination)

    if not resultat.reussi:
        # Invariant : le registre est alimenté meme en cas d'échec.
        registre.consigner_echec_technique(
            id_jeu=metadonnees.get("id_jeu") or "",
            organisation=metadonnees.get("organisation") or "",
            licence=metadonnees.get("licence") or "",
            url=url,
            detail=f"Statut HTTP {resultat.status_code}" if resultat.status_code else (resultat.erreur or "echec"),
        )
        registre.sauvegarder()
        logger.error(
            "Échec du téléchargement",
            url=url,
            statut=resultat.statut,
            status_code=resultat.status_code,
            erreur=resultat.erreur,
        )
        log_to_file(
            "Échec du téléchargement",
            url=url,
            statut=resultat.statut,
            status_code=resultat.status_code,
            erreur=resultat.erreur,
        )
        return {
            "statut": "echec_technique",
            "message": f"Le serveur d'origine a refusé l'accès ({resultat.status_code or resultat.erreur}).",
            "donnees": {"suggestion": "fichier_heberge_exterieurement"},
        }

    logger.info(
        "Téléchargement terminé",
        url=url,
        chemin_local=str(destination),
        taille_octets=destination.stat().st_size,
    )
    log_to_file(
        "Téléchargement terminé",
        url=url,
        chemin_local=str(destination),
        taille_octets=destination.stat().st_size,
    )

    resultat_mention = mention_attribution(
        organisation=metadonnees.get("organisation"),
        licence=metadonnees.get("licence"),
        derniere_maj=metadonnees.get("derniere_maj"),
        licence_conditionnelle=bool(metadonnees.get("licence_conditionnelle", False)),
    )
    donnees_sortie = {
        "chemin_local": str(destination),
        "format": metadonnees.get("format") or "",
        "licence": metadonnees.get("licence") or "",
        "licence_conditionnelle": bool(metadonnees.get("licence_conditionnelle", False)),
        "mention_attribution": resultat_mention["donnees"].get("mention"),
    }

    # T10.8 : traçabilité acquisition -> jeu dans le manifeste de l'exécution ;
    # un échec d'écriture ne fait jamais échouer le téléchargement.
    enregistrer_acquisition(
        identifiant,
        {
            "fichier": destination.name,
            "voie": "telechargement",
            "id_ressource": id_ressource,
            "titre_ressource": metadonnees.get("titre") or "",
            "id_jeu": metadonnees.get("id_jeu") or "",
            "titre_jeu": metadonnees.get("titre_jeu") or "",
            "organisation": metadonnees.get("organisation") or "",
            "url_jeu": metadonnees.get("url_jeu") or "",
            "url_source": url,
            "licence": metadonnees.get("licence") or "",
            "licence_conditionnelle": bool(metadonnees.get("licence_conditionnelle", False)),
            "mention_attribution": resultat_mention["donnees"].get("mention"),
        },
    )
    if resultat_mention["statut"] != "succes":
        logger.warning(
            "Mention d'attribution non generee",
            licence=metadonnees.get("licence"),
            statut_mention=resultat_mention["statut"],
        )
        log_to_file(
            "Mention d'attribution non generee",
            licence=metadonnees.get("licence"),
            statut_mention=resultat_mention["statut"],
            message=resultat_mention["message"],
        )
    return {
        "statut": "succes",
        "message": resultat_mention["message"] if resultat_mention["statut"] != "succes" else "",
        "donnees": donnees_sortie,
    }
