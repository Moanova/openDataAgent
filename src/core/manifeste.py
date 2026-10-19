# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : manifeste.py
# Version      : 1
# Date         : 19-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Manifeste d'acquisition par exécution (T10.8).

Source de vérité « acquisition » côté disque : chaque acquisition réussie
de telecharger_brut ou extraire_ressource ajoute une entrée dans
data/raw/<id_execution>/manifeste_acquisitions.json, avec toutes les
métadonnées nécessaires à la partie 2 (jeu, licence, mention
d'attribution, voie, troncature) et la demande utilisateur en en-tête.

Invariants :
- écriture atomique (fichier .part puis renommage) ;
- additive : les entrées existantes ne sont jamais altérées ;
- un échec d'écriture ne fait jamais échouer l'acquisition (warning) ;
- la lecture est défensive : fichier absent ou invalide -> None, jamais
  d'exception vers l'appelant.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger, log_to_file

logger = get_logger("openDataAgent.core.manifeste")

NOM_MANIFESTE = "manifeste_acquisitions.json"
RACINE_DEFAUT = Path("data") / "raw"


def _chemin_manifeste(id_execution: str, racine: Path = RACINE_DEFAUT) -> Path:
    return racine / id_execution / NOM_MANIFESTE


def lire_manifeste(
    id_execution: str,
    racine: Path = RACINE_DEFAUT,
) -> Optional[Dict[str, Any]]:
    """Lit le manifeste d'une exécution ; None si absent ou invalide.

    Ne lève jamais d'exception : un manifeste illisible est une
    commodité perdue, pas une erreur d'exécution.
    """
    chemin = _chemin_manifeste(id_execution, racine)
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        logger.warning("Manifeste illisible", chemin=str(chemin), erreur=str(exc))
        log_to_file("Manifeste illisible", chemin=str(chemin), erreur=str(exc))
        return None


def _ecrire(chemin: Path, manifeste: Dict[str, Any]) -> bool:
    """Écrit le manifeste de façon atomique ; False en cas d'échec."""
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = chemin.with_name(chemin.name + ".part")
        temporaire.write_text(
            json.dumps(manifeste, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporaire.rename(chemin)
        return True
    except OSError as exc:
        logger.warning("Échec d'écriture du manifeste", chemin=str(chemin), erreur=str(exc))
        log_to_file("Échec d'écriture du manifeste", chemin=str(chemin), erreur=str(exc))
        return False


def consigner_demande(
    id_execution: str,
    demande: str,
    racine: Path = RACINE_DEFAUT,
) -> None:
    """Écrit l'en-tête du manifeste (id_execution, demande, date).

    Appelé en début d'exécution (CLI chat, download, extract) ;
    n'écrase jamais des acquisitions déjà consignées : seul l'en-tête
    est complété si le manifeste existe déjà.
    """
    manifeste = lire_manifeste(id_execution, racine) or {"acquisitions": []}
    manifeste.setdefault("acquisitions", [])
    manifeste["id_execution"] = id_execution
    manifeste["demande"] = demande
    manifeste["generé_le"] = datetime.now().isoformat(timespec="seconds")
    _ecrire(_chemin_manifeste(id_execution, racine), manifeste)


def enregistrer_acquisition(
    id_execution: str,
    entree: Dict[str, Any],
    racine: Path = RACINE_DEFAUT,
) -> None:
    """Ajoute une acquisition au manifeste de l'exécution.

    L'entrée est fournie par la voie d'acquisition (téléchargement ou
    extraction) après succès ; un même fichier ne peut pas figurer deux
    fois (garde anti-doublon, les collisions de nommage sont déjà
    suffixées par resoudre_collision). Un échec d'écriture produit un
    warning, jamais un échec de l'acquisition.
    """
    manifeste = lire_manifeste(id_execution, racine) or {"acquisitions": []}
    acquisitions: List[Dict[str, Any]] = manifeste.setdefault("acquisitions", [])
    fichier = entree.get("fichier")
    if fichier and any(a.get("fichier") == fichier for a in acquisitions):
        logger.warning("Acquisition déjà consignée", fichier=fichier, id_execution=id_execution)
        return
    entree = dict(entree)
    entree.setdefault("horodatage", datetime.now().isoformat(timespec="seconds"))
    acquisitions.append(entree)
    manifeste.setdefault("id_execution", id_execution)
    _ecrire(_chemin_manifeste(id_execution, racine), manifeste)
    logger.info(
        "Acquisition consignée au manifeste",
        fichier=fichier,
        id_execution=id_execution,
    )
    log_to_file("Acquisition consignée au manifeste", fichier=fichier, id_execution=id_execution)
