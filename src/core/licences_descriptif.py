# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : licences_descriptif.py
# Version      : 1
# Date         : 15-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Registre descriptif des licences et mention d'attribution (T7.5).

Deterministe : aucune decision agentique. Miroir de la politique
documentee dans docs/README.md (section Politique de licence).
Proprietes jamais devinees : les licences `other-*` et `notspecified`
sont marquees `a_verifier` ; toute licence hors registre produit un
echec propre.
"""

from typing import Any, Dict, Optional

# Statuts de verification :
#   "connu"       : proprietes certaines (texte de licence public) ;
#   "a_verifier"   : license declaree ouverte/attribution/domaine public
#                   sans texte connu : obligations a verifier sur la
#                   fiche du jeu, jamais devinees.
PROPRIETES_LICENCES: Dict[str, Dict[str, Any]] = {
    "lov2": {
        "nom": "Licence Ouverte / Open Licence 2.0 (Etalab)",
        "attribution_requise": True,
        "attribution_facultative": False,
        "partage_a_l_identique_requis": False,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "fr-lo": {
        "nom": "Licence Ouverte (variante d'ecriture data.gouv.fr)",
        "attribution_requise": True,
        "attribution_facultative": False,
        "partage_a_l_identique_requis": False,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "odc-odbl": {
        "nom": "Open Database License (ODbL)",
        "attribution_requise": True,
        "attribution_facultative": False,
        "partage_a_l_identique_requis": True,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "odc-by": {
        "nom": "Open Data Commons Attribution",
        "attribution_requise": True,
        "attribution_facultative": False,
        "partage_a_l_identique_requis": False,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "odc-pddl": {
        "nom": "Open Data Commons Public Domain Dedication and License",
        "attribution_requise": False,
        "attribution_facultative": True,
        "partage_a_l_identique_requis": False,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "cc-by": {
        "nom": "Creative Commons Attribution 4.0",
        "attribution_requise": True,
        "attribution_facultative": False,
        "partage_a_l_identique_requis": False,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "cc-by-sa": {
        "nom": "Creative Commons Attribution - ShareAlike 4.0",
        "attribution_requise": True,
        "attribution_facultative": False,
        "partage_a_l_identique_requis": True,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "cc-zero": {
        "nom": "CC0 1.0 (domaine public)",
        "attribution_requise": False,
        "attribution_facultative": True,
        "partage_a_l_identique_requis": False,
        "usage_commercial_autorise": True,
        "a_verifier": False,
    },
    "other-open": {
        "nom": "Autre licence ouverte (mention libre du producteur)",
        "attribution_requise": None,
        "attribution_facultative": None,
        "partage_a_l_identique_requis": None,
        "usage_commercial_autorise": None,
        "a_verifier": True,
    },
    "other-attribution": {
        "nom": "Autre licence a attribution",
        "attribution_requise": None,
        "attribution_facultative": None,
        "partage_a_l_identique_requis": None,
        "usage_commercial_autorise": None,
        "a_verifier": True,
    },
    "other-pd": {
        "nom": "Autre mention de domaine public",
        "attribution_requise": None,
        "attribution_facultative": None,
        "partage_a_l_identique_requis": None,
        "usage_commercial_autorise": None,
        "a_verifier": True,
    },
    "notspecified": {
        "nom": "Licence non renseignee",
        "attribution_requise": None,
        "attribution_facultative": None,
        "partage_a_l_identique_requis": None,
        "usage_commercial_autorise": None,
        "a_verifier": True,
    },
}


def _normaliser(licence: Optional[str]) -> str:
    if not isinstance(licence, str):
        return ""
    return licence.strip().lower()


def propriete_licence(licence: Optional[str]) -> Dict[str, Any]:
    """Retourne les proprietes descriptives d'une licence du registre.

    Echec propre : une licence absente, nulle, vide ou hors registre
    produit un statut d'erreur explicite, jamais de proprietes devinees.
    """
    code = _normaliser(licence)
    if code not in PROPRIETES_LICENCES:
        return {
            "statut": "licence_inconnue",
            "message": f"La licence '{licence or ''}' n'est pas referencee dans le registre descriptif.",
            "donnees": {},
        }
    return {
        "statut": "succes",
        "message": "",
        "donnees": dict(PROPRIETES_LICENCES[code]),
    }


def _predicat(licence: Optional[str], cle: str) -> Optional[bool]:
    proprietes = propriete_licence(licence)
    if proprietes["statut"] != "succes":
        return None
    return proprietes["donnees"][cle]


def attribution_requise(licence: Optional[str]) -> Optional[bool]:
    """True si l'attribution est obligatoire ; None si a verifier / inconnue."""
    return _predicat(licence, "attribution_requise")


