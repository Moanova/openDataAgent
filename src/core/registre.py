# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : registre.py
# Version      : 1
# Date         : 22-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Consultation du registre des sources inaccessibles (T11.4).

Outil agentique `consulter_registre` : lecture seule du registre
persistant `data/registre_sources.json` (toutes exécutions confondues), pour
donner à l'agent une mémoire cross-session des sources déjà écartées.
Le rapport est limitable (`derniere_n`) et filtrable (`motif`) pour
maîtriser sa taille. Aucune fonction exposée ne modifie le registre
(invariant du contrat global).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.contracts.consulter_registre import MotifRegistre
from src.utils.journalisation import bind_context, get_logger, log_to_file
from src.utils.registre_sources import RegistreSourcesInaccessibles

logger = get_logger("openDataAgent.core.registre")

DERNIERE_N_DEFAUT = 20

_registre_par_defaut = RegistreSourcesInaccessibles()


def consulter_registre(
    derniere_n: int = DERNIERE_N_DEFAUT,
    motif: Optional[str] = None,
    id_execution: Optional[str] = None,
    registre: Optional[RegistreSourcesInaccessibles] = None,
) -> Dict[str, Any]:
    """Retourne un rapport limité/filtré du registre des sources inaccessibles.

    Lecture seule : le registre n'est ni modifié ni sauvegardé. Un registre
    absent ou illisible produit un rapport vide (`succes`), jamais une
    exception (cohérent avec le chargement défensif du registre).

    Args:
        derniere_n : Nombre maximum d'entrées retournées (les plus
            récentes, ordre chronologique conservé). Défaut 20.
        motif : Filtre optionnel (`licence_incompatible` ou
            `serveur_origine_bloque`).
        id_execution : Identifiant unique pour tracer l'exécution.
        registre : Registre à lire ; par défaut, l'instance globale sur
            data/registre_sources.json.

    Returns:
        Dict[str, Any]: Réponse normalisée {statut, message, donnees} ;
        donnees contient sources_inaccessibles, total (taille réelle du
        registre, hors limite et hors filtre) et nb_retournees.
    """
    if id_execution:
        bind_context(id_execution=id_execution)
    if registre is None:
        registre = _registre_par_defaut

    logger.info("Appel de consulter_registre", derniere_n=derniere_n, motif=motif)
    log_to_file("Appel de consulter_registre", derniere_n=derniere_n, motif=motif)

    if derniere_n < 1:
        logger.error("Erreur de paramètres : derniere_n doit être >= 1")
        return {
            "statut": "erreur_parametres",
            "message": "Le paramètre 'derniere_n' doit être un entier >= 1.",
            "donnees": {},
        }
    if motif is not None:
        try:
            motif = MotifRegistre(motif).value
        except ValueError:
            valeurs = [m.value for m in MotifRegistre]
            logger.error("Erreur de paramètres : motif inconnu", motif=motif)
            return {
                "statut": "erreur_parametres",
                "message": f"Le paramètre 'motif' doit être l'un de : {valeurs}.",
                "donnees": {},
            }

    entrees = registre.rapport_pour_agent()["sources_inaccessibles"]
    total = len(entrees)
    if motif is not None:
        entrees = [e for e in entrees if e.get("motif") == motif]
    entrees = entrees[-derniere_n:]

    logger.info(
        "Registre consulté",
        total=total,
        nb_retournees=len(entrees),
        motif=motif,
    )
    log_to_file(
        "Registre consulté",
        total=total,
        nb_retournees=len(entrees),
        motif=motif,
    )
    return {
        "statut": "succes",
        "message": "",
        "donnees": {
            "sources_inaccessibles": entrees,
            "total": total,
            "nb_retournees": len(entrees),
        },
    }
