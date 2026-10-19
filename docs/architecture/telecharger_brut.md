## Fichier : telecharger_brut.md

# Outil telecharger_brut

## Intention

Acquérir une ressource non indexée par l'API tabulaire dans son état brut (voie 2), vers le stockage local. Cette fonction écrit sur le disque : elle doit être réservée aux ressources sélectionnées, pas employée en exploration.

## Sémantique des arguments

- `id_ressource` (obligatoire) : identifiant issu de `lister_ressources`. La fonction ne prend pas d'URL : l'URL est résolue par le code à partir des métadonnées enregistrées lors de l'inventaire.

## Retour en succès

`donnees.chemin_local` : chemin relatif du fichier acquis. `donnees.format` : format de la ressource. La licence est incluse afin que les obligations d'attribution suivent le fichier jusqu'à la visualisation. `donnees.licence_conditionnelle` : vrai si la licence a été acceptée par dérogation (producteur public). `donnees.mention_attribution` : mention d'attribution prête à afficher, générée par le code à partir des métadonnées de l'inventaire (organisation, licence, date de mise à jour) ; `null` pour les licences à vérifier (`other-*`, `notspecified`) — jamais devinée, le message de la réponse l'explique alors. Version 1.1.0 (T7.5).

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
