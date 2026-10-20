# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : journal.py
# Version      : 1
# Date         : 14-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Journal des conversations agentiques (T5.3.3, schéma multi-tours T11.1).

Conserve pour chaque conversation : contexte (modèle, empreinte du
prompt, date, plafond), un événement `debut_tour`/`fin_tour` par tour
utilisateur (horodaté, avec son compte d'invocations et sa synthèse),
les invocations d'outils avec leurs arguments, les résultats normalisés,
les raisonnements de l'agent (texte émis entre les tool_calls) et un
événement `fin` final (totaux de la conversation).

Format : JSONL, un enregistrement par ligne, dans
conversations/<id_execution>/conversation.jsonl. Une conversation = un
id_execution. Ces journaux servent aux tests de propriétés TA (rejeu)
et à l'audit (plan_tests section 9).

Aucune erreur d'écriture ne remonte vers la boucle : la journalisation
ne doit jamais interrompre une acquisition."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPERTOIRE_JOURNAUX = Path("conversations")

EVENEMENTS = (
    "contexte",
    "debut_tour",
    "raisonnement_agent",
    "outil_invoque",
    "outil_resultat",
    "plafond_atteint",
    "erreur_api",
    "fin_tour",
    "fin",
)


class JournalConversation:
    """Journal JSONL d'une conversation agentique.

    Attributs :
        id_execution : identifiant du flux.
        chemin : fichier du journal (conversations/<id>/conversation.jsonl).
    """

    def __init__(self, id_execution: str, modele: str = "", prompt: str = "", plafond: int = 0, repertoire: Optional[Path] = None) -> None:
        self.id_execution = id_execution
        self.chemin = (repertoire or REPERTOIRE_JOURNAUX) / id_execution / "conversation.jsonl"
        self._flux = None
        try:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            self._flux = open(self.chemin, "a", encoding="utf-8")
            self._ecrire(
                "contexte",
                id_execution=id_execution,
                modele=modele,
                prompt=prompt,
                plafond=plafond,
                date=datetime.now().isoformat(),
            )
        except OSError:
            self._flux = None

    def enregistrer(self, event: str, **champs: Any) -> None:
        """Ajoute un évènement au journal (échec d'écriture silencieux)."""
        if event not in EVENEMENTS:
            event = "fin"
        self._ecrire(event, **champs)

    def fermer(self, statut: str, **champs: Any) -> None:
        """"Écrit l'évènement de fin et ferme le fichier."""
        self._ecrire("fin", statut=statut, **champs)
        if self._flux is not None:
            try:
                self._flux.close()
            except OSError:
                pass
            self._flux = None

    def _ecrire(self, event: str, **champs: Any) -> None:
        if self._flux is None:
            return
        enregistrement = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "id_execution": self.id_execution,
            **champs,
        }
        try:
            self._flux.write(json.dumps(enregistrement, ensure_ascii=False) + "\n")
            self._flux.flush()
        except (OSError, TypeError, ValueError):
            pass


def lire_journal(chemin: Path) -> List[Dict[str, Any]]:
    """Charge un journal JSONL en liste d'enregistrements.

    Les lignes illisibles sont ignorées : le rejeu ne doit jamais
    échouer sur une ligne corrompue.
    """
    if not chemin.is_file():
        return []
    enregistrements = []
    with open(chemin, encoding="utf-8") as flux:
        for ligne in flux:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                enregistrements.append(json.loads(ligne))
            except json.JSONDecodeError:
                continue
    return enregistrements


def extraire_invocations(enregistrements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extrait la séquence ordonnée des invocations d'outils d'un journal.

    Base du rejeu TA-01 (integrité des identifiants) et TA-02 (ordre
    des appels) : chaque entrée comporte tour, outil, arguments et le
    statut du résultat associé.
    """
    invocations: List[Dict[str, Any]] = []
    attente_resultat: Optional[Dict[str, Any]] = None
    for enregistrement in enregistrements:
        event = enregistrement.get("event")
        if event == "outil_invoque":
            attente_resultat = {
                "tour": enregistrement.get("tour"),
                "outil": enregistrement.get("outil"),
                "arguments": enregistrement.get("arguments"),
            }
        elif event == "outil_resultat" and attente_resultat is not None:
            attente_resultat["statut"] = enregistrement.get("statut")
            invocations.append(attente_resultat)
            attente_resultat = None
    return invocations
