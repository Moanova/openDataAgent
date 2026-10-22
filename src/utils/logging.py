# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : logging.py
# Version      : 1
# Date         : 12-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""
Module de configuration du logging pour openDataAgent.
Utilise `structlog` pour produire des logs structurés au format JSON.
"""

import structlog
import logging
from typing import Optional, Dict, Any, TextIO
import sys
from datetime import datetime
import json
import os

# Configuration par défaut pour les métadonnées dynamiques
_default_context: Dict[str, Any] = {
    "id_execution": None,
}

# Fichier de logs pour le JSON
_log_file: Optional[TextIO] = None


def configure_logging(id_execution: Optional[str] = None, silencieux: bool = False) -> None:
    """
    Configure `structlog` pour produire des logs JSON.

    Args:
        id_execution (Optional[str]): Identifiant unique pour tracer une exécution.
            Si non fourni, un horodatage est généré.
        silencieux (bool): Si True (T13.2, option --quiet), aucun handler console :
            les logs [info]/[error] ne sortent plus, le fichier de logs reste écrit.
    """
    global _log_file

    if id_execution is None:
        id_execution = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Mettre à jour le contexte par défaut
    _default_context["id_execution"] = id_execution

    # Créer le dossier de logs s'il n'existe pas
    os.makedirs("logs", exist_ok=True)

    # Fermer l'éventuel fichier de logs précédent avant d'en ouvrir un
    # nouveau : configure_logging est appelé à chaque commande (et plusieurs
    # fois dans les tests) ; sans fermeture, l'ancien descripteur fuirait et
    # un fichier fermé laisserait log_to_file écrire dans le vide.
    if _log_file is not None:
        try:
            _log_file.close()
        except OSError:
            pass
    # Ouvrir le fichier de logs en mode append
    _log_file = open(f"logs/openDataAgent_{id_execution}.log", "a", encoding="utf-8")
    
    # Configuration des processors pour structlog
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        _injecter_contexte_global,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Configuration pour la console (format clé-valeur)
    console_processors = [
        *shared_processors,
        structlog.dev.ConsoleRenderer(),
    ]
    
    # Configuration pour le fichier (format JSON)
    file_processors = [
        *shared_processors,
        structlog.processors.JSONRenderer(),
    ]
    
    # Configuration de structlog pour la console
    structlog.configure(
        processors=console_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configuration du logger racine pour la console. Les handlers existants
    # sont retirés d'abord : configure_logging peut être appelé plusieurs fois
    # dans un même processus (tests), basicConfig seul serait alors sans effet.
    racine = logging.getLogger()
    for handler in list(racine.handlers):
        racine.removeHandler(handler)
        # Fermer proprement le handler retiré : sous pytest, son flux (capture)
        # est fermé en fin de test ; un handler orphelin lèverait alors
        # ValueError("I/O operation on closed file") au Logging error.
        try:
            handler.close()
        except Exception:
            pass
    if silencieux:
        # T13.2 (--quiet) : NullHandler absorbe tout (y compris le lastResort
        # de Python, qui écrirait sinon les WARNING+ sur stderr).
        racine.addHandler(logging.NullHandler())
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        racine.addHandler(handler)
        racine.setLevel(logging.INFO)


def _injecter_contexte_global(logger, method_name, event_dict):
    """Processor structlog : injecte le contexte global dans chaque évènement.

    Le contexte doit refléter la valeur courante (notamment id_execution
    defini par configure_logging), pas un instantané pris a l'import.
    """
    for cle, valeur in _default_context.items():
        event_dict.setdefault(cle, valeur)
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Retourne un logger configuré pour le module spécifié.
    
    Args:
        name (str): Nom du module (ex : "openDataAgent.core.search").
    
    Returns:
        structlog.stdlib.BoundLogger: Logger configuré.
    """
    logger = structlog.get_logger(name)
    return logger


def bind_context(**kwargs: Any) -> None:
    """
    Met à jour le contexte global pour tous les loggers.
    
    Args:
        **kwargs: Paires clé-valeur à ajouter au contexte (ex : id_jeu="12345").
    """
    _default_context.update(kwargs)


def log_to_file(event: str, **kwargs: Any) -> None:
    """
    Écrit un log directement dans le fichier JSON.
    
    Args:
        event (str): Message de log.
        **kwargs: Champs supplémentaires à logger.
    """
    global _log_file
    if _log_file is None or _log_file.closed:
        return

    # Créer le log structuré
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        **_default_context,
        **kwargs,
    }

    # Écrire dans le fichier
    try:
        _log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        _log_file.flush()
    except (OSError, ValueError):
        # Fichier fermé en dehors (tests, fin de processus) : le log fichier
        # ne doit jamais faire échouer l'appelant.
        pass