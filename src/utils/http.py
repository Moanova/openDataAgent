# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : http.py
# Version      : 1
# Date         : 12-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Client HTTP générique pour l'API data.gouv.fr.

Couche unique d'accès réseau du projet (T3.1.1). Fournit :
- une session `requests` réutilisable avec `User-Agent` explicite ;
- des tentatives de reprise sur les statuts transitoires (429, 502, 503)
  et les erreurs de connexion, avec délai croissant ;
- des retours structurés sans exception : aucun appel ne lève, les
  echecs sont convertis en statut `echec_technique` (ou `jeu_introuvable`
  pour un 404).
"""
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from src.utils.logging import get_logger, log_to_file

load_dotenv()

logger = get_logger("openDataAgent.utils.http")

URL_BASE_DEFAUT = "https://www.data.gouv.fr/api/2/"
URL_BASE_TABULAIRE_DEFAUT = "https://tabular-api.data.gouv.fr/api"
PAGE_SIZE_INVENTAIRE = 50
PLAFOND_PAGES_INVENTAIRE = 20
DELAIS_TENTATIVES = (1, 2)
STATUTS_TRANSITOIRES = {429, 502, 503}


@dataclass
class ResultatAppel:
    """Résultat structuré d'un appel API, sans exception."""

    statut: str
    status_code: Optional[int] = None
    donnees: Dict[str, Any] = field(default_factory=dict)
    erreur: Optional[str] = None

    @property
    def reussi(self) -> bool:
        return self.statut == "succes"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "openDataAgent/1.0 (https://github.com/Moanova/openDataAgent)"})
    return session


_SESSION = _session()


def appel_api(
    chemin: str,
    params: Optional[Dict[str, Any]] = None,
    url_base: Optional[str] = None,
    timeout: float = 10.0,
    nb_tentatives: int = 3,
    statut_404: str = "jeu_introuvable",
) -> ResultatAppel:
    """Effectue un appel GET vers une API data.gouv.fr avec reprise sur échec transitoire.

    Ne lève jamais d'exception : les échecs techniques (injoignable,
    éxpiration du délai, statut transitoire persistant) produisent un
    `ResultatAppel` de statut `echec_technique` ; un 404 produit le
    statut `statut_404` (par defaut `jeu_introuvable`, ou
    `ressource_non_indexee` pour l'API tabulaire).
    """
    base = url_base or os.environ.get("DATA_GOUV_API_URL", URL_BASE_DEFAUT)
    url = f"{base.rstrip('/')}/{chemin.lstrip('/')}"

    for tentative in range(1, nb_tentatives + 1):
        try:
            reponse = _SESSION.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            log_to_file(
                "Échec de l'appel HTTP à data.gouv.fr",
                url=url,
                tentative=tentative,
                erreur=str(exc),
                suggestion="Réessayer apres 30 secondes",
            )
            if tentative < nb_tentatives:
                time.sleep(DELAIS_TENTATIVES[min(tentative - 1, len(DELAIS_TENTATIVES) - 1)])
                continue
            return ResultatAppel(statut="echec_technique", erreur=str(exc))

        if reponse.status_code == 404:
            return ResultatAppel(statut=statut_404, status_code=404)

        if reponse.status_code in STATUTS_TRANSITOIRES and tentative < nb_tentatives:
            log_to_file(
                "Statut transitoire, nouvelle tentative",
                url=url,
                status_code=reponse.status_code,
                tentative=tentative,
            )
            time.sleep(DELAIS_TENTATIVES[min(tentative - 1, len(DELAIS_TENTATIVES) - 1)])
            continue

        if reponse.status_code >= 400:
            # Message d'erreur actionnable quand l'API en fournit un
            # (ex : colonne de filtre inexistante -> detail.message).
            detail_erreur = None
            try:
                corps = reponse.json()
                erreurs = corps.get("errors") if isinstance(corps, dict) else None
                if erreurs and isinstance(erreurs, list):
                    detail = (erreurs[0] or {}).get("detail") or {}
                    detail_erreur = detail.get("message") or (erreurs[0] or {}).get("title")
                elif isinstance(corps, dict) and corps.get("message"):
                    detail_erreur = corps["message"]
            except ValueError:
                detail_erreur = None
            log_to_file(
                "Echec de l'appel HTTP a data.gouv.fr",
                url=url,
                status_code=reponse.status_code,
                erreur=detail_erreur,
                suggestion="Réessayer apres 30 secondes",
            )
            return ResultatAppel(statut="echec_technique", status_code=reponse.status_code, erreur=detail_erreur)

        try:
            donnees = reponse.json()
        except ValueError as exc:
            return ResultatAppel(
                statut="echec_technique",
                status_code=reponse.status_code,
                erreur=f"Réponse non parsable en JSON : {exc}",
            )
        return ResultatAppel(statut="succes", status_code=reponse.status_code, donnees=donnees)

    return ResultatAppel(statut="echec_technique", erreur="Tentatives epuisees")


