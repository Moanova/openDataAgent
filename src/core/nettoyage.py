# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : nettoyage.py
# Version      : 1
# Date         : 22-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Nettoyage automatique des anciennes exécutions (T7.2).

Cinq familles de traces s'accumulent par id_execution :
- data/raw/<id_execution>/          (fichiers acquis + manifeste)
- data/processed/<id_execution>/    (fichiers normalisés, T10.1)
- data/executions/<id_execution>/    (inventaire persistant, T10.2)
- conversations/<id_execution>/     (journal de conversation, T11.1)
- logs/openDataAgent_<id_execution>.log  (logs structurés, fichiers plats)

Le critère de rétention est l'âge, lu dans le préfixe date de l'id
(AAAAMMJJ_HHMMSS, hash court optionnel). Les registres globaux
(data/registre_sources.json, data/registre_acceptations.json) et tout nom non
reconnu sont conservés (fail-safe). L'exécution courante est toujours
protégée. Un échec de suppression est consigné, jamais bloquant.
"""
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.utils.journalisation import log_to_file

AGE_DEFAUT_JOURS = 30

RACINES_SOUS_DOSSIERS = (
    Path("data") / "raw",
    Path("data") / "processed",
    Path("data") / "executions",
    Path("conversations"),
)
RACINE_LOGS = Path("logs")
PREFIXE_LOG = "openDataAgent_"
SUFFIXE_LOG = ".log"

_MOTIF_ID = re.compile(r"^(\d{8}_\d{6})(?:_|$)")


def _date_depuis_id_execution(id_execution: str) -> Optional[datetime]:
    """Extrait la date de création d'un id_execution (préfixe AAAAMMJJ_HHMMSS).

    Retourne None si le nom ne correspond pas au format attendu : l'appelant
    conserve alors la trace (fail-safe, aucune suppression sur doute).
    """
    correspondance = _MOTIF_ID.match(id_execution)
    if not correspondance:
        return None
    try:
        return datetime.strptime(correspondance.group(1), "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def _taille_octets(chemin: Path) -> int:
    """Taille totale d'un fichier ou d'un répertoire (récursif)."""
    if chemin.is_file():
        return chemin.stat().st_size
    if chemin.is_dir():
        return sum(f.stat().st_size for f in chemin.rglob("*") if f.is_file())
    return 0


def _executions_sur_racine(racine: Path) -> list:
    """Id d'exécutions présents sous une racine de sous-dossiers.

    Seuls les répertoires sont considérés ; les fichiers plats (ex. registres)
    sont ignorés et donc conservés.
    """
    if not racine.is_dir():
        return []
    return sorted(e.name for e in racine.iterdir() if e.is_dir())


def _executions_sur_logs(racine_logs: Path) -> list:
    """Id d'exécutions présents dans les logs (fichiers openDataAgent_<id>.log)."""
    if not racine_logs.is_dir():
        return []
    ids = []
    for fichier in racine_logs.iterdir():
        if not fichier.is_file():
            continue
        nom = fichier.name
        if nom.startswith(PREFIXE_LOG) and nom.endswith(SUFFIXE_LOG):
            ids.append(nom[len(PREFIXE_LOG):-len(SUFFIXE_LOG)])
    return sorted(set(ids))


def executions_a_supprimer(
    age_jours: int,
    id_execution_courante: Optional[str] = None,
    racines: tuple = RACINES_SOUS_DOSSIERS,
    racine_logs: Path = RACINE_LOGS,
    maintenant: Optional[datetime] = None,
) -> list:
    """Sélectionne les exécutions antérieures au seuil d'âge (T7.2).

    Une exécution est supprimable si sa date de création est antérieure à
    `maintenant - age_jours` jours, si son nom est reconnu, et si ce n'est
    pas l'exécution courante (toujours protégée). Les racines inexistantes
    sont ignorées.
    """
    maintenant = maintenant or datetime.now()
    seuil = maintenant - timedelta(days=age_jours)
    ids = set(_executions_sur_logs(racine_logs))
    for racine in racines:
        ids.update(_executions_sur_racine(racine))
    a_supprimer = []
    for id_execution in sorted(ids):
        if id_execution_courante is not None and id_execution == id_execution_courante:
            continue
        date_creation = _date_depuis_id_execution(id_execution)
        if date_creation is None:
            continue
        if date_creation < seuil:
            a_supprimer.append(id_execution)
    return a_supprimer


