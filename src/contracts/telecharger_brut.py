# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : telecharger_brut.py
# Version      : 1
# Date         : 12-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Contrat Pydantic pour l'outil `telecharger_brut`.

Miroir du fichier JSON `contrats/telecharger_brut.json` et de la documentation
`docs/architecture/telecharger_brut.md`.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------

class TelechargerBrutInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    """Paramètres d'entrée de l'outil `telecharger_brut`."""

    id_ressource: str = Field(
        ...,
        description="Identifiant de la ressource, issu de `lister_ressources`.",
    )


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------

class TelechargerBrutOutput(BaseModel):
    """Données retournées en cas de succès par `telecharger_brut`."""

    chemin_local: str = Field(description="Chemin relatif du fichier téléchargé.")
    format: str = Field(description="Format du fichier téléchargé.")
    licence: str = Field(description="Licence du jeu de données.")
    licence_conditionnelle: bool = Field(
        default=False,
        description="Vrai si la licence a été acceptée par dérogation (producteur public, licence non renseignée).",
    )
    mention_attribution: str | None = Field(
        default=None,
        description="Mention d'attribution prête à afficher ; null si la licence est à vérifier (jamais devinée).",
    )
    suggestion: str | None = Field(
        default=None,
        description="Suggestion en cas d'échec (ex : 'fichier_heberge_exterieurement').",
    )
    nb_tentatives: int = Field(
        default=1,
        description="Nombre de tentatives du téléchargement (1 = succès au premier essai).",
    )
    motif: Optional[str] = Field(
        default=None,
        description="Motif de l'échec HTTP (T7.1 : 'transitoire' après épuisement des tentatives, 'acces_refuse', 'ressource_supprimee', 'requete_invalide') ; en mode agentique, 'circuit_ouvert' (T7.7) quand le circuit breaker a intercepté l'appel. None en cas de succès.",
    )
