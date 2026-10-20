# Journal des décisions de conception

Ce document recense les décisions prises lors de la conception du projet **openDataAgent**, ainsi que leur justification, leur date de prise de décision et leur impact sur les artefacts du projet.

---

## Décisions prises le **10 octobre 2026**

---

### 1. Diagramme des flux

#### Décision
Utiliser le fichier [`docs/conception.mmd`](conception.mmd) pour représenter le diagramme des flux du projet.

### Justification
- Le fichier `conception.mmd` couvre déjà l'ensemble des **étapes agentiques** (A1 à A4) et **algorithmiques** (B1 à B8).
- Il décrit également les **interactions** entre l'agent et le code, ainsi que les **points de décision** (ex : filtre de licence, classification des ressources).

### Impact
- Référencé dans [`architecture.md`](architecture.md).
- Aucun ajout ou modification nécessaire.

---

### 2. Arborescence pour le stockage des fichiers téléchargés

#### Décision
Adopter l'arborescence suivante pour le stockage des fichiers téléchargés :
```
openDataAgent/
├── data/
│   ├── raw/                  # Fichiers bruts téléchargés
│   │   ├── <id_execution>/   # Identifiant unique par exécution (ex : 20261010_143022_a1b2c3)
│   │   │   ├── <id_ressource>_<nom_fichier_original>.<extension>
│   │   │   └── ...
│   │   └── ...
│   ├── processed/            # Fichiers normalisés (si applicable)
│   └── registry.json         # Registre des sources inaccessibles
```

### Détails
- **`<id_execution>`** : Identifiant unique pour chaque exécution, au format `<date>_<heure>_<hash_court>` (ex : `20261010_143022_a1b2c3`).
- **`<id_ressource>`** : Identifiant de la ressource (ex : `71ff1335`).
- **`<nom_fichier_original>`** : Nom du fichier d'origine (nettoyé pour éviter les caractères spéciaux).
- **`<extension>`** : Extension du fichier (ex : `csv`, `zip`, `geojson`).

### Justification
- **Évite les conflits de noms** : Chaque exécution est isolée dans un dossier dédié.
- **Traçabilité** : L'`id_execution` permet de retrouver tous les fichiers d'une session.
- **Persistance** : Le registre (`registry.json`) est stocké dans `data/` pour être conservé entre les exécutions.

### Impact
- Documenté dans [`stockage.md`](stockage.md).

---

### 3. Réalignement des contrats JSON

#### Décision
Mettre à jour les fichiers JSON des contrats pour les aligner sur leur documentation (`*.md`). Les modifications apportées sont les suivantes :

| Fichier JSON | Champ ajouté/modifié | Description |
|--------------|-----------------------|-------------|
| `rechercher_jeux.json` | `donnees.exclus_licence` | Nombre de jeux écartés par le filtre de licence. |
| `lister_ressources.json` | `donnees.indetermination` | Identifiants des ressources non classées automatiquement. |
| `interroger_ressource.json` | `donnees.recommandation` | Recommandation pour les volumes élevés (ex : `volume_eleve_telechargement_brut_suggere`). |
| `telecharger_brut.json` | `donnees.chemin_local`, `donnees.licence`, `donnees.suggestion` | Métadonnées du fichier téléchargé et suggestion en cas d'échec. |

### Justification
- **Cohérence** : Aligner les schémas JSON sur la documentation pour éviter les divergences.
- **Exhaustivité** : Tous les champs mentionnés dans la documentation sont désormais définis dans les contrats.

### Impact
- Fichiers JSON mis à jour dans `contrats/`.

---

### 4. Gestion des conflits de noms de fichiers

#### Décision
Utiliser l'`id_execution` et l'`id_ressource` pour éviter les conflits de noms de fichiers téléchargés.

### Détails
- **Conflits entre exécutions** : Résolus par l'`id_execution` (ex : `20261010_143022_a1b2c3`).
- **Conflits dans une même exécution** : Si deux fichiers ont le même `<nom_fichier_original>.<extension>`, un suffixe numérique est ajouté (ex : `71ff1335_budget-fr-indicateurs_1.csv`).

