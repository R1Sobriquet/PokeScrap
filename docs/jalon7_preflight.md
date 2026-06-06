# Jalon 7 — Pré-vol : PSA Public API (vérification de cert)

## Méthode

Docs `psacard.com/publicapi/documentation` en **403** au fetcher. Forme reconstituée
depuis le contenu indexé + un client open-source (`brad-newman/fetch-psa-api`).

Sources :
- PSA Public API : https://www.psacard.com/publicapi
- Swagger : https://api.psacard.com/publicapi/swagger/ui/index
- Client OSS : https://github.com/brad-newman/fetch-psa-api

## Confirmé

| Élément | Réel |
|---|---|
| Endpoint cert | `GET https://api.psacard.com/publicapi/cert/GetByCertNumber/{certNumber}` |
| Auth | `Authorization: Bearer {token}` |
| Objet renvoyé | `PSACert` (champs **PascalCase**) |
| Champs utiles | `CertNumber`, `CardGrade`, `GradeDescription`, `IsValid`, `TotalPopulation`, `PopulationHigher`, `SpecID` |

## Corrigé (écarts vs spec Jalon 2)

1. **Auth** : la spec décrivait un *OAuth2 password grant*. En réalité PSA fournit
   un **token statique** généré dans le compte. → `PSAClient` supporte
   `PSA_API_TOKEN` (prioritaire, aucun échange) ; le password grant reste en repli.
2. **Base URL** : `api.psacard.com/publicapi` (et non `www.…`). Défaut + `.env.example`
   mis à jour.
3. **Chemin** : `/cert/GetByCertNumber/{n}` (au lieu de `/cert/{n}`).
4. **Champs** : `parse_cert` lit désormais PascalCase (`CardGrade`,
   `GradeDescription`, `IsValid`) et construit `pop_data` depuis
   `TotalPopulation`/`PopulationHigher`/`SpecID` ; les clés minuscules restent en
   repli (compat tests/mocks).

## Smoke-test

```bash
python scripts/smoke_psa.py        # skip propre sans creds ; sinon appel réel + mapping
```

Vérifié : **skip propre** sans creds (exit 0). Avec un `PSA_API_TOKEN` et
`PSA_SMOKE_CERT`, il imprime « champ API → colonne `psa_certs` ».

## Garde-fou métier

`verify_slab` ne renvoie **jamais** « authentique garanti » : un cert valide →
`WARN` (« cohérent ✔, inspection physique requise »), car des contrefaçons
réutilisent de vrais numéros. Cert invalide → `HARD_BLOCK('cert_invalid')`.
