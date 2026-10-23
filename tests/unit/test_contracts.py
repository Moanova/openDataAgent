# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------
# Application  : openDataAgent
# Script       : test_contracts.py
# Version      : 1
# Date         : 12-10-2026
# Design       : TSC
# Build        : Mistral Vibe
# ---------------------------------------------------------------------
"""Tests unitaires pour les contrats Pydantic (src/contracts/).

Couvre :
- TU-25 a TU-28 : Chargement et validation des contrats JSON.
- TC-01 a TC-05 : Coherence entre contrats JSON, modeles Pydantic et documentation.
- Validation des modeles Pydantic (bornes, defauts, champs obligatoires).
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.contracts import (
    ClasseRessource,
    FenetreMaj,
    FiltreColonne,
    InterrogerRessourceInput,
    InterrogerRessourceOutput,
    JeuResume,
    ListerRessourcesInput,
    ListerRessourcesOutput,
    OperateurFiltre,
    OrdreTri,
    ReponseBase,
    RechercherJeuxInput,
    RechercherJeuxOutput,
    RessourceResume,
    StatutEnum,
    TelechargerBrutInput,
    ExtraireRessourceInput,
    ExtraireRessourceOutput,
    TelechargerBrutOutput,
    TriColonne,
    TriRecherche,
    ConsulterRegistreInput,
    ConsulterRegistreOutput,
    MotifRegistre,
    valider_coherence_contrat,
)

# Chemin vers les contrats JSON reels (relatif a la racine du projet)
CONTRATS_DIR = Path("contrats")
MANIFESTE_PATH = CONTRATS_DIR / "manifeste.json"

OUTILS_ATTENDUS = {"rechercher_jeux", "lister_ressources", "interroger_ressource", "telecharger_brut", "extraire_ressource", "consulter_registre"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def contrats_temp():
    """Cree une copie temporaire du repertoire contrats/ pour les tests de mutation."""
    temp_dir = Path(tempfile.mkdtemp(prefix="openDataAgent_contrats_"))
    temp_contrats = temp_dir / "contrats"
    shutil.copytree(CONTRATS_DIR, temp_contrats)
    yield temp_contrats
    shutil.rmtree(temp_dir, ignore_errors=True)


# ===========================================================================
# TU-25 : Chargement du manifeste reel
# ===========================================================================

class TestTU25_ChargementManifeste:
    """TU-25 : Le manifeste reel contient les six outils avec des declarations conformes."""

    def test_manifeste_existe(self):
        assert MANIFESTE_PATH.exists(), "Le fichier manifeste.json doit exister."

    def test_six_outils_declares(self):
        manifeste = json.loads(MANIFESTE_PATH.read_text(encoding="utf-8"))
        noms = {o["nom"] for o in manifeste["outils"]}
        assert noms == OUTILS_ATTENDUS

    def test_chaque_outil_a_fichier_et_version(self):
        manifeste = json.loads(MANIFESTE_PATH.read_text(encoding="utf-8"))
        for outil in manifeste["outils"]:
            assert "nom" in outil
            assert "fichier" in outil
            assert "version" in outil
            assert outil["fichier"] == f"{outil['nom']}.json"

    def test_rechercher_jeux_version_1_5_0_deprecation_fenetre(self):
        # T11.3 (E4) : le contrat migré en v1.3.0 (dépréciation fenetre_maj, mapping
        # derniere_maj) ; T7.1 (E4) : v1.4.0 ajoute le champ nb_tentatives ;
        # T7.7 (E3) : v1.5.0 ajoute le champ motif.
        manifeste = json.loads(MANIFESTE_PATH.read_text(encoding="utf-8"))
        outil = next(o for o in manifeste["outils"] if o["nom"] == "rechercher_jeux")
        assert outil["version"] == "1.5.0"

    def test_fichiers_contrats_existent(self):
        manifeste = json.loads(MANIFESTE_PATH.read_text(encoding="utf-8"))
        for outil in manifeste["outils"]:
            chemin = CONTRATS_DIR / outil["fichier"]
            assert chemin.exists(), f"Fichier contrat absent : {chemin}"

    def test_function_name_correspond_au_nom(self):
        manifeste = json.loads(MANIFESTE_PATH.read_text(encoding="utf-8"))
        for outil in manifeste["outils"]:
            contrat = json.loads((CONTRATS_DIR / outil["fichier"]).read_text(encoding="utf-8"))
            assert contrat["function"]["name"] == outil["nom"]


# ===========================================================================
# TU-26 : Nom divergent manifeste / function.name
# ===========================================================================

class TestTU26_NomDivergent:
    """TU-26 : Un manifeste avec un nom divergent du function.name provoque un echec."""

    def test_divergence_detectee(self, contrats_temp):
        # Modifier le manifeste pour declarer un nom qui ne correspond pas au function.name
        manifeste_path = contrats_temp / "manifeste.json"
        manifeste = json.loads(manifeste_path.read_text(encoding="utf-8"))
        manifeste["outils"][0]["nom"] = "nom_divergent"
        manifeste_path.write_text(json.dumps(manifeste, ensure_ascii=False), encoding="utf-8")

        # Verifier que le function.name du JSON correspondant ne correspond plus
        contrat = json.loads((contrats_temp / "rechercher_jeux.json").read_text(encoding="utf-8"))
        assert contrat["function"]["name"] == "rechercher_jeux"
        assert contrat["function"]["name"] != manifeste["outils"][0]["nom"]


# ===========================================================================
# TU-27 : Nom de fichier divergent du nom declare
# ===========================================================================

class TestTU27_FichierDivergent:
    """TU-27 : Un nom de fichier divergent du nom declare provoque un echec."""

    def test_fichier_renomme_detecte(self, contrats_temp):
        # Renommer le fichier JSON sans changer le manifeste
        ancien = contrats_temp / "rechercher_jeux.json"
        nouveau = contrats_temp / "autre_nom.json"
        ancien.rename(nouveau)

        manifeste = json.loads((contrats_temp / "manifeste.json").read_text(encoding="utf-8"))
        fichiers_declares = {o["fichier"] for o in manifeste["outils"]}
        fichiers_presents = {f.name for f in contrats_temp.glob("*.json") if f.name != "manifeste.json"}

        assert "rechercher_jeux.json" in fichiers_declares
        assert "rechercher_jeux.json" not in fichiers_presents
        assert "autre_nom.json" in fichiers_presents


# ===========================================================================
# TU-28 : Contrat JSON absent
# ===========================================================================

class TestTU28_ContratAbsent:
    """TU-28 : Un contrat JSON absent du chemin declare provoque un echec au demarrage."""

    def test_fichier_supprime_detecte(self, contrats_temp):
        (contrats_temp / "telecharger_brut.json").unlink()

        manifeste = json.loads((contrats_temp / "manifeste.json").read_text(encoding="utf-8"))
        fichiers_declares = {o["fichier"] for o in manifeste["outils"]}
        fichiers_presents = {f.name for f in contrats_temp.glob("*.json") if f.name != "manifeste.json"}

        assert "telecharger_brut.json" in fichiers_declares
        assert "telecharger_brut.json" not in fichiers_presents


# ===========================================================================
# TC-01 : Coherence triple manifeste / nom de fichier / function.name
# ===========================================================================

class TestTC01_CoherenceTriple:
    """TC-01 : Pour chaque outil, le manifeste, le nom de fichier et function.name concordent."""

    def test_coherence_totale(self):
        manifeste = json.loads(MANIFESTE_PATH.read_text(encoding="utf-8"))
        for outil in manifeste["outils"]:
            nom = outil["nom"]
            fichier = outil["fichier"]
            contrat = json.loads((CONTRATS_DIR / fichier).read_text(encoding="utf-8"))
            function_name = contrat["function"]["name"]

            assert nom == function_name, f"Manifeste '{nom}' != function.name '{function_name}'"
            assert fichier == f"{nom}.json", f"Fichier '{fichier}' devrait etre '{nom}.json'"
            assert (CONTRATS_DIR / fichier).stem == nom, f"Stem de '{fichier}' devrait etre '{nom}'"


# ===========================================================================
# TC-02 : Chaque argument du schema JSON existe dans le modele Pydantic
# ===========================================================================

class TestTC02_ArgumentsExistants:
    """TC-02 : Chaque argument du schema JSON existe dans la signature du modele Pydantic."""

    @pytest.mark.parametrize("nom_outil,modele_input", [
        ("rechercher_jeux", RechercherJeuxInput),
        ("lister_ressources", ListerRessourcesInput),
        ("interroger_ressource", InterrogerRessourceInput),
        ("telecharger_brut", TelechargerBrutInput),
        ("extraire_ressource", ExtraireRessourceInput),
        ("consulter_registre", ConsulterRegistreInput),
    ])
    def test_champs_json_presents_dans_pydantic(self, nom_outil, modele_input):
        contrat = json.loads((CONTRATS_DIR / f"{nom_outil}.json").read_text(encoding="utf-8"))
        champs_json = set(contrat["function"]["parameters"].get("properties", {}).keys())
        champs_pydantic = set(modele_input.model_fields.keys())

        for champ in champs_json:
            assert champ in champs_pydantic, (
                f"[{nom_outil}] Champ '{champ}' dans le JSON mais absent du modele Pydantic."
            )

    @pytest.mark.parametrize("nom_outil,modele_output", [
        ("rechercher_jeux", RechercherJeuxOutput),
        ("lister_ressources", ListerRessourcesOutput),
        ("interroger_ressource", InterrogerRessourceOutput),
        ("telecharger_brut", TelechargerBrutOutput),
        ("extraire_ressource", ExtraireRessourceOutput),
        ("consulter_registre", ConsulterRegistreOutput),
    ])
    def test_champs_sortie_json_presents_dans_pydantic(self, nom_outil, modele_output):
        contrat = json.loads((CONTRATS_DIR / f"{nom_outil}.json").read_text(encoding="utf-8"))
        donnees_json = contrat["function"]["returns"]["properties"]["donnees"]
        champs_json = set(donnees_json.get("properties", {}).keys())
        champs_pydantic = set(modele_output.model_fields.keys())

        for champ in champs_json:
            assert champ in champs_pydantic, (
                f"[{nom_outil}] Champ de sortie '{champ}' dans le JSON mais absent du modele Pydantic."
            )


# ===========================================================================
# TC-03 : Chaque argument obligatoire du schema JSON est requis dans Pydantic
# ===========================================================================

class TestTC03_ChampsObligatoires:
    """TC-03 : Chaque argument obligatoire du JSON est requis dans le modele Pydantic."""

    @pytest.mark.parametrize("nom_outil,modele_input", [
        ("rechercher_jeux", RechercherJeuxInput),
        ("lister_ressources", ListerRessourcesInput),
        ("interroger_ressource", InterrogerRessourceInput),
        ("telecharger_brut", TelechargerBrutInput),
        ("extraire_ressource", ExtraireRessourceInput),
        ("consulter_registre", ConsulterRegistreInput),
    ])
    def test_champs_obligatoires_requis(self, nom_outil, modele_input):
        contrat = json.loads((CONTRATS_DIR / f"{nom_outil}.json").read_text(encoding="utf-8"))
        required_json = set(contrat["function"]["parameters"].get("required", []))

        for champ in required_json:
            field_info = modele_input.model_fields.get(champ)
            assert field_info is not None, f"[{nom_outil}] Champ obligatoire '{champ}' absent du modele."
            assert field_info.is_required(), (
                f"[{nom_outil}] Champ '{champ}' obligatoire dans le JSON mais optionnel dans Pydantic."
            )


# ===========================================================================
# TC-04 : Descriptions non vides et enums non vides
# ===========================================================================

class TestTC04_DescriptionsEtEnums:
    """TC-04 : Chaque description est non vide ; chaque enum declare est non vide."""

    def test_descriptions_fonction_non_vides(self):
        for nom in OUTILS_ATTENDUS:
            contrat = json.loads((CONTRATS_DIR / f"{nom}.json").read_text(encoding="utf-8"))
            desc = contrat["function"].get("description", "")
            assert desc.strip(), f"[{nom}] Description de la fonction vide."

    def test_descriptions_parametres_non_vides(self):
        for nom in OUTILS_ATTENDUS:
            contrat = json.loads((CONTRATS_DIR / f"{nom}.json").read_text(encoding="utf-8"))
            for champ, spec in contrat["function"]["parameters"].get("properties", {}).items():
                desc = spec.get("description", "")
                assert desc.strip(), f"[{nom}.{champ}] Description du parametre vide."

    def test_enums_parametres_non_vides(self):
        for nom in OUTILS_ATTENDUS:
            contrat = json.loads((CONTRATS_DIR / f"{nom}.json").read_text(encoding="utf-8"))
            for champ, spec in contrat["function"]["parameters"].get("properties", {}).items():
                if "enum" in spec:
                    assert len(spec["enum"]) > 0, f"[{nom}.{champ}] Enum declare mais vide."

    def test_enums_pydantic_correspondent(self):
        """Les enums Pydantic ont exactement les memes valeurs que les enums JSON."""
        # rechercher_jeux
        assert {e.value for e in TriRecherche} == {"pertinence", "recent", "vues", "reutilisations"}
        assert {e.value for e in FenetreMaj} == {"toutes", "30_jours", "12_mois", "3_ans"}
        # lister_ressources
        assert {e.value for e in ClasseRessource} == {
            "fichier_tabulaire", "fichier_autre_format", "page_web", "api_distante", "indetermine",
        }
        # interroger_ressource
        assert {e.value for e in OperateurFiltre} == {
            "exact", "contient", "inferieur", "superieur",
            "strictement_inferieur", "strictement_superieur",
        }
        assert {e.value for e in OrdreTri} == {"croissant", "decroissant"}


# ===========================================================================
# TC-05 : Codes de statut dans la documentation vs StatutEnum
# ===========================================================================

class TestTC05_CodesStatut:
    """TC-05 : Chaque code de statut mentionne dans la documentation existe dans StatutEnum."""

    def test_statut_enum_complet(self):
        valeurs = {e.value for e in StatutEnum}
        attendues = {
            "succes", "jeu_introuvable", "ressource_introuvable",
            "ressource_non_indexee", "licence_refusee", "echec_technique",
            "erreur_parametres",
        }
        assert valeurs == attendues

    def test_statut_enum_dans_contrat_global(self):
        """Les codes de statut du contrat_global.md sont tous dans StatutEnum."""
        doc_path = Path("docs/architecture/contrat_global.md")
        if doc_path.exists():
            contenu = doc_path.read_text(encoding="utf-8")
            valeurs_statut = {e.value for e in StatutEnum}
            for code in valeurs_statut:
                assert code in contenu, f"Code '{code}' absent de contrat_global.md"


# ===========================================================================
# Validation des modeles Pydantic (bornes, defauts, champs obligatoires)
# ===========================================================================

class TestValidationModeles:
    """Tests de validation des modeles Pydantic eux-memes."""

    # --- RechercherJeuxInput ---

    def test_rechercher_jeux_input_valide(self):
        # Réf. tests/plan_tests.md : TU-13 (limite omise -> valeur par défaut 10)
        inp = RechercherJeuxInput(mots_cles=["dette", "publique"])
        assert inp.mots_cles == ["dette", "publique"]
        assert inp.tri == TriRecherche.PERTINENCE
        assert inp.fenetre_maj == FenetreMaj.TOUTES
        assert inp.limite == 10

    def test_rechercher_jeux_input_mots_cles_obligatoires(self):
        # Réf. tests/plan_tests.md : TU-12 (mots_cles vide -> erreur_parametres)
        with pytest.raises(ValidationError):
            RechercherJeuxInput()

    def test_rechercher_jeux_input_mots_cles_non_vide(self):
        # Réf. tests/plan_tests.md : TU-12 (mots_cles vide -> erreur_parametres)
        with pytest.raises(ValidationError):
            RechercherJeuxInput(mots_cles=[])

    def test_rechercher_jeux_input_limite_bornees(self):
        # Réf. tests/plan_tests.md : TU-14 (limite au-delà du maximum -> corrigée, pas d'exception)
        with pytest.raises(ValidationError):
            RechercherJeuxInput(mots_cles=["test"], limite=0)
        with pytest.raises(ValidationError):
            RechercherJeuxInput(mots_cles=["test"], limite=21)
        # Valeurs limites acceptees
        RechercherJeuxInput(mots_cles=["test"], limite=1)
        RechercherJeuxInput(mots_cles=["test"], limite=20)

    def test_rechercher_jeux_input_tri_invalide(self):
        # Réf. tests/plan_tests.md : TU-16 (tri invalide -> erreur_parametres)
        with pytest.raises(ValidationError):
            RechercherJeuxInput(mots_cles=["test"], tri="invalide")

    # --- ListerRessourcesInput ---

    def test_lister_ressources_input_valide(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        inp = ListerRessourcesInput(id_jeu="67660551c8588734a16a6a60")
        assert inp.id_jeu == "67660551c8588734a16a6a60"

    def test_lister_ressources_input_id_jeu_obligatoire(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        with pytest.raises(ValidationError):
            ListerRessourcesInput()

    # --- InterrogerRessourceInput ---

    def test_interroger_ressource_input_valide(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        inp = InterrogerRessourceInput(id_ressource="abc123")
        assert inp.id_ressource == "abc123"
        assert inp.page == 1
        assert inp.taille_page == 20
        assert inp.filtre is None
        assert inp.tri is None

    def test_interroger_ressource_input_avec_filtre_et_tri(self):
        # Réf. tests/plan_tests.md : TU-15 (tri et fenetre_maj valides -> traduction correcte)
        inp = InterrogerRessourceInput(
            id_ressource="abc123",
            page=2,
            taille_page=50,
            filtre=FiltreColonne(colonne="annee", valeur="2024", operateur=OperateurFiltre.EXACT),
            tri=TriColonne(colonne="annee", ordre=OrdreTri.DECROISSANT),
        )
        assert inp.page == 2
        assert inp.taille_page == 50
        assert inp.filtre.colonne == "annee"
        assert inp.tri.ordre == OrdreTri.DECROISSANT

    def test_interroger_ressource_input_taille_page_bornees(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        with pytest.raises(ValidationError):
            InterrogerRessourceInput(id_ressource="abc", taille_page=0)
        with pytest.raises(ValidationError):
            InterrogerRessourceInput(id_ressource="abc", taille_page=51)
        InterrogerRessourceInput(id_ressource="abc", taille_page=50)

    def test_interroger_ressource_input_page_bornee(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        with pytest.raises(ValidationError):
            InterrogerRessourceInput(id_ressource="abc", page=0)

    # --- TelechargerBrutInput ---

    def test_telecharger_brut_input_valide(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        inp = TelechargerBrutInput(id_ressource="71ff1335")
        assert inp.id_ressource == "71ff1335"

    def test_telecharger_brut_input_id_ressource_obligatoire(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        with pytest.raises(ValidationError):
            TelechargerBrutInput()

    # --- Modeles de sortie ---

    def test_jeu_resume_valide(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        jeu = JeuResume(
            id="abc",
            titre="Titre",
            organisation="Insee",
            licence="lov2",
            derniere_maj="2026-01-15",
            nb_ressources=2,
            url="https://...",
        )
        assert jeu.id == "abc"
        assert jeu.nb_ressources == 2

    def test_ressource_resume_valide(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        res = RessourceResume(
            id="res1",
            titre="Fichier CSV",
            format="csv",
            classe=ClasseRessource.FICHIER_TABULAIRE,
            api_tabulaire=True,
            heberge_sur_plateforme=False,
            url="https://...",
        )
        assert res.classe == ClasseRessource.FICHIER_TABULAIRE
        assert res.taille_octets is None

    def test_reponse_base_defaut(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        rep = ReponseBase(statut=StatutEnum.SUCCES)
        assert rep.statut == StatutEnum.SUCCES
        assert rep.message == ""
        assert rep.donnees == {}

    def test_rechercher_jeux_output_valide(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        out = RechercherJeuxOutput(
            total_trouves=39,
            jeux=[],
            exclus_licence=3,
            page_courante=1,
            page_suivante=None,
        )
        assert out.total_trouves == 39
        assert out.exclus_licence == 3
        assert out.page_courante == 1
        assert out.page_suivante is None

    def test_lister_ressources_output_indetermination_defaut(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        out = ListerRessourcesOutput(ressources=[])
        assert out.indetermination == []

    def test_interroger_ressource_output_recommandation_optionnelle(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        out = InterrogerRessourceOutput(
            total_lignes=74,
            colonnes=["a", "b"],
            lignes=[{"a": 1}],
            page=1,
        )
        assert out.recommandation is None

    def test_telecharger_brut_output_suggestion_optionnelle(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        out = TelechargerBrutOutput(
            chemin_local="donnees/fichier.csv",
            format="csv",
            licence="lov2",
        )
        assert out.suggestion is None


# ===========================================================================
# Test de la fonction valider_coherence_contrat
# ===========================================================================

class TestValiderCoherenceContrat:
    """Tests de la fonction de validation de coherence JSON <-> Pydantic."""

    @pytest.mark.parametrize("nom_outil", sorted(OUTILS_ATTENDUS))
    def test_coherence_parfaite(self, nom_outil):
        """Aucune divergence sur les contrats reels."""
        # Réf. tests/plan_tests.md : TC-02 (introspection arguments JSON / signature Python)
        divergences = valider_coherence_contrat(nom_outil)
        assert divergences == [], f"Divergences pour '{nom_outil}' : {divergences}"

    def test_outil_inconnu(self):
        # Test annexe : sans référence directe dans tests/plan_tests.md
        with pytest.raises(ValueError, match="Outil inconnu"):
            valider_coherence_contrat("outil_inexistant")

    def test_contrat_json_absent(self, contrats_temp):
        # Réf. tests/plan_tests.md : TU-28 (contrat JSON absent -> échec au démarrage)
        (contrats_temp / "telecharger_brut.json").unlink()
        with pytest.raises(ValueError, match="Contrat JSON absent"):
            valider_coherence_contrat("telecharger_brut", repertoire_contrats=contrats_temp)
