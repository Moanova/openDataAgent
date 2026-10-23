# Projet openDataAgent

Ce document suit l'avancement des tâches pour l'implémentation du projet **openDataAgent**. Il est organisé en **5 colonnes** :
- **À faire** : Tâches non commencées.
- **En cours** : Tâches en cours d'implémentation.
- **En revue** : Tâches prêtes pour une revue ou des tests.
- **Terminé** : Tâches validées.
- **Annulé** : Tâches abandonnées (remplacées par une solution existante ou rendues inutiles).

> Nota de traçabilité : la partie agentique Mistral est une partie d'implémentation à part entière, pas une sous-partie de tests ; les identifiants de tâches (T5.3.x, T5.1.x, T5.2.x) sont conservés inchangés pour la traçabilité avec `tests/plan_tests.md`, `docs/tasks/` et `SESSIONS.md`.


---

# Tableau du kanban

## À faire
T7.3 (optionnel)
T7.4 (à traiter dans la version 2 du projet)
T7.6 (optionnel ou à traiter dans la version 2 du projet)
T10.6 (optionnel)
T10.9 (optionnel ou à traiter dans la version 2 du projet)
T11.2 (optionnel ou à traiter dans la version 2 du projet)
T13.4


## En cours
T10.1


## En revue
T11.4


## Terminé
T1.1
T1.2
T1.3
T2.1
T2.2
T3.1.1
T3.1.2
T3.1.3
T3.1.4
T3.1.5
T3.2.1
T3.2.2
T3.2.3
T3.3.1
T3.3.2
T3.3.3
T3.4.1
T3.4.2
T3.4.3
T4.1
T4.2
T4.3
T5.1.1
T5.1.2
T5.1.3
T5.1.4
T5.1.5
T5.2.1
T5.2.2
T5.3.1
T5.3.2
T5.3.3
T5.3.4
T6.1
T6.2
T7.1
T7.2
T7.5
T7.7
T10.2
T10.3
T10.4
T10.5
T10.7
T10.8
T11.1
T11.3
T13.2
T13.3


## Annulé
T13.1


---

# Description des tâches

> Tâches triées par ordre numérique d'identifiant. L'état d'avancement de chaque tâche est indiqué dans le tableau ci-dessus.


## T1.1 — Initialisation du projet
Créer la structure des dossiers (`src/`, `tests/`, `src/contracts/`, `src/core/`, `src/utils/`). *(Terminé le 10/10/2026)*


## T1.2 — Initialisation du projet
Configurer le fichier `.env` avec les variables d'environnement (ex : `DATA_GOUV_API_URL`). *(Terminé le 10/10/2026)*


## T1.3 — Initialisation du projet
Initialiser le logging avec `structlog` (`src/utils/logging.py`). *(Terminé le 10/10/2026)*


## T2.1 — Implémentation des contrats
Créer les schémas Pydantic pour les contrats (`src/contracts/`). *(Terminé le 12/10/2026)*


## T2.2 — Implémentation des contrats
Valider les schémas avec `jsonschema` pour les réponses de l'API data.gouv.fr. *(Terminé le 12/10/2026 — tests TB/TA non passés dans la sandbox, à exécuter en local)*


## T3.1.1 — Recherche de jeux (`rechercher_jeux`)
Implémenter l'appel HTTP à l'API data.gouv.fr (`src/utils/http.py`). *(Terminé le 13/10/2026 — API v1, TB-01/TB-03 non passés dans la sandbox, à exécuter en local)*


## T3.1.2 — Recherche de jeux (`rechercher_jeux`)
Appliquer le filtre de licence (`src/core/search.py`). *(Terminé le 13/10/2026 — politique v1 : lov2, fr-lo, odc-odbl, cc-by, cc-by-sa, cc-zero, other-open)*


## T3.1.3 — Recherche de jeux (`rechercher_jeux`)
Consigner les exclusions de licence dans le registre (`src/utils/registry.py`). *(Terminé le 13/10/2026)*


## T3.1.4 — Recherche de jeux (`rechercher_jeux`)
Retourner les résultats au format normalisé (statut/message/données). *(Terminé le 13/10/2026)*


## T3.1.5 — Recherche de jeux (`rechercher_jeux`)
Ajouter la pagination à `rechercher_jeux` (argument `page`, exposer `page_suivante`/`page_courante` dans la réponse) pour permettre à l'agent d'évaluer tous les jeux trouvés. *(Terminé le 13/10/2026 — contrat v1.1.0, validé en réel depuis la sandbox)*


## T3.2.1 — Inventaire des ressources (`lister_ressources`)
Implémenter l'appel HTTP pour lister les ressources d'un jeu (`src/core/resources.py`). *(Terminé le 13/10/2026 — inventaire validé en réel depuis la sandbox, classification T3.2.2 restant à livrer)*


## T3.2.2 — Inventaire des ressources (`lister_ressources`)
Classifier les ressources (tabulaire, autre format, etc.). *(Terminé le 13/10/2026 — TU-05..11 passés, ordre HTML > API > tabulaire > autre, validé en réel depuis la sandbox)*


## T3.2.3 — Inventaire des ressources (`lister_ressources`)
Identifier les ressources ambiguës (`indetermination`). *(Terminé le 13/10/2026 — sémantique actée : contradictoire tranché par priorité, inconnu seulement → indéterminé ; autoportance A3 verrouillée)*


