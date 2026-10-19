# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : resources.py
# Version      : 1
# Date         : 13-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Inventaire des ressources d'un jeu de données (lister_ressources, T3.2.1).

L'appel enregistre les métadonnées de chaque ressource (invariant du
contrat) dans un inventaire en mémoire : c'est ce qui arme
`telecharger_brut` et `interroger_ressource` ensuite, et qui permet de
refuser tout identifiant jamais delivré par la chaine.
"""
from typing import Any, Dict, Optional

from src.utils.logging import get_logger, bind_context, log_to_file
from src.utils.registry import RegistreSourcesInaccessibles
from src.utils.registre_acceptations import RegistreAcceptationsConditionnelles
from src.core.licence import reinitialiser_politique
from src.core.classification import classer_ressource
from src.utils.http import lister_ressources_api, est_indexee_api_tabulaire

logger = get_logger("openDataAgent.core.resources")

_registre_par_defaut = RegistreSourcesInaccessibles()

# Jeux acceptes sous licence conditionnelle (T7.5) : peuples par
# rechercher_jeux, consultes par lister_ressources pour propager le
# marquage jusqu'aux ressources (puis les deux voies d'acquisition).
_jeux_conditionnels: Dict[str, bool] = {}


def declarer_jeu_conditionnel(id_jeu: str) -> None:
    """Marque un jeu comme accepte sous licence conditionnelle (T7.5)."""
    _jeux_conditionnels[id_jeu] = True

# Inventaire en mémoire : id_ressource -> métadonnées normalisées.
# Peuplé a chaque appel de lister_ressources, consommé par telecharger_brut
# (T3.4.1) et interroger_ressource (T3.3.1).
_inventaire: Dict[str, Dict[str, Any]] = {}

# Métadonnées du jeu en cours d'inventaire (id, licence) ; positionnées
# le temps de l'appel a lister_ressources.
_jeu_courant: Dict[str, Any] = {}


def inventaire() -> Dict[str, Dict[str, Any]]:
    """Retourne une copie de l'inventaire des ressources déjà vues."""
    return dict(_inventaire)


def decharger_inventaire() -> Dict[str, Dict[str, Any]]:
    """Retourne une copie sérialisable de l'inventaire (persistance T10.2).

    Les métadonnées de jeu (id_jeu, organisation, licence) sont
    dénormalisées dans chaque ressource : ce dump suffit à armer
    telecharger_brut et interroger_ressource lors d'un rechargement.
    """
    return {id_ressource: dict(metadonnees) for id_ressource, metadonnees in _inventaire.items()}


def charger_inventaire(donnees: Dict[str, Dict[str, Any]]) -> int:
    """Fusionne un inventaire sérialisé dans l'inventaire en mémoire.

    Enrichissement cumulatif : les entrées existantes ne sont pas
    écrasées, les nouvelles sont ajoutées. Retourne le nombre de
    ressources ajoutées.
    """
    ajoutees = 0
    for id_ressource, metadonnees in donnees.items():
        if id_ressource not in _inventaire:
            _inventaire[id_ressource] = dict(metadonnees)
            ajoutees += 1
    return ajoutees


