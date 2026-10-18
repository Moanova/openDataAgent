# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : licence.py
# Version      : 2
# Date         : 15-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Filtre de licence du projet openDataAgent (T3.1.2, evolue T7.5-chantier A).

Deterministe : aucune decision agentique. Une licence absente, nulle
ou vide est refusee (comportement sur par defaut). L'evaluation est
insensible a la casse et aux espaces parasites.

La politique est parametree par `config/politique_licences.json`
(preparation de l'ouverture a d'autres sources, T7.4) ; en son absence
ou si le fichier est invalide, la politique integree ci-dessous
s'applique (memes valeurs, comportement sur inchange).

Regles :
- une licence explicite listee dans `licences_acceptees` est acceptee ;
- une licence listee dans `licences_conditionnelles` n'est acceptee que
  si le type d'organisation fourni figure dans les types autorises pour
  cette licence (ex. `notspecified` pour un service public, CRPA) ;
- toute autre valeur — y compris absente, nulle ou vide — est refusee,
  quelle que soit l'organisation : une licence incompatible declaree
  n'est jamais contournee, meme pour un etablissement public.
"""

import json
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Set

from src.utils.logging import get_logger, log_to_file

logger = get_logger("openDataAgent.core.licence")

CHEMIN_POLITIQUE = Path("config/politique_licences.json")

SOURCE_DEFAUT = "data.gouv.fr"

LICENCES_ACCEPTES_DEFAUT = frozenset({
    "lov2",
    "fr-lo",
    "odc-odbl",
    "odc-by",
    "odc-pddl",
    "cc-by",
    "cc-by-sa",
    "cc-zero",
    "other-open",
    "other-attribution",
    "other-pd",
})

LICENCES_CONDITIONNELLES_DEFAUT: Dict[str, FrozenSet[str]] = {
    "notspecified": frozenset({"service_public", "collectivite_territoriale"}),
}

LICENCES_ACCEPTES = LICENCES_ACCEPTES_DEFAUT
LICENCES_CONDITIONNELLES = LICENCES_CONDITIONNELLES_DEFAUT


def charger_politique(
    chemin: Optional[Path] = None,
    source: str = SOURCE_DEFAUT,
) -> Dict[str, Any]:
    """Charge la politique de licence depuis le fichier JSON de configuration.

    Un fichier absent, illisible ou dont la cle `source` est manquante
    produit la politique integree par defaut (comportement sur) ; aucune
    exception n'est levee.
    """
    chemin = Path(chemin) if chemin else CHEMIN_POLITIQUE
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _politique_defaut()
    except (json.JSONDecodeError, OSError) as exc:
        log_to_file(
            "Politique de licence illisible, politique par defaut appliquee",
            chemin=str(chemin),
            erreur=str(exc),
        )
        return _politique_defaut()
    if not isinstance(contenu, dict) or not isinstance(contenu.get(source), dict):
        log_to_file(
            "Cle de source absente de la politique de licence, politique par defaut appliquee",
            chemin=str(chemin),
            source=source,
        )
        return _politique_defaut()
    section = contenu[source]
    acceptees = section.get("licences_acceptees", [])
    conditionnelles = section.get("licences_conditionnelles", {})
    if not isinstance(acceptees, list) or not isinstance(conditionnelles, dict):
        log_to_file(
            "Politique de licence mal formee, politique par defaut appliquee",
            chemin=str(chemin),
            source=source,
        )
        return _politique_defaut()
    politique = {
        "licences_acceptees": frozenset(
            str(licence).strip().lower() for licence in acceptees if isinstance(licence, str)
        ),
        "licences_conditionnelles": {
            str(licence).strip().lower(): frozenset(
                str(type_org).strip().lower()
                for type_org in types
                if isinstance(type_org, str)
            )
            for licence, types in conditionnelles.items()
            if isinstance(licence, str) and isinstance(types, list)
        },
    }
    return politique


def _politique_defaut() -> Dict[str, Any]:
    return {
        "licences_acceptees": LICENCES_ACCEPTES_DEFAUT,
        "licences_conditionnelles": LICENCES_CONDITIONNELLES_DEFAUT,
    }


def _normaliser(valeur: Optional[str]) -> str:
    if not isinstance(valeur, str):
        return ""
    return valeur.strip().lower()


def licence_est_acceptable(
    licence: Optional[str],
    type_organisation: Optional[str] = None,
    politique: Optional[Dict[str, Any]] = None,
) -> bool:
    """Retourne True si la licence est compatible avec la politique du projet.

    Args:
        licence (Optional[str]): Code de licence data.gouv.fr (ex. `lov2`).
        type_organisation (Optional[str]): Type de l'organisation productrice
            (ex. `service_public`). Seules les licences conditionnelles en
            dependent ; une licence acceptee l'est quel que soit le type.
        politique (Optional[Dict[str, Any]]): Politique pre-chargee (sortie de
            `charger_politique`) ; par defaut, le fichier de configuration est
            lu une seule fois puis memoise.

    Regles : voir docstring du module. Toute autre valeur — y compris
    absente, nulle ou vide — est refusee, quelle que soit l'organisation.
    """
    if politique is None:
        politique = _politique_cachee()
    code = _normaliser(licence)
    if not code:
        return False
    if code in politique["licences_acceptees"]:
        return True
    types_autorises = politique["licences_conditionnelles"].get(code)
    if types_autorises is None:
        return False
    return _normaliser(type_organisation) in types_autorises


_politique_memoisee: Optional[Dict[str, Any]] = None


def _politique_cachee() -> Dict[str, Any]:
    global _politique_memoisee
    if _politique_memoisee is None:
        _politique_memoisee = charger_politique()
    return _politique_memoisee


def reinitialiser_politique() -> None:
    """Force le rechargement de la politique au prochain appel (tests)."""
    global _politique_memoisee
    _politique_memoisee = None
