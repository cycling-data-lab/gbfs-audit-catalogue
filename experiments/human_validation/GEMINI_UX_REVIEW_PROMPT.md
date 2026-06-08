# Prompt — avis Gemini sur l'instrument + l'UX/UI de l'app d'annotation

Copier-coller le bloc ci-dessous dans Gemini.

---

Tu es à la fois méthodologue en validation par annotation humaine ET designer
produit/UX. Je veux une critique sévère et concrète de mon application web
d'annotation, sur deux plans : (1) la qualité de l'instrument de mesure,
(2) l'UX/UI. Pas d'encouragements de complaisance ; donne des recommandations
actionnables et, quand c'est pertinent, des réécritures de libellés (en français).

## Contexte scientifique

J'audite des flux GBFS (open data de vélos/trottinettes en libre-service). Un
pipeline classe chaque station selon 7 règles d'anomalie :
- A1 hors-domaine (autopartage de voitures listé comme vélo-partage)
- A2 capacité placeholder (capacité constante factice)
- A3 sur-capacité structurelle (station « virtuelle » free-floating vendue comme dock)
- A4 outlier géospatial (station isolée, incohérente avec son réseau)
- A5 hors-périmètre (coordonnées hors zone de service)
- A6 dock à capacité zéro
- A7 champ capacité NaN (niveau système, non vérifiable sur imagerie)

But de l'app : deux annotateurs humains jugent EN AVEUGLE (sans voir la sortie
du pipeline), à partir d'imagerie, la réalité physique de ~530 stations d'un
échantillon stratifié. On en dérive a posteriori la précision/le rappel de chaque
règle et l'accord inter-annotateurs. Contrainte forte : les 2 annotateurs sont
les 2 auteurs du papier (pas d'annotateur externe) ; on compense par
pré-enregistrement, codebook verrouillé, aveuglement, et publication des labels
bruts. Une campagne v1 avec 4 questions posées EN PARALLÈLE avait échoué : deux
questions interprétatives s'étaient effondrées (accord de Cohen kappa = 0,17 et
0,13), car posées hors-contexte et mal formulées.

## L'instrument actuel (v2) : une question à la fois, arbre de décision

La première question est un classement de TYPE à 5 entrées (au lieu d'un
binaire), censé couvrir 1:1 les classes d'audit. Le routage conditionnel évite
de poser une question hors-contexte.

```
Q0  Quelle est la nature de la station ?  (une seule réponse)
  1) VLS à borne (docks physiques visibles)            -> Q2 taille -> Q3a, Q3b
  2) Vélos en libre-service SANS borne (flotte libre)  -> Q3a, Q3b   [= A3]
  3) Trottinettes en libre-service                     -> STOP  [hors-domaine]
  4) Autopartage de voitures                           -> STOP  [= A1]
  5) Rien / aucun service visible                      -> STOP  [station fantôme / zombie]
  6) Indéterminé                                       -> STOP

Q2  Combien de points d'ancrage (docks) comptez-vous ?
    classes ordinales : 0 / 1-5 / 6-10 / 11-20 / 21-30 / 31-50 / >50 / Indéterminé
    (on demande de compter ce qu'on voit, pas la valeur déclarée du flux).
    Posée seulement si Q0 = VLS à borne.

Q3a L'emplacement est-il géographiquement valide ?  (oui/non/indéterminé)
    = sur terre, bon pays / bonne agglomération.   [non => profil A5]

Q3b L'emplacement est-il au contact de son réseau ?  (oui/non/indéterminé)
    = à moins de 1 km d'une station sœur, ou dans l'enveloppe du réseau.  [non => profil A4]
```

Prédicats dérivés (jamais un jugement « le pipeline a raison/tort ») :
A1 = autopartage ; A3 = vélos sans borne ; A4 = Q3b non ; A5 = Q3a non ;
A6 = VLS à borne ET capacité du flux = 0 ; A2 = nombre de docks compté incohérent
avec la capacité déclarée (à +/-50 %). Endpoints : alpha de Krippendorff par
question + verdict composite, précision/rappel par règle (Wilson 95 %), et le
taux de faux positifs du détecteur A4 « legacy » sur sa strate discordante.

## L'UI actuelle (Streamlit, layout centré, sans barre latérale)

```
+--------------------------------------------------------------+
|  Validation humaine de l'audit GBFS            [pastille Aveugle]|  <- en-tête
|  Annotation en aveugle . une question à la fois . pré-enregistré
|  [ Annotateur v ] [ Tour v ]            [ Exporter CSV ]      |  <- barre de contrôle
|  [#####################-------]  312/530 stations . ~40 min   |  <- progression
+--------------------------------------------------------------+
|  STREET VIEW (interactif, pleine largeur, ~560 px)           |  <- imagerie unique
|  Street View - capture : 2021-08. Si > 24 mois -> Indéterminé. [Plein écran]
+--------------------------------------------------------------+
|  [ Bordeaux ]  Pony            pony_bordeaux/xyz             |  <- identité station
|  [ etape . etape . etape . etape ]                           |  <- indicateur d'étapes
|  QUESTION 1 / 4                                              |
|  Quelle est la nature de la station ?                        |
|  classez d'après l'imagerie et l'opérateur                   |
|  [ VLS à borne (docks physiques visibles) ]                  |  <- 1 bouton par type
|  [ Vélos en libre-service SANS borne ]                       |
|  [ Trottinettes en libre-service ]                           |
|  [ Autopartage de voitures ]                                 |
|  [ Rien / aucun service visible ici ]                        |
|  [ Indéterminé ]                                             |
|  [ < Question précédente ]        [ Passer la station > ]    |
|  > Explication détaillée de cette question (repliable)       |
+--------------------------------------------------------------+
```

