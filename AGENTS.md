# Guide pour les Agents (AGENTS.md)

Ce fichier décrit la **méthode de travail** à suivre pour contribuer au projet **openDataAgent**.
Il est automatiquement chargé à chaque séance, mais **aucune action structurante n'est déclenchée sans demande explicite** de l'utilisateur.

---

## **1. Reprise de contexte à chaque séance**
### **Étapes automatiques (sans initiative de l'agent)**
À chaque début de séance, l'agent **recharge automatiquement** les fichiers clés suivants pour reprendre le contexte :
1. **`docs/design/conception.md`** pour reprendre connaissance du schéma de conception du projet.
2. **`docs/specs/architecture.md`** pour reprende connaissance de l'architecture technique du projet.
3. **`docs/design/decisions_conception.md`** : pour reprendre connaissance des choix de conception du projet.
4. **`docs/architecture/*.md`** : pour reprendre connaissance des contrats et des invariants.
5. **`tests/plan_tests.md`** : pour reprendre connaissance des tests associés aux tâches.
6. **`docs/test/acceptation.md`** : pour reprendre connaissance des critères d'acceptation des réalisations du projet.
7. **`SESSIONS.md`** : pour reprendre connaissance des **actions, décisions et blocages** des séances précédentes.
8. **`docs/projet/kanban.md`** : pour reprendre connaissance du tableau des tâches.


### **Étapes à suivre (sur initiative de l'utilisateur)**
1. **Vérifier les derniers commits** (si modifications hors session).
   - Exemple de demande :
     ```markdown
     Peux-tu lister les 5 derniers commits pour voir les changements récents ?
     ```
2. **Demander un résumé du contexte** :
   - Exemple de demande :
     ```markdown
     Peux-tu me faire un résumé des tâches en cours et des décisions de conception clés ?
     ```

---

## **2. Workflow par tâche**

### **Étape 1 : Choix de la tâche (sur initiative de l'utilisateur)**
- **Action** : Identifier **la tâche explicitement demandée par l'utilisateur** dans `kanban.md` et la déplacer dans le bon paragraphe ("À faire", "En cours", "En revue", "Terminé").
  - *L'agent ne choisit **jamais** automatiquement une tâche prioritaire, mais peut proposer une évaluation des priorités si l'utilisateur le demande.*
- **Vérification** : S'assurer que ses dépendances sont terminées (ex : T1.3 avant T2.1) et vérifier s'il y a des dépendances éventuelles avec d'autres tâches.
- **Exemple de demande** :
  ```markdown
  Peux-tu préparer le travail sur la tâche T2.1 du kanban ?
  ```
- **Exemple de proposition de priorisation (sur demande)** :
  ```markdown
  Quelles tâches me recommandes-tu de prioriser dans le kanban ?
  ```

---

### **Étape 2 : Planification (sur initiative de l'utilisateur)**
- **Actions** :
  1. Lire les spécifications associées à la tâche dans les sources suivantes :
     - `docs/architecture/<nom_contrat>.md` (ex : `rechercher_jeux.md`).
     - `docs/design/decisions_conception.md` (pour les choix techniques).
     - `tests/plan_tests.md` (pour les tests associés).
     - `SESSIONS.md` (pour les décisions passées).
  2. Établir un **plan détaillé** avec :
     - Sous-tâches (ex : "Créer le schéma Pydantic pour `mots_cles`").
     - Fichiers à modifier (ex : `src/contracts/rechercher_jeux.py`).
     - Tests associés (ex : TU-12 à TU-16 dans `plan_tests.md`).
- **Exemple de demande** :
  ```markdown
  Peux-tu établir un plan détaillé pour la tâche T2.1 ?
  ```

---