## T3.3.1 — Interrogation des ressources (`interroger_ressource`)
Implémenter l'appel à l'API tabulaire (`src/core/query.py`). *(Terminé le 13/10/2026 — API sondée en réel au préalable, détection api_tabulaire incluse, max taille_page 50, validé en réel : films CNC avec filtre et tri)*


## T3.3.2 — Interrogation des ressources (`interroger_ressource`)
Gérer la pagination, le filtrage et le tri. *(Terminé le 13/10/2026 — traductions livrées avec T3.3.1 ; consolide : page_suivante (contrat v1.1.0), erreur actionnable colonne inexistante)*


## T3.3.3 — Interrogation des ressources (`interroger_ressource`)
Retourner une recommandation pour les volumes élevés. *(Terminé le 13/10/2026 — livrée avec T3.3.1, revue formelle concluante : seuil 5000 configurable, TI-09 en trois volets)*


## T3.4.1 — Téléchargement brut (`telecharger_brut`)
Implémenter le téléchargement des fichiers (`src/core/download.py`). *(Terminé le 13/10/2026 — TI-05..07 passés, écriture atomique, validé en réel depuis la sandbox : CSV 4,3 Mo via API Insee)*


## T3.4.2 — Téléchargement brut (`telecharger_brut`)
Stocker les fichiers dans `data/raw/<id_execution>/` (`src/utils/storage.py`). *(Terminé le 13/10/2026 — nommage et arborescence livrés avec T3.4.1, collisions par suffixe numérique ajoutées)*


## T3.4.3 — Téléchargement brut (`telecharger_brut`)
Gérer les échecs techniques et consigner dans le registre. *(Terminé le 13/10/2026 — TI-08 passe, motif serveur_origine_bloque statu quo, organisation reportée)*


## T4.1 — Intégration et CLI
Créer la CLI avec Typer (`src/main.py`). *(Terminé le 14/10/2026 — commandes search, list, query, download livrées et testées)*


## T4.2 — Intégration et CLI
Configurer les arguments et options pour chaque commande. *(Terminé le 14/10/2026 — gardes CLI filtre/tri ajoutées sur query, codes de sortie 0/1/2)*


## T4.3 — Intégration et CLI
Commande `chat` : point d'entrée agentique grand public — un prompt libre en argument ; crée l'agent (T5.3.1), conduit la conversation (T5.3.2), journalise (T5.3.3), détruit l'agent, affiche la synthèse finale et le chemin du journal. Options : `--plafond`, `--id-execution`, `--json`. *(Terminé le 14/10/2026 — 7 tests CLI TU-E1..E7, documentation d'utilisation dans docs/README.md, destruction garantie par finally)*


## T5.1.1 — Tests unitaires
Écrire les tests pour `rechercher_jeux` (`tests/unit/test_search.py`). *(Terminé le 13/10/2026 — TU-12, TU-14, TU-17, invariants licence/registre, pagination)*


## T5.1.2 — Tests unitaires
Écrire les tests pour `lister_ressources` (`tests/unit/test_resources.py`). *(Terminé le 13/10/2026 — TI-01, TI-02, TU-37, cohérence indétermination)*


## T5.1.3 — Tests unitaires
Écrire les tests pour `interroger_ressource` (`tests/unit/test_query.py`). *(Terminé le 13/10/2026 — livrés avec T3.3.x, kanban non tenu à jour)*


## T5.1.4 — Tests unitaires
Écrire les tests pour `telecharger_brut` (`tests/unit/test_download.py`). *(Terminé le 13/10/2026 — livrés avec T3.4.x, kanban non tenu à jour)*


## T5.1.5 — Tests unitaires
Tester les formats non tabulaires (ZIP, GeoJSON, etc.). *(Terminé le 14/10/2026 — chaînage inventaire → telecharger_brut → persistance pour ZIP/GeoJSON/JSON/SHP/PDF, TU-40..46 (renumérotation section 3.9 du plan), 9 tests ; TI-11/TI-12 réels à passer en local)*


## T5.2.1 — Tests d'intégration
Tester le flux complet (recherche → inventaire → téléchargement). *(Terminé le 14/10/2026 — TI-14/TI-14b dans tests/unit/test_integration.py : flux nominal avec exclusion licence + ressource hors chaîne refusée ; flux complet nominal mocké déjà couvert par TI-05 ; validation réelle en mode chat à passer en local, recoupe TB-04)*