Détails techniques et choix de design déjà faits :
- Imagerie = Google Street View SEUL en vue principale (pas de satellite), car
  l'annotateur voulait une vue au sol. Une carte OSM (non-satellite) avec les
  stations sœurs + un cercle de 1 km n'apparaît QUE sur les étapes de placement
  (Q3a/Q3b), car Street View ne montre pas la proximité réseau.
- Street View est un embed sans clé (astuce output=svembed) ; la DATE de prise
  de vue est récupérée via la Street View Metadata API (gratuite, clé requise)
  et stockée en base, pour écarter l'imagerie trop ancienne.
- Une question à la fois (l'imagerie ne se recharge pas entre deux réponses,
  grâce à @st.fragment).
- Boutons OUI/NON volontairement NEUTRES et identiques (pas de vert/rouge) pour
  ne pas biaiser le jugement.
- Indicateur d'étapes, puce d'identité station, barre de progression globale.
- Explication détaillée repliable (optionnelle) sous chaque question.
- Test-retest (un 2e tour 2 semaines après) pour la fiabilité intra-annotateur ;
  stations-pièges possibles ; temps par station enregistré.
- Sortie du pipeline JAMAIS affichée (aveuglement).

## Ce sur quoi je veux ton avis (sois tranchant)

### A. Instrument de mesure
1. Le type à 5 entrées couvre-t-il bien mes 7 règles ? Manque-t-il un cas, ou
   y a-t-il un chevauchement dangereux entre deux entrées (ex : « vélos sans
   borne » vs « rien » le jour où aucun vélo n'est garé) ?
2. Compter les docks (Q2) à partir de Street View SEUL, sans vue satellite du
   dessus, est-ce réaliste au-delà de 10 docks (camionnettes, angles morts,
   distorsion) ? Faut-il réintroduire une vue aérienne au moins pour Q2 ?
3. Les bandes ordinales de Q2 permettent-elles vraiment de dériver A2
   (capacité incohérente à +/-50 %), ou faut-il une estimation numérique brute ?
4. Q3a (périmètre) et Q3b (proximité réseau) sont scindées en deux binaires durs
   (critère 1 km / enveloppe convexe). Est-ce suffisant pour éviter
   l'effondrement d'accord qu'on avait sur la « position cohérente » en v1 ?
5. Routage : une station réelle peut-elle tomber dans un trou (aucune feuille
   valide) ? Les STOP sur trottinettes/autopartage/rien font-ils perdre de
   l'information utile (ex : placement A4/A5 d'un objet hors-domaine) ?
6. Anti-ancrage et aveuglement : montrer la date Street View, l'opérateur et la
   ville introduit-il un biais ? Comment le limiter sans rendre la tâche infaisable ?

### B. UX / UI
7. Charge cognitive et rythme : une question à la fois est-il le bon choix pour
   530 stations x 2 tours, ou faut-il un mode « tout voir » pour les experts ?
   Comment limiter la fatigue et la dérive d'attention ?
8. Disposition : imagerie en haut puis questions en dessous (layout centré).
   Faut-il plutôt imagerie à gauche / questions à droite (côte à côte, image
   toujours visible) ? Avantages/inconvénients pour CETTE tâche.
9. Hauteur Street View (~560 px) + scroll pour atteindre les boutons : problème ?
   Que recommandes-tu (sticky, split, redimensionnable) ?
10. Boutons neutres identiques (anti-biais) vs affordance/lisibilité : bon
    compromis, ou nuire à la vitesse ? Faut-il des raccourcis clavier (1-6, O/N/I) ?
11. Micro-copie : réécris les énoncés et aides que tu juges ambigus (Q0 surtout,
    et la phrase sur la date Street View). Vise une formulation opérationnelle.
12. Feedback et erreurs : retour arrière, « passer », confirmation avant
    enregistrement, indicateurs de progression — qu'ajouter ou retirer ?
13. Accessibilité : contraste, taille de police, navigation clavier, daltonisme —
    points à corriger.
14. Confiance et traçabilité : faut-il un champ « preuve » (source d'imagerie +
    date + observation) obligatoire par réponse pour rendre les labels auditables,
    au prix de la vitesse ?

## Format de réponse attendu

1. Verdict en 3 lignes (ce qui va, ce qui cloche le plus).
2. Liste PRIORISÉE de recommandations (P0 bloquant / P1 / P2), instrument et UX
   mélangés mais étiquetés.
3. Réécriture concrète des libellés Q0/Q2/Q3 et de la micro-copie (en français).
4. Une recommandation tranchée sur LE point le plus structurant (disposition
   image/questions, ou Street View seul vs satellite pour le comptage).
