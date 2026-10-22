## Fichier : rechercher_jeux.md

# Outil rechercher_jeux

## Intention

Exécuter une recherche sur le catalogue data.gouv.fr à partir de mots-clés produits par l'étape de reformulation du thème (A1). C'est l'unique point d'entrée du flux : aucun autre outil ne doit être appelé sans un identifiant issu de cette fonction.

## Sémantique des arguments

- `mots_cles` (obligatoire) : la recherche applique une logique ET sur l'ensemble des termes. Des termes génériques (« données », « fichier ») produisent peu ou pas de résultats. L'agent doit produire des termes courts et spécifiques, et peut lancer plusieurs recherches complémentaires pour couvrir un thème.
- `tri` : `pertinence` (défaut), `recent` (mise à jour décroissante), `vues` (audience décroissante), `reutilisations`.
- `fenetre_maj` **(déprécié, v1.3.0 / T11.3)** : accepté pour compatibilité mais **ignoré** — l'API v2 de data.gouv.fr ne supporte pas la fenêtre de mise à jour (`last_update_range` rejeté en HTTP 400, sondage S11.0). Toute valeur autre que `toutes` (défaut) produit un avertissement dans le `message` de la réponse, sans faire échouer la recherche. Le retrait complet du paramètre est prévu avec T7.4 (autres sources).
- `limite` : nombre maximum de jeux retournés, défaut 10, maximum 20. Au-delà, paginer.
- `page` : numéro de la page de résultats demandée, défaut 1. Chaque appel retourne une seule page ; l'agent pagine en rappelant l'outil avec le même `mots_cles`/`tri` et un `page` incrémenté, tant que la réponse l'y invite (présence d'une page suivante). Le tri doit rester identique entre les pages d'une même requête pour garantir la stabilité de la pagination.

## Retour en succès

`donnees.total_trouves` : nombre total de jeux correspondant à la requête, indépendant de `limite` et de `page`. `donnees.page_courante` : numéro de la page retournée. `donnees.page_suivante` : numéro de la page suivante si elle existe, null sinon ; l'agent utilise ce champ pour décider de paginer. `donnees.jeux` : liste résumée (identifiant, titre, organisation, licence, date de dernière mise à jour, nombre de ressources, URL de la fiche). `donnees.exclus_licence` : nombre de jeux écartés par le filtre de licence et consignés au registre. `donnees.acceptes_licence_conditionnelle` : nombre de jeux acceptés sous licence conditionnelle (producteur public, licence non renseignée), tracés au registre des acceptations. Chaque jeu retourné porte `licence_conditionnelle` (vrai/faux). `donnees.nb_tentatives` : nombre de tentatives de l'appel HTTP (1 = succès au premier essai ; T7.1). `donnees.motif` : motif de l'échec HTTP (`transitoire`, `acces_refuse`, `ressource_supprimee`, `requete_invalide` ; T7.1), ou `circuit_ouvert` en mode agentique quand le circuit breaker a intercepté l'appel (T7.7) — absent (null) en cas de succès. Version 1.5.0 (T7.7 : champ additif `motif` ; la version 1.4.0 ajoutait `nb_tentatives`, T7.1 ; la version 1.3.0 dépréciait `fenetre_maj`, T11.3).

## Comportements d'échec

- `echec_technique` : le catalogue est injoignable après les tentatives configurées. Une seule relance est pertinente, puis abandon.
- `erreur_parametres` : `mots_cles` absent ou vide.

## Exemple de flux

Appel : `{"mots_cles": ["dette", "publique"], "tri": "vues", "limite": 10}`

Réponse (succès) : `{"statut": "succes", "donnees": {"total_trouves": 39, "jeux": [{"id": "67660551c8588734a16a6a60", "titre": "Comptes des administrations publiques", "organisation": "Insee", "licence": "etalab-2.0", "derniere_maj": "2026-01-15", "nb_ressources": 2, "url": "..."}], "exclus_licence": 3}}`

## Source API (T11.3 — migration v1 → v2)

Endpoint : `GET https://www.data.gouv.fr/api/2/datasets/search/`. Décisions actées (concepteur, sondage S11.0) :

- **Pertinence** : le tri `pertinence` est le tri implicite du moteur v2 (celui du site) — aucun paramètre `sort` n'est envoyé.
- **Tri** : mapping inchangé (`recent` → `-last_update`, `vues` → `-views`, `reutilisations` → `-reuses`), vérifiés supportés en v2.
- **`derniere_maj`** : mappé sur `last_update` (dernière mise à jour d'une ressource — fraîcheur des données), pas sur `last_modified` (métadonnées).
- **Pagination** : `next_page` (URL absolue) → `page_suivante` (numéro) ; la pagination s'arrête sur `next_page` absent, jamais sur une erreur HTTP (la v2 peut répondre 400 au-delà du total).
- **`organization`** : modèle identique en v2, badges uData (`public-service`, `local-authority`, `certified`) présents — le chantier B de T7.5 (type d'organisation, licences conditionnelles) est intact.
- **`resources`** : sous-ressource paginée (`rel`/`href`/`total`) dans les résultats de recherche ; `nb_ressources` est lu sur `total`.
- **Schéma** : `contrats/schemas_api/rechercher_jeux.reponse.json` réécrit sur la v2.

## Invariants

- Aucun jeu de licence incompatible n'apparaît dans `jeux`.
- Un jeu exclu n'est jamais retourné par une pagination ultérieure de la même requête.
