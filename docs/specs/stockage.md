# Stockage des fichiers téléchargés

## 1. Objet
Ce document décrit l'organisation du **stockage des fichiers téléchargés** depuis **data.gouv.fr**, ainsi que la gestion des conflits de noms.

## 2. Arborescence
Les fichiers sont stockés dans le répertoire `data/` avec la structure suivante :
```
openDataAgent/
├── data/
│   ├── raw/                  # Fichiers bruts téléchargés
│   │   ├── <id_execution>/   # Identifiant unique par exécution (ex : 20261010_143022_a1b2c3)
│   │   │   ├── <id_ressource>_<nom_fichier_original>.<extension>
│   │   │   └── ...
│   │   └── ...
│   ├── processed/            # Fichiers normalisés (T10.1)
│   └── registry.json         # Registre des sources inaccessibles
```

## 3. Détails
### 3.1. Identifiant d'exécution (`<id_execution>`)
- **Format** : `<date>_<heure>_<hash_court>`.
  - Exemple : `20261010_143022_a1b2c3`.
- **Génération** :
  - Date et heure au format `YYYYMMDD_HHMMSS`.
  - Hash court (6 caractères) basé sur un timestamp ou un UUID.
- **Utilité** :
  - Évite les conflits entre exécutions.
  - Permet de retrouver tous les fichiers d'une session.

### 3.2. Nom des fichiers téléchargés
- **Format** : `<id_ressource>_<nom_fichier_original>.<extension>`.
  - Exemple : `71ff1335_budget-fr-indicateurs.csv`.
- **Règles** :
  - `<id_ressource>` : Identifiant de la ressource (ex : `71ff1335`).
  - `<nom_fichier_original>` : Nom du fichier d'origine (nettoyé pour éviter les caractères spéciaux).
  - `<extension>` : Extension du fichier (ex : `csv`, `zip`, `geojson`).

### 3.3. Exemple concret
```
openDataAgent/
├── data/
│   ├── raw/
│   │   ├── 20261010_143022_a1b2c3/
│   │   │   ├── 71ff1335_budget-fr-indicateurs.csv
│   │   │   ├── 8a2b4c6d_donnees-geographiques.geojson
│   │   │   └── 9e8f7g2h_archive.zip
│   │   └── 20261010_154530_b4c5d6/
│   │       └── 3d4e5f6a_donnees-climatiques.csv
│   └── registry.json
```

## 4. Gestion des conflits
- **Conflits entre exécutions** : Résolus par l'`id_execution`.
- **Conflits dans une même exécution** :
  - Si deux fichiers ont le même `<nom_fichier_original>.<extension>`, un suffixe numérique est ajouté.
  - Exemple : `71ff1335_budget-fr-indicateurs_1.csv`, `71ff1335_budget-fr-indicateurs_2.csv`.

