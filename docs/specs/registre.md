# Registre des sources inaccessibles

## 1. Objet
Ce document décrit le **registre des sources inaccessibles**, utilisé pour consigner :
- Les **exclusions juridiques** (licences incompatibles).
- Les **échecs techniques** (blocages serveurs, erreurs HTTP).

## 2. Structure du registre
Le registre est stocké dans `data/registry.json` et persiste entre les exécutions.
Format :
```json
{
  "sources_inaccessibles": [
    {
      "timestamp": "2026-10-10T14:30:22Z",
      "motif": "licence_incompatible | serveur_origine_bloque | statut_http_*",
      "id_jeu": "67660551c8588734a16a6a60",
      "organisation": "Insee",
      "licence": "notspecified",
      "url": "https://data.gouv.fr/...",
      "detail": "Licence non ouverte | Statut HTTP 403",
      "statut_reprise": "a_retenter | definitif"
    }
  ]
}
```

T7.1 : `statut_reprise` est un champ **additif** des entrées techniques — `a_retenter` (échec transitoire épuisé : réseau, 429/502/503/504) ou `definitif` (400/401/403/410). Les entrées sans le champ (y compris les exclusions juridiques) sont lues comme `definitif` ; aucune entrée existante n'est modifiée.

## 3. Fonctionnement
- **Écriture** :
  - Les exclusions juridiques sont ajoutées par `rechercher_jeux`.
  - Les échecs techniques sont ajoutés par `telecharger_brut`.
- **Lecture** :
  - Le registre est accessible en lecture pour la synthèse finale (étape A4).
- **Persistance** :
  - Le fichier `registry.json` est chargé au démarrage et mis à jour à chaque exécution.

## 4. Exemple
```json
{
  "sources_inaccessibles": [
    {
      "timestamp": "2026-10-10T14:30:22Z",
      "motif": "licence_incompatible",
      "id_jeu": "abc123",
      "organisation": "Ministère X",
      "licence": "other-closed",
      "url": "https://data.gouv.fr/jeu/abc123",
      "detail": "Licence non ouverte"
    },
    {
      "timestamp": "2026-10-10T14:35:45Z",
      "motif": "serveur_origine_bloque",
      "id_jeu": "def456",
      "organisation": "Insee",
      "licence": "lov2",
      "url": "https://api.insee.fr/...",
      "detail": "Statut HTTP 403"
    }
  ]
}
```

## 5. Invariants
- Aucune entrée n'est supprimée ou modifiée après écriture.
- Le registre est **persistant** entre les exécutions.
