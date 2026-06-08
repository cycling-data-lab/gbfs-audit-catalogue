# Prompt — demande d'avis à Gemini sur l'instrument d'annotation

Copier-coller le bloc ci-dessous dans Gemini.

---

Tu es un·e méthodologue en science des données et en validation par
annotation humaine. Je prépare une campagne d'annotation pour valider un audit
de qualité de données sur des flux de vélos/trottinettes en libre-service
(standard GBFS). J'ai besoin d'une **critique sévère** de mon instrument de
questions, pas d'un encouragement.

## Contexte

On audite des flux GBFS (open data de mobilité). Le pipeline classe chaque
station via 7 règles :
- A1 hors-domaine (autopartage de voitures listé comme vélo-partage)
- A2 capacité placeholder (capacité constante factice)
- A3 sur-capacité structurelle (station « virtuelle » free-floating vendue comme dock)
- A4 outlier géospatial (station isolée, incohérente avec son réseau)
- A5 hors-périmètre (coordonnées hors zone de service)
- A6 dock à capacité zéro
- A7 champ capacité null (NaN)

But de l'annotation : pour un échantillon stratifié (~570 stations), deux
annotateurs humains jugent **en aveugle** (sans voir la sortie du pipeline),
à partir d'imagerie (satellite, Street View, carte OSM), la réalité physique
de chaque station, pour en dériver a posteriori la précision/le rappel de
chaque règle et un accord inter-annotateurs.

## Ce qui a échoué dans la campagne précédente (v1)

On posait 4 questions **en parallèle** à toutes les stations. Accord de Cohen :
- Q1 « est-ce un vélo-partage ? » → κ = 0,70 (OK, concret)
- Q2 « la capacité est-elle physique ? » → κ = 0,17 (effondré)
- Q3 « infrastructure au sol ? » → κ = 0,62 (OK)
- Q4 « position réseau cohérente ? » → κ = 0,13 (effondré)

Diagnostic : les questions interprétatives (Q2, Q4) s'effondrent, et Q2 était
posée hors-contexte (« capacité physique » n'a pas de sens sur une station
sans dock). Contrainte forte : les 2 annotateurs sont les 2 auteurs du papier
(pas d'annotateur externe) ; on compense par pré-enregistrement, codebook
verrouillé et publication des labels bruts.

## Mon objectif, en une phrase

Pour chaque station je veux savoir : **(1) y a-t-il des docks physiques, (2) la
bonne taille (capacité) dedans, (3) est-elle placée au bon endroit.**

## Instrument proposé (v2) : 4 questions binaires EN CASCADE

Chaque question = oui / non / indéterminé. `indéterminé` est enregistré, jamais
forcé. Le routage conditionnel évite de poser une question hors-contexte.

**Q0 — Domaine (garde-fou)** : « Service de vélos/trottinettes en libre-service
(pas autopartage de voitures) ? »
 → NON = hors-domaine (A1), on s'arrête. OUI → Q1 et Q3.

**Q1 — Docks présents** : « À l'emplacement, voit-on des docks physiques (borne
fixe, points de verrouillage, structure matérialisée) ? »
 → OUI → Q2. NON (free-floating ou rien) → Q2 sans objet, on passe à Q3.
 (Une station vide de vélos mais avec bornes = OUI.)

**Q2 — Bonne taille** (posée seulement si Q1=oui) : « Le nombre de docks
visibles correspond-il à la capacité annoncée par le flux, à ±50 % près ? »
 → OUI = bonne taille. NON = mauvaise taille (A2). On montre la capacité brute.

**Q3 — Bon endroit** : « Bien placée ? = (a) sur terre, bon pays/agglo, ET
(b) à moins de 1 km d'une station sœur du même opérateur OU dans l'enveloppe
(convex hull) de ses stations. » On montre la carte des stations sœurs + cercle 1 km.
 → OUI = bien placée. NON = mal placée (A4 si isolée dans le réseau, A5 si hors-périmètre).

Mapping de validation : A1⟺Q0=non, A2⟺Q2=non, A3⟺Q1=non, A4⟺Q3=non,
A5⟺Q3=non, A6⟺Q1=non. A7 reste système-niveau (non vérifiable sur imagerie).

## Ce sur quoi je veux ton avis critique

1. **Ces 4 questions couvrent-elles bien mon objectif** (docks / taille /
   placement) ? Manque-t-il une question, ou y en a-t-il une de trop ?
2. **Clarté et non-ambiguïté** : chaque énoncé est-il assez opérationnel pour
   que deux annotateurs indépendants répondent pareil ? Reformule ce qui reste flou.
3. **Q3 est mon point faible** : elle regroupe deux jugements (périmètre +
   proximité réseau), exactement le profil du Q4 v1 qui s'est effondré.
   Faut-il **la scinder en deux** (Q3a périmètre, Q3b proximité) ou le critère
   opérationnel dur (1 km / enveloppe) suffit-il ? Argumente.
4. **Q2 — tolérance ±50 %** : est-ce raisonnable vu l'imprécision du comptage
   de docks sur imagerie ? Proposerais-tu une autre bande, ou une échelle
   ordinale (sous-estimé / correct / sur-estimé) plutôt qu'un binaire ?
5. **Routage conditionnel** : la logique de cascade est-elle correcte ? Y a-t-il
   un cas de station réelle qui tombe dans un trou (aucune feuille valide) ?
6. **Biais d'anchoring** : montrer la capacité brute du flux en Q2 est-il un
   problème ? Et l'overlay des stations sœurs en Q3 ?
7. **Contrainte 2-auteurs** : au-delà du pré-enregistrement et du codebook
   verrouillé, que recommandes-tu pour rendre l'accord crédible malgré
   l'absence d'annotateur externe ?
8. **Métriques** : pour un instrument en cascade, vaut-il mieux reporter
   l'α par question sur l'ensemble co-routé, ou un α sur le verdict composite,
   ou les deux ? Pièges statistiques du routage conditionnel sur le calcul d'accord ?

Donne une **réécriture concrète** des énoncés que tu juges améliorables (FR + EN),
et une recommandation tranchée sur Q3 (scinder ou pas).