## 5. Persistance
- **Registre** : `data/registry.json` est persistant entre les exécutions (idem `data/registre_acceptations.json`, hors périmètre d'une exécution).
- **Fichiers téléchargés** : Conservés jusqu'à suppression manuelle ou automatisée (nettoyage des anciennes exécutions, §8).
- **Fichiers normalisés** (`data/processed/`, T10.1) : même règle de conservation (5ᵉ racine de nettoyage, §8).

## 6. Améliorations futures
- *(aucune en attente sur ce document)*


## 7. Manifeste d'acquisition (T10.8, 19/10/2026)

Chaque exécution ayant acquis des données porte un manifeste :

```
data/raw/<id_execution>/manifeste_acquisitions.json
```

**En-tête** : `id_execution`, `demande` (prompt `demander` ou rappel de commande manuelle), `genere_le` (T13.3 : sans accent, convention contrat_global).

**Entrées** (une par acquisition réussie, dans l'ordre chronologique) : `fichier`, `voie` (`telechargement` | `extraction`), `id_ressource`, `titre_ressource`, `id_jeu`, `titre_jeu`, `organisation`, `url_jeu`, `licence`, `licence_conditionnelle`, `mention_attribution`, `horodatage` ; plus `url_source` (voie 2) ou `tronque`/`nb_lignes` (voie 1).

**Invariants** :
- écrit au cœur (`telecharger_brut`, `extraire_ressource`) : les deux modes (manuel et agentique) produisent le même manifeste ;
- écriture atomique (`.part` puis renommage), additive (aucune entrée altérée), anti-doublon sur `fichier` ;
- un échec d'écriture produit un warning, jamais un échec de l'acquisition ;
- `lister_fichiers` exclut le manifeste (ce n'est pas une donnée acquise) ; `lister_acquisitions` (storage) et la commande CLI `acquisitions <id_execution>` le lisent.

**Rôle** : source de vérité « acquisition » côté disque — la partie 2 (via T10.1, normalisation B7) consomme ce manifeste pour relier chaque fichier à son jeu, sa licence et sa mention d'attribution, sans recroiser inventaire persistant et journal de conversation.


## 7.5 Normalisation B7 (T10.1, 23/10/2026)

La commande `normaliser` (CLI uniquement, pas d'outil agentique) produit, pour chaque exécution de `data/raw/`, un dossier `data/processed/<id_execution>/` contenant **les fichiers finaux destinés à la partie 2** (analyse, visualisation) :

```
python -m src.main normaliser [id_execution] [--simulation] [--json]
```

- **Sans argument** : normalise toutes les exécutions de `data/raw/` (l'exécution courante est exclue).
- **Avec `id_execution`** : normalise une seule exécution.

**Règles de normalisation** (par fichier de `data/raw/<id_execution>/`, hors manifeste) :

| Fichier source | Action | Résultat dans `processed/` |
|---|---|---|
| CSV déjà conforme (UTF-8, virgule, sans BOM) | copié tel quel | même nom (voie 1 : pas de retraitement) |
| CSV non conforme (encodage, séparateur, BOM) | ré-écrit | même nom, UTF-8 virgule sans BOM |
| Tableur (`.xlsx`, `.xls`, `.ods`) | converti | un CSV par feuille : `<fichier>__<feuille>.csv` |
| Autre (zip, geojson, json, shp, pdf, parquet, tsv, inconnu…) | copié tel quel | même nom (brut non normalisable) |

**Invariants** :
- `data/processed/<id_execution>/` ne contient **que** des fichiers finaux (jamais le manifeste d'acquisition, jamais de fichier intermédiaire) ;
- **re-lançable sans doublon** : un fichier déjà produit (même nom) est ignoré, jamais écrasé ni dupliqué ;
- en `--simulation`, le bilan est produit mais **rien n'est écrit** ;
- un échec unitaire (lecture tableur impossible, bibliothèque absente) produit un **avertissement** dans le bilan et les logs, jamais un échec de la commande ; le fichier est alors copié tel quel ou ignoré ;
- les bibliothèques de lecture (`openpyxl`, `xlrd`, `odfpy`, `charset-normalizer`) sont des dépendances optionnelles au runtime : si absentes, les fichiers concernés sont copiés tels quels avec avertissement.

**Métadonnées de schéma** : reportées en version 2 (décision concepteur du 23/10/2026). La partie 2 s'appuie sur le manifeste d'acquisition (§7) pour relier chaque fichier à son jeu, sa licence et sa mention d'attribution.

## 8. Nettoyage des anciennes exécutions (T7.2, 22/10/2026)

Cinq familles de traces s'accumulent par `id_execution` :

```
data/raw/<id_execution>/                    # fichiers acquis + manifeste
data/processed/<id_execution>/              # fichiers normalisés (T10.1)
data/executions/<id_execution>/             # inventaire persistant (T10.2)
conversations/<id_execution>/              # journal de conversation (T11.1)
logs/openDataAgent_<id_execution>.log       # logs structurés (fichiers plats)
```

**Commande** : `python -m src.main nettoyer [--age-jours N] [--simulation] [--json] [--id-execution <id>]` — supprime les exécutions dont l'âge dépasse le seuil (défaut 30 jours), sur les cinq racines, et retourne un bilan normalisé `{statut, message, donnees}` (`supprimes`, `conserves`, `octets_liberes`, `erreurs`, `simulation`).

**Règles** :
- l'âge est lu dans le préfixe date de l'`id_execution` (`AAAAMMJJ_HHMMSS`, hash optionnel) ; un nom non reconnu est **conservé** (fail-safe) ;
- l'exécution courante (`--id-execution`) est **toujours protégée**, même ancienne ;
- les registres globaux (`data/registry.json`, `data/registre_acceptations.json`) et tout fichier hors périmètre d'une exécution sont conservés ;
- un échec de suppression est consigné dans `donnees.erreurs`, **jamais bloquant** (philosophie du manifeste T10.8) ;
- en `--simulation`, rien n'est supprimé : le bilan indique ce qui le serait.

**Automatique** : un hook au callback Typer exécute le nettoyage avant chaque commande si `NETTOYAGE_AUTO=1` dans l'environnement (désactivé par défaut — pas de suppression de données sans consentement explicite). La commande `nettoyer` elle-même ne déclenche pas le hook.
