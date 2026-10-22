## Fichier : telecharger_brut.md

# Outil telecharger_brut

## Intention

Acquérir une ressource non indexée par l'API tabulaire dans son état brut (voie 2), vers le stockage local. Cette fonction écrit sur le disque : elle doit être réservée aux ressources sélectionnées, pas employée en exploration.

## Sémantique des arguments

- `id_ressource` (obligatoire) : identifiant issu de `lister_ressources`. La fonction ne prend pas d'URL : l'URL est résolue par le code à partir des métadonnées enregistrées lors de l'inventaire.

## Retour en succès

`donnees.chemin_local` : chemin relatif du fichier acquis. `donnees.format` : format de la ressource. La licence est incluse afin que les obligations d'attribution suivent le fichier jusqu'à la visualisation. `donnees.licence_conditionnelle` : vrai si la licence a été acceptée par dérogation (producteur public). `donnees.mention_attribution` : mention d'attribution prête à afficher, générée par le code à partir des métadonnées de l'inventaire (organisation, licence, date de mise à jour) ; `null` pour les licences à vérifier (`other-*`, `notspecified`) — jamais devinée, le message de la réponse l'explique alors. `donnees.nb_tentatives` : nombre de tentatives du téléchargement (1 = succès au premier essai ; T7.1). `donnees.motif` : motif de l'échec HTTP (`transitoire`, `acces_refuse`, `ressource_supprimee`, `requete_invalide` ; T7.1), ou `circuit_ouvert` en mode agentique quand le circuit breaker a intercepté l'appel (T7.7) — absent (null) en cas de succès. Version 1.3.0 (T7.7 : champ additif `motif` ; la version 1.2.0 ajoutait `nb_tentatives`, T7.1 ; la version 1.1.0 ajoutait `licence_conditionnelle` et `mention_attribution`, T7.5). Le téléchargement est repris sur les statuts transitoires (429/502/503/504) et les erreurs réseau (backoff exponentiel + jitter, `Retry-After` respecté) ; un fichier partiel `.part` est repris à l'octet atteint (en-tête `Range`) ; les statuts définitifs (400/401/403/410) ne sont jamais retentés et le `.part` est supprimé.

## Comportements d'échec

- `ressource_introuvable` : l'identifiant n'a jamais été vu par `lister_ressources au cours du flux courant. Reprendre par l'inventaire.
- `echec_technique` : le serveur d'origine refuse l'accès (blocage des agents, statut HTTP d'erreur, expiration). Le code consigne l'entrée au registre des sources inaccessibles avec le motif `serveur_origine_bloque`. `donnees.suggestion` vaut `fichier_heberge_exterieurement` : aucune relance immédiate n'est utile ; la source doit figurer dans la synthèse finale (A4) avec proposition d'alternative (jeu équivalent hébergé sur la plateforme).

## Exemple de flux

Appel : `{"id_ressource": "71ff1335-..."}`

Réponse (échec) : `{"statut": "echec_technique", "message": "serveur_origine_bloque", "donnees": {"suggestion": "fichier_heberge_exterieurement"}}`

Réponse (succès) : `{"statut": "succes", "donnees": {"chemin_local": "donnees/71ff1335-....csv", "format": "csv"}}`

## Invariants

- Un échec de cette fonction ne provoque jamais la perte des autres acquisitions : chaque téléchargement est indépendant.
- Le registre est alimenté même en cas d'échec : une source inaccessible doit toujours être tracée.


## Manifeste d'acquisition (T10.8)

En cas de succès, `telecharger_brut` ajoute une entrée au manifeste `data/raw/<id_execution>/manifeste_acquisitions.json` (sortie latérale, sans évolution de contrat) : fichier, voie, identifiants et titre du jeu, organisation, url du jeu, licence, marquage conditionnel, mention d'attribution, horodatage. Un échec d'écriture du manifeste ne fait jamais échouer l'acquisition. Voir `docs/specs/stockage.md` §7.