## T5.2.2 — Tests d'intégration
Valider la persistance du registre des sources inaccessibles. *(Terminé le 14/10/2026 — TI-15/TI-15b/TI-15c : rechargement intégral entre instances, enrichissement cumulatif sans altération, re-test d'entrée technique non bloquant ; persistance confirmée, aucun défaut trouvé)*


## T5.3.1 — Intégration agentique Mistral
Créer (et détruire) l'agent Mistral : prompt système (minimal, enrichi en T5.3.4), choix du modèle, définition des outils (`src/agent/agent.py`). *(Terminé le 14/10/2026 — agent éphémère via client.beta.agents, garde-fou MISTRAL_AGENT_ID, 18 TU ; test réel validé en local par le concepteur)*

*Contexte : l'agent Mistral porte les étapes A1 à A4 du flux (reformulation, sélection, tranchage des indéterminations, synthèse du registre) en s'appuyant sur les fonctions du cœur — c'est la raison d'être du projet.*


## T5.3.2 — Intégration agentique Mistral
Implémenter la boucle de conversation : envoi du message utilisateur, réception et exécution des `tool_calls` vers les fonctions du cœur, renvoi des résultats normalisés (`src/agent/boucle.py`). *(Terminé le 14/10/2026 — dispatch src/agent/outils.py, plafond 10 configurable, journalisation sans blocage TA-02, 12 TU ; test réel validé en local par le concepteur)*


## T5.3.3 — Intégration agentique Mistral
Journaliser les conversations (arguments, résultats, raisonnements) pour les tests TA et l'audit. *(Terminé le 14/10/2026 — src/agent/journal.py, JSONL journaux/<id>/conversation.jsonl, rejeu extraire_invocations, 8 TU)*


## T5.3.4 — Intégration agentique Mistral
Rédiger le prompt système : consignes de reformulation (A1), sélection (A2), tranchage des indéterminations (A3), synthèse du registre (A4), pagination et plafond d'invocations. *(Terminé le 14/10/2026 — prompt structuré s1–s8 (~750 mots) dans src/agent/agent.py, 4 tests de contenu TU-D1..D4 ; évaluation des propriétés TA sur journaux réels à venir en local)*


## T6.1 — Logging et journalisation
Configurer `structlog` pour tracer les appels et les erreurs. *(Terminé le 13/10/2026 — configure_logging/log_to_file/bind_context, TU-29 à TU-32, utilisé par tous les modules)*


## T6.2 — Logging et journalisation
Ajouter des logs pour chaque étape du flux. *(Terminé le 14/10/2026 — recherche, inventaire, interroger, télécharger, HTTP, registre couverts (src/core/*.py, src/utils/*.py), plus les événements agentiques de src/agent/ ; kanban non tenu à jour lors de T3.3/T3.4)*


## T7.1 — Améliorations (robustesse HTTP)
Mécanisme de réessai intelligent pour les échecs techniques — périmètre : client HTTP uniquement. *(E0..E7 implémentés : backoff exponentiel + jitter + `Retry-After` (`src/utils/http.py` `_delai_retry`), distinction statuts transitoires (429/502/503/504, retentés) / définitifs (400/401/403/410, jamais retentés, motif explicite), reprise `Range` sur `.part` + rattrapage coupure mid-stream, champ `nb_tentatives` dans les 4 contrats (rechercher_jeux 1.4.0, telecharger_brut/extraire_ressource/interroger_ressource 1.2.0), registre `statut_reprise` `a_retenter`/`definitif` (rétrocompatible) ; 416 tests verts (401 avant + TU-81..93, TI-19/20). Plan : `docs/tasks/T7.1_reessai_intelligent.md`. Hors périmètre : circuit breaker agentique (T7.7) — Terminé le 22/10/2026, validation réelle par le concepteur)*


## T7.2 — Améliorations (hygiène des exécutions)
Nettoyage automatique des anciennes exécutions — périmètre : les 4 familles de traces par `id_execution` (`data/raw/<id>/`, `data/executions/<id>/`, `conversations/<id>/`, `logs/openDataAgent_<id>.log`). *(E0..E7 implémentés : `src/core/nettoyage.py` (sélection par âge lu dans le préfixe date de l'id, fail-safe sur les noms non reconnus, exécution courante toujours protégée, registres globaux conservés), commande CLI `nettoyer` (`--age-jours` défaut 30, `--simulation`, `--json`, `--id-execution`), hook automatique au callback Typer activé uniquement par `NETTOYAGE_AUTO=1` (désactivé par défaut, `nettoyer` exclu du hook), traces du nettoyage en `log_to_file` (sortie `--json` propre) ; 429 tests verts (416 avant + TU-94..100, TI-21/22). Plan : `docs/tasks/T7.2_nettoyage_executions.md`. Hors périmètre : pas d'outil agent, aucun contrat modifié — Terminé le 22/10/2026, validation réelle par le concepteur)*


## T7.3 — Améliorations futures (optionnel)
Automatiser les tests agentiques.


## T7.4 — Améliorations futures (à traiter dans la version 2 du projet)
Supporter d'autres sources de données (ex : Eurostat, INSEE).


## T7.5 — Licence descriptif et attribution
Registre descriptif des licences et génération de mention d'attribution (`src/core/licences_descriptif.py`) :
- registre des propriétés par licence (attribution obligatoire, partage à l'identique, usage commercial), miroir de la politique documentée dans `docs/README.md` (section Politique de licence) ;
- `mention_attribution()` : génération de la mention prête à afficher à partir des métadonnées de l'inventaire (organisation, licence, date de mise à jour) ;
- prédicats de compatibilité pour la partie 2 (ex. produit dérivé sous licence permissive autorisé ou non) ;
- échec propre sur licence inconnue et sur `other-open`/`other-attribution`/`other-pd` (propriétés à vérifier, jamais devinées) ;
- branchement optionnel sur `telecharger_brut` (champ `mention_attribution` dans la réponse, évolution de contrat à versionner) : à décider séparément ;
- **Chantier A (préalable) ✅** : référentiel de licences élargi au filtre complet du site (`odc-by`, `odc-pddl`, `other-attribution`, `other-pd` ajoutées) + règle sécurisée `notspecified` acceptée pour un producteur public uniquement + politique paramétrée dans `config/politique_licences.json` (une clé par source, préparation T7.4). Voir `docs/tasks/T7.5_licences_descriptif.md` ;
- **Chantier B ✅** : type d'organisation résolu via les badges uData du payload de recherche (`public-service`/`local-authority`) ; marquage `licence_conditionnelle` + compteur dans la réponse ; registre dédié aux acceptations conditionnelles (`data/registre_acceptations.json`), sémantique du registre des sources inaccessibles préservée. Voir `docs/tasks/T7.5_licences_descriptif.md`. *(Terminé le 18/10/2026 — validé en local par le concepteur ; 351 tests verts)*

*Contexte : cette tâche prépare la partie 2 du projet (exploitation et visualisation des données) : l'usage légitime des données acquises dépend des obligations propres à chaque licence (attribution, partage à l'identique). La politique d'acquisition (`src/core/licence.py`) est terminée et ne dépend pas de ces travaux.*


## T7.6 *(optionnel ou à traiter dans la version 2 du projet)*
Enrichir l'acquisition avec les descriptions — consigner, lors de l'acquisition d'une ressource, le contenu du champ `description` du jeu (fiche dataset, Markdown) et le champ `description` de la ressource acquise (présent sur ~51 % des ressources ; sondage du 22/10/2026, synthèse dans SESSIONS.md). Hors périmètre retenu : ressources `type=documentation`, schémas déclaratifs, liens externes de documentation, notice embarquée dans les fichiers.


## T7.7 — Améliorations (robustesse agentique)
Circuit breaker agentique par hôte — après 3 échecs transitoires consécutifs (`motif=transitoire`, T7.1) vers un même hôte dans une conversation, cesser de le solliciter : interception **sans consommer le plafond d'invocations**, résultat `echec_technique`/`motif=circuit_ouvert`/`suggestion=proposer_alternative` renvoyé à l'agent, refroidissement 300 s (semi-ouvert), prompt A4 consigné. Périmètre : tous les hôtes (serveurs d'origine + API data.gouv.fr/tabulaire). État **en mémoire, attaché à la conversation** (option A actée 22/10/2026 : détruit à la clôture, aucun timer entre deux exécutions). Paramétrage : `CIRCUIT_BREAKER_SEUIL`, `CIRCUIT_BREAKER_REFROIDISSEMENT`, `CIRCUIT_BREAKER_DESACTIVE=1`. *(E0..E7 implémentés : `src/agent/circuit.py` (machine à états par hôte, horloge injectable), intégration `src/agent/boucle.py` (`ConversationServeur.circuit`, `_hote_cible` via inventaire/API tabulaire/API plateforme, interception gratuite + alimentation selon `motif`), champ `motif` exposé dans les 4 contrats (rechercher_jeux 1.5.0, telecharger_brut/extraire_ressource/interroger_ressource 1.3.0), prompt A4 ; 445 tests verts (429 avant + TU-101..108, TI-23/24). Plan : `docs/tasks/T7.7_circuit_breaker_agentique.md` — Terminé le 22/10/2026, validation réelle par le concepteur)*


## T10.1 — Mise à disposition des données vers la partie 2
Réaliser la mise à disposition des données vers la partie 2 (maillon B7 → P du schéma de conception, `docs/design/conception.mmd`). **Écart le plus structurel** : en l'état, seule la voie 2 (téléchargement brut) matérialise les données sur disque ; la voie 1 (extraction via API tabulaire) ne persiste rien (exploration conversationnelle uniquement) et aucune normalisation commune B7 n'existe dans le code. Chantiers : persistance des extractions tabulaires (ex. export paginé vers `data/raw/`) et pipeline de normalisation commun aux deux voies. Évolution de contrat probable (v1.2.0, ex. option `destination` sur `interroger_ressource` ou nouvel outil). *(En cours — périmètre précisé : cette entrée porte le chantier 2, pipeline de normalisation commun B7 aux deux voies ; le chantier 1, persistance des extractions de la voie 1, est séparé dans T10.7 ; séquence : T10.7 puis T10.1)*


## T10.2 — Séance d'appropriation du 14/10/2026 (chantiers identifiés)
Inventaire persistant par `id_execution` — évolution « inventaire persistant » évoquée le 14/10 mais non créée ; le concepteur juge le choix actuel trop limitatif : `--id-execution` des commandes manuelles n'a qu'un rôle de trace, aucun chaînage manuel (list puis download) n'est possible. Design acté en séance : persistance côté CLI uniquement (`data/executions/<id_execution>/inventaire.json`), méthodes de sérialisation additives sur l'inventaire (`src/core/resources.py`), chargement/sauvegarde dans le callback Typer, enrichissement cumulatif, mode agentique et cœur inchangés (TI-14b reste vert). Précision de la convention 1 du contrat global (« jamais vu par le flux d'exécution courant ») ; réécriture de la section « piège list→download » du README (limite → fonctionnalité). Lié à T7.2. *(Terminé le 15/10/2026 — sérialisation additive decharger/charger dans resources.py, persistance CLI data/executions/<id>/inventaire.json, chaînage list→download fonctionnel, id d'exécution affiché, convention 1 précisée, README réécrit ; 4 nouveaux tests ; 267 verts)*


## T10.3 — Séance d'appropriation du 14/10/2026 (chantiers identifiés)
Corriger le bug `id_execution` dans `executer_outil` (`src/agent/outils.py`) : le paramètre reçu de la boucle n'est pas injecté dans l'appel au cœur si l'agent ne le fournit pas ; et s'il le fournit, il entre en conflit avec celui de la boucle (`TypeError` → `erreur_parametres`). Correctif : `options.setdefault("id_execution", id_execution)` (et retrait d'`id_execution` des `FILTRES_OPTIONS`). *(Terminé le 15/10/2026 — correctif appliqué, retrait d'`id_execution` des `FILTRES_OPTIONS`, TU-B1/TU-B3 mis à jour + 2 nouveaux tests dans tests/unit/test_boucle.py ; suite complète 255 verts ; correctifs associés au tour précédent : clé `operateur` dans main.py et faute « plafoné » dans le prompt)*


## T10.4 — Séance d'appropriation du 14/10/2026 (chantiers identifiés)
Brancher la validation Pydantic des arguments d'outil au runtime : les modèles `Input/Output` de `src/contracts/` ne servaient qu'aux tests de cohérence (`valider_coherence_contrat`) ; la validation runtime des `tool_calls` reposait sur des lambdas superficielles (`ARGUMENTS_OBLIGATOIRES`). Divergence entre la docstring de `src/contracts/validation_api.py` (« les modèles Pydantic valident la couche sortante ») et le comportement réel. À acter : brancher `*.model_validate(arguments)` dans `executer_outil`, ou assumer la simplification et corriger la docstring. *(Terminé le 15/10/2026 — MODELES_INPUT branché dans executer_outil, extra="ignore" sur les 4 *Input, model_dump(exclude_unset=True), id_execution injecté après validation, docstring validation_api.py corrigée ; 5 nouveaux tests ; 263 verts)*


## T10.5 — Séance d'appropriation du 14/10/2026 (chantiers identifiés)
Déplacer les vocabulaires fermés de `main.py` vers le cœur (source unique de vérité) : `TRIS`, `OPERATEURS_FILTRE`, `ORDRES_TRI`, `FENETRES_MAJ` (éventuellement en `StrEnum`), importés par la CLI et le cœur ; constante ou option `--apercu N` pour le plafond d'affichage (5 lignes) de `query` ; dédupliquer le `help` de `--id-execution`. *(Terminé le 15/10/2026 — module src/core/vocabulaires.py (4 StrEnum + APERCU_DEFAUT), contrats et CLI branchés dessus, option --apercu sur query, aide --id-execution dédupliquée ; 3 nouveaux tests ; 263 verts au total avec T10.4)*


## T10.6 *(optionnel, si packaging/portage un jour)*
Nom de paquet générique `src` (collision/convention), `pyproject.toml` + point d'entrée console, externalisation des chemins relatifs au CWD (`data/`, `conversations/`, registre), `libmagic` sous Windows, chargement du `.env` explicite.

*Contexte : tâche issue de la séance d'appropriation du 14/10/2026 (soir) — relecture guidée du code avec le concepteur (questions/réponses sur Python, Typer, contrats, agent et logique applicative). Aucune modification de code effectuée à cette séance ; ces entrées formalisent les écarts et chantiers détectés.*


## T10.7 — Persistance des extractions de la voie 1
Persistance des extractions de la voie 1 (issu du chantier 1 de T10.1). En l'état, `interroger_ressource` retourne des pages à l'agent sans rien écrire sur disque (exploration conversationnelle uniquement) : les données sélectionnées ne sont jamais matérialisées via la voie 1. Chantier : extraction paginée vers `data/raw/` (nouveau module cœur `src/core/extraction.py`, réutilisant `interroger_ressource_api` et la logique `page_suivante`), plafond de sécurité (pages/lignes), accessible en mode manuel (commande CLI `extract`) **et** en mode agentique (évolution de contrat v1.2.0 à définir — exigence concepteur : les deux modes doivent pouvoir acquérir les données). Séquence : T10.7 avant T10.1 (normalisation B7). *(Terminé le 18/10/2026 — E1..E6 implémentées : fonction cœur `src/core/extraction.py`, contrat v1.2.0 (manifeste 1.1), dispatch agent (5ᵉ outil), commande CLI extract, tests et docs ; validé en local par le concepteur ; suite 351 verts)*


## T10.8 — Traçabilité des acquisitions (séance du 19/10/2026)
Manifeste d'acquisition par exécution — écriture au cœur, à chaque acquisition (`telecharger_brut` et `extraire_ressource`), d'une entrée dans `data/raw/<id_execution>/manifeste_acquisitions.json` : fichier, voie (téléchargement/extraction), id_ressource, id_jeu, titre du jeu, organisation, url du jeu, licence, licence_conditionnelle, mention_attribution, tronque, horodatage. Additif (aucune évolution de contrat, nommage des fichiers inchangé) ; fonctionne dans les deux modes (manuel et agentique) ; l'inventaire T10.2 et le journal conversation.jsonl restent inchangés — le manifeste est la source de vérité acquisition côté disque. Compléments : demande utilisateur en en-tête du manifeste (traçabilité complète), commande CLI `acquisitions` + `lister_acquisitions` (le manifeste exclu de `lister_fichiers` : ce n'est pas une donnée acquise). *(Terminé le 22/10/2026 — E0..E7 : 385 tests verts, TU-80 (régression WinError 183, correctif E8b via `os.replace`) ; validation réelle par le concepteur : scénario agentique complet via T11.1 E8 (conversation 5 tours, 3 acquisitions, manifeste conforme) + scénario manuel `download`/`acquisitions` ; suivi dans `docs/tasks/T10.8_manifeste_acquisitions.md`)*

*Contexte : issu du constat de la validation T11.3 : en mode agentique, rien ne relie simplement un fichier de `data/raw/<id_execution>/` au jeu de données correspondant (l'inventaire persistant T10.2 n'est écrit que par les commandes CLI ; en mode `chat`, l'inventaire vit en mémoire et disparaît). Préparation directe de T10.1 (normalisation B7 : la partie 2 doit consommer fichier + jeu + licence + mention d'attribution).*


## T10.9 *(optionnel ou à traiter dans la version 2 du projet, préfiguration — prévision partie 2 ; sans précision pour le moment, prise de date séance 22/10/2026)*
Organiser la configuration des dossiers de journalisation, de conversations et de stockage des ressources acquises, et le packaging de l'application. Périmètre à définir : centraliser les racines (`logs/`, `conversations/`, `data/raw/`, `data/executions/`) derrière une configuration unique (chemins relatifs au CWD aujourd'hui, en dur dans `src/utils/logging.py`, `src/agent/journal.py`, `src/utils/storage.py`, `src/core/manifeste.py`, `src/main.py`), rendre les chemins configurables (env/fichier de config), et préparer le packaging (`pyproject.toml`, point d'entrée console, nom de paquet — cf. T10.6).


## T11.1 — Mode conversationnel multi-tours
Mode conversationnel multi-tours (`chat`) — REPL, contexte côté serveur (API Conversations), propose-puis-acquiert, plafond par tour, clôture `stop`, journal multi-tours. *(Terminé le 20/10/2026 — E0..E7 + E8a/E8b : 401 tests verts ; validation réelle par le concepteur en 2 runs (conversation complète jusqu'à l'acquisition de 3 ressources) ; correctifs post-test : reconstitution des `function.call.delta` fragmentés (E8a), écriture atomique du manifeste en `os.replace` (E8b) ; décisions dans `docs/design/decisions_conception.md`, suivi dans `docs/tasks/T11.1_chat_multi_tours.md`)*

*Contexte : issu de la séance du 18/10/2026 (retours d'usage du concepteur sur le flux agentique) — l'arbitrage final de pertinence doit pouvoir se faire pendant la conversation, pas seulement après l'acquisition.*


## T11.2 — Recherche par producteur *(optionnel ou à traiter dans la version 2 du projet)*
Outil `rechercher_organisations` + filtre organisation sur `rechercher_jeux` (issu du constat des traces du 18/10/2026 : l'agent a consacré 3 invocations à chercher « Ministère de l'Intérieur » en mots-clés, sans succès — il n'existe aucun moyen direct de cibler un producteur). Chantier :
- fonction cœur de recherche d'organisations par nom (endpoint `/api/1/organizations/`, déjà sondé — pagination, nom, slug, id, badges) ;
- filtre optionnel `organisation` (id ou slug) sur `rechercher_jeux` (paramètre supporté par l'API v1) — évolution de contrat (v1.2.0 → v1.3.0) ;
- prompt A1 : consigne d'utiliser le filtre producteur quand la portée demandée implique un producteur identifié ;
- question associée à instruire : migration de la recherche v1 → v2 (moteur du site, pertinence très supérieure constatée sur le cas « élections présidentielles » ; SESSIONS.md ligne 128 : bascule envisagée puis ajournée, le choix v1 était un arbitrage de cohérence docs/code, pas un choix de pertinence — à réévaluer au vu des constats du 18/10, idéalement via un adaptateur par source en perspective de T7.4).

*Contexte : issu de la séance du 18/10/2026 (retours d'usage du concepteur sur le flux agentique).*


## T11.3 — Migration API v1 → v2
Migration de l'API data.gouv.fr v1 → v2 pour la recherche et l'inventaire (décision concepteur du 18/10/2026 : bascule pleine v2, pas d'adaptateur — l'adaptateur par source n'aura de sens qu'avec T7.4). Contexte : le moteur v2 est celui du site (pertinence très supérieure constatée sur « élections présidentielles » : jeux du Ministère de l'Intérieur en tête vs jeux communaux en v1 ; total 235 vs 41) ; le choix v1 historique était un arbitrage de cohérence docs/code, pas de pertinence (SESSIONS.md, séance du 13/10). Périmètre :
- **S11.0 sondage préalable ✅** : cartographie champ par champ v1/v2 réalisée en réel (`/api/2/datasets/search/`, détail, ressources paginées, tri, fenêtre, `last_modified` vs `last_update`, badges `organization` confirmés identiques — chantier B T7.5 intact), fixtures v2 réelles capturées dans `tests/fixtures/api_v2/`, API tabulaire vérifiée intacte (ping 200 sur CSV indexé). Constats clés : cas étalon « élections présidentielles » confirmé en v2 (Ministère de l'Intérieur en tête de page 1, total 235) ; `last_update_range` rejeté en v2 (décision à trancher : déprécier le paramètre `fenetre_maj`) ; `resources` en sous-ressource paginée (second appel requis pour l'inventaire) ; pagination au-delà du total → 400 (s'arrêter sur `next_page` absent). Voir `docs/tasks/T11.3_sondage_S11.0.md` ;
- `src/utils/http.py` : URL base, `rechercher_jeux_api`, `lister_ressources_api` (attention : `resources` en sous-ressource paginée en v2 — impact sur l'inventaire) ;
- schémas jsonschema `contrats/schemas_api/*.reponse.json` (recherche + inventaire) réécrits sur la v2 ;
- fixtures `tests/fixtures/api/` re-capturées en réel sur la v2 ;
- normalisation : mapping `derniere_maj` (v1 `last_modified` → v2 `last_update`) dans la couche HTTP/core ; filtre de licence et badges attendus sans changement (même modèle `organization`) — à vérifier en priorité (chantier B T7.5) ;
- docs d'architecture mises à jour ; aucune évolution des sorties normalisées attendue (l'isolant statut/message/donnees absorbe le changement) ;
- validation en réel : TB-01 rejoué + cas étalon « élections présidentielles » (le jeu du Ministère de l'Intérieur doit apparaître en page 1). *(Terminé le 19/10/2026 — E1..E8 : bascule pleine v2, fenetre_maj déprécié (contrat v1.3.0), inventaire en sous-ressource reconstituée, mapping derniere_maj ← last_update ; 361 puis 366 tests verts ; validation en réel par le concepteur : cas étalon satisfait — jeux du Ministère de l'Intérieur en page 1, les 2 tours 2022 acquis ; correctifs post-validation : .env v1, verrou A4 anti-hallucination, consigne A3 ressource non indexée, prompt externalisé dans config/prompt_systeme.txt)*


## T11.4 — Outil agentique `consulter_registre`
Nouvel outil agentique `consulter_registre` — branchement de `rapport_pour_agent()` (RegistreSourcesInaccessibles) dans la boucle agentique, **option B** (outil de lecture invoqué par l'agent quand il en a besoin, pas d'injection dans le contexte). Contexte : le registre (`data/registry.json`) est alimenté par le code et persiste entre les exécutions (T7.2 le conserve), mais l'agent ne le lit jamais aujourd'hui — il ne connaît que les échecs de la conversation en cours (constat séance 22/10/2026, SESSIONS.md). Apports : mémoire cross-session (ne pas retenter une source déjà refusée définitivement), exploitation du champ `statut_reprise` `a_retenter`/`definitif` (T7.1), synthèse finale A4 exhaustive et fidèle (le contrat global prévoit déjà cette lecture « en fin de flux »). Chantier : fonction cœur de lecture (rapport limité/filtrable pour maîtriser la taille — ex. dernières N entrées ou filtre par motif), nouveau contrat JSON + entrée `contrats/manifeste.json` (version 1.0.0), enregistrement dans `TABLE_OUTILS`, consigne prompt A4 (quand consulter : doute sur une source, synthèse finale), tests TU/TI, docs. Frontière code/agent respectée : l'agent décide, le code ne fait que lire. *(En cours depuis le 22/10/2026 — choisie par le concepteur comme prochaine tâche, avant la reprise de T10.1. E0..E7 implémentés : contrat v1.0.0 + manifeste 1.2, fonction cœur `src/core/registre.py`, dispatch agent, consigne prompt A4, TU-114..119 + TI-25/26 ; 466 tests verts (451 avant + 15) ; En revue depuis le 22/10/2026 — validation en réel par le concepteur en cours)*


## T13.1 — Confort d'utilisation de la CLI (séance du 22/10/2026)
~~Aide `--help` sur chaque commande~~ *(Annulée le 22/10/2026 — Typer/Click fournit déjà `--help` nativement sur chaque commande, suffisant tel quel ; testé et validé par le concepteur. T13.2 conservée.)*


## T13.2 — Confort d'utilisation de la CLI (séance du 22/10/2026)
Option silencieuse `--quiet` — masque les logs applicatifs `[info]`/`[error]` console ; les résultats/erreurs de commande restent affichés et le **fichier de logs reste écrit**. *(Terminé le 22/10/2026 — validation réelle par le concepteur : `--quiet search ...` console épurée, résultat visible, log fichier écrit ; implémentée : `configure_logging(silencieux=...)` avec `NullHandler` sur le logger racine (`src/utils/logging.py`), option globale `--quiet` au callback Typer transmise via le wrapper `_configurer_logging` (7 commandes), warning du hook de nettoyage T7.2 masqué en quiet, correctifs de robustesse (fermeture du fichier de logs précédent, `log_to_file` défensif) ; 451 tests verts (445 avant + TU-109..113). Suivi : `docs/tasks/T13.2_option_quiet.md`)*


## T13.3 — Réalignement linguistique de la CLI (séance du 22/10/2026)
Francisation des commandes et options de la CLI, avec conservation des alias anglais pour la rétrocompatibilité (décisions concepteur du 22/10/2026) :
- **Commandes** : `search`→`rechercher`, `list`→`lister`, `download`→`telecharger`, `extract`→`extraire`, `query`→`interroger`, `chat`→`demander`. Alias anglais conservés : `search`, `list`, `download`, `extract`, `query`, **`ask`** (nouveau, alias de `demander` — `chat` étant remplacé par `ask` pour cohérence), **`chat`** (alias historique conservé).
- **Option de journalisation** : `--quiet`→`--silencieux`, alias `--quiet` conservé.
- **Vocabulaire** : `recent` et `indetermine` conservés en l'état (décision concepteur : « récent » sans accent est aligné avec la convention de nommage en minuscules sans accent).
- **Manifeste** : champ `generé_le`→`genere_le` (convention contrat_global : minuscules sans accent).
- Alias = commandes Typer à part entière (même signature, délégation vers la commande française) : l'alias accepte les mêmes arguments et options.
- Périmètre : `src/main.py`, `src/core/manifeste.py`, tests (`test_cli.py`, `test_manifeste.py`), docs (`docs/README.md`, `docs/specs/stockage.md`, `contrat_global.md` convention 5, suivis T13.2/T10.8).
*(En cours depuis le 22/10/2026 — implémentée : E1..E4 + TU-120..123 ; 470 tests verts (466 avant + 4) ; En revue du 22/10 au 23/10/2026 — **validée en réel par le concepteur**, passée en Terminé le 23/10/2026)*


## T13.4 — Réalignement linguistique des modules internes (séance du 23/10/2026)
Francisation des derniers modules nommés en anglais dans `src/core/` et `src/utils/`, dans la continuité de T13.3 (convention contrat_global : code en français). Aucun impact fonctionnel ni sur les contrats exposés (noms d'outils agent, statuts, champs JSON, CLI inchangés).

- **Renommage des modules** (tableau de correspondance) :
  - `src/core/search.py` → `src/core/recherche.py`
  - `src/core/download.py` → `src/core/telechargement.py`
  - `src/core/query.py` → `src/core/interrogation.py`
  - `src/utils/logging.py` → `src/utils/journalisation.py` *(prioritaire : même nom que le module stdlib `logging`, risque de shadowing latent)*
  - `src/utils/registry.py` → `src/utils/registre_sources.py` *(évite le doublon avec `src/core/registre.py` de T11.4)*
  - `src/utils/storage.py` → `src/utils/stockage.py`
- **Renommage des fichiers de tests associés** (correspondance 1:1) : `test_search.py`→`test_recherche.py`, `test_download.py`→`test_telechargement.py`, `test_query.py`→`test_interrogation.py`, `test_logging.py`→`test_journalisation.py`, `test_registry.py`→`test_registre_sources.py`.
- **Renommage du fichier de données** (décision concepteur du 23/10/2026 : en dev, pas de perte) : `data/registry.json` → `data/registre_sources.json`.
- **Points de vigilance** :
  - ~113 références d'imports à mettre à jour dans `src/` et `tests/` (recherches `core.search`, `core.download`, `core.query`, `utils.logging`, `utils.registry`, `utils.storage`) ;
  - chemin par défaut du registre : `src/utils/registry.py` (`Path("data/registry.json")`) et mentions dans `src/core/registre.py`, `src/core/search.py`, `src/core/download.py`, `src/core/resources.py`, `src/core/nettoyage.py` (docstring) ;
  - nettoyage : TU-98 teste la conservation de `data/registry.json` — le nouveau nom `registre_sources.json` doit rester exclu du périmètre de suppression (vérifier la liste des noms reconnus dans `src/core/nettoyage.py` et mettre à jour le test) ;
  - noms de loggers (`get_logger("openDataAgent.utils.registry")` etc.) à réaligner ;
  - mentions de `data/registry.json` dans le contrat `contrats/consulter_registre.json` (description), `config/prompt_systeme.txt` (consigne A4), `docs/specs/registre.md`, `docs/specs/stockage.md`, `docs/README.md`, `docs/design/decisions_conception.md`, `tests/plan_tests.md` (TU-98) ;
  - tests utilisant des chemins temporaires `tmp_path / "registry.json"` à renommer pour cohérence (non bloquant mais recommandé).
- **Hors périmètre** : noms d'outils agent (`rechercher_jeux`, `consulter_registre`, …), statuts et motifs, champs des contrats JSON, `data/registre_acceptations.json` (déjà en français), arborescence `data/` au-delà du registre, variables d'environnement.
- **Validation** : suite complète `pytest tests/unit` verte après renommage (470 tests avant la tâche).


## Commande `search` — Intégration et CLI
Appelle `rechercher_jeux`. *(Livrée le 13/10/2026 — T4.1/T4.2)*


## Commande `list` — Intégration et CLI
Appelle `lister_ressources`. *(Livrée le 13/10/2026 — avec T3.2.1)*


## Commande `query` — Intégration et CLI
Appelle `interroger_ressource`. *(Livrée le 14/10/2026 — avec T4.1/T4.2, gardes CLI filtre/tri)*


## Commande `download` — Intégration et CLI
Appelle `telecharger_brut`. *(Livrée le 14/10/2026 — avec T4.1/T4.2)*


## Prompt A1/A2 (préalable, séance du 18/10/2026)
Règle générique sur les qualificatifs de portée (géographique, temporelle, juridique) — ils expriment un critère de sélection, pas de recherche ; vérification à l'étape A2 de la cohérence portée demandée / organisation productrice (une mairie ne produit pas de données nationales). Cas de test : « résultats nationaux des élections présidentielles » doit retenir un producteur national, pas une commune. *(Terminé le 18/10/2026 — consigne dans `config/prompt_systeme.txt`, commit `ea89453` ; déplacé en Terminé le 22/10/2026 lors de la revue du kanban)*