def _numero_page_depuis_url(url_next: Optional[str]) -> Optional[int]:
    """Extrait le numero de page d'une URL `next_page` de l'API v2."""
    from urllib.parse import urlparse, parse_qs

    if not url_next:
        return None
    numero = parse_qs(urlparse(url_next).query).get("page")
    return int(numero[0]) if numero else None


def rechercher_jeux_api(
    mots_cles: list,
    tri: str = "pertinence",
    fenetre_maj: str = "toutes",
    limite: int = 10,
    page: int = 1,
    **kwargs: Any,
) -> ResultatAppel:
    """Appelle l'endpoint de recherche /api/2/datasets/search/ (v2).

    Traduit les arguments normalisés vers les paramètres de l'API et
    valide la reponse contre le schema jsonschema de l'outil (T2.2) ;
    une reponse invalide produit un échec propre sans exception.
    Le tri `pertinence` est le tri implicite du moteur v2 (celui du site).
    Le parametre `fenetre_maj` est accepte pour compatibilite mais ignore :
    l'API v2 ne supporte pas `last_update_range` (HTTP 400, sondage S11.0) ;
    sa deprecation est tracee au niveau du coeur et du contrat (v1.3.0).
    Expose dans `donnees` la pagination normalisée `page_suivante`
    (numero entier extrait de l'URL `next_page` de la v2, null si absente).
    """
    from src.contracts.validation_api import valider_reponse_api

    TRIS_API = {"recent": "-last_update", "vues": "-views", "reutilisations": "-reuses"}

    params = {
        "q": " ".join(mots_cles),
        "page_size": limite,
        "page": page,
    }
    if tri != "pertinence":
        params["sort"] = TRIS_API[tri]

    resultat = appel_api("/datasets/search/", params=params, **kwargs)
    if not resultat.reussi:
        return resultat

    validation = valider_reponse_api("rechercher_jeux", resultat.donnees)
    if not validation.valide:
        return ResultatAppel(
            statut="echec_technique",
            status_code=resultat.status_code,
            erreur="Reponse de recherche invalide : " + " ; ".join(validation.erreurs),
        )

    resultat.donnees["page_suivante"] = _numero_page_depuis_url(resultat.donnees.get("next_page"))
    return resultat


def lister_ressources_api(id_jeu: str, **kwargs: Any) -> ResultatAppel:
    """Inventorie les ressources d'un jeu via l'API v2 (deux appels).

    En v2, `resources` n'est plus embarque dans le detail du jeu mais
    expose en sous-ressource paginee (sondage S11.0) :
    1. GET /api/2/datasets/{id} : metadonnees du jeu (404 -> `jeu_introuvable`) ;
    2. GET /api/2/datasets/{id}/resources/ : ressources paginees, boucle
       sur `next_page` jusqu'a epuisement (jamais au-dela : la v2 peut
       repondre 400 ou une liste vide au-dela du total).
    Plafond de securite `PLAFOND_PAGES_INVENTAIRE` (garde anti-boucle).
    Le payload retourne est reconstitue au format attendu par le coeur
    (dictionnaire du jeu avec liste `resources` plate), de sorte que la
    normalisation aval ne change pas (isolant HTTP, T11.3).
    """
    from src.contracts.validation_api import valider_reponse_api

    resultat = appel_api(f"/datasets/{id_jeu}/", **kwargs)
    if not resultat.reussi:
        return resultat

    jeu = resultat.donnees
    ressources: list = []
    numero_page: Optional[int] = 1
    pages = 0
    while numero_page is not None and pages < PLAFOND_PAGES_INVENTAIRE:
        resultat_ressources = appel_api(
            f"/datasets/{id_jeu}/resources/",
            params={"page": numero_page, "page_size": PAGE_SIZE_INVENTAIRE},
            **kwargs,
        )
        if not resultat_ressources.reussi:
            return resultat_ressources
        ressources.extend(resultat_ressources.donnees.get("data", []))
        numero_page = _numero_page_depuis_url(resultat_ressources.donnees.get("next_page"))
        pages += 1

    if numero_page is not None:
        return ResultatAppel(
            statut="echec_technique",
            status_code=resultat.status_code,
            erreur=f"Inventaire interrompu : plafond de {PLAFOND_PAGES_INVENTAIRE} pages atteint",
        )

    jeu["resources"] = ressources
    validation = valider_reponse_api("lister_ressources", jeu)
    if not validation.valide:
        return ResultatAppel(
            statut="echec_technique",
            status_code=resultat.status_code,
            erreur="Réponse d'inventaire invalide : " + " ; ".join(validation.erreurs),
        )
    return ResultatAppel(statut="succes", status_code=resultat.status_code, donnees=jeu)


def _base_tabulaire() -> str:
    return os.environ.get("TABULAR_API_URL", URL_BASE_TABULAIRE_DEFAUT)