### Justification
- **Robustesse** : Évite les écrasements accidentels.
- **Traçabilité** : Permet de retrouver l'origine d'un fichier.

### Impact
- Documenté dans [`stockage.md`](stockage.md).

---

### 5. Tests des formats non tabulaires

#### Décision
Ajouter des tests pour valider le traitement des formats non tabulaires (ZIP, GeoJSON, JSON, SHP, PDF).

### Détails
- **Tests unitaires (TU-29 à TU-33)** : Validation de la classification et de la persistance.
- **Tests d'intégration (TI-11 et TI-12)** : Téléchargement et vérification des fichiers ZIP et GeoJSON.

### Justification
- **Exhaustivité** : Couvrir tous les formats mentionnés dans la documentation.
- **Robustesse** : Valider le traitement des formats complexes.

### Impact
- Ajout des tests dans [`plan_test.md`](plan_test.md).

---

### 6. Sécurité

#### Décision
Ne pas implémenter de **listes blanches** ni de **chiffrement** pour ce projet.

### Justification
- **Listes blanches** : Les données de **data.gouv.fr** sont publiques et ne présentent pas de risque de phishing ou de liens malveillants.
- **Chiffrement** : Aucune donnée sensible n'est manipulée (pas de mots de passe, pas de tokens, pas de données personnelles).

### Impact
- Aucun impact sur les artefacts du projet.

---

### 7. Déploiement

#### Décision
Le projet s'exécute :
- **En local** : Sur le poste de travail de l'utilisateur.
- **En ligne** : Sur un compte Mistral (intégration directe via les outils exposés).

### Justification
- **Simplicité** : Pas besoin de configuration complexe ou d'infrastructure dédiée.
- **Flexibilité** : Adapté à un usage personnel ou en ligne.

### Impact
- Documenté dans [`architecture.md`](architecture.md).

---

### 8. Journalisation des décisions

#### Décision
Créer ce fichier (`decisions_conception.md`) pour journaliser les décisions de conception.

### Justification
- **Traçabilité** : Conserver une trace des choix de conception et de leur justification.
- **Maintenabilité** : Faciliter l'onboarding et les évolutions futures.

### Impact
- Fichier créé dans `docs/`.

---

### 9. Prochaines étapes

Les décisions suivantes sont reportées à des itérations ultérieures :
- **Réessai intelligent** : Mécanisme de réessai avec délai exponentiel pour les échecs techniques.
- **Support pour d'autres sources de données** : Intégration de plateformes comme Eurostat ou INSEE.
- **Nettoyage automatique** : Suppression des anciennes exécutions (ex : dossiers vieux de plus de 30 jours).
- **Automatisation des tests agentiques** : Automatisation des tests TA avec des scénarios prédéfinis.

---

## Décisions prises le **15 octobre 2026** (T10.7 — persistance de la voie 1)

### 1. Symétrie mode manuel / mode agentique pour l'acquisition

#### Décision
L'extraction paginée d'une ressource indexée existe sous forme d'une **fonction cœur unique** (`extraire_ressource`, `src/core/extraction.py`) exposée par **deux portes d'entrée** : la commande CLI `extract` (mode manuel) et le 5ᵉ outil agent `extraire_ressource` (contrat v1.2.0, manifeste 1.1). Exigence du concepteur : les données doivent être récupérables dans les deux modes.

### Justification
- **Cohérence architecturale** : chaque pouvoir du mode manuel a déjà son miroir agentique (search/list/query/download) ; l'extraction honore ce principe.
- **Écart structurel levé** : la voie 1 restait conversationnelle — aucune donnée indexée n'était jamais matérialisée sur disque.

### 2. Frontière exploration / acquisition

#### Décision
`interroger_ressource` n'écrit jamais rien (exploration page à page) ; `extraire_ressource` et `telecharger_brut` écrivent sur disque (acquisition). Le prompt système impose à l'agent de réserver l'extraction à l'acquisition finale et de citer `chemin_local` + licence dans la synthèse.

### 3. Plafond de sécurité : succès partiel explicite

#### Décision
Plafond de lignes extraites (`PLAFOND_EXTRACTION`, défaut 10 000) ; l'atteinte produit un **succès** avec `tronque: true` et un message signalant la troncature — jamais un échec silencieux, jamais une perte cachée.

