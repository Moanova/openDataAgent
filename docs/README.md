# openDataAgent

**openDataAgent** est un projet d'acquisition de données depuis [data.gouv.fr](https://www.data.gouv.fr/) via des agents Mistral. Il permet de :
- Rechercher des jeux de données par mots-clés.
- Lister les ressources (fichiers) associées à un jeu.
- Interroger les ressources indexées par l'API tabulaire.
- Télécharger les fichiers bruts pour les ressources non indexées.
- Consigner les sources inaccessibles dans un registre.

---

## 📁 Structure du projet
```
openDataAgent/
├── .env                         # Variables d'environnement
├── requirements.txt             # Dépendances Python
├── venv/                        # Environnement virtuel (ignoré par Git)
│
├── docs/                        # Documentation globale
│   ├── README.md                # Présentation du projet (ce fichier)
│   ├── projet/
│   │   └── kanban.md            # Kanban des tâches
│
├── specs/                       # Spécifications techniques
│   ├── contracts/               # Contrats JSON des outils
│   │   ├── rechercher_jeux.json
│   │   ├── lister_ressources.json
│   │   ├── interroger_ressource.json
│   │   ├── telecharger_brut.json
│   │   └── manifeste.json
│   │
│   ├── architecture.md          # Architecture technique
│   ├── registre.md              # Spécifications du registre
│   └── stockage.md              # Spécifications du stockage
│
├── design/                      # Conception et décisions
│   ├── conception.mmd           # Diagramme des flux
│   └── decisions_conception.md  # Journal des décisions
│
│
├── src/                         # Code source
│   ├── __init__.py
│   ├── main.py                  # CLI (Typer)
│   ├── agent/                   # Partie agentique Mistral (agent, boucle, journal, outils)
│   ├── contracts/               # Schémas Pydantic
│   ├── core/                    # Logique métier
│   └── utils/                   # Fonctions utilitaires
│
├── tests/                       # Tests
│   ├── unit/                    # Tests unitaires
│   ├── integration/             # Tests d'intégration
│   └── plan_tests.md            # Plan de tests
│
└── data/                        # Stockage des fichiers téléchargés
    ├── raw/                     # Fichiers bruts
    ├── processed/               # Fichiers normalisés
    └── registry.json            # Registre des sources inaccessibles
```

---

## 🚀 Installation
### Prérequis
- Python 3.9+
- Un compte Mistral (pour les agents)

### Étapes
1. **Cloner le projet** :
   ```bash
   git clone <url_du_projet>
   cd openDataAgent
   ```

2. **Créer et activer un environnement virtuel** :
   - **Windows** :
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - **macOS/Linux** :
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer les variables d'environnement** :
   - Copier `.env.example` en `.env` et remplir les valeurs nécessaires.
     ```ini
     DATA_GOUV_API_URL=https://www.data.gouv.fr/api/1
     LOG_LEVEL=INFO
     ```

---

## ▶️ Utilisation
Le projet s'utilise via une **CLI** (Command Line Interface) avec Typer. Voici les commandes disponibles :

| Commande   | Description                                          | Exemple                                      |
|------------|------------------------------------------------------|----------------------------------------------|
| `search`   | Recherche des jeux de données par mots-clés.         | `python -m src.main search "dette publique"` |
| `list`     | Liste les ressources d'un jeu.                       | `python -m src.main list <id_jeu>`           |
| `query`    | Interroge une ressource indexée par l'API tabulaire. | `python -m src.main query <id_ressource>`    |
| `extract`  | Extrait une ressource indexée vers un CSV local (voie 1 matérialisée). | `python -m src.main extract <id_ressource>` |
| `download` | Télécharge une ressource non indexée.                | `python -m src.main download <id_ressource>` |
| `chat`     | Conversation agentique : un prompt libre, l'agent conduit le flux complet. | `python -m src.main chat "cherche les données de la dette publique"` |

Les cinq premières commandes (`search`, `list`, `query`, `extract`, `download`) sont le mode manuel : l'utilisateur joue lui-même les étapes de sélection. La commande `chat` est le mode agentique : l'agent Mistral conduit le flux de bout en bout (reformulation, sélection, acquisition) en s'appuyant sur les mêmes fonctions.

### ⌨️ Options des commandes

