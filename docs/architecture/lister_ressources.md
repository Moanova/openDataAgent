## Fichier : lister_ressources.md

# Outil lister_ressources

## Intention

Inventorier les ressources (fichiers) d'un jeu retenu par l'étape de sélection (A2), avec classification pré-remplie par le code (B3). C'est la fonction qui arme les décisions ultérieures : voie d'acquisition, classification ambiguë, téléchargement.

## Sémantique des arguments

- `id_jeu` (obligatoire) : identifiant issu de `rechercher_jeux`.

## Retour en succès

`donnees.ressources` : pour chaque ressource, identifiant, titre, format, taille, classe (`fichier_tabulaire` | `fichier_autre_format` | `page_web` | `api_distante` | `indetermine`), disponibilité via l'API tabulaire (`api_tabulaire`), hébergement sur la plateforme (`heberge_sur_plateforme`) et URL. `donnees.indetermination` : sous-ensemble des ressources que le code n'a pas su classer ; c'est le déclencheur de l'étape agentique A3 — l'agent tranche en s'appuyant sur le titre et l'URL, sans possibilité de re-classement par appel d'outil (sa décision est consignée dans son raisonnement, le code garde la classification initiale). Sémantique de l'ambiguïté (T3.2.3) : des signaux contradictoires (ex. format déclaré csv, mime détecté text/html) ne sont pas des ambiguïtés — ils sont tranchés par l'ordre de priorité du classificateur (HTML > api_distante > fichier_tabulaire > fichier_autre_format). Seuls des signaux absents ou inconnus produisent `indetermine`. La réponse est autoportante pour A3 : chaque identifiant de `indetermination` est accompagné, dans `donnees.ressources`, de son titre et de son URL — l'agent tranche sans appel d'outil supplémentaire.

## Comportements d'échec

- `jeu_introuvable` : identifiant inconnu du catalogue. Reprendre à `rechercher_jeux`.

## Exemple de flux

Appel : `{"id_jeu": "67660551c8588734a16a6a60"}`

Réponse (succès) : `{"statut": "succes", "donnees": {"ressources": [{"id": "71ff1335-...", "titre": "Comptes des administrations publiques", "format": "csv", "taille_octets": null, "classe": "fichier_tabulaire", "api_tabulaire": false, "heberge_sur_plateforme": false, "url": "https://api.insee.fr/..."}], "indetermination": []}}`

## Source API (T11.3 — migration v1 → v2)

L'inventaire mobilise **deux appels** séquentiels (en v2, `resources` n'est plus embarqué dans le détail du jeu) :

1. `GET /api/2/datasets/{id}` : métadonnées du jeu (titre, licence, organisation, `last_update`). Un 404 produit `jeu_introuvable` — aucun second appel n'est effectué.
2. `GET /api/2/datasets/{id}/resources/?page=N&page_size=50` : sous-ressource paginée ; la couche HTTP boucle sur `next_page` jusqu'à épuisement (arrêt sur `next_page` absent, jamais sur une erreur HTTP), avec un plafond de sécurité de 20 pages (échec explicite « plafond atteint » en garde anti-boucle).

Le payload retourné au cœur est **reconstitué** au format attendu (détail du jeu + liste `resources` plate) : la normalisation aval est inchangée, l'isolant HTTP absorbe la restructuration v2. `derniere_maj` est mappé sur `last_update`. Schéma : `contrats/schemas_api/lister_ressources.reponse.json` (payload reconstitué).

## Invariants

- L'appel enregistre les métadonnées de chaque ressource : c'est ce qui rend `telecharger_brut` possible ensuite.
- Une ressource `fichier_tabulaire` avec `api_tabulaire` vrai doit être extraite par `interroger_ressource`, jamais téléchargée brutalement en premier recours.
