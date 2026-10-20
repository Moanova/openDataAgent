# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_journal.py
# Version      : 1
# Date         : 14-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires du journal de conversation (T5.3.3, schéma multi-tours T11.1).

Refs tests/plan_tests.md : Annexes T5.3.3 (TU-C1..TU-C8) et section T11.1
(TU-C9, TU-C10). Aucun reseau : le journal ecrit dans des repertoires
temporaires, l'API Conversations est simulee."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.agent.agent import Agent
from src.agent.boucle import cloturer_conversation, creer_conversation, tour_conversation
from src.agent.journal import (
    JournalConversation,
    extraire_invocations,
    lire_journal,
)


def _evt_started(conversation_id="conv-1"):
    return SimpleNamespace(
        event="conversation.response.started",
        data=SimpleNamespace(type="conversation.response.started", conversation_id=conversation_id),
    )


def _evt_message(texte, id_msg="msg-1"):
    return SimpleNamespace(
        event="message.output.delta",
        data=SimpleNamespace(type="message.output.delta", id=id_msg,
                             content={"type": "text", "text": texte}, role="assistant"),
    )


def _evt_call(nom, arguments, tool_call_id="call-1"):
    return SimpleNamespace(
        event="function.call.delta",
        data=SimpleNamespace(type="function.call.delta", id=f"fc-{tool_call_id}", name=nom,
                             tool_call_id=tool_call_id, arguments=json.dumps(arguments)),
    )


def _evt_done():
    return SimpleNamespace(
        event="conversation.response.done",
        data=SimpleNamespace(type="conversation.response.done", usage=SimpleNamespace(total_tokens=42)),
    )


def _agent():
    client = MagicMock()
    return Agent(client=client, agent_id="ag-test", modele="mistral-small-latest", outils=[], ephemere=True)


# ---------------------------------------------------------------------
# JournalConversation (TU-C1..TU-C4)
# ---------------------------------------------------------------------

def test_entete_contexte(tmp_path):
    # Réf. tests/plan_tests.md : TU-C1 — en-tête contexte (modèle, prompt, plafond, date)
    journal = JournalConversation("id_test", modele="mistral-small-latest", prompt="prompt X", plafond=10, repertoire=tmp_path)
    journal.fermer("succes")
    enregistrements = lire_journal(journal.chemin)
    assert enregistrements[0]["event"] == "contexte"
    assert enregistrements[0]["modele"] == "mistral-small-latest"
    assert enregistrements[0]["prompt"] == "prompt X"
    assert enregistrements[0]["plafond"] == 10
    assert enregistrements[0]["date"]
    assert enregistrements[-1]["event"] == "fin"
    assert enregistrements[-1]["statut"] == "succes"


def test_enregistrements_horotes(tmp_path):
    # Réf. tests/plan_tests.md : TU-C2 (T11.1) — un enregistrement JSONL par événement, horodaté
    journal = JournalConversation("id_test", repertoire=tmp_path)
    journal.enregistrer("debut_tour", numero_tour=1, contenu="bonjour")
    journal.enregistrer("outil_invoque", outil="rechercher_jeux", arguments={"mots_cles": ["dette"]}, tour=1)
    journal.fermer("succes")
    lignes = journal.chemin.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 4
    for ligne in lignes:
        enregistrement = json.loads(ligne)
        assert enregistrement["timestamp"]
        assert enregistrement["id_execution"] == "id_test"
    evenements = [json.loads(l)["event"] for l in lignes]
    assert evenements == ["contexte", "debut_tour", "outil_invoque", "fin"]


def test_evenement_inconnu_devient_fin(tmp_path):
    # Réf. tests/plan_tests.md : Test annexe — event hors liste bornée
    journal = JournalConversation("id_test", repertoire=tmp_path)
    journal.enregistrer("evenement_bizarre", x=1)
    journal.fermer("succes")
    evenements = [e["event"] for e in lire_journal(journal.chemin)]
    assert "evenement_bizarre" not in evenements


