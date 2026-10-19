# Fichier : extraire_ressource.md

# Outil extraire_ressource

## Intention

Matérialiser l'acquisition d'une ressource indexée par l'API tabulaire (voie 1) vers le stockage local : la pagination est conduite par le code de bout en bout, les lignes agrégées sont écrites en un CSV pivot dans `data/raw/`. Cette fonction écrit sur le disque : elle est réservée à l'acquisition finale d'une ressource sélectionnée, pas à l'exploration (prévisualisation : `interroger_ressource`).

## Sémantique des arguments

- `id_ressource` (obligatoire) : identifiant issu de `lister_ressources`. Comme `telecharger_brut`, la fonction ne prend pas d'URL : tout est résolu depuis l'inventaire.
- `taille_page` (interne, défaut 100) : lignes demandées par page à l'API — paramètre d'efficacité, pas de périmètre.
- `plafond_lignes` (interne, défaut `PLAFOND_EXTRACTION` = 10 000) : garde-fou contre l'extraction massive non maîtrisée.

## Retour en succès

`donnees.chemin_local` : chemin relatif du CSV extrait. `donnees.total_lignes` / `donnees.lignes_ecrites` : volumétrie côté API et effectivement écrite. `donnees.colonnes` : ordre conservé de l'API. `donnees.tronque` : vrai si le plafond a été atteint (succès partiel explicite — jamais un échec silencieux). La licence est incluse afin que les obligations d'attribution suivent le fichier jusqu'à la visualisation. `donnees.licence_conditionnelle` : vrai si la licence a été acceptée par dérogation (producteur public). `donnees.mention_attribution` : mention d'attribution prête à afficher ; `null` pour les licences à vérifier — jamais devinée. Version 1.1.0 (T7.5).

## Comportements d'échec

- `ressource_introuvable` : identifiant jamais délivré par `lister_ressources` au cours du flux (convention 1). Reprendre par l'inventaire.
- `ressource_non_indexee` : la ressource n'est pas indexée par l'API tabulaire. `donnees.suggestion` vaut `basculer sur telecharger_brut` : la voie 2 est le recours prévu par le contrat.
- `echec_technique` : échec HTTP en cours de pagination ou erreur d'écriture disque ; aucune écriture partielle n'est conservée en cas d'échec HTTP (le fichier n'est pas créé).

## Exemple de flux

Appel : `{"id_ressource": "71ff1335-..."}`

Réponse (succès) : `{"statut": "succes", "message": "", "donnees": {"chemin_local": "data/raw/flux/71ff1335-..._donnees.csv", "total_lignes": 150, "lignes_ecrites": 150, "colonnes": ["theme", "valeur"], "tronque": false, "licence": "lov2"}}`

Réponse (succès partiel) : `{"statut": "succes", "message": "Extraction tronquée au plafond de 10000 lignes (45000 lignes au total).", "donnees": {"tronque": true, ...}}`

## Invariants

- La pagination est conduite par le code : le consommateur (agent ou CLI) n'a jamais à paginer pour acquérir.
- Le plafond produit un succès partiel signalé (`tronque: true`, message), jamais un échec silencieux ni une perte de données cachée.
- Une collision de nom (ré-extraction dans la même exécution) produit un suffixe : un fichier acquis n'est jamais écrasé.
- La répartition exploration/acquisition est explicite : `interroger_ressource` n'écrit rien, `extraire_ressource` et `telecharger_brut` écrivent.


## Manifeste d'acquisition (T10.8)

En cas de succès, `extraire_ressource` ajoute une entrée au manifeste `data/raw/<id_execution>/manifeste_acquisitions.json` (sortie latérale, sans évolution de contrat) : fichier, voie, identifiants et titre du jeu, organisation, url du jeu, licence, marquage conditionnel, mention d'attribution, horodatage. Un échec d'écriture du manifeste ne fait jamais échouer l'acquisition. Voir `docs/specs/stockage.md` §7.