def nettoyer_anciennes_executions(
    age_jours: int = AGE_DEFAUT_JOURS,
    id_execution_courante: Optional[str] = None,
    simulation: bool = False,
    racines: tuple = RACINES_SOUS_DOSSIERS,
    racine_logs: Path = RACINE_LOGS,
    maintenant: Optional[datetime] = None,
) -> dict:
    """Supprime (ou simule la suppression de) les anciennes exécutions.

    Retourne un bilan normalisé {statut, message, donnees}. En simulation,
    rien n'est supprimé : le bilan indique ce qui le serait. Un échec de
    suppression sur un dossier est consigné dans donnees.erreurs et n'interrompt
    pas le nettoyage des autres (jamais bloquant, cf. manifeste T10.8).
    """
    if age_jours < 1:
        return {
            "statut": "erreur_parametres",
            "message": f"L'âge doit être d'au moins 1 jour (reçu : {age_jours}).",
            "donnees": {},
        }

    a_supprimer = executions_a_supprimer(
        age_jours,
        id_execution_courante=id_execution_courante,
        racines=racines,
        racine_logs=racine_logs,
        maintenant=maintenant,
    )
    supprimes = []
    conserves = []
    octets_liberes = 0
    erreurs = []

    for id_execution in a_supprimer:
        chemins = [racine / id_execution for racine in racines]
        log = racine_logs / f"{PREFIXE_LOG}{id_execution}{SUFFIXE_LOG}"
        if log.is_file():
            chemins.append(log)
        taille = sum(_taille_octets(c) for c in chemins if c.exists())
        if not simulation:
            for chemin in chemins:
                if not chemin.exists():
                    continue
                try:
                    if chemin.is_dir():
                        shutil.rmtree(chemin)
                    else:
                        chemin.unlink()
                except OSError as erreur:
                    # Trace fichier uniquement : jamais de log console, pour
                    # garder la sortie `--json` de la CLI propre.
                    log_to_file(
                        "nettoyage_suppression_impossible",
                        id_execution=id_execution,
                        chemin=str(chemin),
                        erreur=str(erreur),
                    )
                    erreurs.append({"id_execution": id_execution, "chemin": str(chemin), "erreur": str(erreur)})
                    continue
        if not any(e["id_execution"] == id_execution for e in erreurs):
            supprimes.append(id_execution)
            octets_liberes += taille
            log_to_file(
                "nettoyage_execution_supprimee" if not simulation else "nettoyage_execution_supprimable",
                id_execution=id_execution,
                simulation=simulation,
                octets=taille,
            )

    ids = set(_executions_sur_logs(racine_logs))
    for racine in racines:
        ids.update(_executions_sur_racine(racine))
    conserves = sorted(ids - set(supprimes))

    action = "serait supprimée" if simulation else "supprimée"
    message = (
        f"{len(supprimes)} exécution(s) {action}(s), {len(conserves)} conservée(s), "
        f"{octets_liberes} octet(s) libéré(s)"
        + (" (simulation)" if simulation else "")
        + (f", {len(erreurs)} erreur(s)" if erreurs else "")
    )
    return {
        "statut": "succes",
        "message": message,
        "donnees": {
            "age_jours": age_jours,
            "simulation": simulation,
            "supprimes": supprimes,
            "conserves": conserves,
            "octets_liberes": octets_liberes,
            "erreurs": erreurs,
        },
    }
