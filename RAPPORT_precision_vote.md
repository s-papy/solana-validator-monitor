# Solana — précision et latence de vote par validateur

*Instantané du **2026-08-16T00:12:32Z** · époque **1017**, 191 234 slots écoulés · lecture RPC directe.*

## 🔴 D'abord : la méthode « récompenses de vote au bloc s+8 » ne marche pas encore

**🔴 Alpenglow PAS actif : les blocs ordinaires ne portent que des recompenses de frais. La methode s+8 n a pas de donnees a lire.**

*Sondé à cette exécution : 4 bloc(s) ordinaire(s) examiné(s), types de récompense trouvés : `{'Fee': 4}`.*

Les récompenses `Voting` existent, mais **groupées dans le premier bloc de chaque époque** — c'est l'ancien schéma, pas le mécanisme par slot d'Alpenglow. **Cette sonde est refaite à chaque exécution** : le jour où Alpenglow s'active, ce rapport le dira tout seul.

## Ce qu'on mesure à la place, et qui fonctionne

**Les crédits de vote pondérés par la latence (SIMD-0033).** Un vote qui arrive 1 slot après sa cible vaut 16 crédits ; 2 slots, 15 ; … ; 16 slots ou plus, 1. Donc `crédits ÷ slots écoulés` **est** une mesure de latence.

| | |
|---|---|
| validateurs mesurés | **688** *(sur 688 actifs · 0 sans crédit cette époque)* |
| crédits/slot — médiane | **15.9185** — soit **99.49 %** du plafond |
| crédits/slot — max observé | **15.9429** / 16 |
| crédits/slot — min observé | **2.9433** |
| **latence de vote implicite, médiane réseau** | **1.082 slot(s)** |
| validateurs délinquants | 9 |

## 🔴 Chronique ou accident — la question qui décide de tout

**Classé sur 5 époques ([1013, 1014, 1015, 1016, 1017]), pas sur une seule.** Un validateur est dit *chronique* s'il passe sous le seuil sur la majorité des époques disponibles, *accidentel* s'il n'y passe qu'à l'époque en cours.

| | validateurs | stake (SOL) |
|---|---|---|
| 🔴 **chroniques** — signal réel | **13** | **747 628.0** |
| 🟠 intermittents | 7 | 2 174 040.0 |
| 🟢 accidentels — dégradés seulement maintenant | 2 | 6 602 214.0 |
| sains sur toutes les époques | 666 | |

> ### **Le chiffre à citer est le stake CHRONIQUE : 747 628.0 SOL, soit 0.1717 % du stake mesuré.** Le stake dégradé à l'instant t est plus gros et trompeur — il gonfle avec le premier gros validateur qui a une mauvaise époque.

| validateur chronique | 1013 | 1014 | 1015 | 1016 | 1017 | stake (SOL) | sous seuil |
|---|---|---|---|---|---|---|---|
| `BULKzVM4…af8b` | 98.68 | 95.04 | 87.07 | 92.55 | 94.93 | 327 979.0 | 3/5 |
| `9GHvMeJ4…MZJQ` | 56.4 | 56.34 | 56.15 | 56.82 | 55.26 | 232 026.0 | 5/5 |
| `kom1oNHy…WknE` | 68.56 | 66.93 | 67.05 | 99.45 | 98.93 | 117 681.0 | 3/5 |
| `E4xNK4Uw…EdGZ` | 70.86 | 70.83 | 69.55 | 70.66 | 68.62 | 26 406.0 | 5/5 |
| `NWY18yrP…chkH` | 70.78 | 70.64 | 69.2 | 70.43 | 68.44 | 20 832.0 | 5/5 |
| `AS4i8EXU…Ds5z` | 70.96 | 70.08 | 69.67 | 99.79 | 99.49 | 11 051.0 | 3/5 |
| `9fa5wcqn…GJfZ` | 70.97 | 70.95 | 69.69 | 70.79 | 68.71 | 10 106.0 | 5/5 |
| `DSRVdh9P…RY4E` | 69.71 | 69.56 | 67.65 | 69.57 | 67.56 | 740.0 | 5/5 |
| `tboxdsRM…uVgs` | — | — | 52.39 | 70.14 | 68.19 | 666.0 | 3/3 |
| `toshB4tP…exn2` | 70.71 | 70.7 | 93.45 | 99.72 | 99.49 | 139.0 | 3/5 |
| `tapeQbu7…4PVf` | — | — | — | 11.87 | 68.77 | 1.0 | 2/2 |
| `bcZxRSoz…5K8V` | 70.57 | 70.49 | 69.12 | 70.31 | 68.37 | 0.0 | 5/5 |
| `BpdmpWst…8vFH` | 70.96 | 70.96 | 69.72 | 70.83 | 68.76 | 0.0 | 5/5 |

