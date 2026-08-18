# Solana — précision et latence de vote par validateur

*Instantané du **2026-08-17T14:56:38Z** · époque **1018**, 95 071 slots écoulés · lecture RPC directe.*

## 🔴 D'abord : la méthode « récompenses de vote au bloc s+8 » ne marche pas encore

**🔴 Alpenglow PAS actif : les blocs ordinaires ne portent que des recompenses de frais. La methode s+8 n a pas de donnees a lire.**

*Sondé à cette exécution : 4 bloc(s) ordinaire(s) examiné(s), types de récompense trouvés : `{'Fee': 4}`.*

Les récompenses `Voting` existent, mais **groupées dans le premier bloc de chaque époque** — c'est l'ancien schéma, pas le mécanisme par slot d'Alpenglow. **Cette sonde est refaite à chaque exécution** : le jour où Alpenglow s'active, ce rapport le dira tout seul.

## Ce qu'on mesure à la place, et qui fonctionne

**Les crédits de vote pondérés par la latence (SIMD-0033).** Un vote qui arrive 1 slot après sa cible vaut 16 crédits ; 2 slots, 15 ; … ; 16 slots ou plus, 1. Donc `crédits ÷ slots écoulés` **est** une mesure de latence.

| | |
|---|---|
| validateurs mesurés | **689** *(sur 689 actifs · 0 sans crédit cette époque)* |
| crédits/slot — médiane | **15.9956** — soit **99.97 %** du plafond |
| crédits/slot — max observé | **15.9969** / 16 |
| crédits/slot — min observé | **9.287** |
| **latence de vote implicite, médiane réseau** | **1.004 slot(s)** |
| validateurs délinquants | 6 |

## 🔴 Chronique ou accident — la question qui décide de tout

**Classé sur 7 époques ([1012, 1013, 1014, 1015, 1016, 1017, 1018]), pas sur une seule.** Un validateur est dit *chronique* s'il passe sous le seuil sur la majorité des époques disponibles, *accidentel* s'il n'y passe qu'à l'époque en cours.

| | validateurs | stake (SOL) |
|---|---|---|
| 🔴 **chroniques** — signal réel | **10** | **312 064.0** |
| 🟠 intermittents | 9 | 9 029 076.0 |
| 🟢 accidentels — dégradés seulement maintenant | 0 | 0 |
| sains sur toutes les époques | 670 | |

> ### **Le chiffre à citer est le stake CHRONIQUE : 312 064.0 SOL, soit 0.0716 % du stake mesuré.** Le stake dégradé à l'instant t est plus gros et trompeur — il gonfle avec le premier gros validateur qui a une mauvaise époque.

| validateur chronique | 1012 | 1013 | 1014 | 1015 | 1016 | 1017 | 1018 | stake (SOL) | sous seuil |
|---|---|---|---|---|---|---|---|---|---|
| `9GHvMeJ4…MZJQ` | — | — | 56.34 | 56.15 | 56.82 | 56.04 | 58.04 | 232 027.0 | 5/5 |
| `E4xNK4Uw…EdGZ` | — | — | 70.83 | 69.55 | 70.66 | 69.35 | 71.26 | 26 406.0 | 5/5 |
| `NWY18yrP…chkH` | — | — | 70.64 | 69.2 | 70.43 | 69.22 | 71.17 | 20 832.0 | 5/5 |
| `tboxdsRM…uVgs` | — | — | — | 52.39 | 70.14 | 68.96 | 99.98 | 15 204.0 | 3/4 |
| `9fa5wcqn…GJfZ` | — | — | 70.95 | 69.69 | 70.79 | 69.43 | 71.34 | 10 106.0 | 5/5 |
| `suoHAQF4…su5U` | 11.04 | 71.01 | 70.36 | 69.25 | — | — | 99.96 | 6 746.0 | 4/5 |
| `DSRVdh9P…RY4E` | — | — | 69.56 | 67.65 | 69.57 | 68.31 | 70.31 | 740.0 | 5/5 |
| `tapeQbu7…4PVf` | — | — | — | — | 11.87 | 69.48 | 99.98 | 2.0 | 2/3 |
| `BpdmpWst…8vFH` | — | — | 70.96 | 69.72 | 70.83 | 69.47 | 71.38 | 0.0 | 5/5 |
| `bcZxRSoz…5K8V` | — | — | 70.49 | 69.12 | 70.31 | 69.09 | 71.02 | 0.0 | 5/5 |

