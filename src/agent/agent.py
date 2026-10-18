# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : agent.py
# Version      : 1.1
# Date         : 14-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Création et destruction de l'agent Mistral (T5.3.1).

L'agent est éphèmere : crée par code au début de l'exécution via l'API
beta `client.beta.agents`, identifié par son agent_id, utilisé par la
suite via `client.agents.complete`, puis détruit en fin de flux. La
configuration (modele, prompt systeme, outils) vit dans le dépot :
contrats JSON chargés depuis le manifeste, prompt constant. Aucun
état de configuration ne vit sur la console au-delà de l'exécution.

Garde-fou : si un MISTRAL_AGENT_ID est present dans l'environnement,
l'agent correspondant est verifié (modèle, empreinte du prompt, outils)
avant toute utilisation ; toute divergence entraine la création d'un
agent éphèmere neuf, jamais l'exécution avec une configuration divergente.

Échec propre systématique : aucune exception ne remonte vers
l'appelant ; toute défaillance est exprimée par un statut normalisé.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.utils.logging import configure_logging, log_to_file

load_dotenv()

REPERTOIRE_CONTRATS = Path(__file__).resolve().parents[2] / "contrats"

MODELE_DEFAUT = "mistral-small-latest"

PROMPT_SYSTEME = """Tu es l'agent d'acquisition de données du projet openDataAgent. Ton rôle : aider l'utilisateur a rechercher, sélectionner et extraire des jeux de données publiés sur data.gouv.fr. Tu conduis les quatre etapes agentiques du flux : reformulation (A1), sélection (A2), résolution des indéterminations (A3), synthèse du registre (A4).

RÈGLES GÉNÉRALES
- Langue : francais exclusivement, pour tes réponses comme pour les arguments des outils.
- Tu ne disposes que de quatre outils : rechercher_jeux, lister_ressources, interroger_ressource, telecharger_brut. Aucun autre accès au réseau ou aux données n'existe.
- Toute invocation d'outil retourne un objet unique {statut, message, donnees} : lis toujours le champ statut avant d'agir. succes : exploiter données. erreur_parametres : corriger les arguments puis réessayer. jeu_introuvable ou ressource_introuvable : ne réessaie jamais avec le même identifiant, reprends a l'étape amont. ressource_non_indexee : bascule sur telecharger_brut. licence_refusee : exclure la source, sans tenter d'accès direct. echec_technique : suis donnees.suggestion (réessayer, basculer ou abandonner).
- Identifiants : un identifiant de jeu provient de rechercher_jeux, un identifiant de ressource provient de lister_ressources. N'invente jamais un identifiant.
- Ordre des étapes : ne jamais appeler telecharger_brut sur une ressource qui n'a pas été vue dans lister_ressources au cours de ce flux.
- Économie d'invocations : le nombre d'appels d'outils est plafonné. Chaque invocation doit etre utile ; évite les appels redondants.
- Licence : chaque réponse de succès mentionne la licence du jeu ; conserve-la jusqu'à la restitution finale, les obligations d'attribution doivent suivre les données.

A1 - REFORMULATION
- Traduis le thème de l'utilisateur en 2 a 4 mots-clés courts et spécifiques (la recherche applique une logique ET : des termes trop nombreux ou trop vagues restreignent le résultat ou noient son information dans du bruit).
- Les qualificatifs de portée (géographique, temporelle, juridique : national, régional, par commune, définitif...) expriment un critère de sélection, pas de recherche : ne les traduis pas en mots-clés. Ils ne figurent généralement pas dans les titres et éliminent les meilleurs résultats. Le sujet s'exprime nu en 2-3 mots ; la portée se vérifie à l'étape A2 en confrontant la portée revendiquée à l'organisation productrice (une mairie ne produit pas de données nationales ; un producteur national ne publie pas des résultats par bureau de vote communal).
- Reformule en francais standard : supprime les sigles ambigus, évite les pluriels et les mots vides.
- Si la recherche ne retourne rien : élargis (retire un mot-clé) ou reformule autrement, puis relance. Si elle retourne trop de résultats noyés dans du bruit : affine.
- Tri : pertinence par défaut ; vues si le thème est large. Contrainte temporelle via fenetre_maj si l'utilisateur veut des données récentes.
- Pagination : si page_suivante est présent, évalue les pages suivantes avant de conclure que les jeux pertinents manquent.

A2 - SÉLECTION
- Pour chaque jeu, lis titre, organisation, licence, dernière mise à jour et nombre de ressources.
- Privilégie les jeux récents, publiés par des organisations officielles (Insee, ministères, collectivités...) et comportant des ressources exploitables.
- Vérifie la cohérence entre la portée demandée par l'utilisateur et l'organisation productrice : une organisation communale ou départementale ne peut pas produire de données nationales ; un producteur national ne publie pas des données au niveau d'une seule commune. Écarte tout jeu dont la portée revendiquée contredit l'organisation, même si la ressource est immédiatement exploitable.
- Justifie chaque jeu retenu en une phrase dans ton raisonnement. Les jeux exclus par licence sont deja filtrés par le code : ne tente pas de les réacquerir.
- Si plusieurs jeux sont équivalents, retiens le mieux maintenu et documente ; ne retiens pas plus de jeux que nécessaire au besoin de l'utilisateur.

A3 - RÉSOLUTION DES INDETERMINATIONS
- Lorsque la reponse de lister_ressources contient des entrées dans donnees.indetermination, tranche leur classe a partir du titre et de l'URL de la ressource. La réponse est autoportante : aucun appel d'outil supplémentaire n'est necessaire ni utile.
- Distinction : des signaux contradictoires (format declaré csv, mime text/html) ne sont pas des ambiguités ; le code les a déjà tranchés par priorité. Seules les ressources marquées indetermine attendent ton arbitrage.
- Consigne ta decision dans ton raisonnement (par exemple : cette URL d'API Insee est une api_distante). Le code garde sa classification initiale : ne demande jamais de retraitement.
- Une ressource tranchée comme non exploitable peut simplement etre ignorée pour la suite.

A4 - SYNTHÈSE DU REGISTRE
- Tout au long du flux, mémorise les sources écartées : licences refusées (statut licence_refusee) et échecs techniques (statut echec_technique, motif dans message ou données).
- Pour une ressource dont le téléchargement échoue avec la suggestion fichier_heberge_exterieurement : ne relance pas immediatement ; propose plutot une alternative, un jeu équivalent hébergé sur la plateforme data.gouv.fr.
- Conclus toujours par un rapport structuré en francais : (1) données acquises, avec leurs chemins locaux et leur licence (attribution) ; (2) sources retenues et pourquoi ; (3) sources écartées avec leur motif ; (4) limites éventuelles de l'acquisition.

PAGINATION ET VOLUMES
- Exploite page_suivante pour paginer la recherche et l'interrogation des ressources ; conserve les mêmes filtres et tris entre les pages d'une extraction.
- Si une réponse de interroger_ressource contient recommandation = volume_eleve_telechargement_brut_suggere, arrête la pagination et bascule sur telecharger_brut : la ressource est trop volumineuse pour une extraction page à page.
- telecharger_brut écrit sur le disque : reserve-le aux ressources réellement selectionnées, pas à l'exploration. Utilise interroger_ressource pour prévisualiser le contenu d'une ressource indexée.
- extraire_ressource écrit aussi sur le disque (extraction paginée complète d'une ressource indexée, avec plafond de sécurité) : réserve-le à l'acquisition finale, après que l'utilisateur a retenu la ressource et que l'exploration via interroger_ressource a validé le choix. Cite le chemin local (donnees.chemin_local) et la licence dans ta synthèse finale. Si tronque est vrai, signale la troncature à l'utilisateur.
"""

