# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : extraire_ressource.py
# Version      : 1
# Date         : 15-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Contrat Pydantic pour l'outil `extraire_ressource` (T10.7, contrat v1.2.0).

Miroir du fichier JSON `contrats/extraire_ressource.json`.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------
class ExtraireRessourceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    """Paramètres d'entrée de l'outil `extraire_ressource`."""
    id_ressource: str = Field(
        ...,
        description="Identifiant de la ressource, issu de `lister_ressources`.",
    )


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------
class ExtraireRessourceOutput(BaseModel):
    """Données retournées en cas de succès par `extraire_ressource`."""

    chemin_local: str = Field(description="Chemin relatif du CSV extrait.")
    total_lignes: int = Field(description="Nombre total de lignes de la ressource côté API.")
    lignes_ecrites: int = Field(description="Nombre de lignes effectivement écrites.")
    colonnes: list[str] = Field(description="Colonnes du CSV, ordre de l'API conservé.")
    tronque: bool = Field(description="Vrai si l'extraction a été tronquée au plafond de sécurité.")
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
        description="Suggestion en cas d'échec (ex : 'basculer sur telecharger_brut').",
    )
