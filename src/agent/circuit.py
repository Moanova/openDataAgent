# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : circuit.py
# Version      : 1
# Date         : 22-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Circuit breaker agentique par hôte (T7.7).

Après N échecs transitoires consécutifs (T7.1 : motif « transitoire »)
vers un même hôte dans une conversation, la boucle cesse de solliciter
cet hôte : l'outil est intercepté avant exécution (sans consommer le
plafond d'invocations) et l'agent reçoit un résultat structuré
`echec_technique` / `motif=circuit_ouvert`.

États par hôte : fermé → ouvert (au seuil) → semi-ouvert (après le
délai de refroidissement, 1 tentative autorisée) → fermé (succès) ou
ouvert (nouvel échec transitoire).

L'état vit **en mémoire, attaché à la conversation** (option A actée
le 22/10/2026) : une nouvelle conversation repart à zéro, aucun timer
ne court entre deux exécutions. Un échec définitif (403/410…) n'alimente
pas le circuit : un refus ne dit rien sur la santé du serveur.

Paramétrage (variables d'environnement, pattern existant) :
- CIRCUIT_BREAKER_SEUIL : échecs consécutifs avant ouverture (défaut 3).
- CIRCUIT_BREAKER_REFROIDISSEMENT : délai en secondes avant le test
  semi-ouvert (défaut 300 s = 5 min).
- CIRCUIT_BREAKER_DESACTIVE=1 : désactive le mécanisme (tout passe).
"""
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse

SEUIL_DEFAUT = 3
REFROIDISSEMENT_DEFAUT_S = 300.0

FERME = "ferme"
OUVERT = "ouvert"
SEMI_OUVERT = "semi_ouvert"

MOTIF_CIRCUIT_OUVERT = "circuit_ouvert"


def _seuil() -> int:
    try:
        return max(1, int(os.environ.get("CIRCUIT_BREAKER_SEUIL", SEUIL_DEFAUT)))
    except ValueError:
        return SEUIL_DEFAUT


def _refroidissement() -> float:
    try:
        return max(0.0, float(os.environ.get("CIRCUIT_BREAKER_REFROIDISSEMENT", REFROIDISSEMENT_DEFAUT_S)))
    except ValueError:
        return REFROIDISSEMENT_DEFAUT_S


def desactive() -> bool:
    return os.environ.get("CIRCUIT_BREAKER_DESACTIVE") == "1"


def hote_depuis_url(url: str) -> Optional[str]:
    """Extrait le nom d'hôte d'une URL (None si absent ou non parsable)."""
    try:
        hote = urlparse(url).netloc
    except ValueError:
        return None
    return hote.lower() or None


@dataclass
class _EtatHote:
    statut: str = FERME
    echecs_consecutifs: int = 0
    ouvert_depuis: Optional[float] = None


@dataclass
class CircuitBreaker:
    """Circuit breaker par hôte, en mémoire, attaché à une conversation.

    Horloge injectable (`maintenant`) pour les tests déterministes.
    """

    seuil: int = field(default_factory=_seuil)
    refroidissement: float = field(default_factory=_refroidissement)
    desactive: bool = field(default_factory=desactive)
    maintenant: callable = field(default=time.monotonic)
    _etats: Dict[str, _EtatHote] = field(default_factory=dict)

    def _etat(self, hote: str) -> _EtatHote:
        if hote not in self._etats:
            self._etats[hote] = _EtatHote()
        return self._etats[hote]

    def autoriser(self, hote: Optional[str]) -> bool:
        """True si un appel vers cet hôte est autorisé maintenant.

        Faux (circuit ouvert) → la boucle intercepte l'outil sans le
        consommer. En semi-ouvert, une seule tentative est autorisée :
        l'appel suivant est de nouveau bloqué jusqu'au résultat.
        """
        if self.desactive or hote is None:
            return True
        etat = self._etat(hote)
        if etat.statut == FERME:
            return True
        if etat.statut == OUVERT:
            if self.maintenant() - (etat.ouvert_depuis or 0.0) >= self.refroidissement:
                etat.statut = SEMI_OUVERT
                return True
            return False
        # SEMI_OUVERT : une tentative en cours ; bloquer les suivantes.
        return False

    def enregistrer_succes(self, hote: Optional[str]) -> None:
        """Succès : le circuit se ferme, compteurs remis à zéro."""
        if hote is None:
            return
        etat = self._etat(hote)
        etat.statut = FERME
        etat.echecs_consecutifs = 0
        etat.ouvert_depuis = None

    def enregistrer_echec_transitoire(self, hote: Optional[str]) -> bool:
        """Échec transitoire (T7.1) : incrémente ; ouvre au seuil.

        Retourne True si le circuit vient de s'ouvrir (utile pour le log).
        """
        if self.desactive or hote is None:
            return False
        etat = self._etat(hote)
        etat.echecs_consecutifs += 1
        if etat.echecs_consecutifs >= self.seuil and etat.statut != OUVERT:
            etat.statut = OUVERT
            etat.ouvert_depuis = self.maintenant()
            return True
        return False

    def enregistrer_echec_definitif(self, hote: Optional[str]) -> None:
        """Échec définitif (403/410…) : ignoré — un refus n'est pas un
        signe de panne du serveur."""
        return None

    def instantanement_ouvert(self, hote: Optional[str]) -> bool:
        """True si le circuit est ouvert pour cet hôte (pour le message
        de l'interception)."""
        if hote is None:
            return False
        return self._etat(hote).statut == OUVERT
