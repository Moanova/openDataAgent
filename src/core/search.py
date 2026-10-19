# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : search.py
# Version      : 1
# Date         : 12-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""
Module pour la recherche de jeux de données sur data.gouv.fr.
"""

from typing import List, Dict, Any, Optional
from src.utils.logging import get_logger, bind_context, log_to_file
from src.utils.http import rechercher_jeux_api
from src.core.licence import licence_est_acceptable, reinitialiser_politique
from src.core.resources import declarer_jeu_conditionnel
from src.utils.registry import RegistreSourcesInaccessibles
from src.utils.registre_acceptations import RegistreAcceptationsConditionnelles

# Initialiser le logger pour ce module
logger = get_logger("openDataAgent.core.search")

_registre_par_defaut = RegistreSourcesInaccessibles()
_registre_acceptations_par_defaut = RegistreAcceptationsConditionnelles()

# Badges uData (organization.badges) -> type d'organisation de la politique
# de licence (config/politique_licences.json).
_BADGES_VERS_TYPE = {
    "public-service": "service_public",
    "local-authority": "collectivite_territoriale",
}


def _nb_ressources(jeu: Dict[str, Any]) -> int:
    """Resout le nombre de ressources d'un jeu selon le format du payload.

    API v2 (T11.3) : `resources` est une sous-ressource paginee
    (dictionnaire rel/href/total) ; les autres formats (liste embarquee,
    ancienne v1 ou fixtures de test) restent toleres.
    """
    resources = jeu.get("resources")
    if isinstance(resources, dict):
        return int(resources.get("total") or 0)
    if isinstance(resources, list):
        return len(resources)
    return 0


def _type_organisation(jeu: Dict[str, Any]) -> Optional[str]:
    """Resout le type d'organisation depuis les badges de l'organisation.

    Le payload de recherche embarque `organization.badges` (kinds uData) :
    `public-service` (service public), `local-authority` (collectivite
    territoriale). Les autres badges (`certified`, etc.) ne sont pas des
    types. Sans badge pertinent, retourne None : l'organisation est
    consideree comme privee (comportement sur).
    """
    badges = ((jeu.get("organization") or {}).get("badges")) or []
    for badge in badges:
        type_org = _BADGES_VERS_TYPE.get(badge.get("kind"))
        if type_org:
            return type_org
    return None


def rechercher_jeux(
    mots_cles: List[str],
    tri: str = "pertinence",
    fenetre_maj: str = "toutes",
    limite: int = 10,
    page: int = 1,
    id_execution: Optional[str] = None,
    registre: Optional[RegistreSourcesInaccessibles] = None,
    registre_acceptations: Optional[RegistreAcceptationsConditionnelles] = None,
) -> Dict[str, Any]:
    """
    Recherche des jeux de données sur data.gouv.fr à partir de mots-clés.
    
    Args:
        mots_cles (List[str]): Liste de mots-clés pour la recherche.
        tri (str): Critère de tri (pertinence, recent, vues, reutilisations).
        fenetre_maj (str): Fenêtre de mise à jour (toutes, 30_jours, 12_mois, 3_ans).
        limite (int): Nombre maximum de jeux à retourner (défaut: 10, max: 20).
        page (int): Numéro de la page de résultats demandée (défaut : 1).
        id_execution (Optional[str]): Identifiant unique pour tracer l'exécution.
        registre (Optional[RegistreSourcesInaccessibles]): Registre des sources
            inaccessibles ; par défaut, l'instance globale sur data/registry.json.
    
    Returns:
        Dict[str, Any]: Résultat de la recherche au format normalisé.
    """
    if registre is None:
        registre = _registre_par_defaut
    if registre_acceptations is None:
        registre_acceptations = _registre_acceptations_par_defaut
    # Mettre à jour le contexte de logging avec l'id_execution
    if id_execution:
        bind_context(id_execution=id_execution)
    
    # Log de l'appel de la fonction (console + fichier)
    logger.info(
        "Appel de rechercher_jeux",
        mots_cles=mots_cles,
        tri=tri,
        fenetre_maj=fenetre_maj,
        limite=limite,
    )
    log_to_file(
        "Appel de rechercher_jeux",
        mots_cles=mots_cles,
        tri=tri,
        fenetre_maj=fenetre_maj,
        limite=limite,
    )
    
    # Validation des arguments
    if not mots_cles:
        logger.error("Erreur de paramètres : mots_cles est vide")
        return {
            "statut": "erreur_parametres",
            "message": "Le paramètre 'mots_cles' est obligatoire et ne peut être vide.",
            "donnees": {},
        }
    
    if limite < 1 or limite > 20:
        limite = 10
        logger.warning(
            "Limite ajustée à la valeur par défaut (10)",
            limite_demandee=limite,
        )

    # T11.3 : l'API v2 ne supporte pas la fenêtre de mise à jour (sondage S11.0) ;
    # le paramètre est déprécié au contrat (v1.3.0), accepté pour compatibilité mais
    # ignoré — signalé à l'appelant sans faire échouer la recherche.
    avertissement_fenetre = ""
    if fenetre_maj != "toutes":
        avertissement_fenetre = (
            "Le paramètre 'fenetre_maj' est déprécié et ignoré : "
            "l'API v2 de data.gouv.fr ne supporte pas la fenêtre de mise à jour."
        )
        logger.warning(
            "fenetre_maj deprecie et ignore (API v2)",
            fenetre_maj=fenetre_maj,
        )
        log_to_file("fenetre_maj deprecie et ignore (API v2)", fenetre_maj=fenetre_maj)
    
    # Appel reel a l'API data.gouv.fr via la couche HTTP (T3.1.1)
    try:
        # Log de début de l'appel HTTP (console + fichier)
        logger.debug("Appel HTTP à l'API data.gouv.fr")
        log_to_file("Appel HTTP à l'API data.gouv.fr")

        resultat = rechercher_jeux_api(
            mots_cles=mots_cles,
            tri=tri,
            fenetre_maj=fenetre_maj,
            limite=limite,
            page=page,
        )

        if not resultat.reussi:
            # Log de l'erreur (console + fichier)
            logger.error(
                "Échec de l'appel HTTP à data.gouv.fr",
                statut=resultat.statut,
                erreur=resultat.erreur,
                suggestion="Réessayer après 30 secondes",
            )
            log_to_file(
                "Échec de l'appel HTTP à data.gouv.fr",
                statut=resultat.statut,
                erreur=resultat.erreur,
                suggestion="Réessayer après 30 secondes",
            )
            return {
                "statut": resultat.statut,
                "message": f"Échec de l'appel à l'API data.gouv.fr : {resultat.erreur or resultat.statut}",
                "donnees": {
                    "suggestion": "réessayer",
                },
            }

        data = resultat.donnees

        # Filtre de licence avant tout retour (T3.1.2) et consignation
        # des exclusions au registre (T3.1.3) ; licences conditionnelles
        # (T7.5) : le type d'organisation (badges uData) active la derogation
        # notspecified pour un producteur public, avec marquage et consignation
        # au registre dedie.
        reinitialiser_politique()
        jeux_acceptes = []
        exclus_licence = 0
        acceptes_conditionnels = 0
        for jeu in data["data"]:
            licence = jeu.get("license")
            type_org = _type_organisation(jeu)
            if licence_est_acceptable(licence, type_organisation=type_org):
                conditionnelle = (
                    isinstance(licence, str)
                    and licence.strip().lower() == "notspecified"
                    and type_org is not None
                )
                if conditionnelle:
                    acceptes_conditionnels += 1
                    declarer_jeu_conditionnel(jeu["id"])
                    registre_acceptations.consigner_acceptation_conditionnelle(
                        id_jeu=jeu["id"],
                        organisation=(jeu.get("organization") or {}).get("name", ""),
                        type_organisation=type_org,
                        licence=licence or "notspecified",
                        url=jeu.get("page", ""),
                    )
                jeux_acceptes.append((jeu, conditionnelle))
            else:
                exclus_licence += 1
                registre.consigner_exclusion_juridique(
                    id_jeu=jeu["id"],
                    organisation=(jeu.get("organization") or {}).get("name", ""),
                    licence=licence or "notspecified",
                    url=jeu.get("page", ""),
                )
        if exclus_licence:
            registre.sauvegarder()
        if acceptes_conditionnels:
            registre_acceptations.sauvegarder()

        # Log du succès (console + fichier)
        logger.info(
            "Recherche terminée",
            total_trouves=data["total"],
            jeux_retournes=len(jeux_acceptes),
            exclus_licence=exclus_licence,
            acceptes_licence_conditionnelle=acceptes_conditionnels,
        )
        log_to_file(
            "Recherche terminée",
            total_trouves=data["total"],
            jeux_retournes=len(jeux_acceptes),
            exclus_licence=exclus_licence,
            acceptes_licence_conditionnelle=acceptes_conditionnels,
        )
        
        # Retour normalisé
        return {
            "statut": "succes",
            "message": avertissement_fenetre,
            "donnees": {
                "total_trouves": data["total"],
                "jeux": [
                    {
                        "id": jeu["id"],
                        "titre": jeu["title"],
                        "organisation": (jeu.get("organization") or {}).get("name", ""),
                        "licence": jeu["license"],
                        "licence_conditionnelle": conditionnelle,
                        "derniere_maj": jeu.get("last_update"),
                        "nb_ressources": _nb_ressources(jeu),
                        "url": jeu.get("page", ""),
                    }
                    for jeu, conditionnelle in jeux_acceptes
                ],
                "exclus_licence": exclus_licence,
                "acceptes_licence_conditionnelle": acceptes_conditionnels,
                "page_courante": page,
                "page_suivante": data.get("page_suivante"),
            },
        }
        
    except Exception as e:
        # Log d'une erreur inattendue (console + fichier)
        logger.error(
            "Erreur inattendue lors de la recherche",
            erreur=str(e),
        )
        log_to_file(
            "Erreur inattendue lors de la recherche",
            erreur=str(e),
        )
        return {
            "statut": "echec_technique",
            "message": f"Erreur inattendue : {str(e)}",
            "donnees": {},
        }