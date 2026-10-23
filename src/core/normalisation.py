# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : normalisation.py
# Version      : 1
# Date         : 23-10-2026
# Design       : Mistral Vibe
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Normalisation B7 des fichiers acquis vers data/processed/ (T10.1).

Maillon B7 -> P du schema de conception : prepare la mise a disposition
des donnees vers la partie 2 (analyse, visualisation). Pour chaque
execution de data/raw/<id_execution>/, produit data/processed/<id_execution>/
contenant :

- les fichiers normalises en CSV UTF-8 (virgule, sans BOM) :
  - CSV source non conforme (encodage non UTF-8, separateur non virgule,
    BOM) : re-ecrit proprement ;
  - tableurs xlsx / xls / ods : un CSV par feuille, nomme
    <fichier>__<feuille>.csv (les noms de feuille sont nettoyes) ;
- les fichiers bruts non normalisables (zip, geojson, shp, pdf, parquet,
  json, tsv, inconnu...) : copies tels quels.

Le CSV pivot de la voie 1 (extraire_ressource, deja UTF-8 virgule) est
detecte conforme et copie tel quel : aucun retraitement.

Regles :
- data/processed/ ne contient que des fichiers finaux (jamais le
  manifeste d'acquisition, jamais de fichier intermediaire) ;
- re-lancable et sans doublon : si data/processed/<id_execution>/
  contient deja un fichier produit (meme nom), il est conserve tel quel
  (jamais ecrase) et le fichier est ignore lors de ce passage ;
- jamais bloquant : un fichier unitaire en echec est copie tel quel
  avec un avertissement consigne dans le bilan et les logs ;
- sans exposition agentique (commande CLI uniquement, T10.1) ;
- les bibliotheques de lecture (openpyxl, xlrd, odfpy,
  charset-normalizer) sont optionnelles : si absentes, les tableurs et
  CSV non conformes sont copies tels quels avec avertissement.
"""
from __future__ import annotations

import csv
import io
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logging import get_logger, log_to_file
from src.utils.storage import lister_fichiers, nettoyer_nom_fichier

logger = get_logger("openDataAgent.core.normalisation")

RACINE_BRUT = Path("data") / "raw"
RACINE_TRAITE = Path("data") / "processed"

EXTENSIONS_TABLEURS = frozenset({".xlsx", ".xls", ".ods"})
EXTENSION_CSV = ".csv"

ENCODAGES_CANDIDATS = ("utf-8", "utf-8-sig", "cp1252", "iso-8859-1")
SEPARATEURS_CANDIDATS = (";", ",", "\t", "|")


def _detecter_encodage(octets: bytes) -> str:
    """Detecte l'encodage d'un contenu textuel (defensif).

    Tente UTF-8 d'abord (avec et sans BOM), puis charset-normalizer si
    disponible, puis cp1252 / iso-8859-1 en dernier recours. Retourne
    toujours un encodage utilisable.
    """
    for encodage in ("utf-8-sig", "utf-8"):
        try:
            octets.decode(encodage)
            return encodage
        except UnicodeDecodeError:
            continue
    try:
        from charset_normalizer import from_bytes

        meilleure = from_bytes(octets).best()
        if meilleure is not None and meilleure.encoding:
            candidat = meilleure.encoding
            try:
                octets.decode(candidat)
                return candidat
            except (UnicodeDecodeError, LookupError):
                pass
    except ImportError:
        pass
    return "cp1252"


def _est_csv_conforme(chemin: Path) -> bool:
    """Determine si un CSV est deja normalise (UTF-8 sans BOM, virgule).

    Lit le fichier en binaire : un BOM UTF-8 ou un octet invalide en
    UTF-8 => non conforme. Le separateur est verifie sur un echantillon
    (csv.Sniffer, limite aux separateurs candidats).
    """
    try:
        octets = chemin.read_bytes()
    except OSError:
        return False
    if octets.startswith(b"\xef\xbb\xbf"):
        return False
    try:
        texte = octets.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if not texte.strip():
        return True
    try:
        dialecte = csv.Sniffer().sniff(texte[:4096], delimiters="".join(SEPARATEURS_CANDIDATS))
    except csv.Error:
        return "," in texte.splitlines()[0]
    return dialecte.delimiter == ","


def _normaliser_csv(source: Path, destination: Path) -> Dict[str, Any]:
    """Re-ecrit un CSV source en CSV UTF-8 virgule sans BOM.

    Detection de l'encodage et du separateur, re-ecriture avec
    csv.writer (separateur virgule, quoting minimal, fin de ligne \\n).
    Retourne un resultat {statut, encodage, separateur}.
    """
    octets = source.read_bytes()
    encodage = _detecter_encodage(octets)
    texte = octets.decode(encodage)
    try:
        dialecte = csv.Sniffer().sniff(texte[:4096], delimiters="".join(SEPARATEURS_CANDIDATS))
        separateur = dialecte.delimiter
    except csv.Error:
        premiere = texte.splitlines()[0] if texte.splitlines() else ""
        separateur = max(SEPARATEURS_CANDIDATS, key=lambda s: premiere.count(s)) if premiere else ","
    lignes = [ligne for ligne in csv.reader(io.StringIO(texte), delimiter=separateur) if ligne]
    with destination.open("w", encoding="utf-8", newline="") as flux:
        ecrivain = csv.writer(flux, lineterminator="\n")
        ecrivain.writerows(lignes)
    return {"statut": "succes", "encodage": encodage, "separateur": separateur}


def _lire_feuilles_tableur(source: Path) -> List[Tuple[str, List[List[Any]]]]:
    """Lit un tableur (xlsx/xls/ods) : liste de (nom_feuille, lignes).

    leve ImportError si la bibliotheque de lecture est absente.
    """
    suffixe = source.suffix.lower()
    if suffixe == ".xlsx":
        import openpyxl

        classeur = openpyxl.load_workbook(source, read_only=True, data_only=True)
        try:
            return [
                (feuille.title, [list(ligne) for ligne in feuille.iter_rows(values_only=True)])
                for feuille in classeur.worksheets
            ]
        finally:
            classeur.close()
    if suffixe == ".xls":
        import xlrd

        classeur = xlrd.open_workbook(source)
        feuilles = []
        for feuille in classeur.sheets():
            lignes = []
            for numero in range(feuille.nrows):
                lignes.append([feuille.cell_value(numero, c) for c in range(feuille.ncols)])
            feuilles.append((feuille.name, lignes))
        return feuilles
    if suffixe == ".ods":
        from odf.opendocument import load
        from odf.table import Table, TableRow, TableCell
        from odf import text as odf_text

        document = load(str(source))
        feuilles = []
        for tableau in document.spreadsheet.getElementsByType(Table):
            nom = tableau.getAttribute("name") or "feuille"
            lignes = []
            for rangee in tableau.getElementsByType(TableRow):
                repetition = int(rangee.getAttribute("numberrowsrepeated") or 1)
                valeurs = []
                for cellule in rangee.getElementsByType(TableCell):
                    col_repetition = int(cellule.getAttribute("numbercolumnsrepeated") or 1)
                    type_valeur = cellule.getAttribute("valuetype")
                    if type_valeur == "float":
                        brut = cellule.getAttribute("value")
                        valeur: Any = float(brut) if brut is not None else ""
                    elif type_valeur in ("percentage", "currency"):
                        brut = cellule.getAttribute("value")
                        valeur = float(brut) if brut is not None else ""
                    elif type_valeur == "boolean":
                        valeur = cellule.getAttribute("booleanvalue") == "true"
                    elif type_valeur == "date":
                        valeur = cellule.getAttribute("datevalue") or ""
                    else:
                        paragraphes = cellule.getElementsByType(odf_text.P)
                        valeur = "\n".join(str(p) for p in paragraphes)
                    valeurs.extend([valeur] * min(col_repetition, 1024))
                lignes.extend([list(valeurs)] * min(repetition, 1024))
            feuilles.append((nom, lignes))
        return feuilles
    raise ValueError(f"Extension de tableur non geree : {suffixe}")


def _ecrire_csv_feuille(destination: Path, lignes: List[List[Any]]) -> None:
    """Ecrit une feuille en CSV UTF-8 virgule (valeurs telles quelles)."""
    with destination.open("w", encoding="utf-8", newline="") as flux:
        ecrivain = csv.writer(flux, lineterminator="\n")
        for ligne in lignes:
            ecrivain.writerow(["" if v is None else v for v in ligne])


def _normaliser_tableur(source: Path, dossier_destination: Path) -> List[Dict[str, Any]]:
    """Convertit un tableur en un CSV par feuille dans le dossier destination.

    Nommage : <nom_source>__<feuille_nettoyee>.csv. Retourne la liste des
    fichiers produits (un dict par CSV : {fichier, feuille, lignes}).
    """
    feuilles = _lire_feuilles_tableur(source)
    produits = []
    ignores = []
    for nom_feuille, lignes in feuilles:
        nom_feuille_nettoye = nettoyer_nom_fichier(nom_feuille) or "feuille"
        nom_fichier = f"{source.stem}__{nom_feuille_nettoye}.csv"
        destination = _destination_libre(dossier_destination, nom_fichier)
        if destination is None:
            ignores.append(nom_fichier)
            continue
        _ecrire_csv_feuille(destination, lignes)
        produits.append(
            {
                "fichier": destination.name,
                "feuille": nom_feuille,
                "lignes": len(lignes),
            }
        )
        logger.info(
            "Feuille exportee en CSV",
            source=source.name,
            feuille=nom_feuille,
            fichier=destination.name,
            lignes=len(lignes),
        )
        log_to_file(
            "Feuille exportee en CSV",
            source=source.name,
            feuille=nom_feuille,
            fichier=destination.name,
            lignes=len(lignes),
        )
    for nom_fichier in ignores:
        logger.info(
            "Feuille deja presente, ignoree",
            source=source.name,
            fichier=nom_fichier,
        )
    return produits, ignores


def _destination_libre(dossier: Path, nom: str) -> Optional[Path]:
    """Chemin de destination, ou None si le fichier est deja produit.

    Re-lancable sans doublon : si le nom existe deja dans le dossier
    (produit lors d'un passage precedent), le fichier est ignore
    (retour None) ; il n'est ni ecrase ni duplique sous un suffixe.
    """
    candidat = dossier / nom
    if candidat.exists():
        return None
    return candidat


def _traiter_fichier(
    source: Path,
    dossier_destination: Path,
) -> Dict[str, Any]:
    """Traite un fichier brut : normalise, copie tel quel, ou ignore.

    Retourne un dict {fichier, action, detail} avec action parmi :
    - 'ignore' : le fichier produit existe deja (re-lancement sans doublon) ;
    - 'conforme' : CSV deja normalise, copie tel quel ;
    - 'normalise' : CSV re-ecrit (encodage/separateur corriges) ;
    - 'convertis' : tableur -> un CSV par feuille (detail = liste des CSV) ;
    - 'copie' : brut non normalisable, copie tel quel ;
    - 'copie_avertissement' : echec de normalisation, copie tel quel.
    """
    suffixe = source.suffix.lower()
    if suffixe == EXTENSION_CSV:
        destination = _destination_libre(dossier_destination, source.name)
        if destination is None:
            return {"fichier": source.name, "action": "ignore", "detail": "deja produit"}
        if _est_csv_conforme(source):
            shutil.copyfile(source, destination)
            logger.info(
                "CSV conforme copie tel quel",
                source=source.name,
                fichier=destination.name,
            )
            log_to_file(
                "CSV conforme copie tel quel",
                source=source.name,
                fichier=destination.name,
            )
            return {"fichier": destination.name, "action": "conforme", "detail": "CSV deja conforme"}
        resultat = _normaliser_csv(source, destination)
        return {
            "fichier": destination.name,
            "action": "normalise",
            "detail": f"re-ecrit (encodage {resultat['encodage']}, separateur {resultat['separateur']!r})",
        }
    if suffixe in EXTENSIONS_TABLEURS:
        try:
            produits, ignores = _normaliser_tableur(source, dossier_destination)
        except ImportError:
            destination = _destination_libre(dossier_destination, source.name)
            if destination is None:
                return {"fichier": source.name, "action": "ignore", "detail": "deja produit"}
            shutil.copyfile(source, destination)
            return {
                "fichier": destination.name,
                "action": "copie_avertissement",
                "detail": "bibliotheque de lecture absente, copie tel quel",
            }
        except Exception as erreur:  # noqa: BLE001 - jamais bloquant
            destination = _destination_libre(dossier_destination, source.name)
            if destination is None:
                return {"fichier": source.name, "action": "ignore", "detail": "deja produit"}
            shutil.copyfile(source, destination)
            return {
                "fichier": destination.name,
                "action": "copie_avertissement",
                "detail": f"lecture impossible ({erreur}), copie tel quel",
            }
        if not produits:
            return {
                "fichier": source.name,
                "action": "ignore",
                "detail": f"feuilles deja produites ({', '.join(ignores)})",
            }
        return {
            "fichier": source.name,
            "action": "convertis",
            "detail": produits,
        }
    destination = _destination_libre(dossier_destination, source.name)
    if destination is None:
        return {"fichier": source.name, "action": "ignore", "detail": "deja produit"}
    shutil.copyfile(source, destination)
    return {"fichier": destination.name, "action": "copie", "detail": "brut non normalisable"}


def _executions_brutes(racine: Path) -> List[str]:
    """Liste les id_execution presents sous data/raw/ (dossiers uniquement)."""
    if not racine.is_dir():
        return []
    return sorted(e.name for e in racine.iterdir() if e.is_dir())


def normaliser_execution(
    id_execution: str,
    racine_brut: Path = RACINE_BRUT,
    racine_traite: Path = RACINE_TRAITE,
    simulation: bool = False,
) -> Dict[str, Any]:
    """Normalise tous les fichiers d'une execution (T10.1, maillon B7).

    Lit data/raw/<id_execution>/ (hors manifeste d'acquisition) et
    produit data/processed/<id_execution>/. Retourne un bilan normalise
    {statut, message, donnees} : fichiers traites, actions, avertissements.
    En simulation, rien n'est ecrit.
    """
    dossier_source = racine_brut / nettoyer_nom_fichier(id_execution)
    if not dossier_source.is_dir():
        return {
            "statut": "erreur_parametres",
            "message": f"Aucune execution '{id_execution}' sous {racine_brut}.",
            "donnees": {"id_execution": id_execution},
        }
    fichiers = lister_fichiers(id_execution, racine=racine_brut)
    if not fichiers:
        return {
            "statut": "succes",
            "message": f"Aucun fichier a normaliser pour l'execution '{id_execution}'.",
            "donnees": {"id_execution": id_execution, "fichiers": [], "avertissements": []},
        }
    dossier_destination = racine_traite / nettoyer_nom_fichier(id_execution)
    resultats = []
    avertissements = []
    if simulation:
        # Dossier jetable : le traitement s'execute reellement (pour produire
        # un bilan fidele) mais rien n'est ecrit sous data/processed/.
        conteneur = tempfile.TemporaryDirectory(prefix="normalisation_simulation_")
        dossier_ecriture = Path(conteneur.name)
    else:
        conteneur = None
        dossier_ecriture = dossier_destination
        dossier_ecriture.mkdir(parents=True, exist_ok=True)
    try:
        for source in fichiers:
            try:
                resultat = _traiter_fichier(source, dossier_ecriture)
            except Exception as erreur:  # noqa: BLE001 - jamais bloquant
                resultat = {
                    "fichier": source.name,
                    "action": "copie_avertissement",
                    "detail": f"erreur inattendue ({erreur}), non traite",
                }
            if resultat["action"] == "copie_avertissement":
                avertissements.append(resultat)
                logger.warning(
                    "Normalisation en echec, fichier non traite",
                    fichier=source.name,
                    id_execution=id_execution,
                    detail=resultat["detail"],
                )
                log_to_file(
                    "Normalisation en echec",
                    fichier=source.name,
                    id_execution=id_execution,
                    detail=resultat["detail"],
                )
            resultats.append(resultat)
    finally:
        if conteneur is not None:
            conteneur.cleanup()
    nb_fichiers = len(resultats)
    message = (
        f"Execution '{id_execution}' : {nb_fichiers} fichier(s) traite(s)"
        + (f", {len(avertissements)} avertissement(s)" if avertissements else "")
        + (" (simulation)" if simulation else "")
        + "."
    )
    return {
        "statut": "succes",
        "message": message,
        "donnees": {
            "id_execution": id_execution,
            "simulation": simulation,
            "fichiers": resultats,
            "avertissements": avertissements,
        },
    }


def normaliser_toutes_executions(
    racine_brut: Path = RACINE_BRUT,
    racine_traite: Path = RACINE_TRAITE,
    simulation: bool = False,
    id_execution_courante: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalise toutes les executions de data/raw/ (commande sans argument).

    L'execution courante (passee en parametre) est exclue : elle est
    encore en cours d'ecriture. Retourne un bilan normalise agrege.
    """
    executions = _executions_brutes(racine_brut)
    if id_execution_courante is not None:
        executions = [e for e in executions if e != id_execution_courante]
    bilans = []
    for id_execution in executions:
        bilan = normaliser_execution(
            id_execution,
            racine_brut=racine_brut,
            racine_traite=racine_traite,
            simulation=simulation,
        )
        bilans.append(bilan)
    traites = [b for b in bilans if b["statut"] == "succes" and b["donnees"]["fichiers"]]
    erreurs = [b for b in bilans if b["statut"] != "succes"]
    avertissements = [a for b in bilans for a in b["donnees"].get("avertissements", [])]
    nb_fichiers = sum(len(b["donnees"].get("fichiers", [])) for b in bilans)
    message = (
        f"{len(traites)} execution(s) normalisee(s), {nb_fichiers} fichier(s) traite(s)"
        + (f", {len(avertissements)} avertissement(s)" if avertissements else "")
        + (f", {len(erreurs)} execution(s) en erreur" if erreurs else "")
        + (" (simulation)" if simulation else "")
        + "."
    )
    return {
        "statut": "succes",
        "message": message,
        "donnees": {
            "simulation": simulation,
            "executions": [b["donnees"]["id_execution"] for b in traites],
            "nb_fichiers": nb_fichiers,
            "avertissements": avertissements,
            "erreurs": [b["donnees"]["id_execution"] for b in erreurs],
        },
    }
