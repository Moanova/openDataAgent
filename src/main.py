# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : main.py
# Version      : 1
# Date         : 13-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""CLI openDataAgent (Typer).

Couche mince de presentation : traduit une ligne de commande en appel
de la fonction coeur correspondante et affiche la reponse normalisée
{statut, message, donnees}. Aucune logique metier ici.

T13.3 (realignement linguistique) : les commandes sont nominees en
francais (rechercher, lister, telecharger, extraire, interroger,
demander) ; les noms anglais (search, list, download, extract, query,
ask, chat) restent des alias fonctionnels. L'option globale est
--silencieux (alias --quiet).
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Optional

import typer

from pathlib import Path

from src.core.search import rechercher_jeux
from src.core.resources import charger_inventaire, decharger_inventaire, lister_ressources
from src.core.download import telecharger_brut
from src.core.extraction import extraire_ressource
from src.core.query import interroger_ressource
from src.utils.logging import configure_logging
from src.agent.agent import creer_agent, detruire_agent
from src.agent.boucle import (
    PLAFOND_DEFAUT,
    cloturer_conversation,
    creer_conversation,
    tour_conversation,
)
from src.agent.journal import REPERTOIRE_JOURNAUX
from src.core.manifeste import consigner_demande, lire_manifeste
from src.core.nettoyage import AGE_DEFAUT_JOURS, nettoyer_anciennes_executions
from src.core.vocabulaires import (
    APERCU_DEFAUT,
    FenetreMaj,
    OperateurFiltre,
    OrdreTri,
    TriRecherche,
    valeurs,
)

app = typer.Typer(help="CLI openDataAgent : acquisition de données de data.gouv.fr.")

AIDE_ID_EXECUTION = "Identifiant d'exécution pour les traces et le chaînage des commandes (généré automatiquement si absent, affiché dans la sortie)."

_SILENCIEUX = False


def _configurer_logging(id_execution: str) -> None:
    """Configure le logging (T13.2 : silencieux si l'option --quiet est passée)."""
    configure_logging(id_execution=id_execution, silencieux=_SILENCIEUX)


def _id_execution_auto() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


REPERTOIRE_EXECUTIONS = Path("data") / "executions"


def _chemin_inventaire(id_execution: str) -> Path:
    return REPERTOIRE_EXECUTIONS / id_execution / "inventaire.json"


def _charger_inventaire_persiste(id_execution: str) -> None:
    """Recharge l'inventaire d'une exécution antérieure (chaînage T10.2)."""
    chemin = _chemin_inventaire(id_execution)
    if not chemin.exists():
        return
    try:
        with chemin.open(encoding="utf-8") as flux:
            charger_inventaire(json.load(flux))
    except (OSError, json.JSONDecodeError) as erreur:
        typer.secho(f"Inventaire persisté illisible ({chemin}) : {erreur}", fg=typer.colors.YELLOW, err=True)


def _persister_inventaire(id_execution: str) -> None:
    """Écrit l'inventaire enrichi sur disque (écriture simple, T10.2)."""
    chemin = _chemin_inventaire(id_execution)
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("w", encoding="utf-8") as flux:
            json.dump(decharger_inventaire(), flux, ensure_ascii=False, indent=2)
    except OSError as erreur:
        typer.secho(f"Impossible de persister l'inventaire ({chemin}) : {erreur}", fg=typer.colors.YELLOW, err=True)


def _afficher_recherche(reponse: dict) -> None:
    if reponse["statut"] != "succes":
        typer.secho(f"[{reponse['statut']}] {reponse['message']}", fg=typer.colors.RED, err=True)
        return
    donnees = reponse["donnees"]
    typer.echo(f"statut : {reponse['statut']}")
    suite = f", page suivante : {donnees['page_suivante']}" if donnees.get("page_suivante") else ""
    typer.echo(f"{donnees['total_trouves']} jeu(x) correspondant(s), "
               f"{len(donnees['jeux'])} retourne(s) (page {donnees['page_courante']}), "
               f"{donnees['exclus_licence']} exclu(s) licence{suite}")
    for jeu in donnees["jeux"]:
        typer.echo(f"- {jeu['titre']}  [{jeu['licence']}]  {jeu['organisation']}")
        typer.echo(f"  id={jeu['id']}  maj={jeu['derniere_maj']}  {jeu['url']}")