def partage_a_l_identique_requis(licence: Optional[str]) -> Optional[bool]:
    """True si le partage a l'identique est obligatoire ; None sinon."""
    return _predicat(licence, "partage_a_l_identique_requis")


def produit_derive_permissif_autorise(licence: Optional[str]) -> Optional[bool]:
    """True si un produit derive sous licence permissive est autorise.

    Faux pour les licences copyleft (`odc-odbl`, `cc-by-sa`) ; vrai pour
    les licences permissives ; None si les proprietes sont a verifier ou
    la licence inconnue — jamais devine.
    """
    if partage_a_l_identique_requis(licence) is True:
        return False
    if partage_a_l_identique_requis(licence) is None:
        return None
    return True


def mention_attribution(
    organisation: Optional[str],
    licence: Optional[str],
    derniere_maj: Optional[str] = None,
    licence_conditionnelle: bool = False,
) -> Dict[str, Any]:
    """Genere la mention d'attribution prete a afficher.

    Args:
        organisation (Optional[str]): Nom de l'organisation productrice.
        licence (Optional[str]): Code de licence (ex. `lov2`).
        derniere_maj (Optional[str]): Date de derniere mise a jour du jeu
            (facultative, mentionnee si fournie).
        licence_conditionnelle (bool): Vrai si la licence a ete acceptee
            par derogation (notspecified + producteur public) : la
            mention porte alors un avertissement de verification.

    Returns:
        Dict[str, Any]: Resultat normalise (statut/message/donnees) ;
        `donnees.mention` contient la mention prete a afficher, `null`
        pour les licences a verifier (other-*, notspecified) — jamais
        devinee.
    """
    code = _normaliser(licence)
    proprietes = propriete_licence(code)
    if proprietes["statut"] != "succes":
        return {
            "statut": "licence_inconnue",
            "message": proprietes["message"],
            "donnees": {"mention": None, "suggestion": "verifier la licence sur la fiche du jeu"},
        }
    props = proprietes["donnees"]
    if props["a_verifier"]:
        return {
            "statut": "licence_a_verifier",
            "message": (
                f"La licence '{code}' ne permet pas de generer une mention fiable : "
                "les obligations exactes dependent du texte de la licence citee sur la fiche du jeu."
            ),
            "donnees": {"mention": None, "suggestion": "verifier la licence sur la fiche du jeu"},
        }

    source = (organisation or "").strip() or "source inconnue"
    mention = f"Source : {source} — donnees sous licence {props['nom']}"

    if props["attribution_facultative"]:
        mention += " (attribution non obligatoire, mention de courtoisie)"
    if props["partage_a_l_identique_requis"]:
        mention += " ; tout produit derive doit etre redistribute sous la meme licence (partage a l'identique)"
    if derniere_maj:
        mention += f", mise a jour du {derniere_maj}"
    if licence_conditionnelle:
        mention += ". Avertissement : licence non renseignee acceptee par derogation (producteur public) — verifier les obligations avant exploitation"

    return {
        "statut": "succes",
        "message": "",
        "donnees": {"mention": mention, "attribution_requise": props["attribution_requise"]},
    }