### Justification
- L'export massif non maîtrisé est un risque opérationnel (disque, temps, quota API) ; le statut « succès partiel signalé » laisse l'utilisateur décider d'un éventuel `telecharger_brut`.

### 4. Format pivot CSV, stockage commun `data/raw/`

#### Décision
L'extraction écrit un CSV UTF-8 dans `data/raw/<id_execution>/` (même racine que la voie 2, gestion de collision par suffixe). Le CSV est un pivot : la normalisation B7 (T10.1) pourra le transformer ensuite.

### Justification
- **Lisibilité et universalité** : le CSV est directement consommable par la partie 2 (pandas) et par l'humain.
- **Simplicité** : l'agrégation de lignes JSON en CSV via `csv.DictWriter` est déterministe et sans dépendance.


---

## 18/10/2026 — T11.3 : migration API data.gouv.fr v1 → v2

### 1. Bascule pleine v2, sans adaptateur

#### Décision
La recherche et l'inventaire passent sur l'API v2 (`/api/2/datasets/search/`, `/api/2/datasets/{id}`, `/api/2/datasets/{id}/resources/`) sans couche d'abstraction par source. L'adaptateur n'aura de sens qu'avec T7.4 (autres sources : Eurostat, INSEE...).

### 2. Mapping `derniere_maj` ← `last_update`