**`search` — recherche de jeux** :
| Option | Description | Défaut |
|---|---|---|
| `mots_cles` (arguments) | Mots-clés de la recherche (logique ET). | Obligatoire |
| `--tri` | `pertinence`, `recent`, `vues`, `reutilisations`. | `pertinence` |
| `--fenetre-maj` | `toutes`, `30_jours`, `12_mois`, `3_ans`. | `toutes` |
| `--limite` | Nombre max de jeux retournés (1-20). | 10 |
| `--page` | Page de résultats demandée. | 1 |
| `--id-execution` | Identifiant d'exécution (traces, logs). | Horodatage auto |
| `--json` | Sortie JSON brute. | Désactivé |

**`list` — inventaire des ressources d'un jeu** :
| Option | Description | Défaut |
|---|---|---|
| `id_jeu` (argument) | Identifiant du jeu, issu de `search`. | Obligatoire |
| `--id-execution`, `--json` | Comme ci-dessus. | — |

**`query` — interrogation d'une ressource indexée (voie 1)** :
| Option | Description | Défaut |
|---|---|---|
| `id_ressource` (argument) | Identifiant de la ressource, issu de `list`. | Obligatoire |
| `--page` | Page demandée. | 1 |
| `--taille-page` | Lignes par page (1-50). | 20 |
| `--filtre-colonne`, `--filtre-valeur` | Filtre sur une colonne (les deux requis ensemble). | — |
| `--filtre-operateur` | `exact`, `contient`, `inferieur`, `superieur`, `strictement_inferieur`, `strictement_superieur`. | `exact` |
| `--tri-colonne` | Colonne du tri. | — |
| `--tri-ordre` | `croissant`, `decroissant`. | `croissant` |
| `--apercu` | Nombre maximum de lignes affichées dans l'aperçu (0 pour tout afficher). | 5 |
| `--id-execution`, `--json` | Comme ci-dessus. | — |

**`extract` — extraction paginée d'une ressource indexée (voie 1)** :
| Option | Description | Défaut |
|---|---|---|
| `id_ressource` (argument) | Identifiant de la ressource indexée, issu de `list`. | Obligatoire |
| `--taille-page` | Lignes demandées par page à l'API tabulaire. | 100 |
| `--plafond-lignes` | Nombre maximum de lignes extraites ; au-delà, succès partiel avec troncature signalée. | `PLAFOND_EXTRACTION` (10000) |
| `--id-execution`, `--json` | Comme ci-dessus. | — |

