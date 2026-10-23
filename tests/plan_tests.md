# Plan de tests — Partie 1 du flux : acquisition data.gouv.fr

## 1. Objet et périmètre

Ce plan décrit la stratégie de vérification de la partie 1 du flux (recherche, sélection, acquisition, registre), couvrant les composants algorithmiques, les contrats de function calling et les étapes agentiques. Il s'appuie sur la pyramide de tests : base large de tests unitaires sans réseau, couche d'intégration entre composants internes, sommet restreint de tests de bout en bout, plus une couche transversale de tests de contrat.

Chaque test est identifié (TU, TI, TB, TC, TA), rattaché au critère d'acceptabilité qu'il vérifie (CA-x, voir le document Critères d'acceptabilité), et associé à un niveau de blocage : bloquant ou avertissement.

## 2. Outillage et conventions

- Cadriciel : pytest, avec fixtures pour les composants partagés (client simulé, registre temporaire).
- Simulation HTTP : responses ou requests-mock pour les tests sans réseau ; enregistrements de réponses réelles comme fixtures (cassette).
- Marqueur réseau : `@pytest.mark.reseau` pour tous les tests nécessitant un accès extérieur ; ces tests sont exclus de l'exécution par défaut et exécutés lors des validations complètes.
- Journaux : toute conversation agentique est journalisée (arguments, résultats) dans un répertoire de traces ; ces journaux servent aux tests de propriétés (TA).
- Exigences : chaque invariant déclaré dans la documentation des contrats (`docs/*.md`) doit être couvert par au moins un test de ce plan.

## 3. Niveau 1 — Tests unitaires (TU)

Tests isolés, sans réseau. La couche HTTP est simulée.

### 3.1 Filtre de licence

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-01 | licence_est_acceptable pour chaque licence acceptée (etalab-2.0, odc-odbl, cc-by, cc-by-sa, other-open) | Vrai pour chacune | Bloquant (CA-1) |
| TU-02 | licences exclues : notspecified, other-closed, valeur commerciale | Faux pour chacune | Bloquant (CA-1) |
| TU-03 | licence absente, nulle, chaîne vide | Faux (comportement sûr par défaut) | Bloquant (CA-1) |
| TU-04 | casse et espaces parasites dans le code de licence | Évaluation insensible à la casse | Bloquant (CA-1) |
| TU-40 | chargement de la politique depuis `config/politique_licences.json` (fichier valide, absent, invalide, source absente, champs mal typés) | Politique du fichier si valide ; politique intégrée par défaut sinon, sans exception | Bloquant (CA-1) |
| TU-41 | licence conditionnelle `notspecified` : sans type d'organisation (faux), avec `service_public`/`collectivite_territoriale` (vrai), avec `entreprise`/`association`/type inconnu (faux) ; licence incompatible (`other-closed`, commerciale) refusée même pour un producteur public | Décision déterministe conforme à la politique paramétrée | Bloquant (CA-1) |
| TU-60 | flux `rechercher_jeux` : `notspecified` + badge `public-service`/`local-authority` (accepté, marqué `licence_conditionnelle`, consigné au registre dédié) ; `notspecified` sans badge type ou avec badge `certified` seul (exclu, motif `licence_incompatible`) ; licence incompatible explicite + producteur public (exclue) ; registre des acceptations : persistance, anti-doublon | Décision déterministe conforme à la règle sécurisée ; registre des sources inaccessibles non alimenté par les acceptations | Bloquant (CA-1) |
| TU-61 | registre descriptif : propriétés par licence (11 + notspecified), échec propre sur licence inconnue, `other-*`/`notspecified` jamais devinés (`a_verifier`, prédicats None) ; prédicats partie 2 (attribution, partage à l'identique, produit dérivé permissif) ; `mention_attribution()` : mention standard, courtoisie `cc-zero`/`odc-pddl`, null + message pour `other-*`/`notspecified`, avertissement conditionnel ; voie 2 (`telecharger_brut`) et voie 1 (`extraire_ressource`) : `mention_attribution` et `licence_conditionnelle` dans la réponse | Mention conforme au registre, jamais devinée ; acquisition jamais bloquée par la mention | Bloquant (CA-1) |

### 3.2 Classificateur de ressources

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-05 | CSV (format csv, mime text/csv) | fichier_tabulaire, non indéterminé | Bloquant (CA-6) |
| TU-06 | XLSX, XLS, TSV | fichier_tabulaire | Bloquant (CA-6) |
| TU-07 | ZIP, GeoJSON, JSON, SHP, PDF, Parquet | fichier_autre_format | Bloquant (CA-6) |
| TU-08 | HTML (format ou mime text/html) | page_web | Bloquant (CA-6) |
| TU-09 | URL contenant /api, format api | api_distante | Bloquant (CA-6) |
| TU-10 | Format inconnu, mime absent, URL neutre | indetermine, indéterminé vrai | Bloquant (CA-6) |
| TU-11 | Absence totale de métadonnées | indetermine, jamais une classification erronée silencieuse | Bloquant (CA-6) |

### 3.3 Normalisation des arguments

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-12 | rechercher_jeux avec mots_cles vide | erreur_parametres, jamais d'appel HTTP | Bloquant (CA-5) |
| TU-13 | limite omise | valeur par défaut 10 appliquée | Bloquant |
| TU-14 | limite au-delà du maximum | corrigée au maximum, pas d'exception | Bloquant (CA-5) |
| TU-15 | tri valide | traduction correcte vers les paramètres API v2 (sort) ; `fenetre_maj` déprécié : jamais traduit, avertissement dans `message` (T11.3) | Bloquant |
| TU-16 | tri invalide | repli sur pertinence ou erreur_parametres, selon spécification | Avertissement |

### 3.4 Réponses normalisées

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-17 | Simuler une erreur HTTP 500 sur la recherche | statut echec_technique, pas d'exception | Bloquant (CA-2, CA-5) |
| TU-18 | Simuler un jeu inexistant (404) | statut jeu_introuvable | Bloquant (CA-5) |
| TU-19 | Simuler l'expiration du délai | statut echec_technique après les tentatives configurées | Bloquant (CA-7) |
| TU-20 | Simuler les statuts 429, 502, 503 | nouvelle tentative puis succès si récupération | Bloquant (CA-7) |

### 3.5 Registre des sources inaccessibles

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-21 | Consignation d'une exclusion juridique | entrée complète : horodatage, motif, id_jeu, organisation, licence, url, detail | Bloquant (CA-2) |
| TU-22 | Sauvegarde puis rechargement | contenu préservé, format JSON valide | Bloquant (CA-2) |
| TU-23 | rapport_pour_agent() | retourne une copie ; la modification de la copie n'altère pas le registre | Bloquant (CA-2) |
| TU-24 | Registre préexistant au démarrage | entrées antérieures chargées et non écrasées | Bloquant (CA-2) |

### 3.6 Chargement des contrats

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-25 | Chargement du manifeste réel | les quatre outils présents, déclarations conformes | Bloquant (CA-8) |
| TU-26 | Manifeste avec nom divergent du function.name | échec au démarrage avec message explicite | Bloquant (CA-8) |
| TU-27 | Nom de fichier divergent du nom déclaré | échec au démarrage | Bloquant (CA-8) |
| TU-28 | Contrat JSON absent du chemin déclaré | échec au démarrage, aucun outil partiellement chargé | Bloquant (CA-8) |

### 3.7 Journalisation (`structlog`)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-29 | Log au format JSON avec `id_execution` | Fichier `logs/openDataAgent_<id>.log` contient un JSON valide avec `timestamp`, `event`, `id_execution` | Bloquant (CA-2) |
| TU-30 | Contexte dynamique (`bind_context`) | Les métadonnées ajoutées via `bind_context` apparaissent dans les logs | Bloquant (CA-2) |
| TU-31 | Écriture dans le fichier de logs | Le fichier est créé et contient les logs attendus | Bloquant (CA-2) |
| TU-32 | Niveaux de log (`DEBUG`, `INFO`, `ERROR`) | Les logs respectent les niveaux demandés (ex : `DEBUG` n'apparaît pas en `INFO`) | Avertissement (CA-2) |

(Nota T5.1.5 : les cinq lignes ci-dessus, initialement numérotées TU-30..TU-33 en doublon de la section journalisation, sont renumérotées TU-40..TU-44 et détaillées en section 3.9.)

### 3.9 Formats non tabulaires (T5.1.5) — classification déjà couverte par TU-07 ; ici le chaînage complet : inventaire → telecharger_brut → persistance

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-40 | Fichier ZIP (format zip, mime application/zip), contenu binaire d'archive valide | statut succes, classe fichier_autre_format, fichier persisté octet-octet, chemin sous data/raw/<id>/, format zip retourné | Bloquant (CA-13) |
| TU-41 | Fichier GeoJSON (format geojson, mime application/geo+json), contenu JSON géographique valide | idem, format geojson | Bloquant (CA-13) |
| TU-42 | Fichier JSON (format json, mime application/json) | idem, format json | Bloquant (CA-13) |
| TU-43 | Fichier SHP (format shp, mime application/octet-stream), contenu binaire brut | idem, format shp | Bloquant (CA-13) |
| TU-44 | Fichier PDF (format pdf, mime application/pdf), contenu binaire factice | idem, format pdf | Bloquant (CA-13) |
| TU-45 | Format inconnu mais mime application/zip | le mime suffit : fichier_autre_format, acquisition réussie | Bloquant (CA-13) |
| TU-46 | Contenu binaire non-UTF8 (octets invalides en UTF-8) | aucune erreur de décodage, fichier écrit identique | Bloquant (CA-13) |

Implémentation : `tests/unit/test_download.py` (section formats non tabulaires). Tests réels correspondants : TI-11 (ZIP) et TI-12 (GeoJSON) — à passer en local sur des jeux réels, avec vérification d'intégrité (ouverture de l'archive, parsing du GeoJSON).

### 3.8 Validation des reponses API (`jsonschema`, T2.2)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-34 | Réponse réelle de recherche de jeux (fixture simulant `/api/2/datasets/search/`) | validation réussie | Bloquant (CA-2) |
| TU-35 | Réponse avec champ obligatoire absent (`total`, `id`) | échec, erreurs listées avec chemin, pas d'exception | Bloquant (CA-2) |
| TU-36 | Réponse avec type inattendu (chaîne au lieu d'un entier) | échec avec chemin de l'erreur (JSON pointer) | Bloquant (CA-2) |
| TU-37 | Charge utile vide / JSON invalide / racine non objet / outil inconnu | échec propre avec statut `echec_technique`, sans exception | Bloquant (CA-2, CA-5) |
| TU-38 | Réponse réelle d'inventaire de ressources (fixture simulant `/api/2/datasets/{id}/`) | validation réussie | Bloquant (CA-2) |

## 4. Niveau 2 — Tests d'intégration (TI)

Composants assemblés, réseau simulé, sans agent.

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TI-01 | Chaîne recherche → inventaire : identifiant de jeu valide issu d'une recherche simulée, puis lister_ressources | inventaire complet, métadonnées enregistrées | Bloquant (CA-3) |
| TI-02 | lister_ressources avec identifiant jamais délivré | jeu_introuvable, aucune écriture au registre | Bloquant (CA-3) |
| TI-03 | Chaîne inventaire → interrogation : ressource api_tabulaire vrai | extraction paginée conforme, colonnes détectées | Bloquant (CA-4) |
| TI-04 | interroger_ressource sur ressource non indexée | ressource_non_indexee, suggestion de bascule vers telecharger_brut | Bloquant (CA-5) |
| TI-05 | Chaîne inventaire → téléchargement : ressource non indexée, URL accessible (simulée) | fichier écrit localement, statut succes, chemin et format exacts | Bloquant (CA-4) |
| TI-06 | telecharger_brut sans inventaire préalable | ressource_introuvable, aucune écriture disque | Bloquant (CA-3) |
| TI-07 | telecharger_brut avec refus serveur simulé | echec_technique, entrée au registre avec motif serveur_origine_bloque, aucune écriture partielle sur disque | Bloquant (CA-2, CA-7) |
| TI-08 | Flux simulé complet avec une exclusion de licence et un échec de téléchargement | registre final : deux entrées, motifs exacts, ordre chronologique | Bloquant (CA-2) |
| TI-09 | Volume tabulaire au-delà du seuil | présence du champ recommandation volume_eleve_telechargement_brut_suggere | Avertissement |
| TI-10 | Vérification systématique des invariants de la documentation : chaque invariant des fichiers docs/*.md couvert par une assertion | tous les invariants vérifiés | Bloquant |
| TI-11 | Téléchargement d'un fichier ZIP | Fichier téléchargé, chemin valide, statut succes | Bloquant (CA-13) |
| TI-12 | Téléchargement d'un fichier GeoJSON | Fichier téléchargé, chemin valide, statut succes | Bloquant (CA-13) |
| TI-14 | T5.2.1 — Flux complet dans un même processus (recherche → inventaire → téléchargement) avec exclusion de licence à la recherche | jeu exclu non exposé, exclusion consignée au registre (licence_incompatible), fichier téléchargé avec licence, chaîne d'identifiants intacte | Bloquant (CA-2, CA-3) |
| TI-14b | T5.2.1 — Ressource jamais délivrée par le flux : téléchargement refusé | ressource_introuvable, suggestion reprendre par l'inventaire, aucune écriture disque (propriété TA-01/TA-02 au niveau intégration) | Bloquant (CA-3) |
| TI-15 | T5.2.2 — Persistance : exécution 1 écrit (exclusion + échec), nouvelle instance retrouve intégralement | 2 entrées rechargées, aucune altérée, JSON valide | Bloquant (CA-2) |
| TI-15b | T5.2.2 — Enrichissement cumulatif : l'exécution 2 ajoute une entrée technique | cumul de 2 (puis relecture 3 : 2), entrée juridique d'origine intacte, ordre chronologique | Bloquant (CA-2) |
| TI-15c | T5.2.2 — Re-test d'une entrée technique possible à l'exécution suivante | aucune API de blocage, relecture conforme au contrat global | Avertissement |

### 5.1 Journalisation (`structlog`)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TI-13 | Appel à `rechercher_jeux` | Logs générés avec `mots_cles`, `tri`, `limite` | Bloquant (CA-2) |
| TI-14 | Succès de `rechercher_jeux` | Log avec `total_trouves`, `jeux_retournes`, `exclus_licence` | Bloquant (CA-2) |
| TI-15 | Échec HTTP dans `rechercher_jeux` | Log d'erreur avec `url`, `status_code`, `suggestion` | Bloquant (CA-2) |

## 5. Niveau 3 — Tests de bout en bout (TB)

Marqueur reseau. Exécutés à la demande ou périodiquement, pas à chaque modification.

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TB-01 | Recherche réelle dette publique, tri vues | le jeu Comptes des administrations publiques figure dans les résultats | Bloquant (CA-9) |
| TB-02 | Interrogation réelle de la ressource budget-fr-indicateurs.csv | 74 lignes, colonnes attendues (theme, indicateur, annee_horizon, valeur, unite, statut, source) | Bloquant (CA-9) |
| TB-03 | Parcours de fumée : flux algorithmique complet sans agent, identifiants figés | données acquises, registre cohérent, aucune exception | Bloquant (CA-9) |
| TB-04 | Flux complet avec agent Mistral, thème simple | conversation terminée sans erreur, données acquises, registre concordant | Avertissement (CA-10) |
| TB-05 | Confrontation réelle au serveur Insee (fichier non indexé) | échec propre : statut echec_technique, entrée au registre, pas de crash | Bloquant (CA-7) |

## 6. Niveau transversal — Tests de contrat (TC)

Vérifient la cohérence entre les trois sources : code, contrats JSON, documentation.

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TC-01 | Cohérence triple manifeste / nom de fichier / function.name pour chaque outil | concordance exacte | Bloquant (CA-8) |
| TC-02 | Introspection : chaque argument du schéma JSON existe dans la signature Python, type compatible | aucune divergence | Bloquant (CA-8) |
| TC-03 | Chaque argument obligatoire du schéma est déclaré required | conformité totale | Bloquant (CA-8) |
| TC-04 | Chaque description (fonction et argument) est non vide ; chaque enum déclaré est non vide | conformité totale | Bloquant (CA-8) |
| TC-05 | Balayage des fichiers docs/*.md : chaque code de statut mentionné existe dans CODES_STATUT, et réciproquement | aucune divergence | Bloquant (CA-8) |
| TC-06 | Invariants mentionnés dans la documentation au moins une fois testés dans le plan | couverture complète | Avertissement |

## 7. Tests de la partie agentique (TA)

Non déterministes : vérification par propriétés observables et grille d'évaluation, sur journaux de conversations réels. Coûteux en tokens : exécutés à chaque évolution du prompt ou du modèle.

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TA-01 | Propriété d'intégrité des identifiants : rejeu des journaux, vérification que tout identifiant utilisé par l'agent figure dans les sorties des outils précédents | zéro identifiant hors chaîne | Bloquant (CA-3) |
| TA-02 | Propriété d'ordre : aucun appel telecharger_brut sans lister_ressources préalable sur la même ressource | zéro violation | Bloquant (CA-3) |
| TA-03 | Propriété de registre : entrées du registre concordent avec les échecs réellement retournés par les outils | concordance totale | Bloquant (CA-2) |
| TA-04 | Grille d'évaluation de la sélection : corpus de listes prédéfinies ; conformité des jeux retenus (présents dans la liste, licences correctes, exclusions justifiées) | taux de conformité supérieur au seuil défini | Avertissement (CA-10) |
| TA-05 | Propriété de terminaison : la conversation agentique se termine en un nombre d'invocations sous le plafond | nombre d'invocations inférieur au plafond | Avertissement (CA-11) |

### Annexes T5.3 — création/destruction de l'agent (tests unitaires, SDK simulé, zéro réseau)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-A1 | Charger les quatre contrats d'outils depuis le manifeste | ensemble exact des 4 noms de fonction | Bloquant (CA-2) |
| TU-A2 | Divergence manifeste/contrat ou manifeste/fichier | refus de démarrer (exception ValueError) | Bloquant (CA-2) |
| TU-A3 | Création de l'agent éphémère via beta.agents.create | succès, model/instructions/outils/metadata conformes au dépôt | Bloquant (CA-2) |
| TU-A4 | MISTRAL_MODELE défini | modèle propagé à la création | Avertissement |
| TU-A5 | Clé MISTRAL_API_KEY absente | échec propre echec_technique, aucune exception | Bloquant (CA-2) |
| TU-A6 | Erreur SDK à la création (429/500) | échec propre echec_technique | Bloquant (CA-2) |
| TU-A7 | MISTRAL_AGENT_ID persistant strictement conforme | réutilisé, aucune création | Avertissement |
| TU-A8 | MISTRAL_AGENT_ID divergent (prompt, modèle, outils) ou inaccessible | agent éphémère neuf créé | Bloquant (CA-2) |
| TU-A9 | Destruction de l'agent éphéméré | succès, beta.agents.delete appelé | Bloquant (CA-2) |
| TU-A10 | Destruction d'un agent déjà absent (404) | succès idempotent | Avertissement |
| TU-A11 | Erreur réseau à la destruction | échec propre avec suggestion nettoyer_agents_orphelins | Avertissement |
| TU-A12 | Agent persistant réutilisé | jamais détruit par le flux | Bloquant (CA-3) |
| TU-A13 | Nettoyage des agents orphelins du projet uniquement | seuls les agents du préfixe projet supprimés | Avertissement |

Implémentation : `tests/unit/test_agent.py` (18 tests). Test réel de bout en bout (création → conversation → destruction sur la console Mistral) : à exécuter en local avec `MISTRAL_API_KEY`, hors sandbox.

### Annexes T5.3.2 — boucle de conversation et exécution des tool_calls (tests unitaires, SDK simulé, zéro réseau)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-B1 | Dispatch des 4 outils vers les fonctions cœur avec arguments positionnels et options | appel exact de la fonction cœur | Bloquant (CA-3) |
| TU-B2 | Outil inconnu ou arguments invalides/manquants | erreur_parametres, aucune exception | Bloquant (CA-2) |
| TU-B3 | Arguments en chaîne JSON (format tool_call) | décodés et transmis | Bloquant (CA-2) |
| TU-B4 | Conversation simple : 1 tool_call puis réponse finale | succès, compteur d'invocations exact | Bloquant (CA-3) |
| TU-B5 | Conversation multi-tours : enchaînement de tool_calls, historique {user, assistant, tool} complet transmis à chaque tour | succès, 2 invocations, résultats normalisés renvoyés | Bloquant (CA-3) |
| TU-B6 | Plafond d'invocations atteint | arrêt propre, synthèse partielle, plafond rapporté | Bloquant (CA-11) |
| TU-B7 | Statut d'erreur du cœur (ressource_introuvable) | renvoyé tel quel à l'agent dans le message tool | Bloquant (CA-2) |
| TU-B8 | tool_call illisible (arguments non-JSON) | erreur_parametres renvoyée à l'agent, conversation continue | Bloquant (CA-2) |
| TU-B9 | Erreur API sur complete (429/500) | echec_technique propre, invocations effectuées rapportées | Bloquant (CA-2) |
| TU-B10 | PLAFOND_INVOCATIONS dans l'environnement | plafond respecté | Avertissement (CA-11) |

Implémentation : `tests/unit/test_boucle.py` (12 tests). Journalisation sans blocage (TA-02) : chaque invocation est journalisée (outil, arguments, tour, statut résultat) ; la propriété d'ordre se vérifie par rejeu des journaux.

### Annexes T5.3.3 — journal des conversations (tests unitaires, zéro réseau)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-C1 | En-tête contexte du journal (modèle, prompt, plafond, date, id_execution) | champs complets, événement fin avec statut | Bloquant (CA-2) |
| TU-C2 | Un enregistrement JSONL horodaté par événement | séquence exacte, id_execution sur chaque ligne | Bloquant (CA-2) |
| TU-C3 | Échec d'écriture disque | silencieux, aucune exception vers la boucle | Bloquant (CA-2) |
| TU-C4 | Événement hors liste bornée | remappé en « fin » | Avertissement |
| TU-C5 | Conversation complète journalisée : message, raisonnement (texte entre tool_calls), invocation, résultat, réponse finale | séquence d'événements exacte, raisonnement avec tour | Bloquant (CA-2) |
| TU-C6 | Plafond atteint et erreur API | événements plafond_atteint / erreur_api journalisés, statut fin correspondant | Bloquant (CA-11) |
| TU-C7 | Rejeu : extraction ordonnée des invocations (outil, arguments décodés, statut, tour) | base TA-01/TA-02 vérifiable | Bloquant (CA-3) |
| TU-C8 | Lecture tolérante : lignes corrompues ignorées, fichier absent → liste vide | rejeu jamais en échec sur ligne illisible | Avertissement |

Implémentation : `tests/unit/test_journal.py` (8 tests). Journaux conservés dans `conversations/<id_execution>/conversation.jsonl` (plan_tests §9 : conservation avec contexte pour l'audit).

### Annexes T5.3.4 — prompt système (tests unitaires de contenu, non bloquants)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-D1 | Sections structurantes A1..A4 présentes | quatre marqueurs de section | Avertissement |
| TU-D2 | Consignes transversales : 4 outils, 7 codes de statut, intégrité des identifiants, français, format normalisé | tous présents | Avertissement |
| TU-D3 | Pagination, plafond, licence, volume élevé, fichier hébergé, indétermination | tous présents | Avertissement |
| TU-D4 | Garde-fou T5.3.1 : le prompt reste passé par constante à la création (empreinte = référence) | vérifié | Avertissement |

Implémentation : `tests/unit/test_agent.py` (4 tests de contenu ajoutés). Le prompt est une variable d'ajustement des propriétés TA-01..TA-05 : itérations évaluées sur journaux réels (TA-04 : conformité ≥ 90 % ; TA-05 : invocations < plafond).

### Annexes T4.3 — commande CLI `chat` (tests unitaires, SDK simulé, zéro réseau)

| Id | Cas de test | Résultat attendu | Blocage |
|---|---|---|---|
| TU-E1 | Flux complet : création, boucle (prompt, plafond, id_execution), destruction systématique, affichage synthèse + invocations + journal | succès, code 0 | Bloquant (CA-2) |
| TU-E2 | `--plafond` et `--id-execution` propagés à la boucle | valeurs exactes | Avertissement |
| TU-E3 | `--json` : réponse normalisée + chemin du journal + statut de destruction | champs présents | Avertissement |
| TU-E4 | Échec de création d'agent (clé absente) | code 1, suggestion affichée, destruction non appelée | Bloquant (CA-2) |
| TU-E5 | Échec en cours de conversation | code 1, agent détruit malgré tout (finally), journal indiqué | Bloquant (CA-2) |
| TU-E6 | Exception inattendue dans la boucle | agent détruit (finally), échec propagé | Bloquant (CA-2) |
| TU-E7 | Prompt vide | code 2 | Avertissement |

Implémentation : `tests/unit/test_cli.py` (7 tests chat). Documentation d'utilisation : `docs/README.md` section Utilisation (commandes, paramètres, variables d'environnement, sortie attendue).

### Section 10.7 — persistance des extractions de la voie 1 (T10.7, tests unitaires et d'intégration, zéro réseau)

| ID | Description | Critère d'acceptabilité | Priorité |
|---|---|---|---|
| TU-47 | Extraction multi-pages (3 pages mockées) : agrégation complète en un CSV | lignes ordonnées a,b,c,d,e ; total_lignes=5, lignes_ecrites=5, tronque=false | Bloquant (CA-2) |
| TU-48 | Ressource jamais vue par l'inventaire | ressource_introuvable, suggestion reprendre par l'inventaire | Bloquant (CA-3) |
| TU-49 | Ressource non indexée par l'API tabulaire | ressource_non_indexee, suggestion basculer sur telecharger_brut | Bloquant (CA-3) |
| TU-50 | Plafond atteint (plafond_lignes=150, total 450) | succes partiel : tronque=true, lignes_ecrites=150, message signale la troncature | Bloquant (CA-2) |
| TU-51 | Plafond par défaut via PLAFOND_EXTRACTION | troncature au seuil environnemental | Bloquant (CA-2) |
| TU-52 | Ré-extraction dans la même exécution | suffixe de collision, jamais d'écrasement, deux fichiers distincts | Bloquant (CA-2) |
| TU-53 | Échec HTTP en page 2 | statut de l'échec propagé, aucune écriture disque | Bloquant (CA-2) |
| TU-B11 | Dispatch du 5e outil extraire_ressource | tool_call routé vers la fonction cœur, id_execution de la boucle injecté | Bloquant (CA-2) |
| TU-B12 | Validation Pydantic d'extraire_ressource | id_ressource manquant -> erreur_parametres avec champ fautif | Bloquant (CA-2) |
| TU-E8..E11 | Commande CLI extract : appel cœur avec options, troncature affichée, code sortie ressource_non_indexee, sortie --json | kwargs exacts, message jaune, code 1, JSON parsable | Bloquant (CA-2) |
| TI-16 | Flux complet voie 1 : recherche -> inventaire -> extraction paginée (2 pages) | CSV sur disque avec en-tête + 2 lignes, licence lov2, tronque=false | Bloquant (CA-2, CA-3) |

Implémentation : `tests/unit/test_extraction.py` (7 tests TU-47..53), `tests/unit/test_boucle.py` (TU-B11/B12), `tests/unit/test_cli.py` (TU-E8..E11), `tests/unit/test_integration.py` (TI-16).

## 8. Ordre d'exécution et définition de fini

1. À chaque modification de code : TU et TI (sans réseau), TC. Exécution en quelques secondes.
2. À chaque validation d'itération : ajout de TB-01 à TB-03, TB-05.
3. À chaque évolution de la boucle agentique ou du prompt : TB-04 et l'ensemble TA, avec conservation des journaux.
4. Définition de fini d'une itération : tous les tests bloquants passent ; les critères d'avertissement sont mesurés et consignés même s'ils ne bloquent pas.

## 9. Traces et conservation

- Fixtures de réponses réelles : enregistrées une fois par version majeure des API, stockées dans le dépôt.
- Journaux de conversations agentiques : conservés avec le contexte d'exécution (modèle, prompt, date), servant aux tests TA et à l'audit.
- Résultats des exécutions de validation : consignés avec la version du code et les seuils mesurés (tokens, invocations, durées), pour le suivi des critères non fonctionnels.

---

## Tests T11.3 — Migration API v2 (18/10/2026)

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-15b | `fenetre_maj != "toutes"` : paramètre ignoré (jamais `last_update_range` dans l'URL), avertissement dépréciation dans `message`, recherche en succès | Succès + avertissement explicite | Bloquant |
| TU-15c | `derniere_maj` alimenté depuis `last_update` (v2), pas `last_modified` | Valeur exacte de `last_update` | Bloquant |
| TU-54 | Inventaire v2 : deux appels (détail + sous-ressource), payload reconstitué (liste `resources` plate), `page_size` 50 | Succès, `resources` liste plate au format cœur | Bloquant |
| TU-55 | Inventaire v2 : boucle sur `next_page` (2 pages, 50 + 10 ressources) | 60 ressources agrégées, arrêt sur `next_page` absent | Bloquant |
| TU-56 | Inventaire v2 : `next_page` aberrant inépuisable → plafond 20 pages | `echec_technique` explicite « plafond atteint » | Bloquant |
| TU-57 | Inventaire v2 : 404 sur le détail → `jeu_introuvable`, aucun second appel | Statut exact, 1 seul appel HTTP | Bloquant |
| TU-58 | Inventaire v2 : jeu sans ressource (total 0) | Succès, liste vide | Non bloquant |
| TC-03 | Manifeste : `rechercher_jeux` en v1.3.0 (dépréciation `fenetre_maj`) | Version exacte | Bloquant |
| TB-01b | Validation en réel : recherche « élections présidentielles » — le jeu du Ministère de l'Intérieur en page 1 (moteur v2) | Cas étalon satisfait | Bloquant (E8) |


## Tests T10.8 — Manifeste d'acquisition (19/10/2026)

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-70 | Manifeste : round-trip écriture/lecture, entrée complète (fichier, voie, titre_jeu, horodatage) | Relu à l'identique | Bloquant |
| TU-71 | Manifeste : additivité (2 acquisitions -> 2 entrées), anti-doublon sur fichier | 2 entrées distinctes / 1 seule par fichier | Bloquant |
| TU-72 | Manifeste : écriture atomique, aucun `.part` résiduel | Fichier final seul présent | Bloquant |
| TU-73 | Manifeste : lecture défensive (absent, JSON invalide) | None sans exception | Bloquant |
| TU-74 | `consigner_demande` : en-tête écrit, acquisitions préservées | Demande en en-tête, entrées intactes | Bloquant |
| TU-75 | Échec d'écriture du manifeste | Warning, aucune exception levée | Bloquant |
| TU-76 | `telecharger_brut` succès -> entrée voie telechargement (titre_jeu, url_jeu, mention) ; échec -> aucune entrée | Entrée exacte / manifeste absent | Bloquant |
| TU-77 | `extraire_ressource` succès -> entrée voie extraction (tronque, nb_lignes) ; garde non indexée -> aucune entrée | Entrée exacte / manifeste absent | Bloquant |
| TU-78 | E0 : `_jeu_courant` porte titre/url du jeu, dénormalisés dans la ressource | titre_jeu, url_jeu présents | Bloquant |
| TU-79 | `lister_acquisitions` (storage) : liste vide si absent, entrées sinon | Comportement défensif | Non bloquant |
| TU-80 | Manifeste : remplacement cross-platform (`.part` orphelin + cible existante, simule Windows WinError 183) | 3 acquisitions consignées, `.part` disparu | Bloquant (régression 20/10) |
| TU-E12 | CLI `acquisitions` : absent -> erreur code 1 ; existant -> affichage lisible (fichier, voie, jeu, licence conditionnelle) | Sorties exactes | Bloquant |
| TU-E13 | CLI `download` : consigne de la demande dans le manifeste | En-tête `demande` écrit | Bloquant |
| TI-17 | Flux deux voies (extraction puis téléchargement) dans une même exécution | Un manifeste, 2 entrées ordonnées aux voies distinctes | Bloquant |


## Tests T11.1 — Mode conversationnel multi-tours (20/10/2026)

Contexte côté serveur (API Conversations `client.beta.conversations`), boucle tool-calling côté client, plafond par tour, propose-puis-acquiert, clôture par `stop`. La boucle one-shot (`boucle_conversation`) est supprimée ; les tests TU-B4..TU-B10 sont remplacés par TU-B13..TU-B24.

### Tests unitaires — boucle multi-tours (`tests/unit/test_boucle.py`)

| R\u00e9f. | Objectif | R\u00e9sultat attendu | Criticit\u00e9 |
|---|---|---|---|
| TU-B13 | `creer_conversation` : contexte (empreinte du prompt, pas le texte), plafond | Champs exacts, empreinte \u2264 16 caract\u00e8res | Bloquant |
| TU-B14 | Tour avec r\u00e9ponse directe (start_stream) | `succes`, synth\u00e8se, 0 invocation, `conversation_id` lu | Bloquant |
| TU-B15 | Tour avec tool_call \u2192 ex\u00e9cution locale \u2192 `function.result` renvoy\u00e9 | R\u00e9sultat exact dans l'entr\u00e9e `function.result`, `append_stream` appel\u00e9 | Bloquant |
| TU-B16 | Multi-tours : contexte serveur conserv\u00e9 | Un seul `start_stream`, `append_stream` avec le `conversation_id`, seul le nouveau message envoy\u00e9 | Bloquant |
| TU-B17 | Plafond r\u00e9initialis\u00e9 par tour | Tour 1 plafonn\u00e9 \u2192 tour 2 repart \u00e0 0 | Bloquant (CA-11) |
| TU-B18 | Erreur c\u0153ur renvoy\u00e9e tel quel | `function.result` avec le statut d'erreur | Bloquant (CA-2) |
| TU-B19 | tool_call illisible (arguments non-JSON) | `erreur_parametres` renvoy\u00e9e, tour continue | Bloquant (CA-2) |
| TU-B20 | Erreur SDK sur `start_stream` | `echec_technique` propre, 0 invocation | Bloquant (CA-2) |
| TU-B21 | \u00c9v\u00e9nement `conversation.response.error` | `echec_technique` avec le message serveur | Bloquant (CA-2) |
| TU-B22 | `PLAFOND_INVOCATIONS` dans l'environnement | Plafond r\u00e9solu depuis l'env | Avertissement (CA-11) |
| TU-B23 | Appel fragmenté en deltas (même `output_index`) | Appel reconstitué (identité 1er delta, arguments concaténés), 1 exécution, 1 `function.result` | Bloquant (régression 20/10) |
| TU-B24 | Deltas de deux appels entremêlés (`output_index` distincts) | Chaque appel reconstitué indépendamment, ordre des `output_index` | Bloquant (régression 20/10) |
| TU-C9 | S\u00e9quence d'\u00e9v\u00e9nements multi-tours | `contexte, debut_tour, ..., fin_tour` exacts | Bloquant (CA-2) |

### Tests unitaires — journal multi-tours (`tests/unit/test_journal.py`)

| R\u00e9f. | Objectif | R\u00e9sultat attendu | Criticit\u00e9 |
|---|---|---|---|
| TU-C10 | `fin` avec totaux de conversation | `nb_tours`, `nb_invocations` exacts | Bloquant (CA-2) |

### Tests unitaires — prompt (`tests/unit/test_agent.py`)

| R\u00e9f. | Objectif | R\u00e9sultat attendu | Criticit\u00e9 |
|---|---|---|---|
| TU-D5 | Propose-puis-acquiert dans le prompt | `PROPOSE-PUIS-ACQUIERT`, `Ne les invoque JAMAIS`, `FEEDBACK UTILISATEUR` pr\u00e9sents ; consigne one-shot retir\u00e9e | Avertissement |
| TU-D6 | Section MULTI-TOURS dans le prompt | `MULTI-TOURS`, plafond par tour, mot-cl\u00e9 `stop` pr\u00e9sents | Avertissement |

### Tests unitaires — CLI `chat` REPL (`tests/unit/test_cli.py`)

| R\u00e9f. | Objectif | R\u00e9sultat attendu | Criticit\u00e9 |
|---|---|---|---|
| TU-E14 | REPL deux tours puis EOF | 2 tours conduits, cl\u00f4ture (conversation + agent) en finally | Bloquant (CA-2) |
| TU-E15 | Mot-cl\u00e9 `stop` (insensible \u00e0 la casse) | Cl\u00f4ture sans tour, agent d\u00e9truit | Bloquant |
| TU-E16 | EOF (Ctrl+D) | Cl\u00f4ture propre, code 0 | Bloquant |
| TU-E17 | `--plafond` propag\u00e9 par tour | `creer_conversation` re\u00e7oit le plafond | Avertissement |
| TU-E18 | `--json` : totaux conversation | `nb_tours`, `nb_invocations`, `conversation_id`, `journal`, `agent_detruit`, `conversation_supprimee` | Avertissement |
| TU-E19 | \u00c9chec technique d'un tour | Cl\u00f4ture quand m\u00eame (finally), statut affich\u00e9 | Bloquant (CA-2) |
| TU-E20 | Exception inattendue dans un tour | Cl\u00f4ture quand m\u00eame (finally) | Bloquant (CA-2) |
| TU-E21 | Prompt vide explicite (`chat "   "`) | Code 2 | Avertissement |

### Tests d'int\u00e9gration — sc\u00e9nario multi-tours simul\u00e9 (`tests/unit/test_integration.py`)

| R\u00e9f. | Objectif | R\u00e9sultat attendu | Criticit\u00e9 |
|---|---|---|---|
| TI-18 | Sc\u00e9nario complet : exploration \u2192 correction utilisateur \u2192 raffinement \u2192 acquisition valid\u00e9e (SDK Conversations + c\u0153ur simul\u00e9s) | 3 tours, 4 invocations, ordre des appels c\u0153ur exact, un seul `start_stream`, journal multi-tours conforme, conversation supprim\u00e9e | Bloquant (CA-2, CA-3, CA-11) |


## Tests T7.1 — Réessai intelligent (22/10/2026)

Périmètre : client HTTP uniquement (`src/utils/http.py`) + registre (`statut_reprise`). Hors périmètre : circuit breaker agentique (T7.7). Plan détaillé : `docs/tasks/T7.1_reessai_intelligent.md`.

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-81 | 429 avec `Retry-After: 5` → délai respecté (mock `time.sleep`) | Délai = 5 s, pas le backoff calculé | Bloquant |
| TU-82 | Backoff exponentiel 1 s → 2 s → 4 s avec jitter borné | Délais croissants, jitter dans la borne | Bloquant |
| TU-83 | 403 → 1 seul appel HTTP, `motif=definitif`, pas de retry | `echec_technique`, 1 requête | Bloquant |
| TU-84 | 410 → idem | `echec_technique`, 1 requête | Bloquant |
| TU-85 | 400 → idem | `echec_technique`, 1 requête | Bloquant |
| TU-86 | `.part` existant + réponse 206 → reprise à l'octet (header `Range`) | Contenu final complet, `.part` renommé | Bloquant |
| TU-87 | Coupure mid-stream (`ChunkedEncodingError` dans `iter_content`) → retry, `.part` conservé | Succès au 2e essai, contenu complet | Bloquant (bug latent) |
| TU-88 | `.part` existant + réponse 200 (Range ignoré) → écrasement propre | Contenu = réponse 200 seule | Bloquant |
| TU-89 | Échec définitif (403) avec `.part` présent → `.part` supprimé | Aucun `.part`, aucun fichier final | Bloquant |
| TU-90 | Succès au 1er essai → `nb_tentatives=1` dans `donnees` ; succès au 3e → `nb_tentatives=3` | Champ exact | Bloquant |
| TU-91 | Échec transitoire épuisé → registre consigné `statut_reprise=a_retenter` | Champ présent, motif conservé | Bloquant |
| TU-92 | Échec définitif (403) → registre consigné `statut_reprise=definitif` | Champ présent | Bloquant |
| TU-93 | Rétrocompatibilité registre : entrée sans `statut_reprise` → lu comme `definitif` | Aucune erreur, défaut appliqué | Bloquant |
| TI-19 | Flux `telecharger_brut` : 1er appel 503 puis succès | Fichier complet, `nb_tentatives=2`, registre vide | Bloquant |
| TI-20 | Flux `telecharger_brut` : 503 × 3 | `echec_technique`, registre `a_retenter`, `nb_tentatives=3` | Bloquant |

## Tests T7.2 — Nettoyage des anciennes exécutions (22/10/2026)

Périmètre : `src/core/nettoyage.py` + commande CLI `nettoyer` + hook `NETTOYAGE_AUTO`. Quatre racines : `data/raw/`, `data/executions/`, `conversations/`, `logs/openDataAgent_<id>.log`. Hors périmètre : outil agent, contrats (aucun modifié). Suivi : `docs/tasks/T7.2_nettoyage_executions.md`.

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-94 | Exécution ancienne → supprimée sur les 4 racines | 4 familles supprimées, bilan `supprimes=[id]` | Bloquant |
| TU-95 | Exécution récente → conservée | Dossiers et log présents | Bloquant |
| TU-96 | Exécution courante (`id_execution_courante`) → protégée même ancienne | `supprimes=[]`, `conserves=[id]` | Bloquant |
| TU-97 | `--simulation` → rien supprimé, bilan indique ce qui le serait | `simulation=true`, traces présentes | Bloquant |
| TU-98 | Registres globaux + noms non reconnus → conservés | `registry.json`, `registre_acceptations.json`, dossier/log inconnus intacts | Bloquant |
| TU-99 | `id_execution` à date invalide (`20261301_...`) → conservé (fail-safe) | Non sélectionné | Bloquant |
| TU-100 | Bilan : compteurs + octets libérés exacts | `octets_liberes` = somme des tailles supprimées | Bloquant |
| TI-21 | Flux complet cœur : vieille supprimée, récente + courante conservées, registres intacts | Bilan conforme, disque conforme | Bloquant |
| TI-22 | CLI `nettoyer` : `--simulation` puis réel puis `--json` ; hook auto désactivé par défaut, `NETTOYAGE_AUTO=1` protège `--id-execution` | Codes sortie 0, disque conforme, JSON valide | Bloquant |

## Tests T7.7 — Circuit breaker agentique (22/10/2026)

Périmètre : `src/agent/circuit.py` + intégration `src/agent/boucle.py` + champ `motif` dans les 4 contrats. Option A actée : état en mémoire, attaché à la conversation. Paramétrage : `CIRCUIT_BREAKER_SEUIL` (3), `CIRCUIT_BREAKER_REFROIDISSEMENT` (300 s), `CIRCUIT_BREAKER_DESACTIVE=1`. Suivi : `docs/tasks/T7.7_circuit_breaker_agentique.md`.

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-101 | État initial | tout hôte autorisé (y compris hôte None) | Bloquant |
| TU-102 | 3 échecs transitoires consécutifs → ouvert, 4e appel bloqué | `autoriser` False au seuil, `instantanement_ouvert` True | Bloquant |
| TU-103 | Succès entre les échecs → compteur remis à zéro | pas d'ouverture avant 3 échecs post-succès | Bloquant |
| TU-104 | Échec définitif (403/410) → ignoré | jamais d'ouverture | Bloquant |
| TU-105 | Refroidissement 300 s → semi-ouvert (1 tentative), succès referme / échec rouvre | transitions conformes | Bloquant |
| TU-106 | Circuits par hôte indépendants | hôte ouvert n'affecte pas les autres | Bloquant |
| TU-107 | `CIRCUIT_BREAKER_DESACTIVE=1` → aucune interception | tout passe | Bloquant |
| TU-108 | Variables d'environnement (seuil, refroidissement, valeurs invalides → défauts) | 3 / 300 s par défaut | Bloquant |
| TI-23 | Boucle : 3 échecs `motif=transitoire` même hôte → 4e appel intercepté | outil non exécuté, `nb_invocations=3`, agent reçoit `circuit_ouvert` + `hote` + `proposer_alternative` | Bloquant |
| TI-24 | Boucle : hôtes indépendants, succès rouvre, échec définitif n'ouvre pas, ressource inconnue = fail-safe | compteurs d'appels et statuts conformes | Bloquant |

## Tests T13.2 — Option --quiet (22/10/2026)

Périmètre : `configure_logging(silencieux=...)` (`src/utils/logging.py`) + option globale `--quiet` au callback Typer (`src/main.py`) + masquage du warning de nettoyage T7.2. Le fichier de logs reste écrit. Suivi : `docs/tasks/T13.2_option_quiet.md`.

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-109 | `silencieux=True` : log structlog info/error | aucune sortie console, fichier de logs écrit | Bloquant |
| TU-110 | `silencieux=False` (défaut) : comportement inchangé | log structlog présent sur la console | Bloquant |
| TU-111 | CLI `--quiet search` (cœur simulé) | résultat affiché, `id_execution` affiché, aucun `[info]`/`[error]` console | Bloquant |
| TU-112 | CLI `search` sans `--quiet` | résultat affiché, comportement inchangé | Bloquant |
| TU-113 | CLI : flag posé au callback + transmis au wrapper ; en `--quiet` le warning du hook de nettoyage T7.2 est masqué (mais le nettoyage a lieu) | `_SILENCIEUX=True`, wrapper appelé, pas de warning console, exécution supprimée | Bloquant |

## Tests T11.4 — Outil agentique `consulter_registre` (22/10/2026)

Périmètre : `src/core/registre.py` (fonction cœur, lecture seule), contrat v1.0.0 (`contrats/consulter_registre.json`, manifeste 1.2), schéma Pydantic (`src/contracts/consulter_registre.py`), dispatch `src/agent/outils.py`, consigne prompt A4 (`config/prompt_systeme.txt`). Suivi : `docs/tasks/T11.4_consulter_registre.md`.

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-114 | Registre absent/illisible | `succes`, liste vide, `total=0`, `nb_retournees=0` | Bloquant |
| TU-115 | Limite `derniere_n` | N entrées les plus récentes, ordre chronologique conservé, `total` = taille réelle hors limite | Bloquant |
| TU-116 | Filtre `motif` | seules les entrées du motif, `total` hors filtre | Bloquant |
| TU-117 | Filtre + limite combinés | les N plus récentes parmi le motif filtré | Bloquant |
| TU-118 | `statut_reprise` exposé | `a_retenter`/`definitif` ; entrée sans champ (exclusion licence) → `definitif` | Bloquant |
| TU-119 | Dispatch agent (`executer_outil`) | validation Pydantic (champs inconnus ignorés), `id_execution` injecté, registre inchangé (lecture seule) | Bloquant |
| TI-25 | Boucle : l'agent invoque `consulter_registre` | rapport normalisé renvoyé, invocation consomme le plafond | Bloquant |
| TI-26 | Mémoire cross-session | entrée consignée par une exécution visible via `consulter_registre` dans l'exécution suivante, registre non réécrit | Bloquant |


## Tests T13.3 — Réalignement linguistique de la CLI (22/10/2026)

Périmètre : `src/main.py` (commandes renommées en français + alias anglais, `--silencieux` alias `--quiet`), `src/core/manifeste.py` (`genere_le`). Suivi : `docs/tasks/T13.3_realignement_linguistique.md`.

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-120 | `--help` : les 8 commandes françaises présentes | `rechercher`, `lister`, `telecharger`, `extraire`, `interroger`, `demander`, `acquisitions`, `nettoyer` dans la sortie | Bloquant |
| TU-121 | Alias anglais `search` | délègue à `rechercher` (mêmes arguments/options, appel cœur identique) | Bloquant |
| TU-122 | `--silencieux` + alias `--quiet` | logs masqués, `_SILENCIEUX=True`, résultat visible, les deux formes fonctionnent | Bloquant |
| TU-123 | Manifeste : champ `genere_le` | `genere_le` présent, `generé_le` absent (convention sans accent) | Bloquant |

## Tests T10.1 — Normalisation B7 (23/10/2026)

Périmètre : `src/core/normalisation.py` (cœur), `src/main.py` (commande `normaliser`), `src/core/nettoyage.py` (5ᵉ racine `data/processed/`). Suivi : `docs/tasks/T10.1_normalisation_b7.md`.

| Réf. | Objectif | Résultat attendu | Criticité |
|---|---|---|---|
| TU-124 | Détection conformité CSV | UTF-8 virgule sans BOM = conforme ; latin-1, BOM, point-virgule, vide = non conforme (vide = conforme) | Bloquant |
| TU-125 | Normalisation CSV (encodage + séparateur) | CSV latin-1 point-virgule ré-écrit en UTF-8 virgule ; BOM retiré (TU-125b) | Bloquant |
| TU-126 | CSV déjà conforme copié tel quel | voie 1 (CSV pivot) : copie octet-octet, pas de ré-écriture | Bloquant |
| TU-127 | Conversion tableurs (xlsx, xls, ods) | un CSV par feuille `<fichier>__<feuille>.csv`, UTF-8 virgule ; nom de feuille nettoyé (TU-127b) | Bloquant |
| TU-128 | Bruts non normalisables copiés tels quels | zip, geojson, tsv, pdf, extension inconnue : copie octet-octet | Bloquant |
| TU-129 | `processed/` ne contient que des fichiers finaux | manifeste d'acquisition exclu ; extensions conformes | Bloquant |
| TU-130 | Re-lancement sans doublon | 2ᵉ passage : tous les fichiers marqués `ignore`, aucun doublon, aucun écrasement | Bloquant |
| TU-131 | Simulation | bilan fidèle produit, rien d'écrit sous `data/processed/` | Bloquant |
| TU-132 | Bilan normalisé et cas limites | exécution inconnue → `erreur_parametres` ; dossier sans fichier → `succes` vide (TU-132b) | Bloquant |
| TU-133 | `normaliser_toutes_executions` | agrégation multi-exécutions, exclusion de l'exécution courante | Bloquant |
| TI-27 | Commande CLI `normaliser` | cycle complet : `--simulation` (rien écrit) → réel → re-lancement (`--json`, tout `ignore`) → sans argument → id inconnu (exit 1) | Bloquant |
