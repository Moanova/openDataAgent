# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_boucle.py
# Version      : 2
# Date         : 20-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de la boucle de conversation multi-tours (T11.1).

Refs tests/plan_tests.md : TU-B1..TU-B3 (dispatch, inchangés) et section
T11.1 (TU-B13..TU-B22). L'API Mistral Conversations et les fonctions
coeur sont simulees : aucun reseau."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import src.agent.outils as module_outils
from src.agent.agent import Agent
from src.agent.boucle import (
    PLAFOND_DEFAUT,
    ConversationServeur,
    cloturer_conversation,
    creer_conversation,
    tour_conversation,
)
from src.agent.journal import JournalConversation
from src.agent.outils import executer_outil


# ---------------------------------------------------------------------
# Helpers : evenements SDK Conversations simules
# ---------------------------------------------------------------------

def _evt_started(conversation_id="conv-1"):
    return SimpleNamespace(
        event="conversation.response.started",
        data=SimpleNamespace(type="conversation.response.started", conversation_id=conversation_id),
    )


def _evt_message(texte, id_msg="msg-1"):
    return SimpleNamespace(
        event="message.output.delta",
        data=SimpleNamespace(
            type="message.output.delta", id=id_msg,
            content={"type": "text", "text": texte}, role="assistant",
        ),
    )


def _evt_call(nom, arguments, tool_call_id="call-1", output_index=0):
    return SimpleNamespace(
        event="function.call.delta",
        data=SimpleNamespace(
            type="function.call.delta", id=f"fc-{tool_call_id}", name=nom,
            tool_call_id=tool_call_id, arguments=json.dumps(arguments),
            output_index=output_index,
        ),
    )


def _evt_done():
    return SimpleNamespace(
        event="conversation.response.done",
        data=SimpleNamespace(type="conversation.response.done", usage=SimpleNamespace(total_tokens=42)),
    )


def _evt_erreur(message="boom"):
    return SimpleNamespace(
        event="conversation.response.error",
        data=SimpleNamespace(type="conversation.response.error", message=message),
    )


def _agent():
    client = MagicMock()
    return Agent(client=client, agent_id="ag-test", modele="m", outils=[], ephemere=True)


def _conversation(agent=None, plafond=10, journal=None):
    agent = agent or _agent()
    return creer_conversation(agent, "id_test", plafond=plafond, journal=journal)


# ---------------------------------------------------------------------
# executer_outil (TU-B1, TU-B2, TU-B3 — inchanges, dispatch vers le coeur)
# ---------------------------------------------------------------------

def test_executer_outil_route_chaque_outil(monkeypatch):
    # Ref. tests/plan_tests.md : TU-B1 — dispatch vers les 5 fonctions coeur
    outils = {}
    for nom in ("rechercher_jeux", "lister_ressources", "interroger_ressource", "telecharger_brut", "extraire_ressource"):
        faux = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})
        monkeypatch.setitem(module_outils.TABLE_OUTILS, nom, faux)
        outils[nom] = faux

    executer_outil("rechercher_jeux", {"mots_cles": ["dette"]}, "id")
    outils["rechercher_jeux"].assert_called_once_with(mots_cles=["dette"], id_execution="id")

    executer_outil("lister_ressources", {"id_jeu": "abc"}, "id")
    outils["lister_ressources"].assert_called_once_with(id_jeu="abc", id_execution="id")

    executer_outil("interroger_ressource", {"id_ressource": "r1", "page": 2, "tri": {"colonne": "v", "ordre": "croissant"}}, "id")
    outils["interroger_ressource"].assert_called_once_with(id_ressource="r1", page=2, tri={"colonne": "v", "ordre": "croissant"}, id_execution="id")

    executer_outil("telecharger_brut", {"id_ressource": "r1"}, "id")
    outils["telecharger_brut"].assert_called_once_with(id_ressource="r1", id_execution="id")

    executer_outil("extraire_ressource", {"id_ressource": "r1"}, "id")
    outils["extraire_ressource"].assert_called_once_with(id_ressource="r1", id_execution="id")


def test_executer_outil_inconnu():
    # Ref. tests/plan_tests.md : TU-B2 — outil hors table → erreur_parametres
    reponse = executer_outil("outil_invente", {}, "id")
    assert reponse["statut"] == "erreur_parametres"
    assert "outil_invente" in reponse["message"]