### **Étape 3 : Implémentation (sur initiative de l'utilisateur)**
- **Actions** :
  1. Coder la fonctionnalité en respectant les **invariants** du projet.
  2. Coder les **tests associés** (unitaires et/ou d'intégration).
- **Exemple de demande** :
  ```markdown
  Peux-tu implémenter la tâche T2.1 en suivant le plan établi ?
  ```

---

### **Étape 4 : Tests et itérations (sur initiative de l'agent à la suite de l'étape 3)**
- **Actions** :
  1. Lancer les tests avec `pytest`.
     - Exemple de commande :
       ```bash
       python -m pytest tests/unit/test_rechercher_jeux.py -v
       ```
  2. **Itérer en cas d’échec** :
     - **1ère tentative** : Corriger directement.
     - **2ème tentative** : vérifier les hypothèses et corriger.
     - **3ème tentative** : **Arrêter** et documenter le blocage.
- **Règle d'arrêt** : Si un test échoue à la troisième tentative, créer une entrée dans [`BLOCKERS.md`](BLOCKERS.md) et passer à une autre tâche.

---

### **Étape 5 : Validation agent (sur initiative de l'agent à la suite de l'étape 4)**
- **Actions** :
  1. Valider que tous les tests passent et que les critères d'acceptation sont respectés.
  2. Mettre à jour `docs/projet/kanban.md` (déplacer la tâche en **En revue**).
  3. Commiter les changements avec un message explicite.

---

### **Étape 6 : Validation utilisateur (sur initiative de l'utilisateur)**
- **Actions** :
  1. Valider que tous les tests passent et que les critères d'acceptation sont respectés.
  2. Mettre à jour `docs/projet/kanban.md` (déplacer la tâche en **En revue**).
  3. Commiter les changements avec un message explicite.
- **Exemple de demande** :
  ```markdown
  Peux-tu valider la tâche T2.1 et la déplacer en Terminé dans le kanban ?
  Peux-tu faire un commit et pousser les changements sur le repository ?
  ```

---

## **3. Règles supplémentaires**
### **A. Documentation systématique (sur initiative de l'agent et éventuelle initiative complémentaire de l'utilisateur)**
- Pour chaque tâche, créer un **fichier de suivi** dans `docs/tasks/` (ex : `T2.1_schémas_pydantic.md`).
  ```markdown
  # Tâche T2.1 : Schémas Pydantic

  ## Statut
  - [X] Implémentation
  - [ ] Tests unitaires
  - [ ] Tests d'intégration

  ## Fichiers modifiés
  - `src/contracts/rechercher_jeux.py`

  ## Blocages
  - Aucun.
  ```
- **Exemple de demande** :
  ```markdown
  Peux-tu créer un fichier de suivi pour la tâche T2.1 dans `docs/tasks/` ?
  ```

---

### **B. Gestion des blocages (sur initiative de l'agent à l'issue de l'étape 4)**
- Si une tâche est bloquée :
  1. Créer une entrée dans [`BLOCKERS.md`](BLOCKERS.md) :
     ```markdown
     # Blocages

     ## T2.1 : Schémas Pydantic
     - **Problème** : Le test TU-14 échoue car le champ `limite` n'est pas validé.
     - **Tentatives** : 3/3.
     - **Proposition** : Vérifier la documentation de Pydantic pour les `conint`.
     ```
  2. Passer à une autre tâche.
- **Exemple de demande** :
  ```markdown
  Peux-tu documenter ce blocage dans `BLOCKERS.md` et passer à une autre tâche ?
  ```

---

### **C. Gestion des changements (sur initiative de l'utilisateur à l'issue de l'étape 5 ou durant l'étape 6)**
- Ne jamais faire un commit, ni pousser un changement dans le repository sans demande explicite de l'utilisateur.

---

## **4. Actions ponctuelles (hors workflow)**
Les actions suivantes peuvent être demandées en séance **sans être référencées dans ce fichier** :
- **Analyse/Revue** :
  ```markdown
  Peux-tu analyser la cohérence entre `src/core/search.py` et `docs/architecture/rechercher_jeux.md` ?
  ```
- **Corrections ponctuelles** :
  ```markdown
  Peux-tu corriger cette erreur de typage dans `src/contracts/rechercher_jeux.py` ?
  ```
- **Génération de documentation** :
  ```markdown
  Peux-tu générer un exemple de payload pour l'API `rechercher_jeux` ?
  ```
- **Autres demandes** :
  ```markdown
  Peux-tu me proposer une évaluation des priorités dans le kanban ?
  ```

---

## **5. Résumé des fichiers clés**
| Fichier                  | Rôle                                                                                            |
|--------------------------|-------------------------------------------------------------------------------------------------|
| `SESSIONS.md`            | Journal des **actions, décisions et blocages** par séance. Utilisé pour la reprise de contexte. |
| `docs/projet/kanban.md`  | Suivi des tâches (À faire → En cours → En revue → Terminé).                                     |
| `tests/plan_tests.md`    | Plan de tests (TU, TI, TB) et couverture des critères d'acceptabilité.                          |
| `docs/tasks/`            | Suivi détaillé par tâche (optionnel).                                                           |
| `BLOCKERS.md`            | Liste des **blocages non résolus** (documentés après 4 échecs de test).                         |
