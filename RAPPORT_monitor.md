# Solana — état du réseau et santé des validateurs

*Instantané du **2026-08-15T21:09:46Z** · lecture RPC directe, sans indexeur tiers.*

## L'essentiel

| | |
|---|---|
| santé du nœud RPC | **ok** |
| époque | **1017** — 38.162 % parcourus |
| slot | **439 508 861** |
| fin d'époque estimée dans | **31.06 h** |
| TPS moyen *(30 échantillons, 1 800 s)* | **3 753.3** |
| TPS hors votes | **2 122.2** |
| durée de slot observée | **0.4186 s** |
| validateurs actifs | **688** |
| validateurs délinquants | **9** (1.29 % du parc) |
| **coefficient de Nakamoto** | **18** |
| stake actif | **435 419 200 SOL** |
| offre totale | **632 261 887 SOL** |
| part du SOL en stake | **68.88 %** |

## Concentration du stake

> **Coefficient de Nakamoto = 18** — c'est le nombre minimal de validateurs qu'il
> faudrait réunir pour dépasser un tiers du stake actif, donc pour bloquer le réseau.
> Plus il est petit, plus le réseau est concentré.

| | |
|---|---|
| part du plus gros validateur | 3.94 % |
| part des 10 premiers | 24.4 % |
| part des 50 premiers | 55.45 % |
| stake délinquant | 72 140 SOL (0.0166 %) |
| commission médiane | 5.0 % |
| validateurs à 100 % de commission | 61 |

## Les 15 plus gros validateurs

| # | identité | stake (SOL) | part | commission |
|---|---|---|---|---|
| 1 | `Fd7btg…69Nk` | 17 161 316 | 3.941 % | 7 % |
| 2 | `HEL1US…e2TU` | 15 969 044 | 3.668 % | 0 % |
| 3 | `JUPiTE…1h4b` | 12 492 108 | 2.869 % | 5 % |
| 4 | `DRpbCB…21hy` | 12 274 846 | 2.819 % | 0 % |
| 5 | `C8Bey3…JP1k` | 9 181 197 | 2.109 % | 7 % |
| 6 | `CAo1dC…Sve4` | 8 981 926 | 2.063 % | 10 % |
| 7 | `E1r4Ps…dxHL` | 8 303 340 | 1.907 % | 0 % |
| 8 | `EvnRmn…qDo4` | 7 969 078 | 1.83 % | 7 % |
| 9 | `9eGrDo…8FoY` | 7 340 396 | 1.686 % | 5 % |
| 10 | `Awes4T…vpLM` | 6 586 185 | 1.513 % | 0 % |
| 11 | `9jxgos…nGFP` | 6 122 617 | 1.406 % | 100 % |
| 12 | `JD549H…HybB` | 5 992 499 | 1.376 % | 0 % |
| 13 | `5pPRHn…HzSm` | 5 990 398 | 1.376 % | 5 % |
| 14 | `5Cchr1…q9Ux` | 5 802 980 | 1.333 % | 100 % |
| 15 | `9rkJMA…NDSQ` | 4 658 022 | 1.07 % | 8 % |

## Contrôles — 9 / 9 passés

| contrôle | | détail |
|---|---|---|
| epoque : progression dans [0,100] | 🟢 | slotIndex=164861 slotsInEpoch=432000 |
| TPS strictement positif | 🟢 | min=3198.0 max=4334.5 sur 30 echantillons |
| duree de slot plausible (0,2 s - 2 s) | 🟢 | 0.4186 s |
| controle du zero : au moins 100 validateurs actifs | 🟢 | 688 actifs, 9 delinquants |
| somme des parts du top = 100 % a l arrondi pres | 🟢 | ecart 0 lamports |
| coefficient de Nakamoto plausible (1-100) | 🟢 | N = 18 |
| offre : circulante <= totale | 🟢 | 510970554 <= 632261887 SOL |
| deux endpoints independants : meme epoque | 🟢 | 1017 vs 1017 |
| deux endpoints independants : ecart de validateurs actifs <= 5 | 🟢 | 688 vs 688 |

**Recoupement sur un second endpoint indépendant :** `https://api.mainnet-beta.solana.com` vs `https://solana-rpc.publicnode.com` — même époque : oui · écart de slot : 18 · validateurs actifs 688 vs 688.

## Ce que cet instantané ne prouve pas

- Les deux endpoints du recoupement sont publics et gratuits : rien ne prouve qu ils ne partagent pas la meme infrastructure en amont. Un accord entre eux ecarte une panne locale ou une reponse tronquee, il NE PROUVE PAS l independance des sources.
- getVoteAccounts ne rend que les validateurs VOTANTS connus du noeud interroge. Le compte absolu n est pas verifiable ici au-dela de l accord des deux endpoints.
- Le temps restant de l epoque est une ESTIMATION : slots restants multiplies par la duree de slot observee sur la fenetre recente. Le reseau ne rend pas cette valeur.
- Le TPS vient de getRecentPerformanceSamples, donc d une fenetre glissante recente, pas d un comptage exhaustif de la chaine.

---

*9 appels RPC, 0 échec(s), latence médiane 148 ms, 8.5 s au total. Endpoints publics sans clé. Aucune valeur interpolée : un appel qui échoue laisse un trou déclaré.*
