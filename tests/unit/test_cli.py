# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_cli.py
# Version      : 1
# Date         : 13-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires de la CLI (src/main.py, T4.1/T4.2 — perimetre search).

La fonction coeur `rechercher_jeux` est simulee : la CLI se teste sans
reseau et sans connaitre le comportement du coeur.
"""
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.main import app

runner = CliRunner()

REPONSE_SUCCES = {
    "statut": "succes",
    "message": "",
    "donnees": {
        "total_trouves": 2,
        "jeux": [
            {
                "id": "abc123",
                "titre": "Comptes des administrations publiques",
                "organisation": "Insee",
                "licence": "lov2",
                "derniere_maj": "2026-09-30",
                "nb_ressources": 2,
                "url": "https://www.data.gouv.fr/datasets/comptes-des-administrations-publiques",
            }
        ],
        "exclus_licence": 1,
        "page_courante": 2,
        "page_suivante": None,
    },
}


@patch("src.main.rechercher_jeux")
def test_search_appel_coeur_avec_options(mock_recherche):
    # Réf. tests/plan_tests.md : TI-13 (appels logs avec mots_cles, tri, limite — via la CLI)
    mock_recherche.return_value = REPONSE_SUCCES
    resultat = runner.invoke(app, ["search", "dette", "publique", "--tri", "vues", "--limite", "5", "--page", "2"])
    assert resultat.exit_code == 0
    mock_recherche.assert_called_once()
    kwargs = mock_recherche.call_args.kwargs
    assert kwargs["mots_cles"] == ["dette", "publique"]
    assert kwargs["tri"] == "vues"
    assert kwargs["limite"] == 5
    assert kwargs["page"] == 2
    assert "Comptes des administrations publiques" in resultat.output
    assert "page 2" in resultat.output
    assert "exclu(s) licence" in resultat.output


@patch("src.main.rechercher_jeux")
def test_search_valeurs_par_defaut(mock_recherche):
    # Réf. tests/plan_tests.md : TU-13 (limite omise -> valeur par défaut 10)
    mock_recherche.return_value = REPONSE_SUCCES
    resultat = runner.invoke(app, ["search", "dette"])
    assert resultat.exit_code == 0
    kwargs = mock_recherche.call_args.kwargs
    assert kwargs["tri"] == "pertinence"
    assert kwargs["fenetre_maj"] == "toutes"
    assert kwargs["limite"] == 10
    assert kwargs["id_execution"]


@patch("src.main.rechercher_jeux")
def test_search_sortie_json(mock_recherche):
    # Test annexe : sans référence directe dans tests/plan_tests.md
    mock_recherche.return_value = REPONSE_SUCCES
    resultat = runner.invoke(app, ["search", "dette", "--json"])
    assert resultat.exit_code == 0
    charge = json.loads(resultat.output)
    assert charge["statut"] == "succes"
    assert charge["donnees"]["exclus_licence"] == 1
    assert charge["donnees"]["jeux"][0]["licence"] == "lov2"


def test_search_limite_hors_bornes():
    # Réf. tests/plan_tests.md : TU-14 (limite au-delà du maximum -> erreur, pas d'exception)
    resultat = runner.invoke(app, ["search", "dette", "--limite", "50"])
    assert resultat.exit_code != 0
    assert "limite" in (resultat.output + str(resultat.stderr)).lower()


def test_search_tri_invalide():
    # Réf. tests/plan_tests.md : TU-16 (tri invalide -> erreur_parametres)
    resultat = runner.invoke(app, ["search", "dette", "--tri", "invalide"])
    assert resultat.exit_code == 2
    assert "invalide" in (resultat.output + str(resultat.stderr)).lower()


@patch("src.main.rechercher_jeux")
def test_search_echec_technique_code_sortie(mock_recherche):
    # Réf. tests/plan_tests.md : TU-17 (erreur HTTP 500 -> statut echec_technique, pas d'exception)
    mock_recherche.return_value = {
        "statut": "echec_technique",
        "message": "Échec de l'appel à l'API data.gouv.fr",
        "donnees": {"suggestion": "réessayer"},
    }
    resultat = runner.invoke(app, ["search", "dette"])
    assert resultat.exit_code == 1
    assert "echec_technique" in (resultat.output + str(resultat.stderr))


@patch("src.main.rechercher_jeux")
def test_search_erreur_parametres_code_sortie(mock_recherche):
    # Réf. tests/plan_tests.md : TU-12 (mots_cles vide -> erreur_parametres)
    mock_recherche.return_value = {
        "statut": "erreur_parametres",
        "message": "Le paramètre 'mots_cles' est obligatoire et ne peut être vide.",
        "donnees": {},
    }
    resultat = runner.invoke(app, ["search", "dette"])
    assert resultat.exit_code == 2


REPONSE_QUERY_SUCCES = {
    "statut": "succes",
    "message": "",
    "donnees": {
        "total_lignes": 74,
        "page": 1,
        "page_suivante": 2,
        "colonnes": ["theme", "indicateur", "valeur"],
        "lignes": [{"theme": "dette", "indicateur": "solde", "valeur": "-100"}],
    },
}


@patch("src.main.interroger_ressource")
def test_query_appel_coeur_avec_options(mock_query):
    # Réf. tests/plan_tests.md : TI-13 (appels logs via la CLI — périmètre query)
    mock_query.return_value = REPONSE_QUERY_SUCCES
    resultat = runner.invoke(app, ["query", "e322fb3f", "--page", "2", "--taille-page", "50",
                                   "--filtre-colonne", "theme", "--filtre-valeur", "dette",
                                   "--filtre-operateur", "contient",
                                   "--tri-colonne", "valeur", "--tri-ordre", "decroissant"])
    assert resultat.exit_code == 0
    mock_query.assert_called_once()
    kwargs = mock_query.call_args.kwargs
    assert kwargs["id_ressource"] == "e322fb3f"
    assert kwargs["page"] == 2
    assert kwargs["taille_page"] == 50
    assert kwargs["filtre"] == {"colonne": "theme", "valeur": "dette", "operateur": "contient"}
    assert kwargs["tri"] == {"colonne": "valeur", "ordre": "decroissant"}
    assert "74 ligne(s)" in resultat.output
    assert "theme" in resultat.output


@patch("src.main.interroger_ressource")
def test_query_valeurs_par_defaut(mock_query):
    # Test annexe : défauts page/taille_page/filtre/tri via la CLI
    mock_query.return_value = REPONSE_QUERY_SUCCES
    resultat = runner.invoke(app, ["query", "e322fb3f"])
    assert resultat.exit_code == 0
    kwargs = mock_query.call_args.kwargs
    assert kwargs["page"] == 1
    assert kwargs["taille_page"] == 20
    assert kwargs["filtre"] is None
    assert kwargs["tri"] is None
    assert kwargs["id_execution"]


@patch("src.main.interroger_ressource")
def test_query_sortie_json(mock_query):
    # Test annexe : sortie JSON brute via --json
    mock_query.return_value = REPONSE_QUERY_SUCCES
    resultat = runner.invoke(app, ["query", "e322fb3f", "--json"])
    assert resultat.exit_code == 0
    assert json.loads(resultat.output)["donnees"]["total_lignes"] == 74


@patch("src.main.interroger_ressource")
def test_query_operateur_invalide(mock_query):
    # Réf. tests/plan_tests.md : TI-04 (opérateur inconnu — garde CLI, même sémantique que erreur_parametres)
    mock_query.return_value = REPONSE_QUERY_SUCCES
    resultat = runner.invoke(app, ["query", "e322fb3f", "--filtre-colonne", "theme",
                                   "--filtre-valeur", "dette", "--filtre-operateur", "egal"])
    assert resultat.exit_code == 2
    assert "invalide" in (resultat.output + str(resultat.stderr)).lower()
    mock_query.assert_not_called()


def test_query_tri_ordre_invalide():
    # Réf. tests/plan_tests.md : TI-04 (ordre inconnu — garde CLI)
    resultat = runner.invoke(app, ["query", "e322fb3f", "--tri-colonne", "valeur", "--tri-ordre", "ascendant"])
    assert resultat.exit_code == 2
    assert "invalide" in (resultat.output + str(resultat.stderr)).lower()


@patch("src.main.interroger_ressource")
def test_query_ressource_non_indexee_code_sortie(mock_query):
    # Réf. tests/plan_tests.md : TI-04 (ressource non indexée -> suggestion telecharger_brut)
    mock_query.return_value = {
        "statut": "ressource_non_indexee",
        "message": "La ressource n'est pas indexee par l'API tabulaire.",
        "donnees": {"suggestion": "utiliser telecharger_brut"},
    }
    resultat = runner.invoke(app, ["query", "e322fb3f"])
    assert resultat.exit_code == 1
    assert "ressource_non_indexee" in (resultat.output + str(resultat.stderr))
    assert "suggestion" in (resultat.output + str(resultat.stderr))


@patch("src.main.interroger_ressource")
def test_query_erreur_parametres_code_sortie(mock_query):
    # Test annexe : erreur_parametres propagée par le cœur, code 2
    mock_query.return_value = {
        "statut": "erreur_parametres",
        "message": "Le parametre 'taille_page' doit etre compris entre 1 et 50.",
        "donnees": {},
    }
    resultat = runner.invoke(app, ["query", "e322fb3f"])
    assert resultat.exit_code == 2


REPONSE_DOWNLOAD_SUCCES = {
    "statut": "succes",
    "message": "",
    "donnees": {
        "chemin_local": "data/raw/20261014_120000/71ff1335.csv",
        "format": "csv",
        "licence": "lov2",
    },
}


@patch("src.main.telecharger_brut")
def test_download_appel_coeur(mock_download):
    # Réf. tests/plan_tests.md : TI-13 (appels logs via la CLI — périmètre download)
    mock_download.return_value = REPONSE_DOWNLOAD_SUCCES
    resultat = runner.invoke(app, ["download", "71ff1335"])
    assert resultat.exit_code == 0
    kwargs = mock_download.call_args.kwargs
    assert kwargs["id_ressource"] == "71ff1335"
    assert kwargs["id_execution"]
    assert "data/raw/20261014_120000/71ff1335.csv" in resultat.output
    assert "csv" in resultat.output


@patch("src.main.telecharger_brut")
def test_download_sortie_json(mock_download):
    # Test annexe : sortie JSON brute via --json
    mock_download.return_value = REPONSE_DOWNLOAD_SUCCES
    resultat = runner.invoke(app, ["download", "71ff1335", "--json"])
    assert resultat.exit_code == 0
    assert json.loads(resultat.output)["donnees"]["format"] == "csv"


@patch("src.main.telecharger_brut")
def test_download_echec_technique_avec_suggestion(mock_download):
    # Réf. tests/plan_tests.md : TI-08 (échec serveur d'origine -> suggestion fichier_heberge_exterieurement)
    mock_download.return_value = {
        "statut": "echec_technique",
        "message": "serveur_origine_bloque",
        "donnees": {"suggestion": "fichier_heberge_exterieurement"},
    }
    resultat = runner.invoke(app, ["download", "71ff1335"])
    assert resultat.exit_code == 1
    assert "echec_technique" in (resultat.output + str(resultat.stderr))
    assert "fichier_heberge_exterieurement" in (resultat.output + str(resultat.stderr))


@patch("src.main.telecharger_brut")
def test_download_ressource_introuvable_code_sortie(mock_download):
    # Réf. tests/plan_tests.md : TI-06 (ressource jamais vue par l'inventaire -> ressource_introuvable)
    mock_download.return_value = {
        "statut": "ressource_introuvable",
        "message": "Ressource inconnue : reprendre par l'inventaire.",
        "donnees": {},
    }
    resultat = runner.invoke(app, ["download", "inconnu"])
    assert resultat.exit_code == 2


REPONSE_CHAT_SUCCES = {
    "statut": "succes",
    "message": "",
    "donnees": {
        "reponse_agent": "Rapport : 1 jeu retenu, 1 fichier acquis (licence lov2).",
        "nb_invocations": 4,
        "plafond": 10,
    },
}

AGENT_CHAT = type("AgentFaux", (), {})()


@patch("src.main.creer_agent")
@patch("src.main.boucle_conversation")
@patch("src.main.detruire_agent")
def test_chat_succes(mock_destruction, mock_boucle, mock_creation):
    # Réf. tests/plan_tests.md : Annexe T4.3 — flux complet affiché, destruction systématique
    mock_creation.return_value = {"statut": "succes", "message": "", "donnees": {"agent": AGENT_CHAT}}
    mock_boucle.return_value = REPONSE_CHAT_SUCCES
    mock_destruction.return_value = {"statut": "succes", "message": "", "donnees": {"detruit": True}}
    resultat = runner.invoke(app, ["chat", "cherche", "la", "dette", "publique"])
    assert resultat.exit_code == 0
    args_boucle = mock_boucle.call_args.args
    kwargs_boucle = mock_boucle.call_args.kwargs
    assert args_boucle[0] is AGENT_CHAT
    assert args_boucle[1] == "cherche la dette publique"
    assert kwargs_boucle["plafond"] == 10
    assert kwargs_boucle["id_execution"]
    assert "4/10" in resultat.output
    assert "Rapport" in resultat.output
    assert "conversation.jsonl" in resultat.output
    mock_destruction.assert_called_once_with(AGENT_CHAT)


@patch("src.main.creer_agent")
@patch("src.main.boucle_conversation")
@patch("src.main.detruire_agent")
def test_chat_plafond_propage(mock_destruction, mock_boucle, mock_creation):
    # Réf. tests/plan_tests.md : Annexe T4.3 — --plafond propagé à la boucle
    mock_creation.return_value = {"statut": "succes", "message": "", "donnees": {"agent": AGENT_CHAT}}
    mock_boucle.return_value = {
        "statut": "succes", "message": "", "donnees": {"reponse_agent": "ok", "nb_invocations": 2, "plafond": 3},
    }
    mock_destruction.return_value = {"statut": "succes", "message": "", "donnees": {"detruit": True}}
    resultat = runner.invoke(app, ["chat", "x", "--plafond", "3", "--id-execution", "id_chat"])
    assert resultat.exit_code == 0
    assert mock_boucle.call_args.kwargs["plafond"] == 3
    assert mock_boucle.call_args.kwargs["id_execution"] == "id_chat"


@patch("src.main.creer_agent")
@patch("src.main.boucle_conversation")
@patch("src.main.detruire_agent")
def test_chat_sortie_json(mock_destruction, mock_boucle, mock_creation):
    # Réf. tests/plan_tests.md : Annexe T4.3 — --json : réponse normalisée + journal + agent_detruit
    mock_creation.return_value = {"statut": "succes", "message": "", "donnees": {"agent": AGENT_CHAT}}
    mock_boucle.return_value = REPONSE_CHAT_SUCCES
    mock_destruction.return_value = {"statut": "succes", "message": "", "donnees": {"detruit": True}}
    resultat = runner.invoke(app, ["chat", "x", "--json"])
    assert resultat.exit_code == 0
    charge = json.loads(resultat.output)
    assert charge["statut"] == "succes"
    assert charge["donnees"]["nb_invocations"] == 4
    assert charge["donnees"]["journal"].endswith("conversation.jsonl")
    assert charge["donnees"]["agent_detruit"] is True


@patch("src.main.creer_agent")
@patch("src.main.detruire_agent")
def test_chat_echec_creation_agent(mock_destruction, mock_creation):
    # Réf. tests/plan_tests.md : Annexe T4.3 — clé absente/erreur : code 1, suggestion affichée
    mock_creation.return_value = {
        "statut": "echec_technique",
        "message": "Variable d'environnement MISTRAL_API_KEY absente ou vide.",
        "donnees": {"suggestion": "definir MISTRAL_API_KEY dans .env"},
    }
    resultat = runner.invoke(app, ["chat", "x"])
    assert resultat.exit_code == 1
    assert "MISTRAL_API_KEY" in (resultat.output + str(resultat.stderr))
    assert "suggestion" in (resultat.output + str(resultat.stderr))
    mock_destruction.assert_not_called()


@patch("src.main.creer_agent")
@patch("src.main.boucle_conversation")
@patch("src.main.detruire_agent")
def test_chat_echec_conversation_destruction_malgre_tout(mock_destruction, mock_boucle, mock_creation):
    # Réf. tests/plan_tests.md : Annexe T4.3 — échec en cours : agent quand même détruit (finally)
    mock_creation.return_value = {"statut": "succes", "message": "", "donnees": {"agent": AGENT_CHAT}}
    mock_boucle.return_value = {
        "statut": "echec_technique", "message": "Echec de l'appel a l'API Mistral : 429", "donnees": {"nb_invocations": 0, "plafond": 10},
    }
    mock_destruction.return_value = {"statut": "succes", "message": "", "donnees": {"detruit": True}}
    resultat = runner.invoke(app, ["chat", "x"])
    assert resultat.exit_code == 1
    assert "echec_technique" in (resultat.output + str(resultat.stderr))
    assert "conversation.jsonl" in (resultat.output + str(resultat.stderr))
    mock_destruction.assert_called_once_with(AGENT_CHAT)


@patch("src.main.creer_agent")
@patch("src.main.boucle_conversation")
@patch("src.main.detruire_agent")
def test_chat_exception_boucle_destruction_quand_meme(mock_destruction, mock_boucle, mock_creation):
    # Test annexe : exception inattendue dans la boucle — la finally détruit l'agent
    mock_creation.return_value = {"statut": "succes", "message": "", "donnees": {"agent": AGENT_CHAT}}
    mock_boucle.side_effect = RuntimeError("bug inattendu")
    mock_destruction.return_value = {"statut": "succes", "message": "", "donnees": {"detruit": True}}
    resultat = runner.invoke(app, ["chat", "x"])
    assert resultat.exit_code != 0
    mock_destruction.assert_called_once_with(AGENT_CHAT)


def test_chat_prompt_vide():
    # Réf. tests/plan_tests.md : Annexe T4.3 — prompt vide : code 2
    resultat = runner.invoke(app, ["chat"])
    assert resultat.exit_code == 2


# ---------------------------------------------------------------------
# T10.5 : vocabulaires au coeur + option --apercu
# ---------------------------------------------------------------------

def test_vocabulaires_source_unique():
    # Réf. T10.5 — le coeur (src/core/vocabulaires.py) est la source des vocabulaires fermés
    from src.core.vocabulaires import APERCU_DEFAUT, FenetreMaj, OperateurFiltre, OrdreTri, TriRecherche

    assert {e.value for e in TriRecherche} == {"pertinence", "recent", "vues", "reutilisations"}
    assert {e.value for e in FenetreMaj} == {"toutes", "30_jours", "12_mois", "3_ans"}
    assert {e.value for e in OperateurFiltre} == {
        "exact", "contient", "inferieur", "superieur", "strictement_inferieur", "strictement_superieur"
    }
    assert {e.value for e in OrdreTri} == {"croissant", "decroissant"}
    assert APERCU_DEFAUT == 5


def test_vocabulaires_partages_avec_les_contrats():
    # Réf. T10.5 — les contrats importent les mêmes StrEnum que la CLI (zéro divergence possible)
    from src.contracts.interroger_ressource import OperateurFiltre as OperateurContrat
    from src.contracts.interroger_ressource import OrdreTri as OrdreContrat
    from src.contracts.rechercher_jeux import FenetreMaj as FenetreContrat
    from src.contracts.rechercher_jeux import TriRecherche as TriContrat
    from src.core.vocabulaires import FenetreMaj, OperateurFiltre, OrdreTri, TriRecherche

    assert TriContrat is TriRecherche
    assert FenetreContrat is FenetreMaj
    assert OperateurContrat is OperateurFiltre
    assert OrdreContrat is OrdreTri


@patch("src.main.interroger_ressource")
def test_query_apercu_limite_lignes_affichees(mock_query):
    # Réf. T10.5 — --apercu borne l'affichage des lignes (défaut APERCU_DEFAUT = 5)
    lignes = [{"n": i} for i in range(8)]
    mock_query.return_value = {
        "statut": "succes",
        "message": "",
        "donnees": {"total_lignes": 8, "colonnes": ["n"], "lignes": lignes},
    }
    resultat = runner.invoke(app, ["query", "e322fb3f", "--taille-page", "50"])
    assert resultat.exit_code == 0
    assert resultat.output.count("- {") == 5
    assert "3 ligne(s) supplémentaires" in resultat.output

    resultat_2 = runner.invoke(app, ["query", "e322fb3f", "--taille-page", "50", "--apercu", "2"])
    assert resultat_2.exit_code == 0
    assert resultat_2.output.count("- {") == 2
    assert "6 ligne(s) supplémentaires" in resultat_2.output


# ---------------------------------------------------------------------
# T10.2 : chaînage list -> download via l'inventaire persistant
# ---------------------------------------------------------------------

@patch("src.main.telecharger_brut")
@patch("src.main.lister_ressources")
def test_chainage_list_download_inventaire_persiste(mock_liste, mock_download, tmp_path, monkeypatch):
    # Réf. T10.2 — même --id-execution : download retrouve l'inventaire de list (nouveau contexte)
    monkeypatch.chdir(tmp_path)
    mock_liste.return_value = {
        "statut": "succes",
        "message": "",
        "donnees": {"ressources": [{"id": "71ff1335", "titre": "Dette", "classe": "fichier_tabulaire",
                                      "format": "csv", "taille_octets": 1024, "url": "https://example.fr/d.csv"}],
                     "indetermination": []},
    }
    resultat_list = runner.invoke(app, ["list", "abc", "--id-execution", "flux-dette"])
    assert resultat_list.exit_code == 0
    chemin = tmp_path / "data" / "executions" / "flux-dette" / "inventaire.json"
    assert chemin.exists()

    import src.core.resources as module
    module._inventaire.clear()

    mock_download.return_value = REPONSE_DOWNLOAD_SUCCES
    resultat_download = runner.invoke(app, ["download", "71ff1335", "--id-execution", "flux-dette"])
    assert resultat_download.exit_code == 0
    mock_download.assert_called_once()
    assert "id_execution : flux-dette" in (resultat_download.output + str(resultat_download.stderr))


@patch("src.main.telecharger_brut")
def test_download_sans_inventaire_persiste_restIntrouvable(mock_download, tmp_path, monkeypatch):
    # Réf. T10.2 — sans inventaire persisté pour cet id : ressource_introuvable (convention 1)
    monkeypatch.chdir(tmp_path)
    import src.core.resources as module
    module._inventaire.clear()
    mock_download.return_value = {
        "statut": "ressource_introuvable",
        "message": "Ressource jamais vue par l'inventaire.",
        "donnees": {},
    }
    resultat = runner.invoke(app, ["download", "introuvable", "--id-execution", "autre-flux"])
    assert resultat.exit_code == 2
    assert not (tmp_path / "data" / "executions" / "autre-flux").exists()


# ---------------------------------------------------------------------
# T10.7/E4 : commande CLI extract
# ---------------------------------------------------------------------

REPONSE_EXTRACT_SUCCES = {
    "statut": "succes",
    "message": "",
    "donnees": {
        "chemin_local": "data/raw/flux/r1_donnees.csv",
        "total_lignes": 150,
        "lignes_ecrites": 150,
        "colonnes": ["theme", "valeur"],
        "tronque": False,
        "licence": "lov2",
    },
}


@patch("src.main.extraire_ressource")
def test_extract_appel_coeur_avec_options(mock_extraction):
    # Réf. T10.7 — la CLI traduit ses options en appel cœur
    mock_extraction.return_value = REPONSE_EXTRACT_SUCCES
    resultat = runner.invoke(app, ["extract", "r1", "--id-execution", "flux", "--taille-page", "50", "--plafond-lignes", "5000"])
    assert resultat.exit_code == 0
    kwargs = mock_extraction.call_args.kwargs
    assert kwargs["id_ressource"] == "r1"
    assert kwargs["id_execution"] == "flux"
    assert kwargs["taille_page"] == 50
    assert kwargs["plafond_lignes"] == 5000
    assert "data/raw/flux/r1_donnees.csv" in resultat.output


@patch("src.main.extraire_ressource")
def test_extract_affiche_la_troncature(mock_extraction):
    # Réf. T10.7 — succès partiel : la troncature est signalée à l'utilisateur
    mock_extraction.return_value = {
        "statut": "succes",
        "message": "Extraction tronquée au plafond de 100 lignes (450 lignes au total).",
        "donnees": dict(REPONSE_EXTRACT_SUCCES["donnees"], lignes_ecrites=100, total_lignes=450, tronque=True),
    }
    resultat = runner.invoke(app, ["extract", "r1"])
    assert resultat.exit_code == 0
    assert "100 écrite(s) sur 450" in resultat.output


@patch("src.main.extraire_ressource")
def test_extract_ressource_non_indexee_code_sortie(mock_extraction):
    # Réf. T10.7 — ressource_non_indexee : code 1, suggestion affichée
    mock_extraction.return_value = {
        "statut": "ressource_non_indexee",
        "message": "La ressource 'r1' n'est pas indexée par l'API tabulaire.",
        "donnees": {"suggestion": "basculer sur telecharger_brut"},
    }
    resultat = runner.invoke(app, ["extract", "r1"])
    assert resultat.exit_code == 1
    assert "basculer sur telecharger_brut" in (resultat.output + str(resultat.stderr))


@patch("src.main.extraire_ressource")
def test_extract_sortie_json(mock_extraction):
    # Réf. T10.7 — sortie --json parsable (sans ligne id_execution)
    mock_extraction.return_value = REPONSE_EXTRACT_SUCCES
    resultat = runner.invoke(app, ["extract", "r1", "--json"])
    assert resultat.exit_code == 0
    assert json.loads(resultat.output)["donnees"]["chemin_local"] == "data/raw/flux/r1_donnees.csv"


# ---------------------------------------------------------------------------
# T10.8 — Manifeste d'acquisition : commande acquisitions + consigne demande
# ---------------------------------------------------------------------------


def test_acquisitions_manifeste_absent_sortie_erreur():
    # T10.8 (E4) : aucune exécution -> message d'erreur, code 1.
    from src.core import manifeste as module_manifeste

    resultat = runner.invoke(app, ["acquisitions", "exec-fantome"])
    assert resultat.exit_code == 1
    assert "Aucun manifeste" in resultat.output


def test_acquisitions_affiche_les_entrees(tmp_path, monkeypatch):
    # T10.8 (E4) : le manifeste existant est affiché lisiblement
    # (fichier, voie, licence, jeu, organisation).
    monkeypatch.chdir(tmp_path)
    from src.core.manifeste import consigner_demande, enregistrer_acquisition

    consigner_demande("exec-a", "résultats des élections présidentielles")
    enregistrer_acquisition(
        "exec-a",
        {
            "fichier": "res-1_resultats-t1.csv",
            "voie": "extraction",
            "id_ressource": "res-1",
            "id_jeu": "jeu-1",
            "titre_jeu": "Élection présidentielle 2022 - 1er tour",
            "organisation": "Ministère de l'intérieur",
            "licence": "notspecified",
            "licence_conditionnelle": True,
            "tronque": False,
            "nb_lignes": 1,
        },
    )
    resultat = runner.invoke(app, ["acquisitions", "exec-a"])
    assert resultat.exit_code == 0
    assert "exec-a" in resultat.output
    assert "résultats des élections présidentielles" in resultat.output
    assert "res-1_resultats-t1.csv" in resultat.output
    assert "Élection présidentielle 2022 - 1er tour" in resultat.output
    assert "extraction" in resultat.output
    assert "(conditionnelle)" in resultat.output


def test_download_consigne_la_demande(tmp_path, monkeypatch):
    # T10.8 (E3) : la commande download écrit l'en-tête demande du manifeste
    # avant l'acquisition (échec réseau inclus : la consigne précède l'appel).
    monkeypatch.chdir(tmp_path)
    with patch("src.main.telecharger_brut") as mock_tele:
        mock_tele.return_value = {
            "statut": "succes",
            "message": "",
            "donnees": {
                "chemin_local": "x",
                "format": "csv",
                "licence": "fr-lo",
                "licence_conditionnelle": False,
                "mention_attribution": None,
            },
        }
        resultat = runner.invoke(app, ["download", "res-9", "--id-execution", "exec-d"])
        assert resultat.exit_code == 0
    from src.core.manifeste import lire_manifeste

    manifeste = lire_manifeste("exec-d")
    assert manifeste is not None
    assert manifeste["demande"] == "download res-9"
