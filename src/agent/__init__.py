# -*- coding: utf-8 -*-
"""Partie agentique openDataAgent : agent Mistral et boucle de conversation."""
from src.agent.agent import (
    Agent,
    MODELE_DEFAUT,
    PREFIXE_NOM,
    PROMPT_SYSTEME,
    charger_outils,
    creer_agent,
    detruire_agent,
    empreinte,
    nettoyer_agents_orphelins,
)

__all__ = [
    "Agent",
    "MODELE_DEFAUT",
    "PREFIXE_NOM",
    "PROMPT_SYSTEME",
    "charger_outils",
    "creer_agent",
    "detruire_agent",
    "empreinte",
    "nettoyer_agents_orphelins",
]

from src.agent.boucle import (
    PLAFOND_DEFAUT,
    ConversationServeur,
    cloturer_conversation,
    creer_conversation,
    tour_conversation,
)
from src.agent.outils import TABLE_OUTILS, executer_outil

__all__ += [
    "PLAFOND_DEFAUT",
    "ConversationServeur",
    "cloturer_conversation",
    "creer_conversation",
    "tour_conversation",
    "TABLE_OUTILS",
    "executer_outil",
]

from src.agent.journal import JournalConversation, extraire_invocations, lire_journal

__all__ += ["JournalConversation", "extraire_invocations", "lire_journal"]
