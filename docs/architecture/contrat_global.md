# Documentation des contrats — Répertoire docs/

Ce document contient le contenu des cinq fichiers de documentation à copier dans le répertoire `docs/` de l'arborescence applicative. Chaque section correspond à un fichier distinct.

---

## Fichier : contrat_global.md

# Contrat global des outils exposés aux agents

## Objet

Ce document spécifie les conventions transversales applicables à l'ensemble des outils exposés aux agents Mistral dans la partie 1 du flux d'acquisition de données data.gouv.fr (recherche thématique, sélection, extraction). Les contrats individuels (`rechercher_jeux.md`, `lister_ressources.md`, `interroger_ressource.md`, `telecharger_brut.md`) décrivent chacun une fonction ; le présent document décrit ce qu'ils partagent.

## Sources de vérité

- Structurelle : les fichiers JSON du répertoire `contrats/`, référencés par `contrats/manifeste.json`. Le code charge les schémas depuis ces fichiers.
- Sémantique : le présent répertoire `docs/`.
- Garantie de cohérence : le code refuse de démarrer si le manifeste, le champ `function.name` et le nom de fichier d'un contrat divergent. Tout changement de schémas doit être répercuté dans les deux sources et incrémenté dans le manifeste.

## Rôles et frontières

- L'agent décide : reformulation du thème, sélection des jeux, classification des ressources ambiguës, synthèse du registre.
- Le code exécute : tous les appels HTTP, le filtre de licence, la normalisation, la persistance. L'agent n'accède jamais directement au réseau ; il ne dispose que des six outils décrits dans ce répertoire.
- Le registre des sources inaccessibles est en écriture interne uniquement : aucune fonction exposée ne permet de le modifier ou de le vider. L'agent n'y accède qu'en lecture, via l'outil `consulter_registre` (T11.4) — invoquable à tout moment (doute sur une source, synthèse finale), pas seulement en fin de flux.

## Format de réponse normalisé

Toute invocation d'outil, sans exception, retourne un objet unique sérialisé en JSON :

```json
{
  "statut": "<code>",
  "message": "<texte court, vide si succès>",
  "donnees": { }
}
```

- `statut` : code normalisé, voir la section suivante.
- `message` : explication brève en cas d'échec ; chaîne vide en cas de succès.
- `donnees` : charge utile spécifique à la fonction, décrite dans son contrat individuel.

Aucune fonction ne lève d'exception vers l'agent. Toute défaillance est exprimée par un code de statut.

## Codes de statut

| Code                    | Signification                                               | Action attendue de l'agent                                                 |
|-------------------------|-------------------------------------------------------------|----------------------------------------------------------------------------|
| `succes`                | Opération réussie.                                          | Exploiter `donnees`.                                                       |
| `erreur_parametres`     | Arguments invalides ou manquants.                           | Corriger les arguments et réessayer.                                       |
| `jeu_introuvable`       | Identifiant de jeu inconnu ou inaccessible.                 | Ne pas réessayer avec le même identifiant ; reprendre à `rechercher_jeux`. |
| `ressource_introuvable` | Identifiant de ressource jamais vu par `lister_ressources`. | Appeler `lister_ressources` sur le jeu concerné.                           |
| `ressource_non_indexee` | Ressource absente de l'API tabulaire.                       | Basculer sur `telecharger_brut`.                                           |
| `licence_refusee`       | Licence du jeu incompatible avec la politique.              | Exclure la source ; ne pas tenter d'accès direct.                          |
| `echec_technique`       | Échec réseau, blocage serveur, expiration.                  | Selon le champ `donnees.suggestion` : réessayer, basculer, ou abandonner.  |
| `echec_technique` + `motif=circuit_ouvert` | Hôte temporairement injoignable (circuit breaker, T7.7). | Ne relancer aucun outil vers cet hôte pendant la conversation ; proposer une alternative ou informer l'utilisateur. |

## Conventions transversales