def _id_execution_demande() -> Optional[str]:
    """Lit `--id-execution` dans les arguments bruts (hook de nettoyage, E3).

    Au callback Typer, les options de la sous-commande ne sont pas encore
    parsées : on balaie sys.argv. Retourne None si l'option est absente.
    """
    args = sys.argv[1:]
    for indice, arg in enumerate(args):
        if arg == "--id-execution" and indice + 1 < len(args):
            return args[indice + 1]
        if arg.startswith("--id-execution="):
            return arg.split("=", 1)[1]
    return None


def _nettoyage_automatique() -> None:
    """Hook de nettoyage des anciennes exécutions (T7.2, E3).

    Actif uniquement si NETTOYAGE_AUTO=1 dans l'environnement ; jamais
    bloquant : un bilan avec suppressions ou erreurs est signalé en warning.
    """
    if os.environ.get("NETTOYAGE_AUTO") != "1":
        return
    # Pas de configure_logging ici : le callback précède la commande, le
    # logging sera configuré par elle. Les traces du nettoyage passent par
    # log_to_file (actif une fois le logging configuré) ; le bilan visible
    # est le warning ci-dessous.
    bilan = nettoyer_anciennes_executions(id_execution_courante=_id_execution_demande())
    donnees = bilan["donnees"]
    if not _SILENCIEUX and (donnees["supprimes"] or donnees["erreurs"]):
        typer.secho(
            f"nettoyage automatique : {bilan['message']}",
            fg=typer.colors.YELLOW,
            err=True,
        )


@app.callback()
def racine(
    ctx: typer.Context,
    silencieux: bool = typer.Option(False, "--silencieux", "--quiet", help="Masque les logs applicatifs [info]/[error] dans la console (le fichier de logs reste écrit)."),
) -> None:
    """CLI openDataAgent : acquisition de données de data.gouv.fr."""
    global _SILENCIEUX
    _SILENCIEUX = silencieux
    if ctx.invoked_subcommand and ctx.invoked_subcommand != "nettoyer":
        _nettoyage_automatique()