## Depuis quand ? — au-delà du plafond de 5 époques du RPC

`epochCredits` plafonne à 5 époques. Les crédits **cumulés depuis toujours** (RPC) divisés par l'âge du validateur (`first_epoch_with_stake`, source **stakewiz (api.stakewiz.com/validators), sans cle**) donnent une moyenne de vie. L'écart entre cette moyenne et les 5 dernières époques dit si la dégradation est **ancienne ou récente**.

🔴 **Et le piège que ça cache :** cette moyenne est un **artefact d'âge** si on ne la borne pas. Avant SIMD-0033 un vote valait 1 crédit, pas 16 — mesuré : la corrélation entre l'âge et la moyenne de vie vaut **−0,95**, et des validateurs *sains aujourd'hui* affichent 99 % s'ils sont nés il y a 200-400 époques mais **41 %** s'ils sont nés il y a 700-1100. **La moyenne de vie n'est donc calculée que pour les validateurs nés après l'époque 700 et âgés d'au moins 20 époques** : **281 exploitables, 408 hors domaine.**

*Contrôle : stakewiz et le RPC s'accordent sur les crédits cumulés à 0.000258 % près.*

| validateur | né à l'époque | âge | moyenne de vie | 5 époques | dégradé depuis ~ | stake (SOL) |
|---|---|---|---|---|---|---|
| `9GHvMeJ4…MZJQ` | 776 | 242 ép. | 94.05 % | 56.34 % | **31 époques (~62 jours)** | 232 027.0 |

### Les trop vieux, rattrapés par leur cohorte de naissance

Pour un validateur né avant la bascule, la moyenne de vie ne se compare pas au plafond de 16 — mais elle se compare à **celle des validateurs nés la même époque**, qui ont vécu le même mélange de barèmes. Le biais est partagé, donc l'écart reste interprétable.

*Contrôle : sur les validateurs sains, cet écart vaut **0.0 pt** en médiane sur 37 cohortes — la référence est donc non biaisée.*

| validateur | né à l'époque | sa vie | sa cohorte | **écart** | 5 époques | stake (SOL) |
|---|---|---|---|---|---|---|
| `bcZxRSoz…5K8V` | 577 | 51.21 % | 75.07 % | **-23.86 pt** 🔴 | 70.31 % | 0.0 |
| `9fa5wcqn…GJfZ` | 405 | 38.2 % | 54.25 % | **-16.05 pt** 🔴 | 70.79 % | 10 106.0 |
| `NWY18yrP…chkH` | 11 | 33.59 % | 36.0 % | **-2.41 pt** 🟠 dans la norme | 70.43 % | 20 832.0 |
| `DSRVdh9P…RY4E` | 203 | 41.23 % | 42.39 % | **-1.15 pt** 🟠 dans la norme | 69.56 % | 740.0 |

⚠️ **La colonne « dégradé depuis » suppose un changement en marche d'escalier** — un validateur sain puis brusquement dégradé. Une dérive progressive donnerait un chiffre trop grand. Elle n'est calculée que si l'écart avec un niveau sain dépasse **15 points** ; en dessous elle serait dominée par le bruit et reste vide.

## L'époque en cours seule — à ne PAS citer sans les tableaux ci-dessus

> **La médiane est à 99.97 % du plafond : classer les « meilleurs » validateurs n'apprend rien, ils sont tous collés au maximum. Ce qui se voit, ce sont les traînards.**

| | |
|---|---|
| validateurs sous 95.0 % du plafond | **7** sur 689 |
| dont avec historique *(donc pas nouvellement activés)* | **7** |
| **stake derrière un vote dégradé** | **290 111.0 SOL** — 0.0666 % du stake mesuré |