def test_executer_outil_arguments_invalides(monkeypatch):
    # Ref. tests/plan_tests.md : TU-B2 — arguments invalides → erreur_parametres
    assert executer_outil("rechercher_jeux", {"mots_cles": []}, "id")["statut"] == "erreur_parametres"
    assert executer_outil("telecharger_brut", {}, "id")["statut"] == "erreur_parametres"
    assert executer_outil("lister_ressources", "pas un json{", "id")["statut"] == "erreur_parametres"
    faux = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "interroger_ressource", faux)
    assert executer_outil("interroger_ressource", json.dumps({"id_ressource": "r1"}), "id")["statut"] == "succes"


def test_executer_outil_id_execution_injecte_si_absent(monkeypatch):
    # Ref. T10.3 — id_execution de la boucle injecte si l'agent ne le fournit pas
    faux = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", faux)
    reponse = executer_outil("rechercher_jeux", {"mots_cles": ["dette"]}, "id-boucle")
    assert reponse["statut"] == "succes"
    faux.assert_called_once_with(mots_cles=["dette"], id_execution="id-boucle")


def test_executer_outil_id_execution_boucle_prioritaire(monkeypatch):
    # Ref. T10.3 — id_execution fourni par l'agent : pas de conflit, celui de la boucle prime
    faux = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", faux)
    reponse = executer_outil(
        "rechercher_jeux",
        {"mots_cles": ["dette"], "id_execution": "id-agent"},
        "id-boucle",
    )
    assert reponse["statut"] == "succes"
    faux.assert_called_once_with(mots_cles=["dette"], id_execution="id-boucle")


def test_executer_outil_arguments_json(monkeypatch):
    # Ref. tests/plan_tests.md : TU-B3 — arguments en chaine JSON acceptes
    faux = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", faux)
    reponse = executer_outil("rechercher_jeux", json.dumps({"mots_cles": ["insee"]}), "id")
    assert reponse["statut"] == "succes"
    faux.assert_called_once_with(mots_cles=["insee"], id_execution="id")


# ---------------------------------------------------------------------
# T10.4 : validation Pydantic des arguments au runtime (inchanges)
# ---------------------------------------------------------------------

@patch.dict(module_outils.TABLE_OUTILS, {"rechercher_jeux": MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})})
def test_outil_valide_bornes_numeriques_pydantic():
    # Ref. T10.4 — limite/page hors bornes du modele Input → erreur_parametres
    reponse = executer_outil("rechercher_jeux", {"mots_cles": ["dette"], "limite": -5}, "id")
    assert reponse["statut"] == "erreur_parametres"
    assert "limite" in reponse["message"]
    reponse_2 = executer_outil("rechercher_jeux", {"mots_cles": ["dette"], "page": 0}, "id")
    assert reponse_2["statut"] == "erreur_parametres"
    assert "page" in reponse_2["message"]


@patch.dict(module_outils.TABLE_OUTILS, {"interroger_ressource": MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})})
def test_outil_valide_sous_modeles_filtre_tri():
    # Ref. T10.4 — tri avec ordre hors vocabulaire → erreur_parametres avec champ fautif
    reponse = executer_outil("interroger_ressource", {"id_ressource": "r1", "tri": {"colonne": "v", "ordre": "ascendant"}}, "id")
    assert reponse["statut"] == "erreur_parametres"
    assert "tri" in reponse["message"]
    module_outils.TABLE_OUTILS["interroger_ressource"].assert_not_called()


@patch.dict(module_outils.TABLE_OUTILS, {"rechercher_jeux": MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})})
def test_outil_ignore_champs_superflus():
    # Ref. T10.4 — extra="ignore" : champ inconnu de l'agent ignore silencieusement
    faux = module_outils.TABLE_OUTILS["rechercher_jeux"]
    reponse = executer_outil("rechercher_jeux", {"mots_cles": ["dette"], "champ_inconnu": 1}, "id")
    assert reponse["statut"] == "succes"
    kwargs = faux.call_args.kwargs
    assert "champ_inconnu" not in kwargs
    assert kwargs["mots_cles"] == ["dette"]


