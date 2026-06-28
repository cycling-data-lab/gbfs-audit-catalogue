# gbfs-toolkit : audit des fonctions manquantes (v2)

Révisé après avoir construit la pipeline unifiée, l'analyse de robustesse et le
re-audit mondial. La librairie est riche (100+ fonctions exportées) et plusieurs
manques de la v1 sont **corrigés** : bug du résolveur de catalogue, plus
`audit_sensitivity` et `flag_rate_ci` ajoutés. Restent des manques structurants.

## Le constat de fond

**La librairie est un moteur de *verdict*, pas un moteur de *pipeline*.** Elle
calcule les flags A1-A7 (`audit_static`) mais n'implémente **aucune
reclassification** : `RULES` décrit la signature A3 (« conditional averaging »)
sans fonction qui la détecte ou qui relabellise. Les étapes S1 (carsharing par
opérateur) et S3 (free-floating par sur-capacité) du protocole de purge vivent
encore dans `audit_pipeline` du catalogue, hors librairie. C'est pourquoi le
re-audit mondial n'a pas pu rendre A1/A3 comparables sans que je recode
`apply_operator_types` à la main, et pourquoi A3 mondial = « free-floating
déclaré » et non « sur-capacité » (la vraie anomalie du papier).

## Tier 1 — bloque la reproduction end-to-end du papier dans la librairie

**T1.1 — Les transforms de reclassification (S1 / S3 / S9).**
`audit_static` lit `station_type` tel quel ; le papier le *produit* en amont.
Manque :
```python
classify_carsharing(info, names, *, keywords=...) -> info  # S1
overcapacity_ratio(info, status) -> Series  # bar_c_profile / bar_c_actual par système
reclassify(info, status=None, *, a3_ratio=5.0, n_min=20) -> info  # S1+S3+S9
```
Sans cela, FR (post-reclassification) et World (brut) ne sont pas auditables
à l'identique. **Note honnête :** la sur-capacité A3 (ratio profil/réel) exige
`station_status` (la capacité réalisée), pas seulement `station_information` ;
toute version statique seule restera un proxy (« free-floating déclaré »).

**T1.2 — `audit_catalogue` (fetch + audit par lot).**
Il y a `audit_feed(url)` (un flux) et `fetch_multiple` (fetch seul), mais rien
qui fetch N systèmes → verdict station-level + statut par système (+ archivage).
Je l'ai recodé deux fois (`unified_audit.py`, `run_unified_audit.py`). API :
```python
audit_catalogue(system_ids=None, *, catalog=None, archive_dir=None,
                a7_scope="docked", max_workers=8) -> (verdict, status)
```

## Tier 2 — ergonomie de recherche que le papier exerce

**T2.1 — `system_flags(verdict)`** : réduction station→système (système flaggé
ssi ≥1 station). Chaque compte par système du papier la refait à la main.

**T2.2 — Archivage reproductible au fetch** : `feed.snapshot(to=dir)` écrivant
les frames canoniques + `fetched_at` + SHA-256 (boucle BYOD « fetch une fois,
geler, auditer »). `generate_manifest` hashe un lake existant mais ne le crée
pas ; j'ai dû coder `fetch_and_archive`.

**T2.3 — Détecteur de sur-capacité A3** exposé (`overcapacity_ratio`) : le
mécanisme Bordeaux/Pony est décrit dans `RULES` mais jamais calculé par l'API.

## Tier 3 — helpers de validation (solidifient le papier)

**T3.1 — Accord inter-juges** : Krippendorff α, Cohen/Fleiss κ, IC de Wilson,
pour les tables d'annotation humaine (`tab:irr`, `tab:perrule`) — calculés hors
librairie aujourd'hui. Un module `agreement` les rendrait reproductibles et
citables, comme `audit_sensitivity` l'a fait pour la robustesse.

**T3.2 — Comptage « exclusif » inter-classes** : « systèmes A7 et aucune autre
classe » (le 245 du papier). `exclusive_flags(verdict)` éviterait de le recoder.

## Priorité

1. **T1.1 (reclassification)** : c'est le manque qui empêche la pipeline unique
   d'être *vraiment* unique sur A1/A3, et qui force le catalogue à garder du code
   métier. Le plus structurant scientifiquement.
2. **T1.2 (`audit_catalogue`)** : le plus utilisé opérationnellement.
3. **T3.1 (accord inter-juges)** : prochaine fonction qui solidifierait le papier,
   après `audit_sensitivity`, en rendant la validation humaine reproductible.