#### Décision
Le champ normalisé `derniere_maj` est alimenté par `last_update` (dernière mise à jour d'une ressource — fraîcheur des données) et non `last_modified` (dernière modification des métadonnées). C'est aussi le champ support du tri `recent` (`-last_update`).

#### Justification
- Sur le jeu étalon (élections présidentielles 2022, Ministère de l'Intérieur) : `last_modified` = 19/04/2022, `last_update` = 14/04/2022 — la sémantique utile au projet est la fraîcheur des données.
- Cohérence avec le tri `recent` et avec la fenêtre de mise à jour (v1) qui portaient déjà sur `last_update`.

### 3. Dépréciation de `fenetre_maj` (contrat v1.2.0 → v1.3.0)

#### Décision
L'API v2 ne supporte pas `last_update_range` (HTTP 400, sondage S11.0) et n'offre pas d'équivalent simple. Le paramètre `fenetre_maj` est conservé en signature (compatibilité CLI/agent) mais **ignoré** : toute valeur autre que `toutes` produit un avertissement explicite dans le `message` de la réponse, sans faire échouer la recherche. Le retrait complet est prévu avec T7.4.

#### Justification
- Évoluer le contrat en fracassant la compatibilité n'était pas justifié : aucun appelant ne dépend de la fenêtre pour la sécurité juridique ou l'acquisition.
- L'avertissement dans `message` plutôt qu'un échec : la recherche reste utile, l'appelant est informé.

### 4. Pagination : arrêt sur `next_page` absent

#### Décision
Toute boucle de pagination (recherche, inventaire) s'arrête exclusivement quand la réponse ne contient plus `next_page` — jamais sur une erreur HTTP ou une liste vide.

#### Justification
- La v2 peut répondre 400 ou une liste vide au-delà du total selon le numéro demandé (comportement moins prévisible que la v1, sondage S11.0) ; le signal serveur `next_page` est le seul fiable.
- Même logique que l'extraction tabulaire (`links.next`, T10.7) — la règle est désormais explicite et uniforme.

### 5. Inventaire : sous-ressource paginée reconstituée par l'isolant HTTP

#### Décision
`lister_ressources_api` enchaîne deux appels (détail du jeu, puis sous-ressource `resources` avec boucle sur `next_page`, `page_size` 50, plafond de sécurité 20 pages) et **reconstitue** le payload au format attendu par le cœur (détail + liste `resources` plate). La normalisation aval est inchangée.

#### Justification
- L'isolant statut/message/donnees absorbe la restructuration v2 : aucune évolution des sorties normalisées (prévision confirmée du kanban).
- Le plafond de pages est une garde anti-boucle explicite (échec propre « plafond atteint »), pas une limite fonctionnelle : 20 × 50 = 1000 ressources suffisent au catalogue réel.

### 6. Choix de la pertinence v2

#### Décision
Le tri `pertinence` est le tri implicite du moteur v2 (celui du site) : aucun paramètre `sort` n'est envoyé.

#### Justification
- Cas étalon « élections présidentielles » : jeux du Ministère de l'Intérieur en tête de page 1 en v2 (total 235) vs jeux communaux en v1 (total 41) — la motivation première de T11.3.


---

## 19/10/2026 — T10.8 : manifeste d'acquisition par exécution

### 1. Source de vérité acquisition côté disque

#### Décision
Chaque acquisition réussie (`telecharger_brut`, `extraire_ressource`) ajoute une entrée à `data/raw/<id_execution>/manifeste_acquisitions.json`, avec la demande utilisateur en en-tête. Le manifeste relie fichier → jeu → licence → mention d'attribution.

#### Justification
- Constat de la validation T11.3 : en mode agentique, le lien fichier → jeu n'était reconstituable qu'en croisant l'inventaire persistant (écrit en CLI uniquement) et le journal de conversation — fragile et incomplet.
- La partie 2 (T10.1/B7) doit consommer ces métadonnées : le manifeste les pose à côté des fichiers, dans les deux modes.

### 2. Écrit au cœur, additif, jamais bloquant

#### Décision
- Écriture au cœur (pas côté CLI) : un seul chemin de code pour les deux modes.
- Aucune évolution de contrat : sortie latérale ; nommage des fichiers et sorties normalisées inchangés.
- Un échec d'écriture du manifeste ne fait jamais échouer l'acquisition (warning) : le manifeste est une commodité de traçabilité, pas une dépendance.

#### Justification
- Symétrie manuel/agentique déjà retenue pour l'extraction (T10.7) : même principe.
- La traçabilité ne doit pas introduire de nouveau point de défaillance sur le chemin d'acquisition.


---

## 20/10/2026 — T11.1 : mode conversationnel multi-tours

### 1. Conservation du contexte côté serveur (API Conversations)

#### Décision
Le contexte conversationnel est conservé **côté serveur** via l'API Conversations du SDK (`client.beta.conversations`) : la conversation est créée par `start_stream` (premier message), poursuivie par `append_stream` (message utilisateur ou résultats d'outils). Seul le nouveau contenu est envoyé à chaque appel ; l'historique complet vit sur la console Mistral. La boucle tool-calling reste **côté client** : les `function.call.delta` émis par le serveur sont exécutés localement (`executer_outil`) et leurs résultats renvoyés au serveur par des entrées `function.result`.

#### Justification
- Décision du concepteur (20/10/2026) : l'option (b) du kanban est retenue — l'agent se souvient, seul le nouveau prompt est envoyé.
- Le `conversation_id` est porté par l'événement `conversation.response.started` du stream ; `append_stream` le prend en paramètre d'URL.
- Conséquence sur l'arbitrage API tranché le 19/10 : `client.beta.agents` reste l'API retenue — l'option serveur n'existe que dans la famille beta (agents + conversations), ce qui clôt définitivement la question `beta.agents` vs `chat.completions`.
- La suppression de la conversation (`client.beta.conversations.delete`) est faite en fin de flux, dans le `finally` de la commande `chat`, à côté de la destruction de l'agent éphémère.

### 2. Propose-puis-acquiert

#### Décision
En mode multi-tours, les tours conversationnels explorent (recherche, inventaire, interrogation — aucune écriture disque) ; `telecharger_brut` et `extraire_ressource` ne s'exécutent qu'après **validation explicite** de l'utilisateur. L'étape A4 du prompt devient une **proposition** (jeux retenus, ressources envisagées, voie d'acquisition proposée) en attente de confirmation.

#### Justification
- Évite les fichiers orphelins des tentatives rejetées par l'utilisateur en cours de conversation.
- Résout le comportement propose-puis-acquiert observé en one-shot (séances du 19/10/2026) : en one-shot, personne ne répondait à la question de l'agent ; en multi-tours, la validation est un tour normal.

### 3. Plafond d'invocations par tour

#### Décision
Le plafond d'invocations d'outils (défaut 10, `--plafond` / `PLAFOND_INVOCATIONS`) s'applique **par tour utilisateur** et est réinitialisé à chaque nouveau prompt. Aucun plafond global de conversation n'est instauré.

#### Justification
- La plupart des conversations n'auront que quelques tours ; un plafond global serait un garde-fou sans cas d'usage réel.
- **Évolution future consignée** : un plafond global de sécurité (ex. 50 invocations par conversation) pourra être ajouté si des conversations longues se généralisent.

### 4. Pas d'étape A0 (clarification avant recherche)

#### Décision
L'agent ne pose pas de question de clarification avant de lancer sa recherche : il commence directement, et l'utilisateur affine sa demande au tour suivant si les résultats ne sont pas satisfaisants.

#### Justification
- Le multi-tours rend l'A0 redondante : le feedback utilisateur joue déjà ce rôle au tour 2.
- **Évolution future consignée** : une étape A0 (question de clarification si la demande est ambiguë) pourra être ajoutée si les retours d'usage montrent des premières recherches trop éloignées.

### 5. Clôture par mot-clé `stop`, plus de mode one-shot

#### Décision
La commande `chat` déclenche directement le mode multi-tours (REPL). Le mot-clé de clôture est `stop` (insensible à la casse, en début de saisie). Le mode one-shot est supprimé : un prompt fourni en argument est simplement le **premier message** de la conversation, qui se poursuit en REPL. `EOF` (Ctrl+D) et `Interrupt` (Ctrl+C) clôturent aussi proprement.

#### Justification
- Le one-shot était un résidu de T4.3 ; le multi-tours le subsume (un seul tour = `chat "prompt"` puis `stop`).
- Un seul chemin de code pour la commande `chat`.

### 6. Journal multi-tours

#### Décision
Une conversation = un `id_execution` = un journal `conversations/<id_execution>/conversation.jsonl`. Le schéma évolue :
- `contexte` (une fois, en-tête) : id_execution, modèle, **empreinte du prompt** (sha256 tronquée), plafond, date ;
- `debut_tour` (par tour) : `numero_tour`, `contenu` (message utilisateur) ;
- `raisonnement_agent`, `outil_invoque`, `outil_resultat`, `plafond_atteint`, `erreur_api` : inchangés, le champ `tour` porte le **numéro d'invocation dans le tour** (réinitialisé à chaque tour) ;
- `fin_tour` (par tour) : `numero_tour`, `statut`, `nb_invocations` (du tour), `synthese` (texte final du tour), `plafond` ;
- `fin` (une fois) : `statut`, `nb_tours`, `nb_invocations` (total conversation).

Les événements `message_utilisateur` et `reponse_finale` de l'ancienne boucle one-shot sont supprimés (remplacés par `debut_tour`/`fin_tour`). Le rejeu `extraire_invocations` (base TA-01/TA-02) est inchangé.

#### Justification
- La granularité par tour préserve l'audit : chaque tour est horodaté avec son compte d'invocations et sa synthèse.
- L'empreinte du prompt dans l'en-tête (au lieu du texte complet) garde le journal lisible tout en permettant de vérifier quelle version du prompt a servi.

### 7. Écriture atomique du manifeste : remplacement cross-platform (E8b, 20/10/2026)

#### Décision
L'écriture atomique du manifeste (`src/core/manifeste.py::_ecrire`) utilise **`os.replace`** (remplacement garanti sur toutes les plateformes) et non `Path.rename`. Sous Windows, `Path.rename` lève `WinError 183` si la cible existe déjà — or un fichier `.part` orphelin (laissé par un plantage précédent) bloquait alors **toutes** les écritures suivantes de la même exécution, produisant un manifeste incomplet.

#### Justification
- 2nd test réel T11.1 (20/10, id `20261020_213621`) : 3 acquisitions réussies, 3x « Échec d'écriture du manifeste » (WinError 183), manifeste final réduit à la dernière entrée. La boucle agentique n'était pas en cause — l'incident était purement système de fichiers, côté cœur (T10.8).
- `os.replace` a la sémantique « écraser si existe » sur Windows comme sur POSIX : l'atomicité est préservée (écriture `.part` complète puis remplacement), sans le point de défaillance Windows.
- Régression couverte par TU-80 (simulation du comportement Windows de `rename`).