@patch.dict(module_outils.TABLE_OUTILS, {"telecharger_brut": MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}})})
def test_outil_champs_absents_non_transmis():
    # Ref. T10.4 — seuls les champs fournis par l'agent sont transmis (exclude_unset)
    faux = module_outils.TABLE_OUTILS["telecharger_brut"]
    executer_outil("telecharger_brut", {"id_ressource": "r1"}, "id")
    kwargs = faux.call_args.kwargs
    assert kwargs == {"id_ressource": "r1", "id_execution": "id"}


def test_outil_message_erreur_exploitable():
    # Ref. T10.4 — le message d'erreur cite le champ fautif (auto-correction de l'agent)
    reponse = executer_outil("lister_ressources", {}, "id")
    assert reponse["statut"] == "erreur_parametres"
    assert "id_jeu" in reponse["message"]


@patch.dict(module_outils.TABLE_OUTILS, {"extraire_ressource": MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"chemin_local": "data/raw/x.csv", "tronque": False}})})
def test_executer_outil_extraire_ressource():
    # Ref. T10.7 — le tool_call extraire_ressource est route vers la fonction coeur
    faux = module_outils.TABLE_OUTILS["extraire_ressource"]
    reponse = executer_outil("extraire_ressource", {"id_ressource": "r1"}, "id-boucle")
    assert reponse["statut"] == "succes"
    faux.assert_called_once_with(id_ressource="r1", id_execution="id-boucle")


def test_executer_outil_extraire_ressource_argument_manquant():
    # Ref. T10.7 — validation Pydantic standard : id_ressource requis
    reponse = executer_outil("extraire_ressource", {}, "id")
    assert reponse["statut"] == "erreur_parametres"
    assert "id_ressource" in reponse["message"]


# ---------------------------------------------------------------------
# T11.1 — creer_conversation / tour_conversation / cloturer_conversation
# ---------------------------------------------------------------------

def test_creer_conversation_journal_contexte(tmp_path):
    # Ref. T11.1 TU-B13 — contexte : empreinte du prompt (pas le texte), plafond, une fois
    journal = JournalConversation("id_test", plafond=7, repertoire=tmp_path)
    conversation = _conversation(plafond=7, journal=journal)
    assert conversation.plafond == 7
    assert conversation.conversation_id is None
    assert conversation.nb_tours == 0
    assert conversation.nb_invocations == 0
    journal.fermer("succes")
    enregistrements = json.loads(journal.chemin.read_text(encoding="utf-8").splitlines()[0])
    assert enregistrements["event"] == "contexte"
    assert enregistrements["plafond"] == 7
    # L'empreinte ne contient pas le texte du prompt
    assert len(enregistrements["prompt"]) <= 16


def test_tour_reponse_directe_sans_outil():
    # Ref. T11.1 TU-B14 — reponse immediate sans outil (start_stream)
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-abc"), _evt_message("Bonjour."), _evt_done(),
    ])
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "bonjour")
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["synthese"] == "Bonjour."
    assert reponse["donnees"]["nb_invocations"] == 0
    assert reponse["donnees"]["numero_tour"] == 1
    assert reponse["donnees"]["conversation_id"] == "conv-abc"
    assert conversation.conversation_id == "conv-abc"
    # start_stream appele avec le message utilisateur, agent_id, store, name, metadata
    kwargs = agent.client.beta.conversations.start_stream.call_args.kwargs
    assert kwargs["inputs"] == "bonjour"
    assert kwargs["agent_id"] == "ag-test"
    assert kwargs["store"] is True
    assert "openDataAgent" in kwargs["name"]


def test_tour_avec_tool_call_puis_reponse_finale(monkeypatch):
    # Ref. T11.1 TU-B15 — 1 tool_call execute localement, resultat renvoye par append_stream
    mock_search = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"jeux": []}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", mock_search)
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"),
        _evt_message("Je lance la recherche."),
        _evt_call("rechercher_jeux", {"mots_cles": ["dette"]}, "c1"),
        _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Voici les jeux."), _evt_done(),
    ])
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "cherche la dette")
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["synthese"] == "Voici les jeux."
    assert reponse["donnees"]["nb_invocations"] == 1
    mock_search.assert_called_once_with(mots_cles=["dette"], id_execution="id_test")
    # Le resultat est renvoye au serveur par une entree function.result
    kwargs = agent.client.beta.conversations.append_stream.call_args.kwargs
    assert kwargs["conversation_id"] == "conv-1"
    entrees = kwargs["inputs"]
    assert len(entrees) == 1
    assert entrees[0]["type"] == "function.result"
    assert entrees[0]["tool_call_id"] == "c1"
    assert json.loads(entrees[0]["result"])["statut"] == "succes"


