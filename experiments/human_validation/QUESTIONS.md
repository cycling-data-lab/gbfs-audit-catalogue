# Human-Validation Annotation — Detailed Question Specification (v2)

Four plain questions in a conditional decision tree. Q1/Q2/Q3 are the three audit
objectives (docks present? right size? right place?); Q0 is a domain gate that
exists only to keep car-sharing out and to validate rule A1. Each answer is
**oui / non / indéterminé**; `indéterminé` is recorded, never forced.

```
Q0  libre-service vélo/trottinette ?        non ──► A1 (hors-domaine)  [STOP]
    │ oui
    ├─ Q1  docks physiques présents ?       oui ──► Q2 ;  non ──► (Q2 sans objet)
    ├─ Q2  bonne taille ? (si Q1=oui)
    └─ Q3  bien placée ?
```

## Objective → question mapping

| Your objective | Question | Rule(s) validated |
|---|---|---|
| (gate — keep car-share out) | Q0 | A1 |
| « est-ce qu'il y a une station avec des docks » | **Q1** | A3, A6 |
| « est-ce qu'il y a la bonne taille dedans » | **Q2** | A2 |
| « est-ce qu'elle est placée au bon endroit » | **Q3** | A4, A5 |
| (not imagery-validatable) | — | A7 (system-level only) |

## Q0 — Domaine (garde-fou)

- **Énoncé (FR)** : « S'agit-il d'un service de **vélos ou trottinettes** en libre-service — et non d'autopartage de voitures ou d'un autre type de véhicule ? »
- **Statement (EN)** : "Is this a shared-bicycle or shared-scooter service (not car-sharing or another vehicle class)?"
- **Montré à l'annotateur** : nom de l'opérateur/réseau, ville, lien vers le site opérateur, coordonnées. *(Pas l'imagerie : c'est une vérification documentaire.)*
- **OUI** : l'opérateur exploite des vélos/trottinettes en libre-service (confirmé par marque/site).
- **NON** : autopartage de voitures (Citiz, Communauto…) ou tout autre objet non vélo/trottinette.
- **INDÉTERMINÉ** : opérateur non identifiable depuis la marque + les coordonnées.
- **Routage** : NON → feuille **A1**, on arrête (ni Q1, ni Q2, ni Q3). OUI → Q1 et Q3.
- **Prédicat a posteriori** : A1 réel ⟺ Q0 = non.

## Q1 — Présence des docks  *(objectif 1)*

- **Énoncé (FR)** : « À l'emplacement indiqué, voit-on des **docks physiques** : une borne d'attache fixe, des points de verrouillage, ou une structure de station matérialisée ? »
- **Statement (EN)** : "At the given location, are physical docks visible — a fixed docking terminal, locking points, or a materialized station structure?"
- **Montré** : satellite + Street View centrés sur les coordonnées, overlay OSM `amenity=bicycle_rental`.
- **OUI** : matériel d'attache fixe visible — **même si la station est vide de vélos**.
- **NON** : aucun matériel fixe (trottoir nu, zone de dépose au sol sans borne, ou rien).
- **INDÉTERMINÉ** : imagerie > 24 mois, occlusion (arbres, ombre), pas de couverture Street View ni satellite exploitable.
- **Routage** : OUI → Q2 ; NON → Q2 sans objet, on passe à Q3.
- **Prédicat a posteriori** : A3 réel ⟺ Q1 = non (pas de dock physique → free-floating réel). A6 idem sur une station déclarée *docked*.
- **Cas limite** : station en travaux/démontée → INDÉTERMINÉ, pas NON.

## Q2 — Bonne taille  *(objectif 2)*

- **Énoncé (FR)** : « Le **nombre de docks visibles** correspond-il à la **capacité annoncée** par le flux, à ±50 % près ? »
- **Statement (EN)** : "Does the number of visible docks match the feed-declared capacity (within ±50%)?"
- **Montré** : la **capacité déclarée** (valeur brute du flux GBFS) + l'imagerie pour compter les docks.
- **OUI** : nombre de docks comptés ∈ [0,5 × capacité ; 1,5 × capacité].
- **NON** : hors de cette bande **OU** capacité = valeur ronde manifestement placeholder (10/20/50/100) avec un nombre de docks visiblement différent.
- **INDÉTERMINÉ** : docks présents mais non dénombrables sur l'imagerie disponible.
- **Routage** : posée **seulement si Q1 = oui** → puis Q3.
- **Prédicat a posteriori** : A2 réel ⟺ Q2 = non.
- **Note anti-anchoring** : on montre la capacité **brute du flux** (donnée d'entrée), jamais un verdict du pipeline — comparer l'observé au déclaré est précisément l'objet de la question, ce n'est pas de l'anchoring sur l'audit.

## Q3 — Bon endroit  *(objectif 3)*

- **Énoncé (FR)** : « La station est-elle **bien placée** ? C.-à-d. **(a)** sur terre, dans le bon pays / la bonne agglomération, **ET (b)** au contact de son réseau : à moins de **1 km** d'une autre station du même opérateur, ou à l'intérieur de l'**enveloppe** (convex hull) de ses stations. »
- **Statement (EN)** : "Is the station correctly located? i.e. (a) on land, in the declared country/metro area, AND (b) attached to its network: within 1 km of a sibling station, or inside the convex hull of the operator's stations."
- **Montré** : carte avec **toutes les stations sœurs** du même opérateur en overlay, plus un cercle de rayon 1 km autour de la station jugée.
- **OUI** : (a) **et** (b) vrais.
- **NON** : (a) faux — point en mer/champ/mauvais pays (profil A5) — **OU** (b) faux — isolée à > 1 km et hors enveloppe (profil A4).
- **INDÉTERMINÉ** : stations sœurs non chargeables pour cet opérateur.
- **Routage** : posée si Q0 = oui, pour **toute** station réelle (dock **ou** flottante).
- **Prédicat a posteriori** : A4 réel ⟺ Q3 = non ; A5 réel ⟺ Q3 = non. *(Le pipeline distingue A4 vs A5 ; l'humain juge seulement « bien placée ou non ». La distinction A4/A5 est reconstruite via le stratum.)*
- **⚠ Risque connu** : cette question regroupe deux jugements (périmètre + proximité réseau) — c'est le profil exact du Q4 v1 qui s'était effondré (κ = 0,13). Le critère opérationnel dur (1 km / enveloppe) + l'overlay pré-calculé visent à neutraliser ce risque. **Alternative à arbitrer** (voir prompt Gemini) : scinder en Q3a « bon pays/périmètre ? » et Q3b « proche de son réseau ? ».

## Endpoints produits

- α (Krippendorff) **par question** sur l'ensemble co-routé — cible ≥ 0,70 (vs 0,17 / 0,13 des questions interprétatives v1).
- α sur le **verdict composite** `TYPE|PLACEMENT`.
- Précision/rappel **par règle** A1–A6 (Wilson 95 %), dérivés a posteriori.
- **Taux de FP du détecteur legacy** sur le stratum `A4_discordant_legacy` = part jugée bien placée (Q3 = oui) — successeur direct du « les 8 005 sont-ils de vrais FP ? ».
- Audit de **divergence de routage** : première question où les deux annotateurs divergent.