def est_indexee_api_tabulaire(id_ressource: str, timeout: float = 5.0) -> bool:
    """Détecte si une ressource est indexée par l'API tabulaire.

    Simple ping GET /resources/{rid}/ : 200 = indexee, 404 ou echec =
    non indexee. Ne leve jamais d'exception ; en cas d'échec reseau, la
    ressource est reputée non indexée (comportement sur par defaut).
    """
    resultat = appel_api(
        f"/resources/{id_ressource}/",
        url_base=_base_tabulaire(),
        timeout=timeout,
        statut_404="ressource_non_indexee",
    )
    return resultat.reussi


def interroger_ressource_api(
    id_ressource: str,
    page: int = 1,
    taille_page: int = 20,
    filtre: Optional[Dict[str, Any]] = None,
    tri: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> ResultatAppel:
    """Appelle l'endpoint /resources/{rid}/data/ de l'API tabulaire.

    Traduit les arguments normalisés vers les paramètres de l'API
    (opérateurs de filtre, tri, pagination) et valide la réponse contre
    le schema jsonschema de l'outil ; un 404 produit le statut
    `ressource_non_indexee`.
    """
    from src.contracts.validation_api import valider_reponse_api

    OPERATEURS_API = {
        "exact": "exact",
        "contient": "contains",
        "inferieur": "less",
        "superieur": "greater",
        "strictement_inferieur": "strictly_less",
        "strictement_superieur": "strictly_greater",
    }

    params = {"page": page, "page_size": taille_page}
    if filtre:
        params[f"{filtre['colonne']}__{OPERATEURS_API[filtre.get('operateur', 'exact')]}"] = filtre["valeur"]
    if tri:
        params[f"{tri['colonne']}__sort"] = "asc" if tri["ordre"] == "croissant" else "desc"

    resultat = appel_api(
        f"/resources/{id_ressource}/data/",
        params=params,
        url_base=_base_tabulaire(),
        statut_404="ressource_non_indexee",
        **kwargs,
    )
    if not resultat.reussi:
        return resultat

    validation = valider_reponse_api("interroger_ressource", resultat.donnees)
    if not validation.valide:
        return ResultatAppel(
            statut="echec_technique",
            status_code=resultat.status_code,
            erreur="Réponse tabulaire invalide : " + " ; ".join(validation.erreurs),
        )
    return resultat


def profil_ressource_api(id_ressource: str, **kwargs: Any) -> ResultatAppel:
    """Appelle /resources/{rid}/profile/ (schema detecte, repli si data vide)."""
    return appel_api(
        f"/resources/{id_ressource}/profile/",
        url_base=_base_tabulaire(),
        statut_404="ressource_non_indexee",
        **kwargs,
    )


def telecharger_fichier(
    url: str,
    destination: Path,
    timeout: float = 30.0,
    nb_tentatives: int = 3,
) -> ResultatAppel:
    """Télécharge un fichier binaire en flux vers `destination`.

    Écriture atomique : le flux est écrit dans un fichier temporaire
    `<destination>.part` et renomme seulement après réussite complète ;
    aucun fichier partiel ne reste sur disque en cas d'échec (TI-07).
    Ne lève jamais d'exception : les échecs sont convertis en
    ResultatAppel de statut `echec_technique`.
    """
    temporaire = destination.with_name(destination.name + ".part")

    for tentative in range(1, nb_tentatives + 1):
        try:
            reponse = _SESSION.get(url, stream=True, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            log_to_file(
                "Echec du telechargement",
                url=url,
                tentative=tentative,
                erreur=str(exc),
            )
            if tentative < nb_tentatives:
                time.sleep(DELAIS_TENTATIVES[min(tentative - 1, len(DELAIS_TENTATIVES) - 1)])
                continue
            return ResultatAppel(statut="echec_technique", erreur=str(exc))

        if reponse.status_code == 404:
            reponse.close()
            return ResultatAppel(statut="jeu_introuvable", status_code=404)

        if reponse.status_code in STATUTS_TRANSITOIRES and tentative < nb_tentatives:
            reponse.close()
            log_to_file(
                "Statut transitoire, nouvelle tentative",
                url=url,
                status_code=reponse.status_code,
                tentative=tentative,
            )
            time.sleep(DELAIS_TENTATIVES[min(tentative - 1, len(DELAIS_TENTATIVES) - 1)])
            continue

        if reponse.status_code >= 400:
            reponse.close()
            log_to_file(
                "Refus du serveur d'origine",
                url=url,
                status_code=reponse.status_code,
            )
            return ResultatAppel(statut="echec_technique", status_code=reponse.status_code)

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(temporaire, "wb") as flux:
                for morceau in reponse.iter_content(chunk_size=8192):
                    flux.write(morceau)
        finally:
            reponse.close()

        temporaire.rename(destination)
        return ResultatAppel(statut="succes", status_code=200, donnees={})

    return ResultatAppel(statut="echec_technique", erreur="Tentatives epuisees")
