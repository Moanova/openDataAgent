# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : consulter_registre.py
# Version      : 1
# Date         : 22-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Contrat Pydantic pour l'outil `consulter_registre` (T11.4, contrat v1.0.0).

Miroir du fichier JSON `contrats/consulter_registre.json`. Lecture seule :
le registre des sources inaccessibles n'est jamais modifie par cet outil.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field



class MotifRegistre(str, Enum):
    """Motifs d'entree du registre des sources inaccessibles."""

    LICENCE_INCOMPATIBLE = "licence_incompatible"
    SERVEUR_ORIGINE_BLOQUE = "serveur_origine_bloque"


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------
class ConsulterRegistreInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    """Paramètres d'entrée de l'outil `consulter_registre`."""

    derniere_n: int = Field(
        default=20,
        ge=1,
        description="Nombre maximum d'entrées retournées (les plus récentes).",
    )
    motif: Optional[MotifRegistre] = Field(
        default=None,
        description="Filtre optionnel : ne retourner que les entrées de ce motif.",
    )


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------
class ConsulterRegistreOutput(BaseModel):
    """Données retournées en cas de succès par `consulter_registre`."""

    sources_inaccessibles: List[Dict[str, Any]] = Field(
        description="Entrées du registre (les plus récentes d'abord si derniere_n est précisé).",
    )
    total: int = Field(
        description="Nombre total d'entrées dans le registre, hors limite et hors filtre.",
    )
    nb_retournees: int = Field(
        description="Nombre d'entrées effectivement retournées.",
    )