def test_tour_multi_tours_contexte_serveur_conserve():
    # Ref. T11.1 TU-B16 — second tour : append_stream avec le nouveau message seul
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"), _evt_message("Tour 1."), _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Tour 2."), _evt_done(),
    ])
    conversation = _conversation(agent)
    r1 = tour_conversation(conversation, "premier message")
    r2 = tour_conversation(conversation, "second message")
    assert r1["donnees"]["numero_tour"] == 1
    assert r2["donnees"]["numero_tour"] == 2
    assert r2["donnees"]["conversation_id"] == "conv-1"
    # Le second tour n'envoie que le nouveau message (contexte serveur)
    kwargs = agent.client.beta.conversations.append_stream.call_args.kwargs
    assert kwargs["inputs"] == "second message"
    assert conversation.nb_tours == 2


def test_tour_plafond_reinitialise_par_tour(monkeypatch):
    # Ref. T11.1 TU-B17 — le plafond s'applique par tour et est reinitialise a chaque tour
    mock_search = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"jeux": []}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", mock_search)
    agent = _agent()
    # Tour 1 : le serveur emet des tool_calls en continu ; le plafond (3) coupe le tour
    def _stream_infini():
        yield _evt_started("conv-1")
        for i in range(100):
            yield _evt_call("rechercher_jeux", {"mots_cles": [f"m{i}"]}, f"c{i}", output_index=i)
        yield _evt_done()
    agent.client.beta.conversations.start_stream.return_value = _stream_infini()
    agent.client.beta.conversations.append_stream.return_value = _stream_infini()
    conversation = _conversation(agent, plafond=3)
    r1 = tour_conversation(conversation, "tour 1")
    assert r1["statut"] == "succes"
    assert "plafond" in r1["message"].lower()
    assert r1["donnees"]["nb_invocations"] == 3
    # Tour 2 : reponse directe sans outil — le plafond est de nouveau disponible
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Tour 2 reussi."), _evt_done(),
    ])
    r2 = tour_conversation(conversation, "tour 2")
    assert r2["statut"] == "succes"
    assert r2["donnees"]["nb_invocations"] == 0
    assert r2["donnees"]["synthese"] == "Tour 2 reussi."
    # Total conversation : 3 invocations (seul le tour 1 en a consomme)
    assert conversation.nb_invocations == 3
    assert conversation.nb_tours == 2


def test_tour_erreur_outil_renvoyee_agent(monkeypatch):
    # Ref. T11.1 TU-B18 — statut d'erreur du coeur renvoye tel quel (entree function.result)
    mock_dl = MagicMock(return_value={"statut": "ressource_introuvable", "message": "inconnu", "donnees": {}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "telecharger_brut", mock_dl)
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"),
        _evt_call("telecharger_brut", {"id_ressource": "r1"}, "c1"),
        _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Ressource introuvable."), _evt_done(),
    ])
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "telecharge")
    assert reponse["statut"] == "succes"
    entrees = agent.client.beta.conversations.append_stream.call_args.kwargs["inputs"]
    assert json.loads(entrees[0]["result"])["statut"] == "ressource_introuvable"


def test_tour_arguments_non_json_erreur_parametres():
    # Ref. T11.1 TU-B19 — tool_call illisible → erreur_parametres renvoyee, tour continue
    agent = _agent()
    appel = SimpleNamespace(
        event="function.call.delta",
        data=SimpleNamespace(
            type="function.call.delta", id="fc-1", name="rechercher_jeux",
            tool_call_id="c1", arguments="{pas du json",
        ),
    )
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"), appel, _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Arguments corriges."), _evt_done(),
    ])
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "x")
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["nb_invocations"] == 1
    entrees = agent.client.beta.conversations.append_stream.call_args.kwargs["inputs"]
    assert json.loads(entrees[0]["result"])["statut"] == "erreur_parametres"


def test_tour_erreur_api_echec_propre():
    # Ref. T11.1 TU-B20 — erreur SDK sur start_stream → echec_technique propre
    agent = _agent()
    agent.client.beta.conversations.start_stream.side_effect = RuntimeError("429 rate limit")
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "x")
    assert reponse["statut"] == "echec_technique"
    assert "429" in reponse["message"]
    assert reponse["donnees"]["nb_invocations"] == 0