def test_erreur_ecriture_silencieuse(tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-C3 — échec d'écriture jamais remonté
    journal = JournalConversation("id_test", repertoire=tmp_path)
    monkeypatch.setattr(journal, "_flux", None)
    journal.enregistrer("debut_tour", numero_tour=1, contenu="x")
    journal.fermer("succes")


# ---------------------------------------------------------------------
# Intégration tour_conversation -> journal (TU-C5, TU-C6, TU-C9, TU-C10)
# ---------------------------------------------------------------------

def test_tour_complete_journalise(tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-C5 (T11.1) — un tour complet : séquence d'événements multi-tours
    import src.agent.outils as module_outils
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux",
                        MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"jeux": []}}))
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"),
        _evt_message("Je lance la recherche."),
        _evt_call("rechercher_jeux", {"mots_cles": ["dette"]}, "a1"),
        _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.return_value = iter([
        _evt_message("Voici les jeux."), _evt_done(),
    ])
    journal = JournalConversation("id_flux", modele="mistral-small-latest", prompt="P", plafond=10, repertoire=tmp_path)
    conversation = creer_conversation(agent, "id_flux", plafond=10, journal=journal)
    reponse = tour_conversation(conversation, "cherche la dette")
    assert reponse["statut"] == "succes"
    evenements = [e["event"] for e in lire_journal(journal.chemin)]
    assert evenements == [
        "contexte",
        "debut_tour",
        "raisonnement_agent",
        "outil_invoque",
        "outil_resultat",
        "raisonnement_agent",
        "fin_tour",
    ]
    enregistrements = lire_journal(journal.chemin)
    assert enregistrements[1]["numero_tour"] == 1
    assert enregistrements[1]["contenu"] == "cherche la dette"
    assert enregistrements[2]["contenu"] == "Je lance la recherche."
    assert enregistrements[2]["tour"] == 1
    fin_tour = enregistrements[-1]
    assert fin_tour["statut"] == "succes"
    assert fin_tour["nb_invocations"] == 1
    assert fin_tour["synthese"] == "Voici les jeux."


def test_journal_plafond_et_erreur(tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-C6 (T11.1) — plafond et erreur API journalisés
    import src.agent.outils as module_outils
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux",
                        MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}}))
    agent = _agent()
    def _stream_infini():
        yield _evt_started("conv-1")
        for i in range(50):
            yield _evt_call("rechercher_jeux", {"mots_cles": ["x"]}, f"c{i}")
        yield _evt_done()
    agent.client.beta.conversations.start_stream.return_value = _stream_infini()
    agent.client.beta.conversations.append_stream.return_value = _stream_infini()
    journal = JournalConversation("id_p", repertoire=tmp_path)
    conversation = creer_conversation(agent, "id_p", plafond=2, journal=journal)
    reponse = tour_conversation(conversation, "x")
    assert "plafond" in reponse["message"].lower()
    evenements = [e["event"] for e in lire_journal(journal.chemin)]
    assert "plafond_atteint" in evenements
    assert "fin_tour" in evenements
    fin_tour = [e for e in lire_journal(journal.chemin) if e["event"] == "fin_tour"][0]
    assert fin_tour["statut"] == "succes_plafond"

    agent_ko = _agent()
    agent_ko.client.beta.conversations.start_stream.side_effect = RuntimeError("429")
    journal_ko = JournalConversation("id_ko", repertoire=tmp_path)
    conversation_ko = creer_conversation(agent_ko, "id_ko", journal=journal_ko)
    reponse_ko = tour_conversation(conversation_ko, "x")
    assert reponse_ko["statut"] == "echec_technique"
    evenements_ko = [e["event"] for e in lire_journal(journal_ko.chemin)]
    assert "erreur_api" in evenements_ko
    assert "fin_tour" in evenements_ko
    fin_tour_ko = [e for e in lire_journal(journal_ko.chemin) if e["event"] == "fin_tour"][0]
    assert fin_tour_ko["statut"] == "echec_technique"


