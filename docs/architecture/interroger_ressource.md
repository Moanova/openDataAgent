## Fichier : interroger_ressource.md

# Outil interroger_ressource

## Intention

Extraire des données d'une ressource indexée par l'API tabulaire (voie 1). Utilisée par l'agent de sélection pour prévisualiser le contenu d'un jeu candidat avant décision, et par le flux pour l'extraction finale.

## Sémantique des arguments

- `id_ressource` (obligatoire) : identifiant issu de `lister_ressources`.
- `page`, `taille_page` : pagination, défaut 1 et 20, maximum 50 (limite de l'API tabulaire, vérifiée en réel).
- `filtre` : objet à trois champs — `colonne`, `valeur`, `operateur` (`exact`, `contient`, `inferieur`, `superieur`, `strictement_inferieur`, `strictement_superieur`, défaut `exact`). Le filtrage s'applique à une colonne à la fois ; un filtrage multi-critères se fait par invocations successives.
- `tri` : objet à deux champs — `colonne`, `ordre` (`croissant`, `decroissant`).

## Retour en succès

`donnees.total_lignes` : nombre total de lignes de la ressource. `donnees.colonnes` : schéma détecté. `donnees.lignes` : page courante. `donnees.page` : numéro de la page courante. `donnees.page_suivante` : numéro de la page suivante si elle existe, null sinon — l'agent l'utilise pour paginer (tri et filtre identiques entre les pages d'une même extraction). `donnees.recommandation` : présent uniquement si `total_lignes` dépasse le seuil configurable (5000 par défaut), avec la valeur `volume_eleve_telechargement_brut_suggere` — l'agent peut alors décider de basculer sur `telecharger_brut`. `donnees.nb_tentatives` : nombre de tentatives de l'appel HTTP (1 = succès au premier essai ; T7.1). `donnees.motif` : motif de l'échec HTTP (`transitoire`, `acces_refuse`, `ressource_supprimee`, `requete_invalide` ; T7.1), ou `circuit_ouvert` en mode agentique quand le circuit breaker a intercepté l'appel (T7.7) — absent (null) en cas de succès. Version 1.3.0 (T7.7 : champ additif `motif` ; la version 1.2.0 ajoutait `nb_tentatives`, T7.1).

## Comportements d'échec

- `ressource_non_indexee` : basculer sur `telecharger_brut`.
- `echec_technique` : une relance est pertinente.

## Exemple de flux

Appel : `{"id_ressource": "e322fb3f-...", "taille_page": 50, "tri": {"colonne": "annee_horizon", "ordre": "decroissant"}}`

Réponse (succès) : `{"statut": "succes", "donnees": {"total_lignes": 74, "page": 1, "colonnes": ["theme", "indicateur", "annee_horizon", "valeur", "unite"], "lignes": ["..."]}}`

## Invariants

- Ne jamais être appelée sur une ressource sans `api_tabulaire` vrai : le code retourne `ressource_non_indexee` dans ce cas, mais l'agent doit lire `lister_ressources` en premier.