La pagination est conduite par la commande : le CSV complet (en-tête + toutes les lignes, ou jusqu'au plafond) est écrit dans `data/raw/<id_execution>/`. En mode `chat`, l'agent dispose du même pouvoir via le 5ᵉ outil `extraire_ressource` — la frontière est : `query` explore sans écrire, `extract` acquiert sur disque.

**`download` — téléchargement brut (voie 2)** :
| Option | Description | Défaut |
|---|---|---|
| `id_ressource` (argument) | Identifiant de la ressource, issu de `list`. | Obligatoire |
| `--id-execution`, `--json` | Comme ci-dessus. | — |

### 🔗 Chaînage des commandes : inventaire persistant par `id_execution`

Chaque commande de la CLI manuelle est un **processus indépendant**, mais l'inventaire des ressources **survit aux commandes** grâce à `--id-execution` : la commande `list` persiste l'inventaire dans `data/executions/<id_execution>/inventaire.json`, et toute commande suivante portant le même identifiant le recharge automatiquement.

```bash
python -m src.main list <id_jeu> --id-execution dette-publique
python -m src.main download <id_ressource> --id-execution dette-publique   # fonctionne : ressource vue par le list
python -m src.main query <id_ressource> --id-execution dette-publique --page 2
```

- **Sans `--id-execution`** : un identifiant est généré automatiquement (horodatage) et **affiché dans la sortie de chaque commande** (`id_execution : ...`) — relevez-le pour le reprendre sur la commande suivante et retrouver vos artefacts (logs, inventaire).
- **Avec `--id-execution`** : vous choisissez le nom du flux ; utile pour conduire un travail de fond nommé, isoler deux investigations parallèles (deux ids = deux inventaires isolés) ou reprendre un flux interrompu (même id, seul l'inventaire est conservé).
- **Enrichissement cumulatif** : plusieurs `list` sur des jeux différents sous le même id enrichissent le même inventaire ; les entrées existantes ne sont jamais écrasées.
- **Mode `chat` inchangé** : l'agent tient l'inventaire en mémoire dans son processus unique, l'inventaire n'y est pas persisté.
- Un `download` sans inventaire correspondant (id jamais utilisé par un `list`) répond toujours `ressource_introuvable` (« identifiant jamais vu par le flux courant ni par une exécution antérieure réactivée sous le même id ») — convention 1 du contrat global.

### 💬 Commande `chat` (mode agentique)

**Usage** :

```bash
python -m src.main chat "<demande en français>" [options]
```

**Paramètres** :

| Paramètre | Description | Défaut |
|---|---|---|
| `prompt` (argument) | La demande en français, entre guillemets ou en mots séparés. Obligatoire. | — |
| `--plafond` | Nombre maximum d'invocations d'outils par conversation. | 10 |
| `--id-execution` | Identifiant d'exécution (traces et nom du journal). | Horodatage auto |
| `--json` | Sortie JSON brute (réponse normalisée + journal + statut de destruction). | Désactivé |

**Variables d'environnement** (fichier `.env`) :

| Variable | Rôle | Défaut |
|---|---|---|
| `MISTRAL_API_KEY` | Clé API Mistral — **obligatoire** pour `chat`. | — |
| `MISTRAL_MODELE` | Modèle de l'agent éphémère. | `mistral-small-latest` |
| `PLAFOND_INVOCATIONS` | Plafond si `--plafond` n'est pas fourni. | 10 |
| `MISTRAL_AGENT_ID` | (Optionnel) Agent console persistant à réutiliser — uniquement s'il est strictement conforme au dépôt (modèle, prompt, outils), sinon agent éphémère créé. | Non défini |

**Déroulement d'une exécution** :

1. Création d'un agent éphémère sur la console Mistral (visible pendant l'exécution, supprimé à la fin).
2. L'agent conduit la conversation : il reformule la demande, appelle les outils (`rechercher_jeux`, `lister_ressources`, `interroger_ressource`, `telecharger_brut`), exécute le code local qui dialogue avec data.gouv.fr.
3. Destruction systématique de l'agent (même en cas d'erreur).
4. Affichage : statut, nombre d'invocations/plafond, synthèse de l'agent (données acquises avec chemins et licences, sources retenues, sources écartées avec motifs, limites).

**Sortie** (exemple) :

```
statut : succes
invocations d'outils : 4/10

Rapport :
- Données acquises : data/raw/20261014_142233/fichier.csv (licence lov2)
- Jeu retenu : Comptes des administrations publiques (Insee) — données à jour, organisation officielle
- Sources écartées : 2 jeux (licence incompatible)
- Limites : aucune

journal de conversation : conversations/20261014_142233/conversation.jsonl
```

Le journal JSONL (`conversations/<id_execution>/conversation.jsonl`) conserve la conversation complète : contexte (modèle, prompt, date), messages, raisonnements de l'agent, invocations d'outils avec arguments et résultats. Il sert à l'audit et aux tests agentiques (propriétés TA).

**Codes de sortie** : `0` succès ; `1` échec technique (clé absente, API injoignable, erreur en cours de conversation) ; `2` paramètres invalides.

---

## 📜 Politique de licence

Le projet n'acquiert que des jeux de données dont la licence est **compatible avec une réutilisation libre** (contrat global : règle déterministe, aucune décision agentique). Un jeu exclu n'est jamais retourné, mais il est consigné au registre des sources inaccessibles avec le motif `licence_incompatible`.

### Licences acceptées et leurs obligations