| validateur | crédits/slot | % du plafond | latence implicite | stake (SOL) | époques |
|---|---|---|---|---|---|
| `9GHvMeJ4…MZJQ` | 9.287 | 58.04 % | 7.713 | 232 027.0 | 5 |
| `DSRVdh9P…RY4E` | 11.2489 | 70.31 % | 5.751 | 740.0 | 5 |
| `bcZxRSoz…5K8V` | 11.3633 | 71.02 % | 5.637 | 0.0 | 5 |
| `NWY18yrP…chkH` | 11.388 | 71.17 % | 5.612 | 20 832.0 | 5 |
| `E4xNK4Uw…EdGZ` | 11.401 | 71.26 % | 5.599 | 26 406.0 | 5 |
| `9fa5wcqn…GJfZ` | 11.4144 | 71.34 % | 5.586 | 10 106.0 | 5 |
| `BpdmpWst…8vFH` | 11.4208 | 71.38 % | 5.579 | 0.0 | 5 |

## Contrôles — 11 / 11 passés

| contrôle | | détail |
|---|---|---|
| credits ponderes par la latence (max/slot proche de 16 sans le depasser) | 🟢 | max observe = 15.9969 |
| controle du zero : au moins 100 validateurs mesures | 🟢 | 689 mesures, 0 sans credit cette epoque |
| aucun credit par slot negatif | 🟢 | min = 9.287 |
| aucun validateur au-dessus du plafond theorique | 🟢 | max = 15.9969 / 16 |
| epoque : slots ecoules > 0 | 🟢 | slotIndex = 95071 |
| assez d epoques pour trancher chronique / accident (>= 3) | 🟢 | 7 epoque(s) disponible(s) : [1012, 1013, 1014, 1015, 1016, 1017, 1018] |
| aucune epoque ne depasse le plafond (denominateur correct) | 🟢 | max serie = 99.98 % du plafond |
| stakewiz et le RPC s accordent sur les credits cumules (< 0,01 %) | 🟢 | ecart relatif median 0.000258 % sur 687 validateurs |
| reference de cohorte non biaisee (ecart median des sains proche de 0) | 🟢 | mediane +0.00 pt sur 658 validateurs sains, 37 cohortes |
| deux endpoints : ecart median des credits < 0,5 % | 🟢 | median 0.00105 % sur 689 validateurs communs |
| feature-gate Alpenglow (SIMD-0384) non actif -- le mecanisme mesure est intact | 🟢 | 🟢 feature-gate Alpenglow ABSENT de la chaine : ni actif, ni meme depose. Le mecanisme de credits mesure ici est intact. |

**Recoupement sur un second endpoint :** `https://api.mainnet-beta.solana.com` vs `https://solana-rpc.publicnode.com` — 689 validateurs communs, écart relatif médian des crédits **0.00105 %**, max 0.00211 %.

## Ce que cette mesure ne prouve pas

- La latence implicite conflue DEUX causes : un vote lent et un vote manque font baisser la moyenne de la meme facon. Ce chiffre ne les separe pas et ne pretend pas le faire.
- epochCredits ne conserve qu un nombre limite d epoques (5 observees). Le filtre -validateur neuf- qui en decoule est donc grossier, pas exact.
- Le bloc -degrades- ci-dessous porte sur l epoque EN COURS SEULE : plus elle est jeune, plus le bruit est grand. C est le bloc -chronicite- qui tranche entre un probleme durable et un accident, et c est LUI qu il faut citer.
- Les deux endpoints du recoupement sont publics : leur accord ecarte une panne locale, il ne prouve pas l independance des sources.
- Ceci mesure le schema de credits ACTUEL (SIMD-0033), pas Alpenglow. Le jour ou Alpenglow s active, la sonde incluse le detectera et cette mesure devra etre refaite.

---

*10 appels RPC, 0 échec(s), latence médiane 225 ms, 2.9 s. Endpoints publics sans clé. Aucune valeur interpolée.*
