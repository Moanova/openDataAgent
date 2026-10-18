# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : rechercher_jeux.py
# Version      : 1
# Date         : 12-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Contrat Pydantic pour l'outil `rechercher_jeux`.

Miroir du fichier JSON `contrats/rechercher_jeux.json` et de la documentation
`docs/architecture/rechercher_jeux.md`.
"""

from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field

from src.contracts.base import JeuResume
from src.core.vocabulaires import FenetreMaj, TriRecherche


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------

class RechercherJeuxInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    """Paramètres d'entrée de l'outil `rechercher_jeux`.

    La recherche applique une logique ET sur les mots-clés.
    """

    mots_cles: list[str] = Field(
        ...,
        min_length=1,
        description="Mots-clés de la recherche, combinés en logique ET.",
    )
    tri: TriRecherche = Field(
        default=TriRecherche.PERTINENCE,
        description="Ordre de tri des résultats.",
    )
    fenetre_maj: FenetreMaj = Field(
        default=FenetreMaj.TOUTES,
        description="Restriction temporelle sur la dernière mise à jour.",
    )
    limite: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Nombre maximum de jeux retournés (defaut : 10, max : 20).",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Numéro de la page de résultats demandée (defaut : 1).",
    )


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------

class RechercherJeuxOutput(BaseModel):
    """Données retournées en cas de succès par `rechercher_jeux`."""

    total_trouves: int = Field(description="Nombre total de jeux correspondant a la requête.")
    jeux: list[JeuResume] = Field(description="Liste resumée des jeux de données.")
    exclus_licence: int = Field(description="Nombre de jeux écartés par le filtre de licence.")
    acceptes_licence_conditionnelle: int = Field(
        default=0,
        description="Nombre de jeux acceptés sous licence conditionnelle (producteur public, licence non renseignée).",
    )
    page_courante: int = Field(description="Numéro de la page retournée.")
    page_suivante: int | None = Field(
        default=None,
        description="Numéro de la page suivante si elle existe, null sinon.",
    )
