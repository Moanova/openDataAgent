# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_circuit.py
# Version      : 1
# Date         : 22-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests du circuit breaker agentique (src/agent/circuit.py, T7.7).

Sans réseau : machine à états pure, horloge injectée pour les tests
déterministes. Références : tests/plan_tests.md TU-101..TU-108.
"""
import pytest

from src.agent.circuit import (
    FERME,
    MOTIF_CIRCUIT_OUVERT,
    OUVERT,
    SEMI_OUVERT,
    CircuitBreaker,
    hote_depuis_url,
)


class _Horloge:
    """Horloge manuelle pour les tests déterministes."""

    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def avancer(self, secondes: float) -> None:
        self.t += secondes


@pytest.fixture
def horloge():
    return _Horloge()


@pytest.fixture
def circuit(horloge):
    return CircuitBreaker(seuil=3, refroidissement=300.0, maintenant=horloge)


def test_hote_depuis_url():
    assert hote_depuis_url("https://ccomptes.fr/fichier.csv") == "ccomptes.fr"
    assert hote_depuis_url("https://WWW.Data.Gouv.FR/api/2/") == "www.data.gouv.fr"
    assert hote_depuis_url("https://tabular-api.data.gouv.fr/api/resources/x/data/") == "tabular-api.data.gouv.fr"
    assert hote_depuis_url("") is None
    assert hote_depuis_url("pas-une-url") is None


def test_ferme_au_depart_tout_passe(circuit):
    # TU-101 : à l'état initial, tout hôte est autorisé
    assert circuit.autoriser("a.fr") is True
    assert circuit.autoriser("b.fr") is True
    assert circuit.autoriser(None) is True


def test_ouverture_au_seuil_et_blocage(circuit):
    # TU-102 : 3 échecs transitoires consécutifs → ouvert, 4e appel bloqué
    hote = "a.fr"
    assert circuit.autoriser(hote) is True
    assert circuit.enregistrer_echec_transitoire(hote) is False
    assert circuit.enregistrer_echec_transitoire(hote) is False
    assert circuit.enregistrer_echec_transitoire(hote) is True  # seuil atteint → ouvert
    assert circuit.autoriser(hote) is False
    assert circuit.instantanement_ouvert(hote) is True


def test_succes_remet_a_zero(circuit):
    # TU-103 : un succès entre les échecs remet le compteur à zéro
    hote = "a.fr"
    circuit.enregistrer_echec_transitoire(hote)
    circuit.enregistrer_echec_transitoire(hote)
    circuit.enregistrer_succes(hote)
    circuit.enregistrer_echec_transitoire(hote)
    circuit.enregistrer_echec_transitoire(hote)
    # 2 échecs après le succès : pas encore le seuil de 3
    assert circuit.autoriser(hote) is True
    assert circuit.instantanement_ouvert(hote) is False


def test_echec_definitif_ignore(circuit):
    # TU-104 : un refus définitif (403/410) n'alimente pas le circuit
    hote = "a.fr"
    for _ in range(10):
        circuit.enregistrer_echec_definitif(hote)
    assert circuit.autoriser(hote) is True
    assert circuit.instantanement_ouvert(hote) is False


def test_refroidissement_et_semi_ouvert(circuit, horloge):
    # TU-105 : après le refroidissement, une tentative est autorisée
    # (semi-ouvert) ; les suivantes sont bloquées jusqu'au résultat.
    hote = "a.fr"
    for _ in range(3):
        circuit.enregistrer_echec_transitoire(hote)
    assert circuit.autoriser(hote) is False
    horloge.avancer(299.0)
    assert circuit.autoriser(hote) is False  # pas encore refroidi
    horloge.avancer(1.0)
    assert circuit.autoriser(hote) is True  # semi-ouvert : 1 tentative
    assert circuit.autoriser(hote) is False  # la suivante bloquée
    # La tentative semi-ouverte réussit → fermé
    circuit.enregistrer_succes(hote)
    assert circuit.autoriser(hote) is True
    assert circuit.instantanement_ouvert(hote) is False


def test_semi_ouvert_echec_reouvre(circuit, horloge):
    # TU-105 (suite) : la tentative semi-ouverte échoue → retour à ouvert
    hote = "a.fr"
    for _ in range(3):
        circuit.enregistrer_echec_transitoire(hote)
    horloge.avancer(300.0)
    assert circuit.autoriser(hote) is True  # semi-ouvert
    circuit.enregistrer_echec_transitoire(hote)  # la sonde échoue
    assert circuit.autoriser(hote) is False  # rouvert
    horloge.avancer(299.0)
    assert circuit.autoriser(hote) is False
    horloge.avancer(1.0)
    assert circuit.autoriser(hote) is True  # nouveau cycle de refroidissement


def test_hotes_independants(circuit):
    # TU-106 : le circuit est par hôte — un hôte ouvert n'affecte pas les autres
    for _ in range(3):
        circuit.enregistrer_echec_transitoire("a.fr")
    assert circuit.autoriser("a.fr") is False
    assert circuit.autoriser("b.fr") is True
    circuit.enregistrer_succes("b.fr")
    assert circuit.autoriser("a.fr") is False


def test_desactive_tout_passe(horloge):
    # TU-107 : CIRCUIT_BREAKER désactivé → aucune interception
    cb = CircuitBreaker(seuil=1, refroidissement=300.0, desactive=True, maintenant=horloge)
    for _ in range(10):
        cb.enregistrer_echec_transitoire("a.fr")
    assert cb.autoriser("a.fr") is True


def test_parametres_env(monkeypatch):
    # TU-108 : lecture des variables d'environnement (seuil, refroidissement)
    monkeypatch.setenv("CIRCUIT_BREAKER_SEUIL", "5")
    monkeypatch.setenv("CIRCUIT_BREAKER_REFROIDISSEMENT", "60")
    cb = CircuitBreaker(maintenant=_Horloge())
    assert cb.seuil == 5
    assert cb.refroidissement == 60.0
    # Valeurs invalides → défauts
    monkeypatch.setenv("CIRCUIT_BREAKER_SEUIL", "abc")
    monkeypatch.setenv("CIRCUIT_BREAKER_REFROIDISSEMENT", "xyz")
    cb2 = CircuitBreaker(maintenant=_Horloge())
    assert cb2.seuil == 3
    assert cb2.refroidissement == 300.0


def test_motif_circuit_ouvert_constante():
    assert MOTIF_CIRCUIT_OUVERT == "circuit_ouvert"


def test_etats_constantes():
    assert (FERME, OUVERT, SEMI_OUVERT) == ("ferme", "ouvert", "semi_ouvert")