**Accidentels — normaux sur les époques précédentes, dégradés seulement maintenant. Les citer comme un problème serait une erreur :**

| validateur | 1013 | 1014 | 1015 | 1016 | 1017 | stake (SOL) |
|---|---|---|---|---|---|---|
| `Awes4Tr6…vpLM` | 99.89 | 99.93 | 99.3 | 99.79 | 88.66 | 6 586 185.0 |
| `DiFeTctQ…LJLE` | 99.89 | 99.93 | 98.84 | 99.78 | 18.4 | 16 029.0 |

## Depuis quand ? — au-delà du plafond de 5 époques du RPC

`epochCredits` plafonne à 5 époques. Les crédits **cumulés depuis toujours** (RPC) divisés par l'âge du validateur (`first_epoch_with_stake`, source **stakewiz (api.stakewiz.com/validators), sans cle**) donnent une moyenne de vie. L'écart entre cette moyenne et les 5 dernières époques dit si la dégradation est **ancienne ou récente**.

🔴 **Et le piège que ça cache :** cette moyenne est un **artefact d'âge** si on ne la borne pas. Avant SIMD-0033 un vote valait 1 crédit, pas 16 — mesuré : la corrélation entre l'âge et la moyenne de vie vaut **−0,95**, et des validateurs *sains aujourd'hui* affichent 99 % s'ils sont nés il y a 200-400 époques mais **41 %** s'ils sont nés il y a 700-1100. **La moyenne de vie n'est donc calculée que pour les validateurs nés après l'époque 700 et âgés d'au moins 20 époques** : **281 exploitables, 407 hors domaine.**

*Contrôle : stakewiz et le RPC s'accordent sur les crédits cumulés à 0.000266 % près.*

| validateur | né à l'époque | âge | moyenne de vie | 5 époques | dégradé depuis ~ | stake (SOL) |
|---|---|---|---|---|---|---|
| `BULKzVM4…af8b` | 869 | 148 ép. | 96.95 % | 94.93 % | — | 327 979.0 |
| `9GHvMeJ4…MZJQ` | 776 | 241 ép. | 94.17 % | 56.34 % | **30 époques (~60 jours)** | 232 026.0 |
| `kom1oNHy…WknE` | 828 | 189 ép. | 92.11 % | 68.56 % | **45 époques (~90 jours)** | 117 681.0 |
| `toshB4tP…exn2` | 808 | 209 ép. | 96.88 % | 93.45 % | — | 139.0 |

### Les trop vieux, rattrapés par leur cohorte de naissance

Pour un validateur né avant la bascule, la moyenne de vie ne se compare pas au plafond de 16 — mais elle se compare à **celle des validateurs nés la même époque**, qui ont vécu le même mélange de barèmes. Le biais est partagé, donc l'écart reste interprétable.

*Contrôle : sur les validateurs sains, cet écart vaut **0.0 pt** en médiane sur 37 cohortes — la référence est donc non biaisée.*

| validateur | né à l'époque | sa vie | sa cohorte | **écart** | 5 époques | stake (SOL) |
|---|---|---|---|---|---|---|
| `bcZxRSoz…5K8V` | 577 | 51.18 % | 75.03 % | **-23.86 pt** 🔴 | 70.31 % | 0.0 |
| `9fa5wcqn…GJfZ` | 405 | 38.16 % | 54.19 % | **-16.04 pt** 🔴 | 70.79 % | 10 106.0 |
| `AS4i8EXU…Ds5z` | 581 | 72.22 % | 75.03 % | **-2.82 pt** 🟠 dans la norme | 70.96 % | 11 051.0 |
| `NWY18yrP…chkH` | 11 | 33.56 % | 35.95 % | **-2.39 pt** 🟠 dans la norme | 70.43 % | 20 832.0 |
| `DSRVdh9P…RY4E` | 203 | 41.21 % | 42.33 % | **-1.12 pt** 🟠 dans la norme | 69.56 % | 740.0 |

⚠️ **La colonne « dégradé depuis » suppose un changement en marche d'escalier** — un validateur sain puis brusquement dégradé. Une dérive progressive donnerait un chiffre trop grand. Elle n'est calculée que si l'écart avec un niveau sain dépasse **15 points** ; en dessous elle serait dominée par le bruit et reste vide.

## L'époque en cours seule — à ne PAS citer sans les tableaux ci-dessus

> **La médiane est à 99.49 % du plafond : classer les « meilleurs » validateurs n'apprend rien, ils sont tous collés au maximum. Ce qui se voit, ce sont les traînards.**