@app.command(name="rechercher")
def rechercher(
    mots_cles: List[str] = typer.Argument(..., help="Mots-clés de la recherche (logique ET)."),
    tri: str = typer.Option("pertinence", "--tri", help="Ordre de tri des resultats."),
    fenetre_maj: str = typer.Option("toutes", "--fenetre-maj", help="Restriction sur la dernière mise à jour."),
    limite: int = typer.Option(10, "--limite", min=1, max=20, help="Nombre maximum de jeux retournés."),
    page: int = typer.Option(1, "--page", min=1, help="Numéro de la page de résultats demandée."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la réponse normalisée."),
) -> None:
    """Recherche des jeux de données sur data.gouv.fr par mots-clés."""
    if tri not in valeurs(TriRecherche):
        typer.secho(f"Valeur --tri invalide : {tri}. Valeurs acceptées : {', '.join(valeurs(TriRecherche))}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    if fenetre_maj not in valeurs(FenetreMaj):
        typer.secho(f"Valeur --fenetre-maj invalide : {fenetre_maj}. Valeurs acceptées : {', '.join(valeurs(FenetreMaj))}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    identifiant = id_execution or _id_execution_auto()
    _configurer_logging(identifiant)
    _charger_inventaire_persiste(identifiant)
    if not sortie_json:
        typer.echo(f"id_execution : {identifiant}", err=True)

    reponse = rechercher_jeux(
        mots_cles=mots_cles,
        tri=tri,
        fenetre_maj=fenetre_maj,
        limite=limite,
        page=page,
        id_execution=identifiant,
    )

    if sortie_json:
        import json
        typer.echo(json.dumps(reponse, ensure_ascii=False, indent=2))
    else:
        _afficher_recherche(reponse)

    if reponse["statut"] == "erreur_parametres":
        raise typer.Exit(code=2)
    if reponse["statut"] != "succes":
        raise typer.Exit(code=1)


@app.command(name="lister")
def lister(
    id_jeu: str = typer.Argument(..., help="Identifiant du jeu, issu de la recherche."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la réponse normalisée."),
) -> None:
    """Liste les ressources d'un jeu de données avec leurs métadonnées."""
    identifiant = id_execution or _id_execution_auto()
    _configurer_logging(identifiant)
    _charger_inventaire_persiste(identifiant)
    if not sortie_json:
        typer.echo(f"id_execution : {identifiant}", err=True)

    reponse = lister_ressources(id_jeu=id_jeu, id_execution=identifiant)
    if reponse["statut"] == "succes":
        _persister_inventaire(identifiant)

    if sortie_json:
        import json
        typer.echo(json.dumps(reponse, ensure_ascii=False, indent=2))
    elif reponse["statut"] == "succes":
        donnees = reponse["donnees"]
        typer.echo(f"statut : {reponse['statut']}")
        typer.echo(f"{len(donnees['ressources'])} ressource(s), "
                   f"{len(donnees['indetermination'])} indeterminée(s)")
        for res in donnees["ressources"]:
            typer.echo(f"- [{res['classe']}] {res['titre']}  ({res['format'] or 'format inconnu'})")
            typer.echo(f"  id={res['id']}  taille={res['taille_octets']}  {res['url']}")
    else:
        typer.secho(f"[{reponse['statut']}] {reponse['message']}", fg=typer.colors.RED, err=True)

    if reponse["statut"] == "erreur_parametres":
        raise typer.Exit(code=2)
    if reponse["statut"] != "succes":
        raise typer.Exit(code=1)


@app.command(name="telecharger")
def telecharger(
    id_ressource: str = typer.Argument(..., help="Identifiant de la ressource, issu de l'inventaire."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la réponse normalisée."),
) -> None:
    """Telecharge une ressource non indexee dans son etat brut."""
    identifiant = id_execution or _id_execution_auto()
    _configurer_logging(identifiant)
    _charger_inventaire_persiste(identifiant)
    if not sortie_json:
        typer.echo(f"id_execution : {identifiant}", err=True)

    consigner_demande(identifiant, f"telecharger {id_ressource}")
    reponse = telecharger_brut(id_ressource=id_ressource, id_execution=identifiant)

    if sortie_json:
        import json
        typer.echo(json.dumps(reponse, ensure_ascii=False, indent=2))
    elif reponse["statut"] == "succes":
        donnees = reponse["donnees"]
        typer.echo(f"statut : {reponse['statut']}")
        typer.echo(f"fichier : {donnees['chemin_local']}")
        typer.echo(f"format : {donnees['format'] or 'inconnu'}  licence : {donnees['licence'] or 'inconnue'}")
    else:
        typer.secho(f"[{reponse['statut']}] {reponse['message']}", fg=typer.colors.RED, err=True)
        if reponse["donnees"].get("suggestion"):
            typer.secho(f"suggestion : {reponse['donnees']['suggestion']}", fg=typer.colors.YELLOW, err=True)

    if reponse["statut"] in ("erreur_parametres", "ressource_introuvable"):
        raise typer.Exit(code=2)
    if reponse["statut"] != "succes":
        raise typer.Exit(code=1)


@app.command(name="extraire")
def extraire(
    id_ressource: str = typer.Argument(..., help="Identifiant de la ressource indexée, issu de l'inventaire."),
    taille_page: int = typer.Option(100, "--taille-page", min=1, help="Lignes demandées par page à l'API tabulaire."),
    plafond_lignes: Optional[int] = typer.Option(None, "--plafond-lignes", min=1, help="Nombre maximum de lignes extraites (défaut : PLAFOND_EXTRACTION, 10000)."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la réponse normalisée."),
) -> None:
    """Extrait une ressource indexée vers un CSV local (pagination conduite par la commande)."""
    identifiant = id_execution or _id_execution_auto()
    _configurer_logging(identifiant)
    _charger_inventaire_persiste(identifiant)
    if not sortie_json:
        typer.echo(f"id_execution : {identifiant}", err=True)
    consigner_demande(identifiant, f"extraire {id_ressource}")
    reponse = extraire_ressource(
        id_ressource=id_ressource,
        id_execution=identifiant,
        taille_page=taille_page,
        plafond_lignes=plafond_lignes,
    )
    if sortie_json:
        import json
        typer.echo(json.dumps(reponse, ensure_ascii=False, indent=2))
    elif reponse["statut"] == "succes":
        donnees = reponse["donnees"]
        typer.echo(f"statut : {reponse['statut']}")
        typer.echo(f"fichier : {donnees['chemin_local']}")
        typer.echo(f"lignes : {donnees['lignes_ecrites']} écrite(s) sur {donnees['total_lignes']}  licence : {donnees['licence'] or 'inconnue'}")
        if donnees.get("tronque"):
            typer.secho(f"attention : {reponse['message']}", fg=typer.colors.YELLOW, err=True)
    else:
        typer.secho(f"[{reponse['statut']}] {reponse['message']}", fg=typer.colors.RED, err=True)
        if reponse["donnees"].get("suggestion"):
            typer.secho(f"suggestion : {reponse['donnees']['suggestion']}", fg=typer.colors.YELLOW, err=True)
    if reponse["statut"] in ("erreur_parametres", "ressource_introuvable"):
        raise typer.Exit(code=2)
    if reponse["statut"] != "succes":
        raise typer.Exit(code=1)


@app.command(name="interroger")
def interroger(
    id_ressource: str = typer.Argument(..., help="Identifiant de la ressource, issu de l'inventaire."),
    page: int = typer.Option(1, "--page", min=1, help="Page demandée."),
    taille_page: int = typer.Option(20, "--taille-page", min=1, max=50, help="Lignes par page (max 50)."),
    colonne: Optional[str] = typer.Option(None, "--filtre-colonne", help="Colonne du filtre."),
    valeur: Optional[str] = typer.Option(None, "--filtre-valeur", help="Valeur du filtre."),
    operateur: Optional[str] = typer.Option("exact", "--filtre-operateur", help="Operateur : exact, contient, inferieur, superieur, strictement_inferieur, strictement_superieur."),
    tri_colonne: Optional[str] = typer.Option(None, "--tri-colonne", help="Colonne du tri."),
    tri_ordre: Optional[str] = typer.Option("croissant", "--tri-ordre", help="Ordre : croissant ou decroissant."),
    apercu: int = typer.Option(APERCU_DEFAUT, "--apercu", min=0, help="Nombre maximum de lignes affichées (aperçu)."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la réponse normalisée."),
) -> None:
    """Interroge une ressource indexee par l'API tabulaire."""
    if operateur not in valeurs(OperateurFiltre):
        typer.secho(f"Valeur --filtre-operateur invalide : {operateur}. Valeurs acceptées : {', '.join(valeurs(OperateurFiltre))}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    if tri_ordre not in valeurs(OrdreTri):
        typer.secho(f"Valeur --tri-ordre invalide : {tri_ordre}. Valeurs acceptées : {', '.join(valeurs(OrdreTri))}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    identifiant = id_execution or _id_execution_auto()
    _configurer_logging(identifiant)
    _charger_inventaire_persiste(identifiant)
    if not sortie_json:
        typer.echo(f"id_execution : {identifiant}", err=True)

    filtre = {"colonne": colonne, "valeur": valeur, "operateur": operateur} if colonne and valeur is not None else None
    tri = {"colonne": tri_colonne, "ordre": tri_ordre} if tri_colonne else None

    reponse = interroger_ressource(
        id_ressource=id_ressource,
        page=page,
        taille_page=taille_page,
        filtre=filtre,
        tri=tri,
        id_execution=identifiant,
    )

    if sortie_json:
        import json
        typer.echo(json.dumps(reponse, ensure_ascii=False, indent=2))
    elif reponse["statut"] == "succes":
        donnees = reponse["donnees"]
        typer.echo(f"statut : {reponse['statut']}")
        typer.echo(f"{donnees['total_lignes']} ligne(s), colonnes : {', '.join(donnees['colonnes']) or '(aucune)'}")
        if donnees.get("recommandation"):
            typer.secho(f"recommandation : {donnees['recommandation']}", fg=typer.colors.YELLOW)
        for ligne in donnees["lignes"][:apercu]:
            typer.echo(f"- {ligne}")
        if len(donnees["lignes"]) > apercu:
            typer.echo(f"  ... ({len(donnees['lignes']) - apercu} ligne(s) supplémentaires)")
    else:
        typer.secho(f"[{reponse['statut']}] {reponse['message']}", fg=typer.colors.RED, err=True)
        if reponse["donnees"].get("suggestion"):
            typer.secho(f"suggestion : {reponse['donnees']['suggestion']}", fg=typer.colors.YELLOW, err=True)

    if reponse["statut"] in ("erreur_parametres", "ressource_introuvable"):
        raise typer.Exit(code=2)
    if reponse["statut"] != "succes":
        raise typer.Exit(code=1)


@app.command()
def acquisitions(
    id_execution: str = typer.Argument(..., help="Identifiant de l'exécution dont on veut le manifeste d'acquisition."),
) -> None:
    """Affiche le manifeste d'acquisition d'une exécution (T10.8).

    Relie chaque fichier de data/raw/<id_execution>/ à son jeu de données :
    voie, licence, mention d'attribution, troncature.
    """
    manifeste = lire_manifeste(id_execution)
    if manifeste is None:
        typer.secho(
            f"Aucun manifeste d'acquisition pour l'exécution '{id_execution}'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    acquisitions = manifeste.get("acquisitions", [])
    typer.echo(f"id_execution : {manifeste.get('id_execution', id_execution)}")
    if manifeste.get("demande"):
        typer.echo(f"demande : {manifeste['demande']}")
    typer.echo(f"acquisitions : {len(acquisitions)}")
    for indice, acquisition in enumerate(acquisitions, 1):
        typer.echo()
        typer.echo(f"  [{indice}] {acquisition.get('fichier', '?')}")
        typer.echo(f"      voie : {acquisition.get('voie', '?')}  licence : {acquisition.get('licence') or 'inconnue'}"
                   + (" (conditionnelle)" if acquisition.get("licence_conditionnelle") else ""))
        typer.echo(f"      jeu : {acquisition.get('titre_jeu') or acquisition.get('id_jeu', '?')}")
        typer.echo(f"      organisation : {acquisition.get('organisation') or '?'}")
        if acquisition.get("mention_attribution"):
            typer.echo(f"      attribution : {acquisition['mention_attribution']}")
        if acquisition.get("voie") == "extraction":
            typer.echo(f"      lignes : {acquisition.get('nb_lignes', '?')}"
                       + ("  (tronqué)" if acquisition.get("tronque") else ""))


@app.command()
def nettoyer(
    age_jours: int = typer.Option(AGE_DEFAUT_JOURS, "--age-jours", min=1, help="Âge minimal d'une exécution pour être supprimée (en jours)."),
    simulation: bool = typer.Option(False, "--simulation", help="Affiche ce qui serait supprimé, sans rien supprimer."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help="Exécution à protéger du nettoyage (l'exécution courante est toujours protégée)."),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute du bilan normalisé."),
) -> None:
    """Supprime les anciennes exécutions (fichiers, inventaires, conversations, logs)."""
    identifiant = id_execution or _id_execution_auto()
    _configurer_logging(identifiant)
    bilan = nettoyer_anciennes_executions(
        age_jours=age_jours,
        id_execution_courante=id_execution,
        simulation=simulation,
    )
    if sortie_json:
        typer.echo(json.dumps(bilan, ensure_ascii=False, indent=2))
    elif bilan["statut"] == "succes":
        donnees = bilan["donnees"]
        typer.echo(f"statut : {bilan['statut']}")
        typer.echo(f"âge seuil : {donnees['age_jours']} jour(s)  simulation : {donnees['simulation']}")
        typer.echo(f"supprimé(s) : {len(donnees['supprimes'])}  conservé(s) : {len(donnees['conserves'])}")
        for id_exec in donnees["supprimes"]:
            typer.echo(f"- {id_exec}")
        typer.echo(f"octets libérés : {donnees['octets_liberes']}")
        for erreur in donnees["erreurs"]:
            typer.secho(f"erreur : {erreur['chemin']} ({erreur['erreur']})", fg=typer.colors.YELLOW, err=True)
    else:
        typer.secho(f"[{bilan['statut']}] {bilan['message']}", fg=typer.colors.RED, err=True)
    if bilan["statut"] != "succes":
        raise typer.Exit(code=1)


@app.command(name="demander")
def demander(
    prompt: Optional[List[str]] = typer.Argument(None, help="Premier message de la conversation (optionnel : le REPL le demande sinon)."),
    plafond: int = typer.Option(10, "--plafond", min=1, help="Nombre maximum d'invocations d'outils par tour."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute (par tour, réponse normalisée)."),
) -> None:
    """Conversation agentique multi-tours (T11.1) : REPL, mot-clé de clôture `stop`."""
    identifiant = id_execution or _id_execution_auto()
    _configurer_logging(identifiant)
    _charger_inventaire_persiste(identifiant)
    if not sortie_json:
        typer.echo(f"id_execution : {identifiant}", err=True)

    premier_message = " ".join(prompt).strip() if prompt else ""
    if prompt is not None and not premier_message:
        typer.secho("Le prompt ne peut pas être vide.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    creation = creer_agent(identifiant)
    if creation["statut"] != "succes":
        typer.secho(f"[{creation['statut']}] {creation['message']}", fg=typer.colors.RED, err=True)
        suggestion = creation.get("donnees", {}).get("suggestion")
        if suggestion:
            typer.secho(f"suggestion : {suggestion}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)
    agent = creation["donnees"]["agent"]

    conversation = None
    destruction = {"statut": "succes", "message": "", "donnees": {"detruit": True}}
    suppression = {"statut": "succes", "message": "", "donnees": {"supprimee": True}}
    try:
        conversation = creer_conversation(agent, identifiant, plafond=plafond)
        if premier_message:
            consigner_demande(identifiant, premier_message)
        if not sortie_json:
            typer.secho(
                "Conversation ouverte. Mot-clé de clôture : stop (ou Ctrl+D / Ctrl+C).",
                fg=typer.colors.BLUE,
                err=True,
            )
        while True:
            try:
                message = premier_message or typer.prompt("vous", prompt_suffix="> ")
            except (EOFError, KeyboardInterrupt, StopIteration):
                if not sortie_json:
                    typer.echo("")
                break
            premier_message = ""
            message = (message or "").strip()
            if not message:
                continue
            if message.lower() == "stop":
                break
            reponse = tour_conversation(conversation, message)
            _afficher_tour(reponse, sortie_json)
            if reponse["statut"] not in ("succes",):
                break
    finally:
        if conversation is not None:
            suppression = cloturer_conversation(conversation)
        destruction = detruire_agent(agent)

    chemin_journal = REPERTOIRE_JOURNAUX / identifiant / "conversation.jsonl"
    if sortie_json:
        import json
        charge = {
            "statut": "succes",
            "message": "",
            "donnees": {
                "nb_tours": conversation.nb_tours if conversation else 0,
                "nb_invocations": conversation.nb_invocations if conversation else 0,
                "plafond": plafond,
                "conversation_id": conversation.conversation_id if conversation else None,
                "journal": str(chemin_journal),
                "agent_detruit": destruction["donnees"].get("detruit", False),
                "conversation_supprimee": suppression["donnees"].get("supprimee", False),
            },
        }
        typer.echo(json.dumps(charge, ensure_ascii=False, indent=2))
    else:
        typer.secho(f"journal de conversation : {chemin_journal}", fg=typer.colors.BLUE)
        if destruction["statut"] != "succes" or not destruction["donnees"].get("detruit", True):
            typer.secho(f"destruction de l'agent : {destruction['statut']} {destruction['message']}", fg=typer.colors.YELLOW, err=True)
        if suppression["statut"] != "succes":
            typer.secho(f"suppression de la conversation : {suppression['message']}", fg=typer.colors.YELLOW, err=True)


# ---------------------------------------------------------------------------
# Alias anglais (T13.3) — rétrocompatibilité des commandes renommées.
# Chaque alias déclare la MÊME signature que la commande française et
# délègue à celle-ci : l'alias accepte les mêmes arguments et options.
# ---------------------------------------------------------------------------

@app.command(name="search")
def search(
    mots_cles: List[str] = typer.Argument(..., help="Mots-clés de la recherche (logique ET)."),
    tri: str = typer.Option("pertinence", "--tri", help="Ordre de tri des resultats."),
    fenetre_maj: str = typer.Option("toutes", "--fenetre-maj", help="Restriction sur la derniere mise a jour."),
    limite: int = typer.Option(10, "--limite", min=1, max=20, help="Nombre maximum de jeux retournes."),
    page: int = typer.Option(1, "--page", min=1, help="Numero de la page de resultats demandee."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la reponse normalisee."),
) -> None:
    """Alias anglais de `rechercher`."""
    rechercher(
        mots_cles=mots_cles, tri=tri, fenetre_maj=fenetre_maj, limite=limite,
        page=page, id_execution=id_execution, sortie_json=sortie_json,
    )


@app.command(name="list")
def list(
    id_jeu: str = typer.Argument(..., help="Identifiant du jeu, issu de la recherche."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la reponse normalisee."),
) -> None:
    """Alias anglais de `lister`."""
    lister(id_jeu=id_jeu, id_execution=id_execution, sortie_json=sortie_json)


@app.command(name="download")
def download(
    id_ressource: str = typer.Argument(..., help="Identifiant de la ressource, issu de l'inventaire."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la reponse normalisee."),
) -> None:
    """Alias anglais de `telecharger`."""
    telecharger(id_ressource=id_ressource, id_execution=id_execution, sortie_json=sortie_json)


@app.command(name="extract")
def extract(
    id_ressource: str = typer.Argument(..., help="Identifiant de la ressource indexee, issu de l'inventaire."),
    taille_page: int = typer.Option(100, "--taille-page", min=1, help="Lignes demandees par page a l'API tabulaire."),
    plafond_lignes: Optional[int] = typer.Option(None, "--plafond-lignes", min=1, help="Nombre maximum de lignes extraites (defaut : PLAFOND_EXTRACTION, 10000)."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la reponse normalisee."),
) -> None:
    """Alias anglais de `extraire`."""
    extraire(
        id_ressource=id_ressource, taille_page=taille_page,
        plafond_lignes=plafond_lignes, id_execution=id_execution,
        sortie_json=sortie_json,
    )


@app.command(name="query")
def query(
    id_ressource: str = typer.Argument(..., help="Identifiant de la ressource, issu de l'inventaire."),
    page: int = typer.Option(1, "--page", min=1, help="Page demandee."),
    taille_page: int = typer.Option(20, "--taille-page", min=1, max=50, help="Lignes par page (max 50)."),
    colonne: Optional[str] = typer.Option(None, "--filtre-colonne", help="Colonne du filtre."),
    valeur: Optional[str] = typer.Option(None, "--filtre-valeur", help="Valeur du filtre."),
    operateur: Optional[str] = typer.Option("exact", "--filtre-operateur", help="Operateur : exact, contient, inferieur, superieur, strictement_inferieur, strictement_superieur."),
    tri_colonne: Optional[str] = typer.Option(None, "--tri-colonne", help="Colonne du tri."),
    tri_ordre: Optional[str] = typer.Option("croissant", "--tri-ordre", help="Ordre : croissant ou decroissant."),
    apercu: int = typer.Option(APERCU_DEFAUT, "--apercu", min=0, help="Nombre maximum de lignes affichees (apercu)."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute de la reponse normalisee."),
) -> None:
    """Alias anglais de `interroger`."""
    interroger(
        id_ressource=id_ressource, page=page, taille_page=taille_page,
        colonne=colonne, valeur=valeur, operateur=operateur,
        tri_colonne=tri_colonne, tri_ordre=tri_ordre, apercu=apercu,
        id_execution=id_execution, sortie_json=sortie_json,
    )


@app.command(name="ask")
def ask(
    prompt: Optional[List[str]] = typer.Argument(None, help="Premier message de la conversation (optionnel : le REPL le demande sinon)."),
    plafond: int = typer.Option(10, "--plafond", min=1, help="Nombre maximum d'invocations d'outils par tour."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute (par tour, reponse normalisee)."),
) -> None:
    """Alias anglais de `demander`."""
    demander(
        prompt=prompt, plafond=plafond,
        id_execution=id_execution, sortie_json=sortie_json,
    )


@app.command(name="chat")
def chat(
    prompt: Optional[List[str]] = typer.Argument(None, help="Premier message de la conversation (optionnel : le REPL le demande sinon)."),
    plafond: int = typer.Option(10, "--plafond", min=1, help="Nombre maximum d'invocations d'outils par tour."),
    id_execution: Optional[str] = typer.Option(None, "--id-execution", help=AIDE_ID_EXECUTION),
    sortie_json: bool = typer.Option(False, "--json", help="Sortie JSON brute (par tour, reponse normalisee)."),
) -> None:
    """Alias anglais historique de `demander` (remplacé par `ask`, T13.3)."""
    demander(
        prompt=prompt, plafond=plafond,
        id_execution=id_execution, sortie_json=sortie_json,
    )



def _afficher_tour(reponse: dict, sortie_json: bool) -> None:
    """Affiche le résultat d'un tour de conversation (T11.1)."""
    import json as _json
    if sortie_json:
        typer.echo(_json.dumps(reponse, ensure_ascii=False, indent=2))
        return
    donnees = reponse["donnees"]
    typer.echo(f"--- tour {donnees['numero_tour']} : {donnees['nb_invocations']}/{donnees['plafond']} invocation(s) ---")
    if reponse["statut"] != "succes":
        typer.secho(f"[{reponse['statut']}] {reponse['message']}", fg=typer.colors.RED, err=True)
    elif reponse["message"]:
        typer.secho(reponse["message"], fg=typer.colors.YELLOW, err=True)
    if donnees.get("synthese"):
        typer.echo(donnees["synthese"])
    typer.echo("")


if __name__ == "__main__":
    app()
