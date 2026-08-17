# Solana Ecosystem & Validator Health Monitor

**Un etat de sante du reseau Solana et de ses validateurs, lu en direct par appels RPC, sans indexeur tiers, sans cle API, sans dependance payante.**

```bash
python3 solana_monitor.py
```

Une execution produit quatre fichiers dans `sortie/` :

| fichier | quoi |
|---|---|
| `index.html` | tableau de bord autonome, theme sombre, **aucune ressource externe** -- s'ouvre hors ligne |
| `RAPPORT.md` | le meme contenu en Markdown lisible |
| `etat.json` | l'instantane structure, machine-readable |
| `historique.jsonl` | une ligne par execution **complete**, en ajout seul |

Dependances : Python 3 + `requests`. Rien d'autre.

---

## Ce qu'il lit

| appel RPC | ce qu'on en tire |
|---|---|
| `getHealth` | sante du noeud interroge |
| `getEpochInfo` | epoque, slot absolu, hauteur de bloc, progression, temps restant estime |
| `getSlot` | hauteur courante |
| `getBlockTime` | horodatage du dernier bloc et **retard d'horloge** |
| `getRecentPerformanceSamples` | TPS moyen / median / max, **TPS hors votes**, duree de slot observee |
| `getVoteAccounts` | validateurs actifs et delinquants, distribution du stake, **coefficient de Nakamoto**, concentration top 1/10/50, commissions |
| `getSupply` | offre totale, circulante, et **part du SOL en stake** |

### Le coefficient de Nakamoto

Le nombre **minimal** de validateurs qu'il faudrait reunir pour depasser un tiers du stake actif -- donc pour bloquer le reseau. Plus il est petit, plus le reseau est concentre. C'est la mesure de decentralisation la plus difficile a maquiller, et elle se calcule entierement a partir de `getVoteAccounts`.

---

## Ce que ce script ne fait jamais

Ces quatre regles sont dans le code, pas dans l'intention.

| | |
|---|---|
| **jamais d'interpolation** | un appel qui echoue apres 3 essais sur chaque endpoint rend `None`. Le champ est marque **manquant avec son motif**. Aucune valeur n'est inventee, ni reportee de l'execution precedente |
| **jamais silencieux** | chaque echec est trace -- methode, endpoint, numero d'essai, motif -- et compte dans les trois sorties |
| **jamais un chiffre non controle** | 9 controles automatiques *(controle du zero, vraisemblance, coherence interne, accord inter-endpoints)*. Leur resultat est publie, reussi ou non |
| **jamais une source unique** | les grandeurs critiques sont relues sur un **second endpoint independant** et l'ecart est publie |

**Et l'historique ne recoit que les instantanes complets** -- une execution partielle produit bien un rapport, marque comme tel, mais n'entre pas dans la serie. Un trou documente vaut mieux qu'un chiffre fabrique.

## Ce qu'il ne prouve pas

Les limites sont **ecrites dans les sorties elles-memes**, pas seulement ici :

- Les deux endpoints du recoupement sont publics et gratuits -- **rien ne prouve qu'ils ne partagent pas la meme infrastructure en amont**. Leur accord ecarte une panne locale ou une reponse tronquee ; il ne prouve pas l'independance des sources.
- `getVoteAccounts` ne rend que les validateurs votants connus du noeud interroge. Le compte absolu n'est pas verifiable au-dela de l'accord des deux endpoints.
- Le temps restant de l'epoque est une **estimation** (slots restants x duree de slot observee), pas une valeur rendue par le reseau.
- Le TPS vient d'une fenetre glissante recente, pas d'un comptage exhaustif de la chaine.

---

## Fiabilite mesuree

*Renseigne par executions reelles, jamais estime.*

| | |
|---|---|
| executions reelles | **5** *(15/08/2026, 21h04 -> 21h09 UTC)* |
| appels RPC par execution | **9** |
| appels cumules | **45** |
| echecs | **0** |
| controles passes | **9 / 9** a chaque execution |
| duree par execution | **7.9 a 8.8 s** |
| latence mediane | **112 a 148 ms** |

**Les 5 executions tiennent dans cinq minutes, pas dans cinq heures.** *Elles etablissent que le script est **reproductible** -- memes controles, meme parc de validateurs, TPS coherent d'une lecture a l'autre -- **pas qu'il tient sur la duree**. La tenue longue n'est pas demontree et ne doit pas etre presentee comme telle.*

---

## Ce qui manque pour que ce soit livrable

*Etat honnete, sans enjoliver.*

| | |
|---|---|
| demo hebergee en direct | le HTML est autonome et pret -- voir demo/ dans ce repo |
| depot public | fait -- ce repo |
| rafraichissement automatique | le script se relance, mais aucune tache planifiee ne le fait tourner |
| tenue longue prouvee | 5 executions en cinq minutes ne valent pas cinq jours |
| le reste | le code tourne, les donnees sont reelles, les controles passent, les trois sorties existent |

