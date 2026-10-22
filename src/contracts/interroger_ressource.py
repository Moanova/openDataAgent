# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : interroger_ressource.py
# Version      : 1
# Date         : 12-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Contrat Pydantic pour l'outil `interroger_ressource`.

Miroir du fichier JSON `contrats/interroger_ressource.json` et de la documentation
`docs/architecture/interroger_ressource.md`.
"""

from __future__ import annotations

from typing import Any, Optional

from src.core.vocabulaires import OperateurFiltre, OrdreTri

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sous-modèles
# ---------------------------------------------------------------------------

class FiltreColonne(BaseModel):
    """Filtre applicable sur une colonne (une colonne a la fois)."""

    colonne: str = Field(description="Nom de la colonne à filtrer.")
    valeur: str = Field(description="Valeur de comparaison.")
    operateur: OperateurFiltre = Field(
        default=OperateurFiltre.EXACT,
        description="Operateur de comparaison (defaut : exact).",
    )


class TriColonne(BaseModel):
    """Tri applicable sur une colonne."""

    colonne: str = Field(description="Nom de la colonne à trier.")
    ordre: OrdreTri = Field(description="Ordre de tri (croissant ou décroissant).")


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------

class InterrogerRessourceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    """Parametres d'entrée de l'outil `interroger_ressource`."""

    id_ressource: str = Field(
        ...,
        description="Identifiant de la ressource, issu de `lister_ressources`.",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Numero de page (defaut : 1).",
    )
    taille_page: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Nombre d'éléments par page (defaut : 20, max : 100).",
    )
    filtre: FiltreColonne | None = Field(
        default=None,
        description="Filtre optionnel sur une colonne.",
    )
    tri: TriColonne | None = Field(
        default=None,
        description="Tri optionnel sur une colonne.",
    )


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------

class InterrogerRessourceOutput(BaseModel):
    """Données retournées en cas de succès par `interroger_ressource`."""

    total_lignes: int = Field(description="Nombre total de lignes de la ressource.")
    colonnes: list[str] = Field(description="Schéma detecte (noms des colonnes).")
    lignes: list[dict[str, Any]] = Field(description="Page courante de données.")
    page: int = Field(description="Numéro de la page retournée.")
    page_suivante: int | None = Field(
        default=None,
        description="Numéro de la page suivante si elle existe, null sinon.",
    )
    recommandation: str | None = Field(
        default=None,
        description="Recommandation pour les volumes élevés "
                    "(ex : 'volume_eleve_telechargement_brut_suggere').",
    )
    nb_tentatives: int = Field(
        default=1,
        description="Nombre de tentatives de l'appel HTTP (1 = succès au premier essai).",
    )
    motif: Optional[str] = Field(
        default=None,
        description="Motif de l'échec HTTP (T7.1 : 'transitoire' après épuisement des tentatives, 'acces_refuse', 'ressource_supprimee', 'requete_invalide') ; en mode agentique, 'circuit_ouvert' (T7.7) quand le circuit breaker a intercepté l'appel. None en cas de succès.",
    )