| | |
|---|---|
| validateurs sous 95.0 % du plafond | **12** sur 688 |
| dont avec historique *(donc pas nouvellement activés)* | **12** |
| **stake derrière un vote dégradé** | **7 220 970.0 SOL** — 1.6584 % du stake mesuré |

| validateur | crédits/slot | % du plafond | latence implicite | stake (SOL) | époques |
|---|---|---|---|---|---|
| `DiFeTctQ…LJLE` | 2.9433 | 18.4 % | 14.057 | 16 029.0 | 5 |
| `9GHvMeJ4…MZJQ` | 8.8423 | 55.26 % | 8.158 | 232 026.0 | 5 |
| `DSRVdh9P…RY4E` | 10.8095 | 67.56 % | 6.191 | 740.0 | 5 |
| `tboxdsRM…uVgs` | 10.9097 | 68.19 % | 6.09 | 666.0 | 3 |
| `bcZxRSoz…5K8V` | 10.9385 | 68.37 % | 6.062 | 0.0 | 5 |
| `NWY18yrP…chkH` | 10.9505 | 68.44 % | 6.05 | 20 832.0 | 5 |
| `E4xNK4Uw…EdGZ` | 10.9793 | 68.62 % | 6.021 | 26 406.0 | 5 |
| `9fa5wcqn…GJfZ` | 10.9942 | 68.71 % | 6.006 | 10 106.0 | 5 |
| `BpdmpWst…8vFH` | 11.0012 | 68.76 % | 5.999 | 0.0 | 5 |
| `tapeQbu7…4PVf` | 11.0028 | 68.77 % | 5.997 | 1.0 | 2 |
| `Awes4Tr6…vpLM` | 14.1861 | 88.66 % | 2.814 | 6 586 185.0 | 5 |
| `BULKzVM4…af8b` | 15.1884 | 94.93 % | 1.812 | 327 979.0 | 5 |

## Contrôles — 11 / 11 passés

| contrôle | | détail |
|---|---|---|
| credits ponderes par la latence (max/slot proche de 16 sans le depasser) | 🟢 | max observe = 15.9429 |
| controle du zero : au moins 100 validateurs mesures | 🟢 | 688 mesures, 0 sans credit cette epoque |
| aucun credit par slot negatif | 🟢 | min = 2.9433 |
| aucun validateur au-dessus du plafond theorique | 🟢 | max = 15.9429 / 16 |
| epoque : slots ecoules > 0 | 🟢 | slotIndex = 191234 |
| assez d epoques pour trancher chronique / accident (>= 3) | 🟢 | 5 epoque(s) disponible(s) : [1013, 1014, 1015, 1016, 1017] |
| aucune epoque ne depasse le plafond (denominateur correct) | 🟢 | max serie = 99.95 % du plafond |
| stakewiz et le RPC s accordent sur les credits cumules (< 0,01 %) | 🟢 | ecart relatif median 0.000266 % sur 686 validateurs |
| reference de cohorte non biaisee (ecart median des sains proche de 0) | 🟢 | mediane +0.00 pt sur 653 validateurs sains, 37 cohortes |
| deux endpoints : ecart median des credits < 0,5 % | 🟢 | median 0.00053 % sur 688 validateurs communs |
| feature-gate Alpenglow (SIMD-0384) non actif -- le mecanisme mesure est intact | 🟢 | 🟢 feature-gate Alpenglow ABSENT de la chaine : ni actif, ni meme depose. Le mecanisme de credits mesure ici est intact. |

**Recoupement sur un second endpoint :** `https://api.mainnet-beta.solana.com` vs `https://solana-rpc.publicnode.com` — 688 validateurs communs, écart relatif médian des crédits **0.00053 %**, max 0.00284 %.

## Ce que cette mesure ne prouve pas

- La latence implicite conflue DEUX causes : un vote lent et un vote manque font baisser la moyenne de la meme facon. Ce chiffre ne les separe pas et ne pretend pas le faire.
- epochCredits ne conserve qu un nombre limite d epoques (5 observees). Le filtre -validateur neuf- qui en decoule est donc grossier, pas exact.
- Le bloc -degrades- ci-dessous porte sur l epoque EN COURS SEULE : plus elle est jeune, plus le bruit est grand. C est le bloc -chronicite- qui tranche entre un probleme durable et un accident, et c est LUI qu il faut citer.
- Les deux endpoints du recoupement sont publics : leur accord ecarte une panne locale, il ne prouve pas l independance des sources.
- Ceci mesure le schema de credits ACTUEL (SIMD-0033), pas Alpenglow. Le jour ou Alpenglow s active, la sonde incluse le detectera et cette mesure devra etre refaite.

---

*10 appels RPC, 0 échec(s), latence médiane 194 ms, 2.3 s. Endpoints publics sans clé. Aucune valeur interpolée.*
