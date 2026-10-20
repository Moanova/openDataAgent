# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_agent.py
# Version      : 1
# Date         : 14-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de la creation/destruction de l'agent Mistral (T5.3.1).

Refs tests/plan_tests.md : Annexes T5.3 (creations agentiques, sans
reseau). Le SDK mistralai n'est jamais appele : le client est simule.
Les contrats reels de contrats/*.json sont charges sans mock."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agent.agent import (
    Agent,
    PREFIXE_NOM,
    PROMPT_SYSTEME,
    charger_outils,
    creer_agent,
    detruire_agent,
    empreinte,
    nettoyer_agents_orphelins,
)

REPERTOIRE_CONTRATS = Path(__file__).resolve().parents[2] / "contrats"


# ---------------------------------------------------------------------
# charger_outils
# ---------------------------------------------------------------------

def test_charger_outils_charge_les_quatres_contrats():
    # Réf. tests/plan_tests.md : Annexe T5.3 — les 4 outils du manifeste
    outils = charger_outils()
    noms = {o["function"]["name"] for o in outils}
    assert noms == {"rechercher_jeux", "lister_ressources", "interroger_ressource", "telecharger_brut", "extraire_ressource"}


def test_charger_outils_refuse_fichier_divergent(tmp_path):
    # Réf. tests/plan_tests.md : Annexe T5.3 — invariant contrat_global (manifeste/fichier)
    import json
    manifeste = json.loads((REPERTOIRE_CONTRATS / "manifeste.json").read_text(encoding="utf-8"))
    (tmp_path / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")
    for entree in manifeste["outils"]:
        source = REPERTOIRE_CONTRATS / entree["fichier"]
        (tmp_path / entree["fichier"]).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    faux = json.loads((tmp_path / "rechercher_jeux.json").read_text(encoding="utf-8"))
    faux["function"]["name"] = "autre_nom"
    (tmp_path / "rechercher_jeux.json").write_text(json.dumps(faux), encoding="utf-8")
    with pytest.raises(ValueError):
        charger_outils(tmp_path)


def test_charger_outils_refuse_manifeste_fichier_divergent(tmp_path):
    # Réf. tests/plan_tests.md : Annexe T5.3 — divergence nom/fichier
    import json
    manifeste = json.loads((REPERTOIRE_CONTRATS / "manifeste.json").read_text(encoding="utf-8"))
    for entree in manifeste["outils"]:
        if entree["nom"] == "rechercher_jeux":
            entree["fichier"] = "autre_fichier.json"
        else:
            source = REPERTOIRE_CONTRATS / entree["fichier"]
            (tmp_path / entree["fichier"]).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")
    with pytest.raises(ValueError):
        charger_outils(tmp_path)


# ---------------------------------------------------------------------
# creer_agent
# ---------------------------------------------------------------------

def _client_faux(agent_id="ag-123"):
    client = MagicMock()
    client.beta.agents.create.return_value = MagicMock(id=agent_id)
    return client


def _env_cle(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "cle-test")
    monkeypatch.delenv("MISTRAL_AGENT_ID", raising=False)
    monkeypatch.delenv("MISTRAL_MODELE", raising=False)


def test_creer_agent_succes_cree_agent_ephemere(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — création éphémère via beta.agents.create
    _env_cle(monkeypatch)
    client = _client_faux()
    reponse = creer_agent("20261014_120000", client=client)
    assert reponse["statut"] == "succes"
    agent = reponse["donnees"]["agent"]
    assert isinstance(agent, Agent)
    assert agent.ephemere is True
    assert agent.agent_id == "ag-123"
    assert agent.modele == "mistral-small-latest"
    client.beta.agents.create.assert_called_once()
    kwargs = client.beta.agents.create.call_args.kwargs
    assert kwargs["model"] == "mistral-small-latest"
    assert kwargs["name"].startswith(PREFIXE_NOM)
    assert kwargs["instructions"] == PROMPT_SYSTEME
    assert len(kwargs["tools"]) == 5
    assert kwargs["metadata"]["id_execution"] == "20261014_120000"


def test_creer_agent_modele_configure(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — MISTRAL_MODELE respecté
    _env_cle(monkeypatch)
    monkeypatch.setenv("MISTRAL_MODELE", "mistral-medium-latest")
    client = _client_faux()
    reponse = creer_agent("id", client=client)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["agent"].modele == "mistral-medium-latest"
    assert client.beta.agents.create.call_args.kwargs["model"] == "mistral-medium-latest"


def test_creer_agent_cle_absente(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — échec propre sans clé
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_AGENT_ID", raising=False)
    reponse = creer_agent("id", client=MagicMock())
    assert reponse["statut"] == "echec_technique"
    assert "MISTRAL_API_KEY" in reponse["message"]


def test_creer_agent_erreur_sdk(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — échec propre si la console refuse
    _env_cle(monkeypatch)
    client = _client_faux()
    client.beta.agents.create.side_effect = RuntimeError("429 rate limit")
    reponse = creer_agent("id", client=client)
    assert reponse["statut"] == "echec_technique"
    assert "429" in reponse["message"]


def test_creer_agent_reutilise_agent_persistant_conforme(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — garde-fou : réutilisation stricte
    _env_cle(monkeypatch)
    monkeypatch.setenv("MISTRAL_AGENT_ID", "ag-persistant")
    client = _client_faux()
    agent_console = MagicMock()
    agent_console.model = "mistral-small-latest"
    agent_console.instructions = PROMPT_SYSTEME
    agent_console.tools = [
        {"type": "function", "function": {"name": nom}}
        for nom in ("rechercher_jeux", "lister_ressources", "interroger_ressource", "telecharger_brut", "extraire_ressource")
    ]
    client.beta.agents.get.return_value = agent_console
    reponse = creer_agent("id", client=client)
    assert reponse["statut"] == "succes"
    agent = reponse["donnees"]["agent"]
    assert agent.ephemere is False
    assert agent.agent_id == "ag-persistant"
    client.beta.agents.create.assert_not_called()


def test_creer_agent_recreate_si_prompt_divergent(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — divergence prompt → agent éphémère neuf
    _env_cle(monkeypatch)
    monkeypatch.setenv("MISTRAL_AGENT_ID", "ag-persistant")
    client = _client_faux()
    agent_console = MagicMock()
    agent_console.model = "mistral-small-latest"
    agent_console.instructions = "un autre prompt modifie a la main"
    agent_console.tools = []
    client.beta.agents.get.return_value = agent_console
    reponse = creer_agent("id", client=client)
    assert reponse["statut"] == "succes"
    agent = reponse["donnees"]["agent"]
    assert agent.ephemere is True
    client.beta.agents.create.assert_called_once()


def test_creer_agent_agent_id_inaccessible(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — MISTRAL_AGENT_ID inconnu → éphémère
    _env_cle(monkeypatch)
    monkeypatch.setenv("MISTRAL_AGENT_ID", "ag-fantome")
    client = _client_faux()
    client.beta.agents.get.side_effect = RuntimeError("404 not found")
    reponse = creer_agent("id", client=client)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["agent"].ephemere is True
    client.beta.agents.create.assert_called_once()


# ---------------------------------------------------------------------
# detruire_agent
# ---------------------------------------------------------------------

def _agent_ephemere(client):
    return Agent(client=client, agent_id="ag-123", modele="mistral-small-latest", outils=[], ephemere=True)


def test_detruire_agent_ephemere():
    # Réf. tests/plan_tests.md : Annexe T5.3 — destruction de l'agent du flux
    client = MagicMock()
    reponse = detruire_agent(_agent_ephemere(client))
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["detruit"] is True
    client.beta.agents.delete.assert_called_once_with(agent_id="ag-123")


def test_detruire_agent_deja_absent():
    # Réf. tests/plan_tests.md : Annexe T5.3 — idempotence (crash entre create et finally)
    client = MagicMock()
    client.beta.agents.delete.side_effect = RuntimeError("404 not found")
    reponse = detruire_agent(_agent_ephemere(client))
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["detruit"] is False


def test_detruire_agent_erreur_reseau():
    # Réf. tests/plan_tests.md : Annexe T5.3 — échec propre + suggestion nettoyage
    client = MagicMock()
    client.beta.agents.delete.side_effect = RuntimeError("503 unavailable")
    reponse = detruire_agent(_agent_ephemere(client))
    assert reponse["statut"] == "echec_technique"
    assert reponse["donnees"]["suggestion"] == "nettoyer_agents_orphelins"


def test_detruire_agent_persistant_non_detruit():
    # Réf. tests/plan_tests.md : Annexe T5.3 — l'agent persistant réutilisé n'est jamais détruit
    client = MagicMock()
    agent = Agent(client=client, agent_id="ag-p", modele="m", outils=[], ephemere=False)
    reponse = detruire_agent(agent)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["detruit"] is False
    client.beta.agents.delete.assert_not_called()


def test_detruire_agent_argument_invalide():
    # Réf. tests/plan_tests.md : Annexe T5.3 — échec propre sur type inattendu
    reponse = detruire_agent("ag-123")
    assert reponse["statut"] == "erreur_parametres"


# ---------------------------------------------------------------------
# nettoyer_agents_orphelins
# ---------------------------------------------------------------------

def test_nettoyer_agents_orphelins(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — nettoyage des agents résiduels du projet
    _env_cle(monkeypatch)
    client = MagicMock()
    du_projet = MagicMock(id="ag-1", metadata={"projet": PREFIXE_NOM})
    du_projet.name = f"{PREFIXE_NOM}-vieux"
    etranger = MagicMock(id="ag-2", metadata={})
    etranger.name = "autre-agent"
    page = MagicMock(data=[du_projet, etranger])
    client.beta.agents.list.return_value = page
    reponse = nettoyer_agents_orphelins(client)
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["detruits"] == ["ag-1"]
    client.beta.agents.delete.assert_called_once_with(agent_id="ag-1")


def test_nettoyer_agents_orphelins_cle_absente(monkeypatch):
    # Réf. tests/plan_tests.md : Annexe T5.3 — échec propre sans clé
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    reponse = nettoyer_agents_orphelins(None)
    assert reponse["statut"] == "echec_technique"


# ---------------------------------------------------------------------
# empreinte
# ---------------------------------------------------------------------

def test_empreinte_differencie_prompts():
    # Réf. tests/plan_tests.md : Annexe T5.3 — base du garde-fou
    assert empreinte("a") != empreinte("b")
    assert empreinte(PROMPT_SYSTEME) == empreinte(PROMPT_SYSTEME)


# ---------------------------------------------------------------------
# Contenu du prompt systeme (T5.3.4)
# ---------------------------------------------------------------------

def test_prompt_sections_structurantes():
    # Réf. tests/plan_tests.md : Annexe T5.3.4 — présence des sections A1..A4 (+ MULTI-TOURS, T11.1)
    for marqueur in ("A1 - REFORMULATION", "A2 - SÉLECTION", "A3 - RÉSOLUTION DES INDETERMINATIONS",
                     "A4 - PROPOSITION ET SYNTHÈSE DU REGISTRE", "MULTI-TOURS"):
        assert marqueur in PROMPT_SYSTEME


def test_prompt_consignes_transversales():
    # Réf. tests/plan_tests.md : Annexe T5.3.4 — outils, statuts, identifiants, langue
    for outil in ("rechercher_jeux", "lister_ressources", "interroger_ressource", "telecharger_brut", "extraire_ressource"):
        assert outil in PROMPT_SYSTEME
    for statut in ("succes", "erreur_parametres", "jeu_introuvable", "ressource_introuvable",
                   "ressource_non_indexee", "licence_refusee", "echec_technique"):
        assert statut in PROMPT_SYSTEME
    assert "n'invente jamais un identifiant" in PROMPT_SYSTEME.lower() or "N'invente jamais un identifiant" in PROMPT_SYSTEME
    assert "francais" in PROMPT_SYSTEME
    assert "{statut, message, donnees}" in PROMPT_SYSTEME


def test_prompt_pagination_plafond_licence():
    # Réf. tests/plan_tests.md : Annexe T5.3.4 — pagination, plafond, licence, volumes
    assert "page_suivante" in PROMPT_SYSTEME
    assert "plafonné" in PROMPT_SYSTEME
    assert "licence" in PROMPT_SYSTEME.lower()
    assert "volume_eleve_telechargement_brut_suggere" in PROMPT_SYSTEME
    assert "fichier_heberge_exterieurement" in PROMPT_SYSTEME
    assert "indetermination" in PROMPT_SYSTEME


def test_prompt_garde_fou_t531_inchange():
    # Réf. tests/plan_tests.md : Annexe T5.3.4 — l'empreinte du prompt reste la référence du garde-fou
    from src.agent.agent import creer_agent
    import inspect
    source = inspect.getsource(creer_agent)
    assert "PROMPT_SYSTEME" in source


# ---------------------------------------------------------------------------
# Externalisation du prompt (19/10/2026) : config/prompt_systeme.txt
# ---------------------------------------------------------------------------


def test_prompt_systeme_charge_depuis_config():
    # Le prompt n'est plus en dur dans le code : il est chargé depuis
    # config/prompt_systeme.txt au démarrage du module.
    from src.agent import agent as module

    assert module.CHEMIN_PROMPT_SYSTEME.exists()
    assert module.PROMPT_SYSTEME == module._charger_prompt_systeme()
    assert module.PROMPT_SYSTEME.strip()
    assert len(module.PROMPT_SYSTEME) > 1000


def test_prompt_systeme_absent_echec_explicite(tmp_path):
    # Un prompt absent produit une ValueError explicite au chargement,
    # jamais un agent silencieusement démarré sans consignes.
    import pytest
    from src.agent.agent import _charger_prompt_systeme

    with pytest.raises(ValueError, match="absent"):
        _charger_prompt_systeme(tmp_path / "introuvable.txt")


def test_prompt_systeme_vide_echec_explicite(tmp_path):
    import pytest
    from src.agent.agent import _charger_prompt_systeme

    chemin = tmp_path / "vide.txt"
    chemin.write_text("   \n  ", encoding="utf-8")
    with pytest.raises(ValueError, match="vide"):
        _charger_prompt_systeme(chemin)


def test_prompt_consigne_interroger_seulement_si_indexee():
    # Verrou A3 (constat du 19/10/2026 : l'agent a sondé via interroger_ressource
    # une ressource indeterminee, api_tabulaire faux — invocation perdue d'avance).
    from src.agent.agent import PROMPT_SYSTEME

    assert "api_tabulaire vrai" in PROMPT_SYSTEME
    assert "ne l'invoque jamais sur une autre ressource" in PROMPT_SYSTEME
    assert "invocation perdue" in PROMPT_SYSTEME


def test_prompt_propose_puis_acquiert():
    # T11.1 (20/10/2026) : en multi-tours, acquisition sur validation explicite
    # de l'utilisateur. Remplace la clarification du 19/10 (le verrou A4 avait
    # rendu l'agent sur-prudent en one-shot ; le multi-tours rend la validation
    # un tour normal).
    from src.agent.agent import PROMPT_SYSTEME

    assert "PROPOSE-PUIS-ACQUIERT" in PROMPT_SYSTEME
    assert "Ne les invoque JAMAIS de toi-même" in PROMPT_SYSTEME
    assert "validation explicite de l'utilisateur" in PROMPT_SYSTEME
    assert "FEEDBACK UTILISATEUR" in PROMPT_SYSTEME
    # La consigne one-shot (acquisition sans attendre) est retirée
    assert "conduis-la sans attendre une autorisation" not in PROMPT_SYSTEME


def test_prompt_multi_tours():
    # T11.1 : section MULTI-TOURS (plafond par tour, contexte conservé, synthèse finale)
    from src.agent.agent import PROMPT_SYSTEME

    assert "MULTI-TOURS" in PROMPT_SYSTEME
    assert "plafond d'invocations est réinitialisé" in PROMPT_SYSTEME
    assert "mot-clé stop" in PROMPT_SYSTEME


def test_prompt_consigne_integrite_registre():
    # Verrou anti-hallucination (constat du 19/10/2026 : l'étape A4 citait un
    # chemin local jamais retourné par un outil) : seules les acquisitions
    # réelles peuvent figurer en "données acquises".
    from src.agent.agent import PROMPT_SYSTEME

    assert "Intégrité du registre" in PROMPT_SYSTEME
    assert "N'invente jamais un chemin local" in PROMPT_SYSTEME
    assert "jamais dans les données acquises" in PROMPT_SYSTEME