def test_tour_erreur_stream_evenement_error():
    # Ref. T11.1 TU-B21 — evenement conversation.response.error → echec_technique
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"), _evt_erreur("quota depasse"), _evt_done(),
    ])
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "x")
    assert reponse["statut"] == "echec_technique"
    assert "quota depasse" in reponse["message"]


def test_tour_plafond_env(monkeypatch):
    # Ref. T11.1 TU-B22 — PLAFOND_INVOCATIONS dans l'environnement (plafond non explicite)
    monkeypatch.setenv("PLAFOND_INVOCATIONS", "2")
    conversation = creer_conversation(_agent(), "id_test")
    assert conversation.plafond == 2
    monkeypatch.delenv("PLAFOND_INVOCATIONS")
    conversation = creer_conversation(_agent(), "id_test")
    assert conversation.plafond == PLAFOND_DEFAUT


def test_cloturer_conversation_supprime_serveur():
    # Ref. T11.1 — cloturer_conversation : evenement fin + delete cote serveur
    agent = _agent()
    conversation = _conversation(agent)
    conversation.conversation_id = "conv-1"
    conversation.nb_tours = 2
    conversation.nb_invocations = 5
    resultat = cloturer_conversation(conversation, "succes")
    assert resultat["statut"] == "succes"
    assert resultat["donnees"]["supprimee"] is True
    agent.client.beta.conversations.delete.assert_called_once_with(conversation_id="conv-1")


def test_cloturer_conversation_sans_id_serveur():
    # Ref. T11.1 — cloture avant le premier tour : pas de delete, pas d'erreur
    agent = _agent()
    conversation = _conversation(agent)
    resultat = cloturer_conversation(conversation, "succes")
    assert resultat["statut"] == "succes"
    assert resultat["donnees"]["supprimee"] is False
    agent.client.beta.conversations.delete.assert_not_called()


def test_cloturer_conversation_deja_absente_idempotent():
    # Ref. T11.1 — conversation deja supprimee (404) : succes idempotent
    agent = _agent()
    agent.client.beta.conversations.delete.side_effect = RuntimeError("404 not found")
    conversation = _conversation(agent)
    conversation.conversation_id = "conv-1"
    resultat = cloturer_conversation(conversation, "succes")
    assert resultat["statut"] == "succes"
    assert resultat["donnees"]["supprimee"] is False


def test_cloturer_conversation_erreur_suppression_non_bloquante():
    # Ref. T11.1 — erreur de suppression : echec_technique retourne, pas d'exception
    agent = _agent()
    agent.client.beta.conversations.delete.side_effect = RuntimeError("500 serveur")
    conversation = _conversation(agent)
    conversation.conversation_id = "conv-1"
    resultat = cloturer_conversation(conversation, "succes")
    assert resultat["statut"] == "echec_technique"
    assert resultat["donnees"]["supprimee"] is False


def test_tour_journalise_schema_multi_tours(tmp_path, monkeypatch):
    # Ref. T11.1 TU-C9 — un tour complet produit debut_tour/fin_tour + invocations
    mock_search = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"jeux": []}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", mock_search)
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"),
        _evt_message("Je cherche."),
        _evt_call("rechercher_jeux", {"mots_cles": ["dette"]}, "c1"),
        _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Synthese."), _evt_done(),
    ])
    journal = JournalConversation("id_test", modele="m", prompt="empreinte", plafond=10, repertoire=tmp_path)
    conversation = creer_conversation(agent, "id_test", plafond=10, journal=journal)
    tour_conversation(conversation, "cherche la dette")
    cloturer_conversation(conversation, "succes")
    lignes = [json.loads(l) for l in journal.chemin.read_text(encoding="utf-8").splitlines()]
    evenements = [l["event"] for l in lignes]
    assert evenements == [
        "contexte", "debut_tour", "raisonnement_agent",
        "outil_invoque", "outil_resultat", "raisonnement_agent", "fin_tour", "fin",
    ]
    assert lignes[1]["numero_tour"] == 1
    assert lignes[1]["contenu"] == "cherche la dette"
    fin_tour = lignes[-2]
    assert fin_tour["event"] == "fin_tour"
    assert fin_tour["numero_tour"] == 1
    assert fin_tour["nb_invocations"] == 1
    assert fin_tour["synthese"] == "Synthese."
    assert lignes[-1]["nb_tours"] == 1
    assert lignes[-1]["nb_invocations"] == 1