1. Identifiants. Les fonctions s'échangent des identifiants, jamais des contenus bruts. Un identifiant de jeu provient de `rechercher_jeux` ; un identifiant de ressource provient de `lister_ressources`. Un identifiant jamais délivré par la chaîne est refusé ; en mode CLI, la chaîne s'étend aux exécutions antérieures réactivées sous le même `id_execution` (inventaire persistant `data/executions/<id_execution>/inventaire.json`), le mode agentique restant en mémoire seule.
2. Bornes. Toute fonction limitant le nombre d'éléments retournés applique un défaut (10) et un maximum (20). Il incombe à l'agent de paginer, pas au code d'étendre les bornes.
3. Licence et attribution. Tout retour de succès inclut la licence du jeu. Les obligations associées (mention de la source pour CC-BY, partage à l'identique pour ODbL) doivent être conservées jusqu'à la partie visualisation.
4. Journalisation. Les appels réels transitent par le code et sont journalisés localement avec leurs arguments et résultats. Le rejeu d'un flux algorithmique est déterministe ; les étapes agentiques sont journalisées séparément.
5. Langue. Les descriptions exposées à l'agent, les messages d'erreur et la documentation sont en français. Les codes de statut sont en minuscules sans accent.
6. Réessai (T7.1). Les appels HTTP sont repris selon leur nature : les statuts transitoires (429, 502, 503, 504) et les erreurs réseau sont retentés (3 tentatives par défaut) avec un backoff exponentiel (base 1 s, plafond 30 s) et un jitter aléatoire, en respectant l'en-tête `Retry-After` du serveur ; les statuts définitifs (400, 401, 403, 410) ne sont **jamais** retentés et produisent un `motif` explicite (`requete_invalide`, `acces_refuse`, `ressource_supprimee`). Le nombre de tentatives est exposé dans `donnees.nb_tentatives` de chaque outil. Un téléchargement interrompu est repris à l'octet atteint (en-tête `Range`) ; un échec définitif supprime le fichier partiel `.part`.
7. Circuit breaker agentique (T7.7). En mode conversation, après 3 échecs transitoires consécutifs (`motif=transitoire`, T7.1) vers un même hôte, la boucle cesse de solliciter cet hôte : l'outil est intercepté **avant exécution et sans consommer le plafond d'invocations**, et l'agent reçoit `echec_technique` avec `donnees.motif=circuit_ouvert`, `donnees.hote` et `donnees.suggestion=proposer_alternative`. Le refroidissement est de 300 s (état semi-ouvert : une tentative autorisée, qui rouvre ou referme selon le résultat). Un échec définitif (403/410…) n'alimente pas le circuit. L'état du circuit est **en mémoire, attaché à la conversation** : il est détruit à la clôture, aucune temporisation ne court entre deux exécutions. Périmètre : tous les hôtes (serveurs d'origine des ressources et API data.gouv.fr / tabulaire). Paramétrage : `CIRCUIT_BREAKER_SEUIL`, `CIRCUIT_BREAKER_REFROIDISSEMENT`, `CIRCUIT_BREAKER_DESACTIVE=1`. Résolution de l'hôte : `telecharger_brut` via l'URL de la ressource (inventaire) ; `extraire_ressource`/`interroger_ressource` via l'API tabulaire ; `rechercher_jeux`/`lister_ressources` via l'API data.gouv.fr. Hôte indéterminé = laisser-passer (fail-safe).

## Politique de licence

Licences acceptées : `lov2`, `fr-lo`, `odc-odbl`, `odc-by`, `odc-pddl`, `cc-by`, `cc-by-sa`, `cc-zero`, `other-open`, `other-attribution`, `other-pd` (référentiel complet du filtre de licence du site, cf. `config/politique_licences.json`). Licences conditionnelles : `notspecified` est acceptée uniquement pour un producteur public (`service_public`, `collectivite_territoriale`) — l'absence de licence déclarée est présumée réutilisable pour un établissement public français (CRPA), sans jamais contourner une licence incompatible explicite. Licences exclues : toute licence fermée ou commerciale, quelle que soit l'organisation ; `notspecified` pour un producteur privé. Le filtre s'applique avant tout retour de résultats : un jeu exclu n'est jamais retourné par `rechercher_jeux`, mais il est consigné au registre avec le motif `licence_incompatible`. Les jeux acceptés par dérogation portent le marquage `licence_conditionnelle: true` dans la réponse de `rechercher_jeux` (avec compteur `acceptes_licence_conditionnelle`) et sont tracés dans un registre dédié aux acceptations (`data/registre_acceptations.json`, motif `licence_absente_producteur_public`) — distinct du registre des sources inaccessibles, dont la sémantique est inchangée. Cette règle est déterministe et ne fait pas l'objet d'une décision agentique. La liste est paramétrée par `config/politique_licences.json` (une clé par source, préparation de l'ouverture à d'autres sites) ; en l'absence du fichier, une politique intégrée équivalente s'applique.

## Registre des sources inaccessibles

Deux familles d'entrées :

- Exclusions juridiques (motif `licence_incompatible`), écrites par `rechercher_jeux`.
- Échecs techniques (motifs `serveur_origine_bloque`, `statut_http_*`), écrits par `telecharger_brut`.

Chaque entrée comporte : horodatage, motif, identifiant et organisation du jeu, licence, URL, détail. Le registre est persistant entre les exécutions. Une entrée technique peut être re-testée lors d'une exécution ultérieure ; une entrée juridique est définitive tant que la licence du jeu ne change pas.

T11.4 : l'outil `consulter_registre` (contrat v1.0.0, `src/core/registre.py`) expose le registre en lecture seule à l'agent, avec une limite `derniere_n` (défaut 20) et un filtre `motif` pour maîtriser la taille du rapport ; `total` indique la taille réelle du registre hors limite et hors filtre.

T7.1 : les entrées techniques portent un champ additif `statut_reprise` — `a_retenter` (échec transitoire épuisé : réseau, 429/502/503/504 après les tentatives) ou `definitif` (refus définitif du serveur : 400/401/403/410). Les entrées antérieures au champ (et les exclusions juridiques) sont lues avec la valeur par défaut `definitif` — aucune entrée n'est modifiée sur disque.