def _normaliser_ressource(ressource: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise une ressource v1 vers le format RessourceResume du contrat."""
    classe, _ = classer_ressource(
        format_ressource=ressource.get("format"),
        mime=ressource.get("mime"),
        url=ressource.get("url"),
    )
    return {
        "id": ressource["id"],
        "id_jeu": _jeu_courant.get("id"),
        "organisation": _jeu_courant.get("organisation"),
        "titre": ressource["title"],
        # T10.8 : métadonnées de jeu dénormalisées (titre, url) pour le
        # manifeste d'acquisition ; sérialisées avec l'inventaire T10.2.
        "titre_jeu": _jeu_courant.get("titre"),
        "url_jeu": _jeu_courant.get("url", ""),
        "format": ressource.get("format"),
        "taille_octets": ressource.get("filesize"),
        "classe": classe,
        # Detection API tabulaire (T3.3.1) : ping /resources/{rid}/ ;
        # seulement pour les fichiers tabulaires (les autres ne sont
        # jamais interrogeables), echec reseau -> non indexee (sur).
        "api_tabulaire": classe == "fichier_tabulaire" and est_indexee_api_tabulaire(ressource["id"]),
        # v1 : filetype "file" = heberge sur la plateforme, "remote" sinon.
        "heberge_sur_plateforme": ressource.get("filetype") == "file",
        "url": ressource["url"],
        # La licence suit le fichier jusqu'a la visualisation (contrat telecharger_brut).
        "licence": _jeu_courant.get("licence"),
        # T7.5 : le marquage conditionnel et la date de mise a jour suivent
        # la licence jusqu'a la mention d'attribution (partie 2).
        "licence_conditionnelle": _jeu_courant.get("licence_conditionnelle", False),
        "derniere_maj": _jeu_courant.get("derniere_maj"),
    }


def lister_ressources(
    id_jeu: str,
    id_execution: Optional[str] = None,
    registre: Optional[RegistreSourcesInaccessibles] = None,
) -> Dict[str, Any]:
    """
    Inventorie les ressources d'un jeu de données data.gouv.fr.

    Args:
        id_jeu (str): Identifiant du jeu, issu de `rechercher_jeux`.
        id_execution (Optional[str]): Identifiant unique pour tracer l'exécution.
        registre (Optional[RegistreSourcesInaccessibles]): Registre des sources
            inaccessibles ; par defaut, l'instance globale sur data/registry.json.

    Returns:
        Dict[str, Any]: Resultat au format normalisé (statut/message/donnees).
    """
    if registre is None:
        registre = _registre_par_defaut

    if id_execution:
        bind_context(id_execution=id_execution)

    logger.info("Appel de lister_ressources", id_jeu=id_jeu)
    log_to_file("Appel de lister_ressources", id_jeu=id_jeu)

    if not id_jeu:
        logger.error("Erreur de parametres : id_jeu est vide")
        return {
            "statut": "erreur_parametres",
            "message": "Le paramètre 'id_jeu' est obligatoire et ne peut être vide.",
            "donnees": {},
        }

    logger.debug("Appel HTTP à l'API data.gouv.fr", id_jeu=id_jeu)
    log_to_file("Appel HTTP à l'API data.gouv.fr", id_jeu=id_jeu)

    resultat = lister_ressources_api(id_jeu=id_jeu)

    if not resultat.reussi:
        logger.error(
            "Échec de l'appel HTTP à data.gouv.fr",
            statut=resultat.statut,
            erreur=resultat.erreur,
            id_jeu=id_jeu,
        )
        log_to_file(
            "Échec de l'appel HTTP à data.gouv.fr",
            statut=resultat.statut,
            erreur=resultat.erreur,
            id_jeu=id_jeu,
        )
        return {
            "statut": resultat.statut,
            "message": f"Échec de l'inventaire du jeu {id_jeu} : {resultat.erreur or resultat.statut}",
            "donnees": {
                "suggestion": "reprendre à rechercher_jeux" if resultat.statut == "jeu_introuvable" else "réessayer",
            },
        }

    data = resultat.donnees
    global _jeu_courant
    _jeu_courant = {
        "id": id_jeu,
        "licence": data.get("license"),
        "organisation": (data.get("organization") or {}).get("name", ""),
        "derniere_maj": data.get("last_update"),
        "licence_conditionnelle": bool(_jeux_conditionnels.get(id_jeu, False)),
        # T10.8 : titre et URL du jeu nécessaires au manifeste d'acquisition
        # (traçabilité fichier -> jeu) ; présents dans le payload v2.
        "titre": data.get("title"),
        "url": data.get("page", ""),
    }
    ressources_normalisees = [_normaliser_ressource(r) for r in data.get("resources", [])]

    # Invariant du contrat : l'appel enregistre les métadonnées de chaque
    # ressource ; c'est ce qui rend telecharger_brut possible ensuite.
    for ressource in ressources_normalisees:
        _inventaire[ressource["id"]] = ressource

    indetermination = [r["id"] for r in ressources_normalisees if r["classe"] == "indetermine"]

    logger.info(
        "Inventaire terminé",
        id_jeu=id_jeu,
        ressources=len(ressources_normalisees),
        indeterminees=len(indetermination),
    )
    log_to_file(
        "Inventaire terminé",
        id_jeu=id_jeu,
        ressources=len(ressources_normalisees),
        indeterminees=len(indetermination),
    )

    return {
        "statut": "succes",
        "message": "",
        "donnees": {
            "ressources": ressources_normalisees,
            "indetermination": indetermination,
        },
    }
