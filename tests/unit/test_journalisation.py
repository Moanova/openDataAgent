# -*- coding: utf-8 -*-
"""
Tests unitaires pour src/utils/logging.py.
Vérifie le format JSON, les métadonnées, l'écriture dans le fichier et les niveaux de log.
"""

import json
import os
import pytest
from unittest.mock import patch, mock_open
from src.utils.journalisation import configure_logging, get_logger, log_to_file, bind_context


@pytest.fixture
def cleanup_logs():
    """Supprime les fichiers de logs créés pendant les tests."""
    yield
    # Fermer le fichier de logs s'il est ouvert
    from src.utils.journalisation import _log_file
    if _log_file is not None:
        _log_file.close()
        _log_file = None
    
    # Nettoyage après les tests
    log_files = [f for f in os.listdir("logs") if f.startswith("openDataAgent_test_")]
    for log_file in log_files:
        try:
            os.remove(os.path.join("logs", log_file))
        except PermissionError:
            pass  # Ignorer si le fichier est encore verrouillé


def test_log_format_json(cleanup_logs):
    """TU-29 : Vérifie que les logs sont au format JSON avec les champs obligatoires."""
    configure_logging(id_execution="test_json")
    log_to_file("Test event", key="value")
    
    # Vérifier que le fichier de logs existe et contient un JSON valide
    log_file_path = "logs/openDataAgent_test_json.log"
    assert os.path.exists(log_file_path), "Le fichier de logs n'a pas été créé"
    
    with open(log_file_path, "r", encoding="utf-8") as f:
        log_entry = json.loads(f.readline())
        assert log_entry["event"] == "Test event"
        assert log_entry["key"] == "value"
        assert "timestamp" in log_entry
        assert log_entry["id_execution"] == "test_json"


def test_bind_context():
    """TU-30 : Vérifie que les métadonnées ajoutées via bind_context apparaissent dans les logs."""
    configure_logging(id_execution="test_context")
    bind_context(id_jeu="12345", custom_key="custom_value")
    
    log_to_file("Test context")
    
    # Vérifier que les métadonnées sont bien dans le log
    log_file_path = "logs/openDataAgent_test_context.log"
    with open(log_file_path, "r", encoding="utf-8") as f:
        log_entry = json.loads(f.readline())
        assert log_entry["id_execution"] == "test_context"
        assert log_entry["id_jeu"] == "12345"
        assert log_entry["custom_key"] == "custom_value"


def test_log_to_file_creation():
    """TU-31 : Vérifie que le fichier de logs est créé et contient les logs attendus."""
    configure_logging(id_execution="test_file_creation")
    log_to_file("Test file creation", test_key="test_value")
    
    # Vérifier que le fichier existe et contient le log
    log_file_path = "logs/openDataAgent_test_file_creation.log"
    assert os.path.exists(log_file_path), "Le fichier de logs n'a pas été créé"
    
    with open(log_file_path, "r", encoding="utf-8") as f:
        log_entry = json.loads(f.readline())
        assert log_entry["event"] == "Test file creation"
        assert log_entry["test_key"] == "test_value"


def test_log_levels():
    """TU-32 : Vérifie que les logs sont écrits correctement (niveaux simulés)."""
    configure_logging(id_execution="test_log_levels")
    
    # Simuler un log
    log_to_file("Test info level")
    
    # Vérifier que le log est bien écrit
    log_file_path = "logs/openDataAgent_test_log_levels.log"
    with open(log_file_path, "r", encoding="utf-8") as f:
        log_entry = json.loads(f.readline())
        assert log_entry["event"] == "Test info level"


@patch("src.utils.journalisation._log_file")
def test_log_to_file_error_handling(mock_log_file):
    # Test annexe : sans référence directe dans tests/plan_tests.md
    """Teste la gestion des erreurs lors de l'écriture dans le fichier de logs."""
    # Simuler un fichier ouvert
    mock_file = mock_open().return_value
    mock_log_file.return_value = mock_file
    
    configure_logging(id_execution="test_error")
    
    # Simuler une erreur d'écriture
    mock_file.write.side_effect = IOError("Erreur d'écriture")
    
    # Vérifier que l'erreur est silencieusement gérée (pas d'exception)
    try:
        log_to_file("Test error handling")
    except IOError:
        pytest.fail("log_to_file a levé une exception alors qu'il devrait la gérer silencieusement")

# ---------------------------------------------------------------------------
# T13.2 — Option --quiet (22/10/2026) : TU-109, TU-110
# ---------------------------------------------------------------------------

def test_quiet_supprime_console_mais_pas_fichier(capsys, cleanup_logs):
    # TU-109 : silencieux=True -> aucun handler console, le fichier de logs
    # reste écrit. Vrai log structlog (pas seulement log_to_file).
    configure_logging(id_execution="test_quiet", silencieux=True)
    logger = get_logger("openDataAgent.test.quiet")
    logger.info("evenement console attendu absent")
    logger.error("erreur console attendue absente")
    log_to_file("evenement fichier attendu present")

    sortie = capsys.readouterr()
    assert "evenement console attendu absent" not in sortie.out
    assert "erreur console attendue absente" not in sortie.err
    assert "[info" not in sortie.out and "[error" not in sortie.err

    with open("logs/openDataAgent_test_quiet.log", encoding="utf-8") as f:
        contenu = f.read()
    assert "evenement fichier attendu present" in contenu


def test_non_quiet_affiche_console(capsys, cleanup_logs):
    # TU-110 : silencieux=False (défaut) -> comportement inchangé, les logs
    # structlog passent bien sur la console.
    configure_logging(id_execution="test_non_quiet", silencieux=False)
    logger = get_logger("openDataAgent.test.nonquiet")
    logger.info("evenement console attendu present")

    sortie = capsys.readouterr()
    assert "evenement console attendu present" in sortie.out