PREFIXE_NOM = "openDataAgent"


@dataclass
class Agent:
    """Agent Mistral éphémère crée pour une exécution.

    Attributs :
        client : client Mistral instancié.
        agent_id : identifiant de l'agent sur la console Mistral.
        modele : modele assigné à l'agent.
        outils : définitions d'outils passées à l'agent.
        ephemere : True si l'agent a été crée par ce flux et doit
                   être détruit en fin d'exécution ; False si un agent
                   persistant existant a été réutilisé après vérification.
        empreinte_prompt : empreinte sha256 du prompt système envoyé.
    """

    client: Any
    agent_id: str
    modele: str
    outils: List[Dict[str, Any]]
    ephemere: bool = True
    empreinte_prompt: str = ""


def empreinte(texte: str) -> str:
    """Empreinte sha256 courte d'un texte (comparaison de prompt)."""
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def charger_outils(repertoire: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Charge les définitions d'outils depuis le manifeste des contrats.

    Refuse de démarrer si le manifeste, le champ function.name et le
    nom de fichier d'un contrat divergent (invariant du contrat global).

    Returns:
        Liste des définitions d'outils au format function calling.

    Raises:
        ValueError : manifeste illisible ou divergence constatée.
        FileNotFoundError : contrat referencé mais absent.
    """
    repertoire = repertoire or REPERTOIRE_CONTRATS
    chemin_manifeste = repertoire / "manifeste.json"
    with open(chemin_manifeste, encoding="utf-8") as flux:
        manifeste = json.load(flux)
    outils = []
    for entree in manifeste["outils"]:
        nom = entree["nom"]
        fichier = entree["fichier"]
        if Path(fichier).stem != nom:
            raise ValueError(
                f"Divergence manifeste/fichier : outil '{nom}' référence "
                f"'{fichier}'."
            )
        with open(repertoire / fichier, encoding="utf-8") as flux:
            contrat = json.load(flux)
        if contrat.get("function", {}).get("name") != nom:
            raise ValueError(
                f"Divergence manifeste/contrat : '{nom}' référence un "
                f"contrat dont function.name vaut "
                f"'{contrat.get('function', {}).get('name')}'."
            )
        outils.append(contrat)
    return outils


def creer_agent(
    id_execution: str,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Crée (ou réutilise apres vérification) l'agent Mistral d'une exécution.

    Garde-fou : si MISTRAL_AGENT_ID est défini et que l'agent correspondant
    est strictement conforme (modèle, empreinte du prompt système, outils),
    il est réutilisé (ephemere=False) ; toute divergence ou absence entraine
    la creation d'un agent éphèmere neuf.

    Returns:
        Reponse normalisée {statut, message, donnees}. En succès, données
        contient l'objet Agent (champ "agent").
    """
    try:
        outils = charger_outils()
    except (ValueError, KeyError, FileNotFoundError) as erreur:
        log_to_file("agent_contrats_invalides", detail=str(erreur), id_execution=id_execution)
        return {
            "statut": "echec_technique",
            "message": f"Contrats d'outils invalides : {erreur}",
            "donnees": {},
        }

    cle = os.environ.get("MISTRAL_API_KEY", "")
    if not cle:
        log_to_file("agent_cle_absente", id_execution=id_execution)
        return {
            "statut": "echec_technique",
            "message": "Variable d'environnement MISTRAL_API_KEY absente ou vide.",
            "donnees": {"suggestion": "définir MISTRAL_API_KEY dans .env"},
        }

    modele = os.environ.get("MISTRAL_MODELE", MODELE_DEFAUT)
    try:
        if client is None:
            client = _instancier_client(cle)
    except Exception as erreur:
        log_to_file("agent_client_erreur", detail=str(erreur), id_execution=id_execution)
        return _echec_instanciation(erreur)

    agent_existant = _verifier_agent_existant(client, outils, modele)
    if agent_existant is not None:
        log_to_file(
            "agent_persistant_reutilise",
            agent_id=agent_existant.agent_id,
            modele=modele,
            id_execution=id_execution,
        )
        return {
            "statut": "succes",
            "message": "",
            "donnees": {"agent": agent_existant},
        }

    nom = f"{PREFIXE_NOM}-{id_execution}"
    try:
        reponse = client.beta.agents.create(
            model=modele,
            name=nom,
            instructions=PROMPT_SYSTEME,
            tools=sorted(outils, key=lambda o: o["function"]["name"]),
            description="Agent d'acquisition de données de data.gouv.fr (flux openDataAgent).",
            metadata={"id_execution": id_execution, "projet": PREFIXE_NOM},
        )
    except Exception as erreur:
        log_to_file("agent_creation_erreur", detail=str(erreur), id_execution=id_execution)
        return {
            "statut": "echec_technique",
            "message": f"Echec de la creation de l'agent Mistral : {erreur}",
            "donnees": {"suggestion": "reessayer"},
        }

    agent = Agent(
        client=client,
        agent_id=reponse.id,
        modele=modele,
        outils=outils,
        ephemere=True,
        empreinte_prompt=empreinte(PROMPT_SYSTEME),
    )
    log_to_file(
        "agent_cree",
        agent_id=agent.agent_id,
        modele=modele,
        nb_outils=len(outils),
        id_execution=id_execution,
    )
    return {
        "statut": "succes",
        "message": "",
        "donnees": {"agent": agent},
    }


def detruire_agent(agent: Any) -> Dict[str, Any]:
    """Détruit l'agent éphèmere sur la console Mistral.

    Un agent non éphèmere (persistant réutilisé) n'est jamais détruit.
    Un agent_id déjà supprimé est un succès (idempotence) : le but est
    qu'aucun agent résiduel ne subsiste, pas l'exactitude de l'état.

    Returns:
        Réponse normalisée {statut, message, donnees}.
    """
    if not isinstance(agent, Agent):
        return {
            "statut": "erreur_parametres",
            "message": "detruire_agent attend un objet Agent.",
            "donnees": {},
        }
    if not agent.ephemere:
        log_to_file("agent_persistant_conserve", agent_id=agent.agent_id)
        return {
            "statut": "succes",
            "message": "Agent persistant réutilisé : non détruit.",
            "donnees": {"detruit": False},
        }
    try:
        agent.client.beta.agents.delete(agent_id=agent.agent_id)
    except Exception as erreur:
        message = str(erreur)
        if "404" in message or "not found" in message.lower():
            log_to_file("agent_deja_absent", agent_id=agent.agent_id)
            return {
                "statut": "succes",
                "message": "Agent déjà absent de la console.",
                "donnees": {"detruit": False},
            }
        log_to_file("agent_destruction_erreur", agent_id=agent.agent_id, detail=message)
        return {
            "statut": "echec_technique",
            "message": f"Echec de la destruction de l'agent : {message}",
            "donnees": {"suggestion": "nettoyer_agents_orphelins"},
        }
    log_to_file("agent_detruit", agent_id=agent.agent_id)
    return {
        "statut": "succes",
        "message": "",
        "donnees": {"detruit": True},
    }


def nettoyer_agents_orphelins(
    client: Any,
    cle: Optional[str] = None,
) -> Dict[str, Any]:
    """Liste et supprime les agents openDataAgent résiduels sur la console.

    Utile apres un crash entre création et destruction. Cible les agents
    dont le nom commence par PREFIXE_NOM et/ou dont metadata.projet
    correspond au projet.

    Returns:
        Reponse normalisée {statut, message, donnees} ; donnees.detruits
        contient la liste des agent_id supprimés.
    """
    if client is None:
        cle_reelle = cle or os.environ.get("MISTRAL_API_KEY", "")
        if not cle_reelle:
            return {
                "statut": "echec_technique",
                "message": "Variable d'environnement MISTRAL_API_KEY absente ou vide.",
                "donnees": {},
            }
        try:
            client = _instancier_client(cle_reelle)
        except Exception as erreur:
            return _echec_instanciation(erreur)
    detruits: List[str] = []
    erreurs: List[str] = []
    try:
        page = client.beta.agents.list(page_size=100)
        candidats = list(getattr(page, "data", page) or [])
    except Exception as erreur:
        return {
            "statut": "echec_technique",
            "message": f"Echec du listage des agents : {erreur}",
            "donnees": {"suggestion": "reessayer"},
        }
    for candidat in candidats:
        nom_candidat = getattr(candidat, "name", "") or ""
        metadata = getattr(candidat, "metadata", None) or {}
        du_projet = nom_candidat.startswith(PREFIXE_NOM) or metadata.get("projet") == PREFIXE_NOM
        if not du_projet:
            continue
        identifiant = getattr(candidat, "id", "")
        try:
            client.beta.agents.delete(agent_id=identifiant)
            detruits.append(identifiant)
        except Exception as erreur:
            erreurs.append(f"{identifiant} : {erreur}")
    log_to_file("agents_orphelins_nettoyes", detruits=detruits, erreurs=erreurs)
    if erreurs:
        return {
            "statut": "echec_technique",
            "message": f"Echec de suppression pour {len(erreurs)} agent(s).",
            "donnees": {"detruits": detruits, "erreurs": erreurs},
        }
    return {
        "statut": "succes",
        "message": "",
        "donnees": {"detruits": detruits},
    }


def _instancier_client(cle: str) -> Any:
    """Instancie le client Mistral (import tolerant des environnements)."""
    try:
        from mistralai import Mistral
    except ImportError:
        from mistralai.client import Mistral
    return Mistral(api_key=cle)


def _verifier_agent_existant(
    client: Any,
    outils: List[Dict[str, Any]],
    modele: str,
) -> Optional[Agent]:
    """Vérifie l'agent persistant designé par MISTRAL_AGENT_ID, s'il existe.

    Retourne un Agent réutilisable seulement si modèle, empreinte du
    prompt système et ensemble d'outils sont strictement conformes ;
    toute divergence retourne None (création éphèmere par l'appelant).
    """
    agent_id = os.environ.get("MISTRAL_AGENT_ID", "")
    if not agent_id:
        return None
    try:
        agent_console = client.beta.agents.get(agent_id=agent_id)
    except Exception:
        log_to_file("agent_persistant_inaccessible", agent_id=agent_id)
        return None
    if getattr(agent_console, "model", None) != modele:
        log_to_file("agent_persistant_divergent", agent_id=agent_id, motif="modele")
        return None
    instructions = getattr(agent_console, "instructions", "") or ""
    if empreinte(instructions) != empreinte(PROMPT_SYSTEME):
        log_to_file("agent_persistant_divergent", agent_id=agent_id, motif="prompt")
        return None
    outils_console = _extraire_outils(agent_console)
    if {o["function"]["name"] for o in outils} != outils_console:
        log_to_file("agent_persistant_divergent", agent_id=agent_id, motif="outils")
        return None
    return Agent(
        client=client,
        agent_id=agent_id,
        modele=modele,
        outils=outils,
        ephemere=False,
        empreinte_prompt=empreinte(PROMPT_SYSTEME),
    )


def _extraire_outils(agent_console: Any) -> set:
    """Extrait l'ensemble des noms de fonctions d'un agent console."""
    outils = getattr(agent_console, "tools", None) or []
    noms = set()
    for outil in outils:
        if isinstance(outil, dict):
            fonction = outil.get("function", {})
            noms.add(fonction.get("name") or outil.get("type", ""))
        else:
            nom = getattr(outil, "function", None)
            nom = getattr(nom, "name", None) if nom is not None else None
            noms.add(nom or getattr(outil, "type", ""))
    return {n for n in noms if n}


def _echec_instanciation(erreur: Exception) -> Dict[str, Any]:
    return {
        "statut": "echec_technique",
        "message": f"Instanciation du client Mistral impossible : {erreur}",
        "donnees": {"suggestion": "verifier l'installation de mistralai"},
    }
