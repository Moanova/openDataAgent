# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : registre_acceptations.py
# Version      : 1
# Date         : 15-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Registre des acceptations conditionnelles (T7.5, chantier B).

Distinct du registre des sources inaccessibles : il trace les jeux dont
la licence absente (`notspecified`) a ete acceptee par derogation
(producteur public, presomption CRPA). Persistant dans
`data/registre_acceptations.json`. Invariants :

- aucune entree n'est supprimee ou modifiee apres ecriture ;
- le registre persiste entre les executions ;
- les obligations de licence restent a verifier : cette acceptation
  n'est jamais une preuve de compatibilite, seulement une trace de la
  decision d'acquisition.
"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.journalisation import get_logger, log_to_file

logger = get_logger("openDataAgent.utils.registre_acceptations")

MOTIF_ACCEPTATION = "licence_absente_producteur_public"


class RegistreAcceptationsConditionnelles:
    """Registre persistant des acceptations conditionnelles de licence (JSON)."""

    def __init__(self, chemin: Optional[Path] = None) -> None:
        self.chemin = Path(chemin) if chemin else Path("data/registre_acceptations.json")
        self._entrees: List[Dict[str, Any]] = self._charger()

    def _charger(self) -> List[Dict[str, Any]]:
        """Charge le registre preexistant sans l'ecraser.

        Un fichier absent ou invalide produit un registre vide, sans
        exception.
        """
        if not self.chemin.exists():
            return []
        try:
            contenu = json.loads(self.chemin.read_text(encoding="utf-8"))
            entrees = contenu.get("acceptations_conditionnelles", [])
            if isinstance(entrees, list):
                return entrees
            return []
        except (json.JSONDecodeError, OSError) as exc:
            log_to_file(
                "Registre des acceptations illisible, demarrage sur registre vide",
                chemin=str(self.chemin),
                erreur=str(exc),
            )
            return []

    def consigner_acceptation_conditionnelle(
        self,
        id_jeu: str,
        organisation: str,
        type_organisation: str,
        licence: str,
        url: str,
        detail: str = "Licence absente acceptee par presomption pour un producteur public ; obligations a verifier avant exploitation",
    ) -> Dict[str, Any]:
        """Consigne une acceptation conditionnelle (ecrit par rechercher_jeux)."""
        entree = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "motif": MOTIF_ACCEPTATION,
            "id_jeu": id_jeu,
            "organisation": organisation,
            "type_organisation": type_organisation,
            "licence": licence,
            "url": url,
            "detail": detail,
        }
        self._entrees.append(entree)
        log_to_file(
            "Acceptation conditionnelle consignee au registre",
            motif=MOTIF_ACCEPTATION,
            id_jeu=id_jeu,
            organisation=organisation,
            type_organisation=type_organisation,
            licence=licence,
            url=url,
            detail=detail,
        )
        return entree

    def id_deja_consigne(self, id_jeu: str) -> bool:
        """Retourne True si une acceptation existe deja pour ce jeu (anti-doublon)."""
        return any(entree.get("id_jeu") == id_jeu for entree in self._entrees)

    def sauvegarder(self) -> None:
        """Ecrit le registre au format JSON valide."""
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        contenu = {"acceptations_conditionnelles": self._entrees}
        self.chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")

    def rapport_pour_agent(self) -> Dict[str, Any]:
        """Retourne une copie pour la lecture agentique."""
        return copy.deepcopy({"acceptations_conditionnelles": self._entrees})