# ---------------------------------------------------------------------
# Rejeu : lire_journal / extraire_invocations (TU-C7, TU-C8)
# ---------------------------------------------------------------------

def test_extraire_invocations_rejeu(tmp_path, monkeypatch):
    # Réf. tests/plan_tests.md : TU-C7 (T11.1) — extraction ordonnée (base TA-01/TA-02)
    import src.agent.outils as module_outils
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux",
                        MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"jeux": [{"id": "abc"}]}}))
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "lister_ressources",
                        MagicMock(return_value={"statut": "succes", "message": "", "donnees": {"ressources": []}}))
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"),
        _evt_call("rechercher_jeux", {"mots_cles": ["dette"]}, "a1"),
        _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.side_effect = [
        iter([_evt_call("lister_ressources", {"id_jeu": "abc"}, "a2"), _evt_done()]),
        iter([_evt_message("Fini."), _evt_done()]),
    ]
    journal = JournalConversation("id_r", repertoire=tmp_path)
    conversation = creer_conversation(agent, "id_r", journal=journal)
    tour_conversation(conversation, "dette")
    invocations = extraire_invocations(lire_journal(journal.chemin))
    assert len(invocations) == 2
    assert invocations[0]["outil"] == "rechercher_jeux"
    assert invocations[0]["arguments"] == {"mots_cles": ["dette"]}
    assert invocations[0]["statut"] == "succes"
    assert invocations[1]["outil"] == "lister_ressources"
    assert invocations[1]["arguments"]["id_jeu"] == "abc"
    assert [i["tour"] for i in invocations] == [1, 2]


def test_journal_fin_totaux_conversation(tmp_path, monkeypatch):
    # Réf. T11.1 TU-C10 — fin : totaux de la conversation (nb_tours, nb_invocations)
    import src.agent.outils as module_outils
    monkeypatch.setitem(module_outils.TABLE_OUTILS, "rechercher_jeux",
                        MagicMock(return_value={"statut": "succes", "message": "", "donnees": {}}))
    agent = _agent()
    agent.client.beta.conversations.start_stream.return_value = iter([
        _evt_started("conv-1"),
        _evt_call("rechercher_jeux", {"mots_cles": ["a"]}, "c1"),
        _evt_done(),
    ])
    agent.client.beta.conversations.append_stream.side_effect = [
        iter([_evt_message("Tour 1."), _evt_done()]),
        iter([_evt_message("Tour 2."), _evt_done()]),
    ]
    journal = JournalConversation("id_tot", repertoire=tmp_path)
    conversation = creer_conversation(agent, "id_tot", journal=journal)
    tour_conversation(conversation, "tour 1")
    tour_conversation(conversation, "tour 2")
    cloturer_conversation(conversation, "succes")
    enregistrements = lire_journal(journal.chemin)
    fin = enregistrements[-1]
    assert fin["event"] == "fin"
    assert fin["statut"] == "succes"
    assert fin["nb_tours"] == 2
    assert fin["nb_invocations"] == 1
    fins_tours = [e for e in enregistrements if e["event"] == "fin_tour"]
    assert [e["numero_tour"] for e in fins_tours] == [1, 2]


def test_lire_journal_tolerant(tmp_path):
    # Réf. tests/plan_tests.md : TU-C8 — lignes corrompues/absentes ignorées
    chemin = tmp_path / "conversation.jsonl"
    chemin.write_text(
        json.dumps({"event": "contexte", "id_execution": "x"}) + "\n"
        + "{ligne corrompue\n"
        + "\n"
        + json.dumps({"event": "fin", "statut": "succes"}) + "\n",
        encoding="utf-8",
    )
    enregistrements = lire_journal(chemin)
    assert len(enregistrements) == 2
    assert lire_journal(tmp_path / "absent.jsonl") == []