---

*Lecture seule - aucun wallet - aucune cle API - aucune dependance payante - zero franc engage.*

---

# precision_vote.py -- precision et latence de vote par validateur

```bash
python3 precision_vote.py
```

Sorties dans `sortie_vote/` : `index.html`, `RAPPORT.md`, `etat.json`, `historique.jsonl`, et **`serie_validateurs.jsonl`**.

## Les trois profondeurs, et ce que chacune vaut

| profondeur | source | portee | ce qu'elle dit |
|---|---|---|---|
| **epoque en cours** | RPC `getVoteAccounts` | 1 epoque | **trompeuse seule** -- un gros validateur ayant une mauvaise journee gonfle le total |
| **5 dernieres epoques** | RPC `epochCredits` | ~10 jours | chronique / intermittent / accidentel |
| **moyenne de vie** | credits cumules RPC + `first_epoch_with_stake` (stakewiz) | toute la vie | **depuis quand** la degradation dure |

## Deux pieges mesures, pas supposes

**Le chiffre de l'epoque en cours est trompeur.** Mesure le 15/08 : 7 220 970 SOL annonces derriere un vote degrade, **747 628 SOL reellement chroniques** -- un facteur 9,7, dont 91% venaient d'un seul validateur qui avait simplement une mauvaise epoque. Le script met desormais le chiffre chronique en avant.

**La moyenne de vie est un artefact d'age si on ne la borne pas.** Avant SIMD-0033 un vote valait 1 credit, pas 16. Mesure : correlation age / moyenne de vie = -0,95. Le script ne calcule donc la moyenne de vie que pour les validateurs nes apres l'epoque 700 et ages d'au moins 20 epoques.

## Ce qui a ete cherche et rejete

| piste | verdict |
|---|---|
| **Alpenglow, methode recompenses au bloc s+8** | pas de donnees -- mecanisme pas actif sur mainnet, testnet ni devnet. Sonde rejouee a chaque execution |
| **Dune solana.rewards** | ne donne pas la performance : recompense = commission x stake x credits, et la commission domine. Correlation mesuree : -0,02 |
| **stakewiz, historique par epoque** | aucun point d'entree -- instantane seulement |
| **stakewiz first_epoch_with_stake** | retenu, avec le garde d'age ci-dessus. Controle : accord avec le RPC a 0,0004% pres |

## serie_validateurs.jsonl -- l'accumulation

Une ligne par (epoque, validateur), en ajout seul, dedupliquee. L'epoque en cours n'y entre jamais.

**Cette serie commence le 16/08/2026 et ne remonte pas dans le passe.** Tant qu'elle n'a pas plus de 5 epoques distinctes, elle n'apporte rien de plus que ce que le RPC donne deja.

---

## CLAUSE DE VIGILANCE -- a lire avant de faire confiance a une sortie

**Le risque le plus serieux pour cet outil n'est pas qu'il tombe en panne : c'est qu'il continue de produire des chiffres d'apparence normale qui ne veulent plus rien dire.**

`precision_vote.py` mesure les credits de vote, qui supposent que les votes passent par des transactions. Alpenglow/Votor supprime cette hypothese -- Alpenglow will no longer use vote transactions (Solana Foundation, solana.com/upgrades/alpenglow, 24/06/2026).

### Ce qu'il faut verifier, et c'est verifiable en une requete

Le feature-gate de la migration (SIMD-0384) est :

```
a1penGLz8Vm2QHYB3JPefBiU4BY3Z6JkW2k3Scw5GWP
```

Le script le lit desormais a chaque execution (`getAccountInfo`) et en fait un controle bloquant du rapport.

| etat sur la chaine | signification |
|---|---|
| **compte absent** | ni actif ni depose -- le mecanisme mesure est intact |
| compte present, 1er octet 0 | depose mais pas actif -- activation imminente, surveiller |
| compte present, 1er octet 1 | actif -- toute sortie doit etre reverifiee avant usage |

### Etat constate le 16/08/2026

**Compte absent des trois clusters -- mainnet, testnet ET devnet.** SIMD-0384 est encore status: Review dans solana-improvement-documents (cree le 21/10/2025). Agave 4.3 n'est qu'a 4.3.0-beta.0 (14/08/2026).

**Fenetre de risque estimee :** au rythme du cycle 4.2 (~1 mois de beta.0 a stable), 4.3.0 stable arriverait mi-septembre. Le Q3 2026 annonce par la Fondation parait donc optimiste : Q4 2026 est plus vraisemblable. Ce n'est pas une date, c'est une extrapolation d'un seul cycle de version.

---
