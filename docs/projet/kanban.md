# Kanban du projet openDataAgent

Ce document suit l'avancement des tâches pour l'implémentation du projet **openDataAgent**. Il est organisé en **4 colonnes** :
- **📌 À faire** : Tâches non commencées.
- **🚧 En cours** : Tâches en cours d'implémentation.
- **🔍 En revue** : Tâches prêtes pour une revue ou des tests.
- **✅ Terminé** : Tâches validées.

---

## 📌 À faire

> Nota : la partie agentique Mistral est une section d'implémentation à part entière (section 5), pas une sous-section de tests ; les identifiants de tâches (T5.3.x, T5.1.x, T5.2.x) sont conservés inchangés pour la traçabilité avec `tests/plan_tests.md`, `docs/tasks/` et `SESSIONS.md`.

### 1. Initialisation du projet

---

### 2. Implémentation des contrats

---

### 3. Implémentation des fonctions de base

#### 3.1. Recherche de jeux (`rechercher_jeux`)


#### 3.2. Inventaire des ressources (`lister_ressources`)

#### 3.3. Interrogation des ressources (`interroger_ressource`)

#### 3.4. Téléchargement brut (`telecharger_brut`)

---

### 4. Intégration et CLI

> ✅ Toutes les commandes livrées (search, list, query, download, chat — T4.1, T4.2, T4.3) — déplacées en colonne ✅ Terminé.

---

### 5. Intégration agentique Mistral

C'est la raison d'être du projet : l'agent Mistral porte les étapes A1 à A4 du flux (reformulation, sélection, tranchage des indéterminations, synthèse du registre) en s'appuyant sur les fonctions du cœur. Les identifiants T5.3.x sont conservés pour la traçabilité avec le plan de tests et les fichiers de suivi.

> ✅ Toutes les tâches de cette section (T5.3.1 à T5.3.4) sont terminées — déplacées en colonne ✅ Terminé.

---

### 6. Tests

#### 6.1. Tests unitaires

> ✅ T5.1.3, T5.1.4, T5.1.5 terminées — déplacées en colonne ✅ Terminé.

#### 6.2. Tests d'intégration

> ✅ T5.2.1 et T5.2.2 terminées — déplacées en colonne ✅ Terminé.

---

### 7. Logging et journalisation

---

### 8. Améliorations futures (optionnel)
- [ ] **T7.1** : Ajouter un mécanisme de réessai intelligent pour les échecs techniques.
- [ ] **T7.2** : Implémenter un nettoyage automatique des anciennes exécutions.
- [ ] **T7.3** : Automatiser les tests agentiques.
- [ ] **T7.4** : Supporter d'autres sources de données (ex : Eurostat, INSEE).

---

### 9. Licence descriptif et attribution

> Cette section prépare la **partie 2 du projet** (exploitation et visualisation des données) : l'usage légitime des données acquises dépend des obligations propres à chaque licence (attribution, partage à l'identique). La politique d'acquisition (section 2, `src/core/licence.py`) est terminée et ne dépend pas de ces travaux.