def _evt_call_fragmente(nom, fragments, tool_call_id, output_index=0, avec_identite_sur_premier=True):
    """Émet un appel d'outil fragmenté en plusieurs deltas (API Conversations réelle).

    L'identité (name, tool_call_id) n'est portée que par le premier delta ;
    chaque delta porte un fragment de la chaîne JSON des arguments.
    """
    evenements = []
    for i, fragment in enumerate(fragments):
        identite = avec_identite_sur_premier and i == 0
        evenements.append(SimpleNamespace(
            event="function.call.delta",
            data=SimpleNamespace(
                type="function.call.delta",
                id=f"fc-{tool_call_id}-{i}",
                name=nom if identite else "",
                tool_call_id=tool_call_id if identite else "",
                arguments=fragment,
                output_index=output_index,
            ),
        ))
    return evenements


def test_tour_deltas_fragmentes_reconstitues(monkeypatch):
    # Ref. T11.1 TU-B23 — un appel fragmente en deltas (même output_index)
    # est reconstitué : identite sur le 1er delta, arguments concaténés.
    # Regression du 20/10/2026 (erreur 400 "Duplicate function results").
    mock_search = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"jeux": []}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", mock_search)
    agent = _agent()
    arguments_complets = json.dumps({"mots_cles": ["résultats", "élections"], "tri": "pertinence"})
    # 3 fragments qui, concaténés, reforment le JSON complet
    f1, f2, f3 = arguments_complets[:10], arguments_complets[10:25], arguments_complets[25:]
    deltas = _evt_call_fragmente("rechercher_jeux", [f1, f2, f3], "EdhJbxRCA", output_index=0)
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"), *deltas, _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Jeux trouvés."), _evt_done(),
    ])
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "cherche les résultats des élections")
    assert reponse["statut"] == "succes"
    # UN SEUL appel exécuté malgré les 3 deltas
    assert reponse["donnees"]["nb_invocations"] == 1
    mock_search.assert_called_once_with(mots_cles=["résultats", "élections"], tri="pertinence", id_execution="id_test")
    # UN SEUL résultat renvoyé, avec le bon tool_call_id
    entrees = agent.client.beta.conversations.append_stream.call_args.kwargs["inputs"]
    assert len(entrees) == 1
    assert entrees[0]["tool_call_id"] == "EdhJbxRCA"
    assert json.loads(entrees[0]["result"])["statut"] == "succes"


def test_tour_deltas_entrelaces_par_output_index(monkeypatch):
    # Ref. T11.1 TU-B24 — deltas de deux appels entremêlés (output_index
    # distincts) : chaque appel est reconstitué indépendamment, dans l'ordre.
    mock_search = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"jeux": []}})
    mock_list = MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"ressources": []}})
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux", mock_search)
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "lister_ressources", mock_list)
    agent = _agent()
    args_a = json.dumps({"mots_cles": ["dette"]})
    args_b = json.dumps({"id_jeu": "jeu-1"})
    # Entrelacement : A1, B1, A2, B2 (output_index 0 = recherche, 1 = listage)
    deltas = [
        *_evt_call_fragmente("rechercher_jeux", [args_a[:8], args_a[8:]], "cA", output_index=0),
        *_evt_call_fragmente("lister_ressources", [args_b[:5], args_b[5:]], "cB", output_index=1),
    ]
    # Ordre réel entremêlé : A1, B1, A2, B2
    entrelaces = [deltas[0], deltas[2], deltas[1], deltas[3]]
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"), *entrelaces, _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Deux appels faits."), _evt_done(),
    ])
    conversation = _conversation(agent)
    reponse = tour_conversation(conversation, "cherche puis liste")
    assert reponse["statut"] == "succes"
    assert reponse["donnees"]["nb_invocations"] == 2
    mock_search.assert_called_once_with(mots_cles=["dette"], id_execution="id_test")
    mock_list.assert_called_once_with(id_jeu="jeu-1", id_execution="id_test")
    # Deux résultats distincts renvoyés, tool_call_ids différents, ordre des output_index
    entrees = agent.client.beta.conversations.append_stream.call_args.kwargs["inputs"]
    assert [e["tool_call_id"] for e in entrees] == ["cA", "cB"]
