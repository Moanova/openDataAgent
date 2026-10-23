# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : boucle.py
# Version      : 2
# Date         : 20-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Conversation agentique multi-tours, contexte côté serveur (T11.1).

La conversation vit sur la console Mistral via l'API Conversations
(`client.beta.conversations`) : `start_stream` crée la conversation au
premier message, `append_stream` la poursuit (message utilisateur ou
résultats d'outils). Seul le nouveau contenu est envoyé à chaque appel ;
l'historique complet est conservé côté serveur.

La boucle tool-calling reste **côté client** : les événements
`function.call.delta` émis par le serveur sont exécutés localement
(`executer_outil`, jamais par l'API) et leurs résultats normalisés sont
renvoyés au serveur par des entrées `function.result`.

Un tour = un message utilisateur, déroulé jusqu'à la réponse finale de
l'agent ou au plafond d'invocations (défaut 10, réinitialisé à chaque
tour — CA-11). La conversation est supprimée côté serveur à la clôture
(`client.beta.conversations.delete`, idempotent).

Journalisation (schéma multi-tours, T11.1) : `contexte` (empreinte du
prompt, une fois), `debut_tour`/`fin_tour` (par tour), `fin` (totaux).
La journalisation ne bloque jamais la conversation (TA-02)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.agent.agent import PREFIXE_NOM, PROMPT_SYSTEME, empreinte
from src.agent.circuit import MOTIF_CIRCUIT_OUVERT, CircuitBreaker, hote_depuis_url
from src.agent.journal import JournalConversation
from src.agent.outils import _decoder_arguments, executer_outil
from src.core.resources import inventaire
from src.utils.http import URL_BASE_DEFAUT as URL_BASE_API_DEFAUT
from src.utils.http import URL_BASE_TABULAIRE_DEFAUT
from src.utils.journalisation import bind_context, get_logger, log_to_file

PLAFOND_DEFAUT = 10

logger = get_logger("openDataAgent.agent.boucle")


@dataclass
class ConversationServeur:
    """État d'une conversation multi-tours côté serveur.

    Attributs :
        agent : objet Agent retourné par creer_agent.
        id_execution : identifiant du flux (une conversation = un id).
        plafond : nombre maximum d'invocations d'outils **par tour**.
        journal : journal JSONL de la conversation (schéma multi-tours).
        conversation_id : identifiant serveur de la conversation (None
                         avant le premier tour, lu sur l'événement
                         `conversation.response.started`).
        nb_tours : nombre de tours utilisateur conduits.
        nb_invocations : nombre total d'invocations d'outils.
        circuit : circuit breaker par hôte (T7.7) — en mémoire, attaché
                 à la conversation ; détruit avec elle à la clôture.
    """

    agent: Any
    id_execution: str
    plafond: int
    journal: JournalConversation
    conversation_id: Optional[str] = None
    nb_tours: int = 0
    nb_invocations: int = 0
    circuit: CircuitBreaker = field(default_factory=CircuitBreaker)


def creer_conversation(
    agent: Any,
    id_execution: str,
    plafond: Optional[int] = None,
    journal: Optional[JournalConversation] = None,
) -> ConversationServeur:
    """Prépare une conversation multi-tours (sans l'ouvrir côté serveur).

    Le plafond est résolu ici (paramètre, puis PLAFOND_INVOCATIONS, puis
    PLAFOND_DEFAUT) : il s'applique par tour, réinitialisé à chaque
    message utilisateur. Le journal reçoit l'événement `contexte`
    (empreinte du prompt, pas le texte complet).
    """
    plafond = plafond or int(os.environ.get("PLAFOND_INVOCATIONS", PLAFOND_DEFAUT))
    bind_context(id_execution=id_execution)
    if journal is None:
        journal = JournalConversation(
            id_execution,
            modele=getattr(agent, "modele", ""),
            prompt=empreinte(PROMPT_SYSTEME)[:16],
            plafond=plafond,
        )
    conversation = ConversationServeur(
        agent=agent,
        id_execution=id_execution,
        plafond=plafond,
        journal=journal,
    )
    log_to_file("conversation_prete", plafond=plafond, id_execution=id_execution)
    return conversation


def _hote_cible(nom: str, arguments: Dict[str, Any]) -> Optional[str]:
    """Hôte réseau visé par un outil (T7.7), résolu sans appel réseau.

    - telecharger_brut : URL de la ressource lue dans l'inventaire
      (jamais un argument) — serveur d'origine du fichier.
    - extraire_ressource / interroger_ressource : API tabulaire
      (hôte fixe `TABULAR_API_URL`), comme rechercher_jeux /
      lister_ressources qui visent l'API data.gouv.fr.
    Retourne None si l'hôte ne peut pas être déterminé (le circuit
    laisse alors passer : fail-safe).
    """
    if nom == "telecharger_brut":
        id_ressource = arguments.get("id_ressource")
        if isinstance(id_ressource, str):
            metadonnees = inventaire().get(id_ressource) or {}
            return hote_depuis_url(metadonnees.get("url") or "")
        return None
    if nom in ("rechercher_jeux", "lister_ressources"):
        return hote_depuis_url(os.environ.get("DATA_GOUV_API_URL", URL_BASE_API_DEFAUT))
    if nom in ("extraire_ressource", "interroger_ressource"):
        return hote_depuis_url(os.environ.get("TABULAR_API_URL", URL_BASE_TABULAIRE_DEFAUT))
    return None


def _intercepter_circuit_ouvert(
    conversation: ConversationServeur,
    nom: str,
    arguments: Dict[str, Any],
    hote: str,
) -> Dict[str, Any]:
    """Résultat structuré renvoyé à l'agent quand le circuit est ouvert.

    L'outil n'est PAS exécuté et ne consomme pas le plafond : le résultat
    est construit ici et journalisé comme une invocation interceptée.
    """
    return {
        "statut": "echec_technique",
        "message": (
            f"Circuit ouvert pour l'hôte '{hote}' : trop d'échecs transitoires "
            f"consécutifs dans cette conversation. Ne relance pas cet hôte ; "
            f"propose une alternative ou informe l'utilisateur."
        ),
        "donnees": {
            "motif": MOTIF_CIRCUIT_OUVERT,
            "hote": hote,
            "suggestion": "proposer_alternative",
        },
    }


def tour_conversation(
    conversation: ConversationServeur,
    message_utilisateur: str,
) -> Dict[str, Any]:
    """Conduit un tour complet : envoi du message, boucle tool-calling.

    Le message utilisateur est envoyé par `start_stream` (premier tour)
    ou `append_stream` (tours suivants). Les tool_calls émis par le
    serveur sont exécutés localement et leurs résultats renvoyés par
    `append_stream` (entrées `function.result`) jusqu'à la réponse finale
    ou au plafond du tour.

    Returns:
        Réponse normalisée {statut, message, donnees} ; donnees contient
        numero_tour, synthese (texte final du tour), nb_invocations (du
        tour), plafond et conversation_id.
    """
    numero_tour = conversation.nb_tours + 1
    conversation.nb_tours = numero_tour
    plafond = conversation.plafond
    identifiant = conversation.id_execution
    journal = conversation.journal

    journal.enregistrer("debut_tour", numero_tour=numero_tour, contenu=message_utilisateur)
    log_to_file(
        "tour_debut",
        numero_tour=numero_tour,
        plafond=plafond,
        id_execution=identifiant,
    )

    invocations = 0
    try:
        stream = _envoyer(conversation, inputs=message_utilisateur)
    except Exception as erreur:
        return _terminer_tour(
            conversation, numero_tour, "echec_technique",
            f"Échec de l'appel à l'API Mistral : {erreur}",
            invocations, "", erreur_api=str(erreur),
        )

    while True:
        texte, tool_calls, erreur_stream = _consommer_stream(stream)
        if erreur_stream is not None:
            return _terminer_tour(
                conversation, numero_tour, "echec_technique",
                f"Échec de l'API Mistral en cours de tour : {erreur_stream}",
                invocations, "", erreur_api=erreur_stream,
            )
        if texte:
            journal.enregistrer(
                "raisonnement_agent", tour=invocations + 1, numero_tour=numero_tour, contenu=texte
            )
        if not tool_calls:
            return _terminer_tour(
                conversation, numero_tour, "succes", "", invocations, texte
            )
        entrees_resultats = []
        for tool_call in tool_calls:
            if invocations >= plafond:
                journal.enregistrer(
                    "plafond_atteint",
                    numero_tour=numero_tour,
                    nb_invocations=invocations,
                    plafond=plafond,
                )
                log_to_file(
                    "tour_plafond_atteint",
                    numero_tour=numero_tour,
                    nb_invocations=invocations,
                    plafond=plafond,
                    id_execution=identifiant,
                )
                return _terminer_tour(
                    conversation, numero_tour, "succes_plafond",
                    f"Plafond de {plafond} invocations atteint pour ce tour : synthèse partielle.",
                    invocations,
                    "",
                    plafond_atteint=True,
                )
            nom = tool_call.get("name", "")
            arguments = tool_call.get("arguments", {})
            id_appel = tool_call.get("tool_call_id", "")
            arguments_dict = _decoder_arguments(arguments) or {}
            # T7.7 : interception du circuit breaker — avant exécution et
            # sans consommer le plafond d'invocations.
            hote = _hote_cible(nom, arguments_dict)
            if hote is not None and not conversation.circuit.autoriser(hote):
                resultat = _intercepter_circuit_ouvert(conversation, nom, arguments_dict, hote)
                journal.enregistrer(
                    "outil_invoque",
                    outil=nom,
                    arguments=arguments_dict,
                    tour=invocations + 1,
                    numero_tour=numero_tour,
                    circuit_ouvert=True,
                    hote=hote,
                )
                log_to_file(
                    "tour_circuit_ouvert",
                    outil=nom,
                    numero_tour=numero_tour,
                    hote=hote,
                    id_execution=identifiant,
                )
                journal.enregistrer(
                    "outil_resultat",
                    outil=nom,
                    statut=resultat["statut"],
                    tour=invocations + 1,
                    numero_tour=numero_tour,
                    message=resultat.get("message", ""),
                    motif=MOTIF_CIRCUIT_OUVERT,
                )
            else:
                invocations += 1
                journal.enregistrer(
                    "outil_invoque",
                    outil=nom,
                    arguments=arguments_dict,
                    tour=invocations,
                    numero_tour=numero_tour,
                )
                log_to_file(
                    "tour_outil_invoque",
                    outil=nom,
                    numero_tour=numero_tour,
                    tour=invocations,
                    plafond=plafond,
                    id_execution=identifiant,
                )
                resultat = executer_outil(nom, arguments, identifiant)
                # T7.7 : alimentation du circuit selon le motif T7.1.
                if hote is not None:
                    motif = resultat.get("donnees", {}).get("motif")
                    if resultat.get("statut") == "succes":
                        conversation.circuit.enregistrer_succes(hote)
                    elif motif == "transitoire":
                        conversation.circuit.enregistrer_echec_transitoire(hote)
                    elif motif is not None:
                        conversation.circuit.enregistrer_echec_definitif(hote)
                journal.enregistrer(
                    "outil_resultat",
                    outil=nom,
                    statut=resultat["statut"],
                    tour=invocations,
                    numero_tour=numero_tour,
                    message=resultat.get("message", ""),
                )
                log_to_file(
                    "tour_outil_resultat",
                    outil=nom,
                    statut=resultat["statut"],
                    numero_tour=numero_tour,
                    id_execution=identifiant,
                )
            entrees_resultats.append({
                "tool_call_id": id_appel,
                "result": json.dumps(resultat, ensure_ascii=False),
                "object": "entry",
                "type": "function.result",
            })
        try:
            stream = _envoyer(conversation, inputs=entrees_resultats)
        except Exception as erreur:
            return _terminer_tour(
                conversation, numero_tour, "echec_technique",
                f"Échec de l'appel à l'API Mistral : {erreur}",
                invocations, "", erreur_api=str(erreur),
            )


def cloturer_conversation(
    conversation: ConversationServeur,
    statut: str = "succes",
) -> Dict[str, Any]:
    """Écrit l'événement `fin` (totaux) et supprime la conversation serveur.

    La suppression est idempotente (conversation déjà absente = succès)
    et jamais bloquante pour l'appelant : son échec est journalisé et
    retourné, sans exception.
    """
    journal = conversation.journal
    journal.fermer(
        statut,
        nb_tours=conversation.nb_tours,
        nb_invocations=conversation.nb_invocations,
    )
    log_to_file(
        "conversation_fin",
        statut=statut,
        nb_tours=conversation.nb_tours,
        nb_invocations=conversation.nb_invocations,
        id_execution=conversation.id_execution,
    )
    if not conversation.conversation_id:
        return {"statut": "succes", "message": "", "donnees": {"supprimee": False}}
    try:
        conversation.agent.client.beta.conversations.delete(
            conversation_id=conversation.conversation_id
        )
    except Exception as erreur:
        message = str(erreur)
        if "404" in message or "not found" in message.lower():
            log_to_file(
                "conversation_deja_absente",
                conversation_id=conversation.conversation_id,
                id_execution=conversation.id_execution,
            )
            return {"statut": "succes", "message": "", "donnees": {"supprimee": False}}
        log_to_file(
            "conversation_suppression_erreur",
            conversation_id=conversation.conversation_id,
            detail=message,
            id_execution=conversation.id_execution,
        )
        return {
            "statut": "echec_technique",
            "message": f"Échec de la suppression de la conversation : {message}",
            "donnees": {"supprimee": False},
        }
    log_to_file(
        "conversation_supprimee",
        conversation_id=conversation.conversation_id,
        id_execution=conversation.id_execution,
    )
    return {"statut": "succes", "message": "", "donnees": {"supprimee": True}}


def _envoyer(conversation: ConversationServeur, inputs: Any) -> Any:
    """Envoie un message ou des résultats d'outils à la conversation serveur.

    Premier envoi : `start_stream` (crée la conversation, le
    `conversation_id` est lu sur l'événement `conversation.response.started`).
    Envois suivants : `append_stream`. Lève toute exception SDK vers
    l'appelant (traduites en échec propre par `tour_conversation`).
    """
    client = conversation.agent.client
    conversations = client.beta.conversations
    if conversation.conversation_id is None:
        stream = conversations.start_stream(
            inputs=inputs,
            agent_id=conversation.agent.agent_id,
            store=True,
            name=f"{PREFIXE_NOM}-{conversation.id_execution}",
            metadata={"id_execution": conversation.id_execution, "projet": PREFIXE_NOM},
        )
        # Le conversation_id arrive dans le flux : le lire avant de le consommer.
        return _amorcer_conversation(conversation, stream)
    return conversations.append_stream(
        conversation_id=conversation.conversation_id,
        inputs=inputs,
        store=True,
    )


def _amorcer_conversation(conversation: ConversationServeur, stream: Any) -> Any:
    """Lit le conversation_id sur l'événement started d'un start_stream.

    Le stream est un itérable d'événements ; le premier utile porte le
    `conversation_id`. On consomme l'itérateur via un générateur qui
    mémorise l'identifiant lu, puis on renvoie un itérable équivalent
    pour la suite du traitement.
    """
    # Matérialiser les événements : les streams Mistral sont courts (un
    # tour = quelques dizaines d'événements au plus).
    evenements = list(stream)
    for evenement in evenements:
        donnees = getattr(evenement, "data", None)
        type_evt = getattr(donnees, "type", "") or (
            evenement.get("data", {}).get("type", "") if isinstance(evenement, dict) else ""
        )
        if type_evt == "conversation.response.started":
            conversation_id = getattr(donnees, "conversation_id", None)
            if conversation_id is None and isinstance(donnees, dict):
                conversation_id = donnees.get("conversation_id")
            if conversation_id:
                conversation.conversation_id = conversation_id
                log_to_file(
                    "conversation_demarree",
                    conversation_id=conversation_id,
                    id_execution=conversation.id_execution,
                )
                break
    return iter(evenements)


def _consommer_stream(stream: Any) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    """Consomme un stream d'événements de l'API Conversations.

    Les deltas `function.call.delta` sont regroupés par `output_index`
    (sémantique du SDK, `client/conversations.py`) : un appel d'outil est
    émis en plusieurs deltas — l'identité (`tool_call_id`, `name`) est lue
    sur le premier delta du groupe, les arguments sont la concaténation
    des fragments.

    Returns:
        (texte, tool_calls, erreur) : texte concaténé des deltas
        `message.output.delta`, tool_calls reconstitués des
        `function.call.delta` ({tool_call_id, name, arguments}), erreur
        du premier `conversation.response.error` (None sinon).
    """
    texte = ""
    groupes: Dict[Any, List[Any]] = {}
    erreur: Optional[str] = None
    for evenement in stream:
        donnees = _donnees_evenement(evenement)
        if donnees is None:
            continue
        type_evt = _champ(donnees, "type", "")
        if type_evt == "message.output.delta":
            texte += _extraire_texte(_champ(donnees, "content", ""))
        elif type_evt == "function.call.delta":
            index = _champ(donnees, "output_index", 0)
            if index is None:
                index = 0
            groupes.setdefault(index, []).append(donnees)
        elif type_evt == "conversation.response.error":
            erreur = _champ(donnees, "message", "erreur inconnue")
    tool_calls = [
        _reconstituer_appel(groupe)
        for _, groupe in sorted(groupes.items(), key=lambda paire: paire[0])
    ]
    return texte, tool_calls, erreur


def _reconstituer_appel(deltas: List[Any]) -> Dict[str, Any]:
    """Reconstitue un appel d'outil à partir de ses deltas `function.call.delta`.

    L'identité (`tool_call_id`, `name`) est lue sur le premier delta ;
    les arguments sont la concaténation des fragments (chaîne JSON).
    """
    premier = deltas[0]
    arguments = "".join(_champ(delta, "arguments", "") or "" for delta in deltas)
    return {
        "tool_call_id": _champ(premier, "tool_call_id", ""),
        "name": _champ(premier, "name", ""),
        "arguments": arguments or "{}",
    }


def _donnees_evenement(evenement: Any) -> Any:
    """Extrait l'objet `data` d'un événement (format objet ou dict)."""
    donnees = getattr(evenement, "data", None)
    if donnees is not None:
        return donnees
    if isinstance(evenement, dict):
        return evenement.get("data")
    return None


def _champ(donnees: Any, nom: str, defaut: Any) -> Any:
    """Lit un champ sur un objet SDK ou un dict."""
    if isinstance(donnees, dict):
        return donnees.get(nom, defaut)
    return getattr(donnees, nom, defaut)


def _extraire_texte(contenu: Any) -> str:
    """Extrait le texte d'un contenu de delta (str, TextChunk ou dict)."""
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, dict):
        if contenu.get("type") == "text":
            return contenu.get("text", "")
        return ""
    texte = getattr(contenu, "text", None)
    return texte if isinstance(texte, str) else ""


def _terminer_tour(
    conversation: ConversationServeur,
    numero_tour: int,
    statut: str,
    message: str,
    invocations: int,
    synthese: str,
    erreur_api: Optional[str] = None,
    plafond_atteint: bool = False,
) -> Dict[str, Any]:
    """Écrit l'événement `fin_tour` et retourne la réponse du tour."""
    conversation.nb_invocations += invocations
    if erreur_api is not None:
        conversation.journal.enregistrer(
            "erreur_api",
            numero_tour=numero_tour,
            detail=erreur_api,
            nb_invocations=invocations,
        )
        log_to_file(
            "tour_erreur_api",
            numero_tour=numero_tour,
            detail=erreur_api,
            id_execution=conversation.id_execution,
        )
    conversation.journal.enregistrer(
        "fin_tour",
        numero_tour=numero_tour,
        statut=statut,
        nb_invocations=invocations,
        synthese=synthese,
        plafond=conversation.plafond,
    )
    log_to_file(
        "tour_fin",
        numero_tour=numero_tour,
        statut=statut,
        nb_invocations=invocations,
        id_execution=conversation.id_execution,
    )
    return {
        "statut": "succes" if statut in ("succes", "succes_plafond") else statut,
        "message": message,
        "donnees": {
            "numero_tour": numero_tour,
            "synthese": synthese,
            "nb_invocations": invocations,
            "plafond": conversation.plafond,
            "conversation_id": conversation.conversation_id,
        },
    }