- [ ] **T7.5** *(en revue)* : Registre descriptif des licences et génération de mention d'attribution (`src/core/licences_descriptif.py`) :
  - registre des propriétés par licence (attribution obligatoire, partage à l'identique, usage commercial), miroir de la politique documentée dans `docs/README.md` (section Politique de licence) ;
  - `mention_attribution()` : génération de la mention prête à afficher à partir des métadonnées de l'inventaire (organisation, licence, date de mise à jour) ;
  - prédicats de compatibilité pour la partie 2 (ex. produit dérivé sous licence permissive autorisé ou non) ;
  - échec propre sur licence inconnue et sur `other-open`/`other-attribution`/`other-pd` (propriétés à vérifier, jamais devinées) ;
  - branchement optionnel sur `telecharger_brut` (champ `mention_attribution` dans la réponse, évolution de contrat à versionner) : à décider séparément.
  - **Chantier A (préalable) ✅** : référentiel de licences élargi au filtre complet du site (`odc-by`, `odc-pddl`, `other-attribution`, `other-pd` ajoutées) + règle sécurisée `notspecified` acceptée pour un producteur public uniquement + politique paramétrée dans `config/politique_licences.json` (une clé par source, préparation T7.4). Voir `docs/tasks/T7.5_licences_descriptif.md`.
  - **Chantier B ✅** : type d'organisation résolu via les badges uData du payload de recherche (`public-service`/`local-authority`) ; marquage `licence_conditionnelle` + compteur dans la réponse ; registre dédié aux acceptations conditionnelles (`data/registre_acceptations.json`), sémantique du registre des sources inaccessibles préservée. Voir `docs/tasks/T7.5_licences_descriptif.md`.

---

### 10. Séance d'appropriation du 14/10/2026 (soir) — chantiers identifiés

> Tâches issues de la relecture guidée du code avec le concepteur (questions/réponses sur Python, Typer, contrats, agent et logique applicative). Aucune modification de code effectuée à cette séance ; ces entrées formalisent les écarts et chantiers détectés.

- [ ] **T10.6** (optionnel, si packaging/portage un jour) : nom de paquet générique `src` (collision/convention), `pyproject.toml` + point d'entrée console, externalisation des chemins relatifs au CWD (`data/`, `conversations/`, registre), `libmagic` sous Windows, chargement du `.env` explicite.

---

### 11. Mode conversationnel multi-tours

> Issu de la séance du 18/10/2026 (retours d'usage du concepteur sur le flux agentique) : l'arbitrage final de pertinence doit pouvoir se faire *pendant* la conversation, pas seulement après l'acquisition.

- [ ] **T11.1** : Mode conversationnel multi-tours (`chat`) : boucle REPL où l'utilisateur raffine sa demande par une succession de prompts, l'agent conservant le contexte accumulé jusqu'à la fin de conversation (mot-clé de clôture). Décisions de conception à trancher en premier :
  - **propose-puis-acquiert** (recommandé) : les tours conversationnels explorent (recherche, inventaire, interrogation — pas d'écriture disque) ; `extraire_ressource`/`telecharger_brut` ne s'exécutent qu'après validation explicite de l'utilisateur (évite les fichiers orphelins de tentatives rejetées) ;
  - plafond d'invocations **par tour** (reinitialisé à chaque prompt utilisateur), pas par conversation ;
  - étape A0 possible : question de clarification avant recherche si la demande est ambiguë ;
  - journal multi-tours : une conversation = un `id_execution`, chaque tour horodaté avec son compte d'invocations et sa synthèse.
  Composants touchés : `src/main.py` (commande chat, REPL + clôture, one-shot conservé en compatibilité), `src/agent/boucle.py` (état de conversation/historique des messages), `src/agent/agent.py` (prompt : A4 devient proposition en attente de validation, intégration du feedback), `src/agent/journal.py` (schéma multi-tours). **Aucune évolution de contrat cœur** : la conversation est une couche au-dessus des outils existants.
  Prérequis : tests d'intégration multi-tours simulés (exploration → correction utilisateur → raffinement → acquisition validée).
- [ ] **T11.2** : Outil `rechercher_organisations` + filtre organisation sur `rechercher_jeux` (issu du constat des traces du 18/10/2026 : l'agent a consacré 3 invocations à chercher "Ministère de l'Intérieur" en mots-clés, sans succès — il n'existe aucun moyen direct de cibler un producteur). Chantier :
  - fonction cœur de recherche d'organisations par nom (endpoint `/api/1/organizations/`, déjà sondé — pagination, nom, slug, id, badges) ;
  - filtre optionnel `organisation` (id ou slug) sur `rechercher_jeux` (paramètre supporté par l'API v1) — évolution de contrat (v1.2.0 → v1.3.0) ;
  - prompt A1 : consigne d'utiliser le filtre producteur quand la portée demandée implique un producteur identifié ;
  - question associée à instruire : migration de la recherche v1 → v2 (moteur du site, pertinence très supérieure constatée sur le cas « élections présidentielles » ; SESSIONS.md ligne 128 : bascule envisagée puis ajournée, le choix v1 était un arbitrage de cohérence docs/code, pas un choix de pertinence — à réévaluer au vu des constats du 18/10, idéalement via un adaptateur par source en perspective de T7.4).
- [ ] **T11.3** : Migration de l'API data.gouv.fr v1 → v2 pour la recherche et l'inventaire (décision concepteur du 18/10/2026 : bascule pleine v2, pas d'adaptateur — l'adaptateur par source n'aura de sens qu'avec T7.4). Contexte : le moteur v2 est celui du site (pertinence très supérieure constatée sur « élections présidentielles » : jeux du Ministère de l'Intérieur en tête vs jeux communaux en v1 ; total 235 vs 41) ; le choix v1 historique était un arbitrage de cohérence docs/code, pas de pertinence (SESSIONS.md, séance du 13/10). Périmètre :
  - **S11.0 sondage préalable** (½ journée) : cartographie champ par champ v1/v2 (search `/api/2/datasets/search/`, détail de jeu, pagination `next_page`, tri, fenêtre de mise à jour, `last_modified` vs `last_update`, badges `organization` — déjà constatés identiques), capture des fixtures v2 réelles, vérification du statut de l'API tabulaire et du ping `est_indexee_api_tabulaire` (hors périmètre attendu) ;
  - `src/utils/http.py` : URL base, `rechercher_jeux_api`, `lister_ressources_api` (attention : `resources` en sous-ressource paginée en v2 — impact sur l'inventaire) ;
  - schémas jsonschema `contrats/schemas_api/*.reponse.json` (recherche + inventaire) réécrits sur la v2 ;
  - fixtures `tests/fixtures/api/` re-capturées en réel sur la v2 ;
  - normalisation : mapping `derniere_maj` (v1 `last_modified` → v2 `last_update`) dans la couche HTTP/core ; filtre de licence et badges attendus sans changement (même modèle `organization`) — à vérifier en priorité (chantier B T7.5) ;
  - docs d'architecture mises à jour ; aucune évolution des sorties normalisées attendue (l'isolant statut/message/donnees absorbe le changement) ;
  - validation en réel : TB-01 rejoué + cas étalon « élections présidentielles » (le jeu du Ministère de l'Intérieur doit apparaître en page 1).
- [X] **Prompt A1/A2 (préalable, séance du 18/10/2026)** : règle générique sur les qualificatifs de portée (géographique, temporelle, juridique) — ils expriment un critère de sélection, pas de recherche ; vérification à l'étape A2 de la cohérence portée demandée / organisation productrice (une mairie ne produit pas de données nationales). Cas de test : « résultats nationaux des élections présidentielles » doit retenir un producteur national, pas une commune.

---

## 🚧 En cours

- [ ] **T10.7** : Persistance des extractions de la voie 1 (issu du chantier 1 de T10.1). En l'état, `interroger_ressource` retourne des pages à l'agent sans rien écrire sur disque (exploration conversationnelle uniquement) : les données sélectionnées ne sont jamais matérialisées via la voie 1. Chantier : extraction paginée vers `data/raw/` (nouveau module cœur `src/core/extraction.py`, réutilisant `interroger_ressource_api` et la logique `page_suivante`), plafond de sécurité (pages/lignes), accessible en mode manuel (commande CLI `extract`) **et** en mode agentique (évolution de contrat v1.2.0 à définir — exigence concepteur : les deux modes doivent pouvoir acquérir les données). Séquence : T10.7 avant T10.1 (normalisation B7). *(En cours — E1..E6 implémentées : fonction cœur, contrat v1.2.0 (manifeste 1.1), dispatch agent, commande CLI extract, tests 285 verts, docs ; validation en local en attente)*


- [ ] **T10.1** : Réaliser la mise à disposition des données vers la partie 2 (maillon B7 → P du schéma de conception, `docs/design/conception.mmd`). **Écart le plus structurel** : en l'état, seule la voie 2 (téléchargement brut) matérialise les données sur disque ; la voie 1 (extraction via API tabulaire) ne persiste rien (exploration conversationnelle uniquement) et aucune normalisation commune B7 n'existe dans le code. Chantiers : persistance des extractions tabulaires (ex. export paginé vers `data/raw/`) et pipeline de normalisation commun aux deux voies. Évolution de contrat probable (v1.2.0, ex. option `destination` sur `interroger_ressource` ou nouvel outil). *(En cours — périmètre précisé : cette entrée porte le chantier 2, pipeline de normalisation commun B7 aux deux voies ; le chantier 1, persistance des extractions de la voie 1, est séparé dans T10.7 ci-dessous ; séquence : T10.7 puis T10.1)*

---

## ✅ Terminé

- [X] **T10.2** : Inventaire persistant par `id_execution` — évolution « inventaire persistant » évoquée le 14/10 mais non créée ; le concepteur juge le choix actuel trop limitatif : `--id-execution` des commandes manuelles n'a qu'un rôle de trace, aucun chaînage manuel (list puis download) n'est possible. Design acté en séance : persistance côté CLI uniquement (`data/executions/<id_execution>/inventaire.json`), méthodes de sérialisation additives sur l'inventaire (`src/core/resources.py`), chargement/sauvegarde dans le callback Typer, enrichissement cumulatif, mode agentique et cœur inchangés (TI-14b reste vert). Précision de la convention 1 du contrat global (« jamais vu par le flux d'exécution courant ») ; réécriture de la section « piège list→download » du README (limite → fonctionnalité). Lié à T7.2. *(Terminé le 15/10/2026 — sérialisation additive decharger/charger dans resources.py, persistance CLI data/executions/<id>/inventaire.json, chaînage list→download fonctionnel, id d'exécution affiché, convention 1 précisée, README réécrit ; 4 nouveaux tests ; 267 verts)*
- [X] **T10.4** : Brancher la validation Pydantic des arguments d'outil au runtime : les modèles `Input/Output` de `src/contracts/` ne servent aujourd'hui qu'aux tests de cohérence (`valider_coherence_contrat`) ; la validation runtime des `tool_calls` repose sur des lambdas superficielles (`ARGUMENTS_OBLIGATOIRES`). Divergence entre la docstring de `src/contracts/validation_api.py` (« les modèles Pydantic valident la couche sortante ») et le comportement réel. À acter : brancher `*.model_validate(arguments)` dans `executer_outil`, ou assumer la simplification et corriger la docstring. *(Terminé le 15/10/2026 — MODELES_INPUT branché dans executer_outil, extra="ignore" sur les 4 *Input, model_dump(exclude_unset=True), id_execution injecté après validation, docstring validation_api.py corrigée ; 5 nouveaux tests ; 263 verts)*
- [X] **T10.5** : Déplacer les vocabulaires fermés de `main.py` vers le cœur (source unique de vérité) : `TRIS`, `OPERATEURS_FILTRE`, `ORDRES_TRI`, `FENETRES_MAJ` (éventuellement en `StrEnum`), importés par la CLI et le cœur ; constante ou option `--apercu N` pour le plafond d'affichage (5 lignes) de `query` ; dédupliquer le `help` de `--id-execution`. *(Terminé le 15/10/2026 — module src/core/vocabulaires.py (4 StrEnum + APERCU_DEFAUT), contrats et CLI branchés dessus, option --apercu sur query, aide --id-execution dédupliquée ; 3 nouveaux tests ; 263 verts au total avec T10.4)*
- [X] **T10.3** : Corriger le bug `id_execution` dans `executer_outil` (`src/agent/outils.py`) : le paramètre reçu de la boucle n'est pas injecté dans l'appel au cœur si l'agent ne le fournit pas ; et s'il le fournit, il entre en conflit avec celui de la boucle (`TypeError` → `erreur_parametres`). Correctif : `options.setdefault("id_execution", id_execution)` (et retrait d'`id_execution` des `FILTRES_OPTIONS`). *(Terminé le 15/10/2026 — correctif appliqué, retrait d'`id_execution` des `FILTRES_OPTIONS`, TU-B1/TU-B3 mis à jour + 2 nouveaux tests dans tests/unit/test_boucle.py ; suite complète 255 verts ; correctifs associés au tour précédent : clé `operateur` dans main.py et faute « plafoné » dans le prompt)*
- [X] **T5.2.1** : Tester le flux complet (recherche → inventaire → téléchargement). *(Terminé le 14/10/2026 — TI-14/TI-14b dans tests/unit/test_integration.py : flux nominal avec exclusion licence + ressource hors chaîne refusée ; flux complet nominal mocké déjà couvert par TI-05 ; validation réelle en mode chat à passer en local, recoupe TB-04)*

- [X] **T5.2.2** : Valider la persistance du registre des sources inaccessibles. *(Terminé le 14/10/2026 — TI-15/TI-15b/TI-15c : rechargement intégral entre instances, enrichissement cumulatif sans altération, re-test d'entrée technique non bloquant ; persistance confirmée, aucun défaut trouvé)*

  - [X] Commande `search` : Appelle `rechercher_jeux`. *(Livrée le 13/10/2026 — T4.1/T4.2)*

  - [X] Commande `list` : Appelle `lister_ressources`. *(Livrée le 13/10/2026 — avec T3.2.1)*

  - [X] Commande `query` : Appelle `interroger_ressource`. *(Livrée le 14/10/2026 — avec T4.1/T4.2, gardes CLI filtre/tri)*

  - [X] Commande `download` : Appelle `telecharger_brut`. *(Livrée le 14/10/2026 — avec T4.1/T4.2)*

  - [X] **T4.3** : Commande `chat` : point d'entrée agentique grand public — un prompt libre en argument ; crée l'agent (T5.3.1), conduit la conversation (T5.3.2), journalise (T5.3.3), détruit l'agent, affiche la synthèse finale et le chemin du journal. Options : `--plafond`, `--id-execution`, `--json`. *(Terminé le 14/10/2026 — 7 tests CLI TU-E1..E7, documentation d'utilisation dans docs/README.md, destruction garantie par finally)*

- [X] **T5.1.5** : Tester les formats non tabulaires (ZIP, GeoJSON, etc.). *(Terminé le 14/10/2026 — chaînage inventaire → telecharger_brut → persistance pour ZIP/GeoJSON/JSON/SHP/PDF, TU-40..46 (renumérotation section 3.9 du plan), 9 tests ; TI-11/TI-12 réels à passer en local)*

- [X] **T5.3.4** : Rédiger le prompt système : consignes de reformulation (A1), sélection (A2), tranchage des indéterminations (A3), synthèse du registre (A4), pagination et plafond d'invocations. *(Terminé le 14/10/2026 — prompt structuré s1–s8 (~750 mots) dans src/agent/agent.py, 4 tests de contenu TU-D1..D4 ; évaluation des propriétés TA sur journaux réels à venir en local)*

- [X] **T5.3.3** : Journaliser les conversations (arguments, résultats, raisonnements) pour les tests TA et l'audit. *(Terminé le 14/10/2026 — src/agent/journal.py, JSONL journaux/<id>/conversation.jsonl, rejeu extraire_invocations, 8 TU)*

- [X] **T5.3.2** : Implémenter la boucle de conversation : envoi du message utilisateur, réception et exécution des `tool_calls` vers les fonctions du cœur, renvoi des résultats normalisés (`src/agent/boucle.py`). *(Terminé le 14/10/2026 — dispatch src/agent/outils.py, plafond 10 configurable, journalisation sans blocage TA-02, 12 TU ; test réel validé en local par le concepteur)*

- [X] **T5.3.1** : Créer (et détruire) l'agent Mistral : prompt système (minimal, enrichi en T5.3.4), choix du modèle, définition des outils (`src/agent/agent.py`). *(Terminé le 14/10/2026 — agent éphémère via client.beta.agents, garde-fou MISTRAL_AGENT_ID, 18 TU ; test réel validé en local par le concepteur)*

- [X] **T4.1** : Créer la CLI avec Typer (`src/main.py`). *(Terminé le 14/10/2026 — commandes search, list, query, download livrées et testées)*

- [X] **T4.2** : Configurer les arguments et options pour chaque commande. *(Terminé le 14/10/2026 — gardes CLI filtre/tri ajoutées sur query, codes de sortie 0/1/2)*

- [X] **T6.2** : Ajouter des logs pour chaque étape du flux. *(Terminé le 14/10/2026 — recherche, inventaire, interroger, télécharger, HTTP, registre couverts (src/core/*.py, src/utils/*.py), plus les événements agentiques de src/agent/ ; kanban non tenu à jour lors de T3.3/T3.4)*

- [X] **T5.1.3** : Écrire les tests pour `interroger_ressource` (`tests/unit/test_query.py`). *(Terminé le 13/10/2026 — livrés avec T3.3.x, kanban non tenu à jour)*

- [X] **T5.1.4** : Écrire les tests pour `telecharger_brut` (`tests/unit/test_download.py`). *(Terminé le 13/10/2026 — livrés avec T3.4.x, kanban non tenu à jour)*

- [X] **T3.3.2** : Gérer la pagination, le filtrage et le tri. *(Termine le 13/10/2026 - traductions livrees avec T3.3.1 ; consolide : page_suivante (contrat v1.1.0), erreur actionnable colonne inexistante)*
- [X] **T3.3.3** : Retourner une recommandation pour les volumes élevés. *(Termine le 13/10/2026 - livree avec T3.3.1, revue formelle conclurante : seuil 5000 configurable, TI-09 en trois volets)*

- [X] **T3.3.1** : Implémenter l'appel à l'API tabulaire (`src/core/query.py`). *(Termine le 13/10/2026 - API sondée en réel au préalable, détection api_tabulaire incluse, max taille_page 50, validé en réel : films CNC avec filtre et tri)*

- [X] **T3.4.3** : Gérer les échecs techniques et consigner dans le registre. *(Termine le 13/10/2026 - TI-08 passe, motif serveur_origine_bloque statu quo, organisation reportee)*

- [X] **T3.4.2** : Stocker les fichiers dans `data/raw/<id_execution>/` (`src/utils/storage.py`). *(Termine le 13/10/2026 - nommage et arborescence livres avec T3.4.1, collisions par suffixe numerique ajoutees)*

- [X] **T3.4.1** : Implémenter le téléchargement des fichiers (`src/core/download.py`). *(Termine le 13/10/2026 - TI-05..07 passes, ecriture atomique, valide en reel depuis la sandbox : CSV 4,3 Mo via API Insee)*

- [X] **T6.1** : Configurer `structlog` pour tracer les appels et les erreurs. *(Terminé le 13/10/2026 — configure_logging/log_to_file/bind_context, TU-29 à TU-32, utilisé par tous les modules)*
- [X] **T5.1.1** : Écrire les tests pour `rechercher_jeux` (`tests/unit/test_search.py`). *(Terminé le 13/10/2026 — TU-12, TU-14, TU-17, invariants licence/registre, pagination)*
- [X] **T5.1.2** : Écrire les tests pour `lister_ressources` (`tests/unit/test_resources.py`). *(Terminé le 13/10/2026 — TI-01, TI-02, TU-37, cohérence indétermination)*

- [X] **T3.2.3** : Identifier les ressources ambiguës (`indetermination`). *(Termine le 13/10/2026 - semantique actee : contradictoire tranche par priorite, inconnu seulement -> indetermine ; autoportance A3 verrouillee)*

- [X] **T3.2.2** : Classifier les ressources (tabulaire, autre format, etc.). *(Termine le 13/10/2026 - TU-05..11 passes, ordre HTML > API > tabulaire > autre, valide en reel depuis la sandbox)*

- [X] **T3.2.1** : Implémenter l'appel HTTP pour lister les ressources d'un jeu (`src/core/resources.py`). *(Termine le 13/10/2026 - inventaire valide en reel depuis la sandbox, classification T3.2.2 restant a livrer)*

- [X] **T3.1.5** : Ajouter la pagination a `rechercher_jeux` (argument `page`, exposer `page_suivante`/`page_courante` dans la reponse) pour permettre a l'agent d'evaluer tous les jeux trouves. *(Termine le 13/10/2026 - contrat v1.1.0, valide en reel depuis la sandbox)*

- [X] **T3.1.1** : Implémenter l'appel HTTP à l'API data.gouv.fr (`src/utils/http.py`). *(Terminé le 13/10/2026 — API v1, TB-01/TB-03 non passés dans la sandbox, à exécuter en local)*
- [X] **T3.1.2** : Appliquer le filtre de licence (`src/core/search.py`). *(Terminé le 13/10/2026 — politique v1 : lov2, fr-lo, odc-odbl, cc-by, cc-by-sa, cc-zero, other-open)*
- [X] **T3.1.3** : Consigner les exclusions de licence dans le registre (`src/utils/registry.py`). *(Terminé le 13/10/2026)*
- [X] **T3.1.4** : Retourner les résultats au format normalisé (statut/message/données). *(Terminé le 13/10/2026)*
- [X] **T1.1** : Créer la structure des dossiers (`src/`, `tests/`, `src/contracts/`, `src/core/`, `src/utils/`). *(Terminé le 10/10/2026)*
- [X] **T1.2** : Configurer le fichier `.env` avec les variables d'environnement (ex : `DATA_GOUV_API_URL`). *(Terminé le 10/10/2026)*
- [X] **T1.3** : Initialiser le logging avec `structlog` (`src/utils/logging.py`). *(Terminé le 10/10/2026)*
- [X] **T2.1** : Créer les schémas Pydantic pour les contrats (`src/contracts/`). *(Terminé le 12/10/2026)*
- [X] **T2.2** : Valider les schémas avec `jsonschema` pour les réponses de l'API data.gouv.fr. *(Terminé le 12/10/2026 — tests TB/TA non passés dans la sandbox, à exécuter en local)*