| Licence | Nom complet | Attribution | Partage à l'identique | Usage commercial | Notes |
|---|---|---|---|---|---|
| `lov2` | Licence Ouverte / Open Licence 2.0 (Etalab) | ✅ Obligatoire | ❌ Non | ✅ Autorisé | Licence de référence des administrations françaises (décret 2017-638) ; compatible OGL, ODC-BY, CC-BY 2.0 |
| `fr-lo` | Licence Ouverte (variante d'écriture data.gouv.fr) | ✅ Obligatoire | ❌ Non | ✅ Autorisé | Même licence que `lov2` |
| `odc-odbl` | Open Database License (ODbL) | ✅ Obligatoire | ✅ **Obligatoire** (clause 4.4 : toute base dérivée est redistribuée sous ODbL) | ✅ Autorisé | Licence copyleft des bases de données (OpenStreetMap, collectivités) ; **contrainte forte sur les produits dérivés** |
| `odc-by` | Open Data Commons Attribution | ✅ Obligatoire | ❌ Non | ✅ Autorisé | Équivalent ODbL sans clause de partage à l'identique : permissive pour les produits dérivés |
| `odc-pddl` | Open Data Commons Public Domain Dedication and License | ⛔ Facultative | ❌ Non | ✅ Autorisé | Dédicace au domaine public des bases de données : aucune obligation légale |
| `cc-by` | Creative Commons Attribution 4.0 | ✅ Obligatoire | ❌ Non | ✅ Autorisé | Permissive, la plus courante des CC |
| `cc-by-sa` | CC Attribution - ShareAlike 4.0 | ✅ Obligatoire | ✅ **Obligatoire** (les adaptations sont licenciées sous conditions identiques) | ✅ Autorisé | Copyleft ; homologuée en France pour certains périmètres (ex. SHOM) |
| `cc-zero` | CC0 1.0 (domaine public) | ⚪ Facultative (recommandée par courtoisie) | ❌ Non | ✅ Autorisé | Renoncement aux droits : aucune obligation légale |
| `other-open` | Autre licence ouverte (mention libre du producteur) | ⚠️ À vérifier au cas par cas | ⚠️ À vérifier | ⚠️ À vérifier | Le producteur déclare une licence ouverte sans en préciser la nature : les obligations exactes dépendent du texte de la licence citée sur la fiche du jeu |
| `other-attribution` | Autre licence à attribution | ⚠️ Attribution requise, autres clauses à vérifier | ⚠️ À vérifier | ⚠️ À vérifier | Le producteur déclare une licence à attribution sans en préciser la nature : à vérifier sur la fiche du jeu |
| `other-pd` | Autre mention de domaine public | ⚠️ À vérifier au cas par cas | ⚠️ À vérifier | ⚠️ À vérifier | Le producteur déclare une dedication au domaine public : à vérifier sur la fiche du jeu |

### Licence conditionnelle

`notspecified` (licence non renseignée) est acceptée **uniquement pour un producteur public** (`service_public`, `collectivité territoriale`) : l'absence de licence déclarée est présumée réutilisable pour un établissement public français (présomption de réutilisation, CRPA / décret 2017-638). Elle est refusée pour un producteur privé (`entreprise`, `association`). Cette acceptation est un **marquage** : les obligations restent à vérifier avant toute exploitation en partie 2.

### Licences exclues

Toute licence fermée ou commerciale est refusée, **quelle que soit l'organisation** — une licence incompatible explicite n'est jamais contournée, même pour un établissement public. Une licence **absente ou vide est également refusée** (comportement sûr par défaut).

### Implication pour l'exploitation des données (partie 2 du projet)

- **Attribution** : pour toutes les licences sauf `cc-zero`, toute restitution des données doit mentionner la source (producteur, organisation, date de mise à jour). Le projet conserve la licence avec chaque fichier acquis (`telecharger_brut` la retourne) et l'agent la restitue dans son rapport final.
- **Partage à l'identique** (`odc-odbl`, `cc-by-sa`) : tout produit dérivé des données doit être redistribué sous la même licence. Les visualisations et jeux dérivés de la partie 2 devront le respecter — c'est la contrainte la plus structurante du catalogue.
- **`other-open` / `other-attribution` / `other-pd`** : la licence déclarée doit être vérifiée sur la fiche data.gouv.fr avant toute exploitation.

### Paramétrage de la politique

La liste des licences (acceptées, conditionnelles, types d'organisation de confiance) est paramétrée dans [`config/politique_licences.json`](../config/politique_licences.json), avec une clé par source de données (préparation de l'ouverture à d'autres sites, T7.4). En l'absence ou en cas d'invalidité du fichier, une politique intégrée équivalente s'applique (comportement sûr).

---

## 📋 Suivi des tâches
Le suivi des tâches est disponible dans [`docs/projet/kanban.md`](projet/kanban.md).

---

## 📄 Licence
Ce projet est sous licence **MIT**.
