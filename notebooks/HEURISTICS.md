# Réflexion : l'heuristique carsharing et les autres

Note de conception, fondée sur une sonde empirique (échantillon de 140 systèmes
joignables du catalogue MobilityData, 2026-06).

## Le retournement : GBFS v3 encode déjà la plupart des signaux

J'archivais A1 (carsharing) comme « heuristique » parce que `station_information`
ne déclare pas le type. **C'était une erreur de périmètre** : le signal existe,
mais dans un *autre flux*.

| Signal spec GBFS v3 | Ce qu'il détermine | Couverture mesurée |
|---|---|---|
| `vehicle_types.form_factor == "car"` | carsharing (A1) | **96 %** des feeds joignables publient `form_factor` |
| `station_information.is_virtual_station` | ancre free-floating (A3) | **71 %** |
| `capacity == NaN` / `== 0` | A7 / A6 | 100 % (champ obligatoire) |

Donc **A1 et A3 sont feed-intrinsèques pour la grande majorité des feeds**, via
les champs propres du standard. L'heuristique (nom d'opérateur pour A1, ratio de
sur-capacité pour A3) n'est qu'un **fallback** pour le trou de couverture
(~4 % sur `form_factor`, ~29 % sur `is_virtual_station`).

Conséquence directe pour le papier : **A1 World n'est pas 0**, c'est le nombre de
systèmes déclarant `form_factor="car"` (certain, feed-intrinsèque). Le 36 par nom
d'opérateur n'est utile que pour les ~4 % sans `vehicle_types`. Cela mérite de
réviser la décision « A1 archivé = 0 ».

## Le principe scientifique unificateur

> **Une anomalie se détecte d'abord par le signal spec-compliant le plus
> spécifique disponible ; l'heuristique est le fallback quand ce signal est
> absent. Le statut scientifique d'une heuristique se définit par (a) le trou de
> couverture qu'elle comble et (b) sa précision/rappel validée sur ce trou.**

Cela rend chaque heuristique auditable : on mesure la fréquence du signal certain,
et on ne valide le fallback que sur le résidu. C'est la discipline « ne garder
que le sûr » rendue systématique, en trois tiers :

- **Tier 0 — certain (feed-intrinsèque)** : `form_factor`, `is_virtual_station`,
  `capacity` NaN/0. Aucune heuristique.
- **Tier 1 — définitionnel** : règles structurelles transparentes (A2
  zéro-variance, A5 bbox, A7 taux NaN). Seuils, mais explicites et sweepables
  (`audit_sensitivity`).
- **Tier 2 — heuristique fallback** : quand Tier 0 manque (nom d'opérateur,
  ratio de sur-capacité). À valider, à étiqueter, à archiver séparément.

## Revue des heuristiques

**H1. Carsharing (A1).** Tier 0 = `form_factor="car"` (96 %). Fallback = regex de
noms d'opérateurs (`citiz`, `car2go`, …) pour les 4 % sans `vehicle_types`.
Action : `classify_from_vehicle_types(info, vehicle_types)` (feed-intrinsèque) ;
le regex devient un fallback validé sur le résidu. Attention au piège déjà
rencontré : `cargo_bicycle` contient « car » → matcher le form_factor en égalité
exacte, pas en sous-chaîne.

**H2. Free-floating (A3).** Tier 0 = `is_virtual_station=true` (71 %) ou
`station_type` natif. Fallback = `overcapacity_ratio > 5` (déjà dans la
librairie) pour les 29 % sans le champ. La sur-capacité reste utile en soi (le
mécanisme Bordeaux), mais comme fallback de classification elle est second rang
derrière le booléen spec.

**H3. Outlier géospatial (A4).** Heuristique statistique (3σ MAD sur distance au
plus proche voisin), durcie par la version topologie-aware (HDBSCAN + spectral).
Robustesse déjà mesurée (`audit_sensitivity` : Jaccard ≥ 0,91 sur σ∈[2,4]).
Pas de signal spec ; reste Tier 2 mais validé.

**H4. Hors-périmètre (A5).** Seuil d'aire bbox > 50 000 km². Heuristique
géographique ; la bbox surestime pour les réseaux allongés (cas Suisse). Piste :
convex hull plutôt que bbox, et A5 calculée *après* le filtre A4 (cas Sevici, la
sentinelle (0,0)).

**H5. Seuils de taux A6/A7 (1 %, 50 %) et N_min=20.** Justifiés par la
distribution bimodale (A7) et la littérature des réseaux maillés (N_min).
Sweepables ; robustesse mesurée (A7 Jaccard ≥ 0,96).

**H6. Coordonnée sentinelle (0,0).** Heuristique d'hygiène : une station à (0,0)
gonfle la bbox d'un facteur 10⁴. Détection triviale et certaine ; à intégrer en
pré-filtre.

**H7. Station zombie.** Présente dans `station_information`, disparue au sol.
Non détectable en statique : exige la fraîcheur `station_status`
(`last_reported`) ou l'imagerie. L'annotation v1 en a trouvé 12,9 %. C'est le
manque dynamique (D-classes), Tier 2 fondé sur le temps.

## Heuristiques nouvelles à considérer

- **Empreinte de convention de capacité** : classer chaque système dans
  {NaN, placeholder constant, ratio par véhicule, profil conditionnel} — les 6
  conventions du papier. Une fonction `capacity_convention(info)`.
- **Identité d'opérateur multi-signal** : croiser nom MobilityData +
  `system_information.operator` + domaine de l'URL, plus robuste qu'un regex
  unique pour le fallback H1.
- **Mix multi-modal** : systèmes `form_factor` mixtes (un Citiz déclarait
  `car + cargo_bicycle + other`) — carsharing partiel, à arbitrer.

## Méthodologie de validation (commune)

Chaque heuristique Tier 2 se valide ainsi, et la librairie a déjà les outils :
1. Mesurer la couverture du signal Tier 0 (fait : 96 % / 71 %).
2. Construire un set étiqueté sur le résidu (l'annotation humaine est ce set).
3. Précision/rappel avec IC de Wilson (`wilson_interval`), accord inter-juges
   (`krippendorff_alpha`, `cohen_kappa`).
4. Sensibilité de tout seuil (`audit_sensitivity`).

## Recommandations

1. **Promouvoir A1 en feed-intrinsèque** via `form_factor` (96 % de couverture) :
   `classify_from_vehicle_types`. Réviser l'A1 World du papier (≠ 0).
2. **Hiérarchiser A3** : `is_virtual_station` d'abord, `overcapacity_ratio` en
   fallback.
3. **Garder les seuils (A4/A5/A6/A7, N_min) en Tier 1** avec leur sweep de
   robustesse, déjà reproductible.
4. **Archiver les fallbacks de noms** (carsharing regex, identité opérateur) en
   Tier 2 explicite, validés seulement sur le résidu de couverture.
5. Le seul vrai angle mort reste **H7 (zombie)**, qui demande le dynamique.
