# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : outils.py
# Version      : 2
# Date         : 15-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Exécution des tool_calls vers les fonctions du coeur (T5.3.2, T10.4).

L'API Mistral n'exécute jamais les fonctions : ce module reçoit le
nom d'un outil et ses arguments, les valide contre les modèles Pydantic
des contrats (src/contracts/), exécute la fonction du coeur
correspondante et retourne la réponse normalisée {statut, message,
donnees}. Aucune exception ne remonte vers l'agent.

Les modèles *Input sont la source unique de vérité des arguments :
les champs inconnus sont ignorés (extra="ignore") et id_execution,
identifiant de flux interne fourni par la boucle, est injecté après
validation — jamais lu depuis les arguments de l'agent."""
from __future__ import annotations

import json
from typing import Any, Dict

from pydantic import BaseModel, ValidationError

from src.contracts.consulter_registre import ConsulterRegistreInput
from src.contracts.extraire_ressource import ExtraireRessourceInput
from src.contracts.interroger_ressource import InterrogerRessourceInput
from src.contracts.lister_ressources import ListerRessourcesInput
from src.contracts.rechercher_jeux import RechercherJeuxInput
from src.contracts.telecharger_brut import TelechargerBrutInput
from src.core.telechargement import telecharger_brut
from src.core.extraction import extraire_ressource
from src.core.interrogation import interroger_ressource
from src.core.registre import consulter_registre
from src.core.resources import lister_ressources
from src.core.recherche import rechercher_jeux

TABLE_OUTILS: Dict[str, Any] = {
    "rechercher_jeux": rechercher_jeux,
    "lister_ressources": lister_ressources,
    "interroger_ressource": interroger_ressource,
    "telecharger_brut": telecharger_brut,
    "extraire_ressource": extraire_ressource,
    "consulter_registre": consulter_registre,
}

MODELES_INPUT: Dict[str, type[BaseModel]] = {
    "rechercher_jeux": RechercherJeuxInput,
    "lister_ressources": ListerRessourcesInput,
    "interroger_ressource": InterrogerRessourceInput,
    "telecharger_brut": TelechargerBrutInput,
    "extraire_ressource": ExtraireRessourceInput,
    "consulter_registre": ConsulterRegistreInput,
}


def executer_outil(nom: str, arguments: Any, id_execution: str) -> Dict[str, Any]:
    """Exécute un tool_call vers la fonction coeur correspondante.

    Args:
        nom : nom de l'outil appelé par l'agent.
        arguments : arguments de l'appel (dictionnaire ou chaene JSON).
        id_execution : identifiant d'exécution lié au flux.

    Returns:
        Réponse normalisée {statut, message, donnees}. Toute
        défaillance (outil inconnu, arguments invalides, exception du
        coeur) devient un statut, jamais une exception vers l'agent.
    """
    fonction = TABLE_OUTILS.get(nom)
    if fonction is None:
        return {
            "statut": "erreur_parametres",
            "message": f"Outil inconnu : '{nom}'. Outils disponibles : {sorted(TABLE_OUTILS)}.",
            "donnees": {},
        }
    arguments_dict = _decoder_arguments(arguments)
    if arguments_dict is None:
        return {
            "statut": "erreur_parametres",
            "message": "Arguments du tool_call invalides : objet JSON attendu.",
            "donnees": {},
        }
    modele = MODELES_INPUT[nom]
    try:
        valide = modele.model_validate(arguments_dict)
    except ValidationError as erreur_validation:
        return {
            "statut": "erreur_parametres",
            "message": f"Arguments invalides pour '{nom}' : {_resume_erreurs(erreur_validation)}",
            "donnees": {},
        }
    options = valide.model_dump(exclude_unset=True)
    options.setdefault("id_execution", id_execution)
    try:
        return fonction(**options)
    except TypeError as erreur_type:
        return {
            "statut": "erreur_parametres",
            "message": f"Arguments refusés par '{nom}' : {erreur_type}",
            "donnees": {},
        }
    except Exception as erreur_coeur:
        return {
            "statut": "echec_technique",
            "message": f"Erreur inattendue de '{nom}' : {erreur_coeur}",
            "donnees": {},
        }


def _decoder_arguments(arguments: Any) -> Any:
    """Décode les arguments d'un tool_call en dictionnaire, ou None."""
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            valeurs = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            return None
        return valeurs if isinstance(valeurs, dict) else None
    return None


def _resume_erreurs(erreur: ValidationError) -> str:
    """Condense une ValidationError Pydantic en message lisible pour l'agent."""
    return " ; ".join(
        f"{e['loc'][0] if e['loc'] else '?'} — {e['msg']}" for e in erreur.errors()
    )
