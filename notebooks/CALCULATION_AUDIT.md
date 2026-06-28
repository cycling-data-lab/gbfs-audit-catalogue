# Audit des calculs du papier (A1-A7) et pipeline unifiée

Vérification reproductible des comptes du manuscrit, et correctif : **une seule
pipeline** (`gbfs_toolkit.audit_static`) pour la France et le monde.

Tout est rejouable depuis ce dossier avec le venv du toolkit
(`../../gbfs-toolkit/.venv/bin/python`).

## Résumé exécutif

| Constat | Statut |
|---|---|
| La colonne FR de la Table 1 se reproduit exactement par la librairie | OK (notebook 01) |
| La colonne Global et la colonne FR viennent de **deux pipelines différents** | **À corriger** |
| Le `verify_snapshot.py` du repo passe ses 19 checks (les chiffres globaux sont cohérents *entre eux*) | OK |
| `A3 FR=41 > A3 Global=33` est impossible sous « Global ⊇ FR » | **Incohérence de définition** |
| Le tableau global du papier reporte FR=(17,**14**,**4**,**3**,3), la Table 1 FR=(17,**1**,**41**,**88**,4) | **Contradiction interne** |
| `A5 Global = 17` non reproductible (recalcul = 10) | **À vérifier** |
| Les deux fichiers globaux du repo se contredisent (A3 = 31 vs 265) | **Artefacts incohérents** |
| IC du taux de retrait `[-18,6 %, 63,6 %]` (borne négative) | Déjà retiré du `.tex` |

## 1. Le problème central : deux pipelines sous les mêmes labels

La Table 1 met côte à côte deux calculs incomparables :

- **Colonne FR** = parquet certifié, station-level, **post-audit** (reclassification
  S1/S3). `A3 = 41` = systèmes avec ≥1 `free_floating` après S3 ; `A4 = 88` =
  détecteur d'**outlier** topologique au niveau station.
- **Colonne Global** = snapshot brut `massive_audit_results.csv`, **system-level**,
  inférence de type par **nom d'opérateur**, seuils **stricts**, sans S3.
  `A3 = 33` = `a3_overcap_flag` (ratio > 5) ; `A4 = 81` = `a4_perim_flag`
  (hors périmètre), un détecteur **différent** de l'outlier.

Conséquences mesurées :

```
FR via la librairie (notebook 01) : A1=17 A2=1  A3=41 A4=88 A5=4 A6=0 A7=32   (= Table 1 FR, exact)
FR via le snapshot global          : A1=17 A2=14 A3=4  A4=3  A5=3             (verify_snapshot.py)
```

Le même « A3 France » vaut **41** (Table 1) et **4** (tableau global) ; « A4 France »
vaut **88** vs **3**. Ce ne sont pas des erreurs de calcul isolées : ce sont deux
définitions sous un seul intitulé, ce qui rend `A3 FR=41 > Global=33` mécaniquement
impossible.

## 2. La colonne Global mélange trois conventions de comptage

Sur le snapshot (France incluse, 255 systèmes FR sur 1509) :

| Classe | Table 1 « Global » | Reproduit par | Base / convention |
|---|---|---|---|
| A1 | 46 | **46** | systèmes publiant station_information (917), monde |
| A2 | 48 | **48** | idem (917) |
| A3 | 33 | **33** | idem (917), détecteur strict |
| A4 | 81 | **81** | idem (917), `a4_perim_flag` |
| A5 | 17 | **10** | ne reproduit pas (à vérifier) |
| A6 | 22 | **22** | docked ≥20 stations (base 301) |
| A7 | 245 | **245** | A7 **exclusif**, ≥20 stations (base 640) |

Donc dans une seule colonne : A1-A4 sur base « 917, inclusif » ; A6/A7 sur base
« ≥20 stations » ; A7 en définition **exclusive** ; A5 d'une source non
retrouvée. Le funnel se reproduit, lui : `1509 → 1420 reachable → 917
station_information → 204 déclenchent A1-A5`.

## 3. Autres soucis

- **Deux fichiers globaux incohérents** : `massive_audit_results.csv` donne A3=31
  (strict) ; `global_audit_results_typed.csv` donne A3=265 (toute station A3).
  Choisir un artefact canonique unique.
- **A5 = 17** : non couvert par `verify_snapshot.py` et non reproduit (recalcul
  `a5_macro_flag` sur la base 917 = 10). Probable coquille ou run antérieur.
- **IC `[-18,6 %, 63,6 %]`** : borne inférieure négative pour une proportion ;
  déjà remplacé dans le manuscrit par « does not yield an informative interval ».

## 4. Le correctif : une seule pipeline (ces notebooks)

`gbfs_toolkit.audit_static` est appliqué **à l'identique** aux deux corpus
(`unified_audit.py`) :

- **`01_audit_unifie_france.ipynb`** : France, hors-ligne, depuis le parquet.
  Reproduit la colonne FR **exactement** (assertion verte).
- **`02_audit_unifie_global.ipynb`** : monde (France incluse), **re-fetch live**
  via la librairie, **même** fonction d'audit. FR ⊂ World, chaque classe sous une
  définition unique.

Mise en garde : le sweep global est **live**. C'est un *nouveau* snapshot (date du
jour) ; des flux du gel 2026-04 sont morts (couverture rapportée, ~80 % sur
échantillon). Adopter cette pipeline pour le papier signifie **remplacer** les
chiffres globaux 2026-04 par un audit unifié daté. Lancer le sweep complet :
mettre `SAMPLE = None` dans le notebook 02.
