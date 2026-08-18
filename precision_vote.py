#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PRECISION ET LATENCE DE VOTE PAR VALIDATEUR SOLANA -- lecture RPC directe.

Ne le 15/08/2026, en reponse a un besoin exprime publiquement par un operateur
de validateur (Zantetsu / Shinobi Systems, Discord Solana Tech, 09/08/2026) :
mesurer la precision et la rapidite de vote par validateur a partir du RPC seul.

🔴 CE QUE LA VERIFICATION A MONTRE AVANT D ECRIRE UNE LIGNE DE CE SCRIPT
La methode proposee -- lire les recompenses de vote au bloc s+8 -- NE MARCHE PAS
AUJOURD HUI, et pas par notre faute : elle decrit le mecanisme d ALPENGLOW, qui
n est actif nulle part. Mesure le 15/08/2026 sur les TROIS clusters :
    mainnet / testnet / devnet : blocs ordinaires -> UNIQUEMENT des recompenses
    de type 'Fee'. Aucune recompense de vote par slot, sur aucun cluster.
    Les recompenses 'Voting' existent bien, mais GROUPEES dans le PREMIER BLOC
    DE CHAQUE EPOQUE (682 lignes sur mainnet a l epoque 1017) -- c est l ancien
    schema, pas le s+8 d Alpenglow.

CE QUE CE SCRIPT MESURE A LA PLACE, et pourquoi c est le plus proche equivalent
qui existe reellement : les CREDITS DE VOTE PONDERES PAR LA LATENCE (SIMD-0033).
Un vote qui arrive 1 slot apres sa cible vaut 16 credits, 2 slots -> 15, ... et
16 slots ou plus -> 1. Donc :

    credits gagnes / slots ecoules  =  mesure directe de la latence de vote
    latence moyenne implicite       =  17 - (credits par slot)

🔴 CETTE INVERSION CONFLUE DEUX CHOSES et ne pretend pas les separer : un vote
LENT et un vote MANQUE font tous les deux baisser la moyenne. C est precisement
ce que l operateur appelait un « vote-accuracy/participation accuracy proxy ».

L HYPOTHESE EST TESTEE A CHAQUE EXECUTION, pas supposee : si les credits sont
bien ponderes par la latence, le maximum observe doit s approcher de 16 sans le
depasser. S il plafonne a ~1, le schema pondere n est pas actif et le script
REFUSE de convertir les credits en latence.

    python3 precision_vote.py

Sorties : sortie_vote/etat.json, RAPPORT.md, index.html, historique.jsonl
Aucune cle API, aucune dependance payante, aucun wallet, lecture seule.
"""
import argparse, json, os, statistics, sys, time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("🔴 module 'requests' absent : python3 -m pip install --user requests")

ENDPOINTS = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com"]
PLAFOND_CREDITS = 16          # SIMD-0033 : 16 credits pour un vote a 1 slot de latence
SEUIL_DEGRADE = 0.95          # sous 95 % du plafond, on considere le vote degrade
LAMPORTS = 1e9
RACINE = os.path.dirname(os.path.abspath(__file__))


class Client:
    def __init__(self, endpoints, essais=3, timeout=40):
        self.endpoints, self.essais, self.timeout = list(endpoints), essais, timeout
        self.appels, self.echecs, self.latences = 0, [], []

    def appel(self, methode, params=None, endpoint=None):
        for ep in ([endpoint] if endpoint else self.endpoints):
            for k in range(self.essais):
                self.appels += 1
                t0 = time.time()
                try:
                    j = requests.post(ep, json={"jsonrpc": "2.0", "id": self.appels,
                                                "method": methode, "params": params or []},
                                      timeout=self.timeout).json()
                    self.latences.append(time.time() - t0)
                    if "result" in j:
                        return j["result"], ep
                    self.echecs.append({"methode": methode, "endpoint": ep, "essai": k + 1,
                                        "motif": str(j.get("error"))[:160]})
                except Exception as e:
                    self.latences.append(time.time() - t0)
                    self.echecs.append({"methode": methode, "endpoint": ep, "essai": k + 1,
                                        "motif": type(e).__name__ + ": " + str(e)[:120]})
                time.sleep(0.5 * (k + 1))
        return None, None


def controle(nom, ok, detail):
    return {"controle": nom, "passe": bool(ok), "detail": detail}


GATE_ALPENGLOW = "a1penGLz8Vm2QHYB3JPefBiU4BY3Z6JkW2k3Scw5GWP"
PROG_FEATURE = "Feature111111111111111111111111111111111111"


def sonder_feature_gate(c):
    """🔴 LE RISQUE LE PLUS SERIEUX POUR CET OUTIL, et il est verifiable en direct.

    SIMD-0384 (migration Alpenglow) porte le feature-gate ci-dessus. Quand il
    s activera, Alpenglow cessera d utiliser des TRANSACTIONS de vote -- les votes
    passeront directement entre validateurs. Le mecanisme de credits que tout cet
    outil mesure changera donc DE NATURE, pas seulement d echelle, et une sortie
    d apparence normale pourrait ne plus rien vouloir dire.

    Ce controle lit l etat REEL sur la chaine a chaque execution. Sur Solana, un
    feature-gate non encore depose n a PAS de compte ; depose mais pas actif, le
    premier octet de ses donnees vaut 0 ; actif, il vaut 1 suivi du slot.
    Verifie le 16/08/2026 sur deux gates connus actifs avant de s en servir."""
    r, _ = c.appel("getAccountInfo", [GATE_ALPENGLOW, {"encoding": "base64"}])
    val = (r or {}).get("value") if isinstance(r, dict) else None
    if val is None:
        return {"gate": GATE_ALPENGLOW, "compte_present": False, "actif": False,
                "verdict": "🟢 feature-gate Alpenglow ABSENT de la chaine : ni actif, "
                           "ni meme depose. Le mecanisme de credits mesure ici est intact."}
    import base64 as _b64
    d = _b64.b64decode(val["data"][0])
    tag = d[0] if d else None
    slot = int.from_bytes(d[1:9], "little") if tag == 1 and len(d) >= 9 else None
    return {"gate": GATE_ALPENGLOW, "compte_present": True,
            "proprietaire_est_programme_feature": val.get("owner") == PROG_FEATURE,
            "actif": tag == 1, "slot_activation": slot,
            "verdict": ("🔴 ALPENGLOW ACTIF depuis le slot %s -- les votes ne passent plus par "
                        "des transactions. TOUTE SORTIE DE CET OUTIL DOIT ETRE REVERIFIEE "
                        "AVANT USAGE : le mecanisme mesure a change de nature." % slot)
                       if tag == 1 else
                       "🟠 feature-gate DEPOSE mais pas encore actif -- l activation est "
                       "desormais imminente, surveiller a chaque execution."}


def sonder_alpenglow(c):
    """Verifie SI la methode s+8 d Alpenglow est devenue disponible. Ce controle
    est refait A CHAQUE EXECUTION : le jour ou Alpenglow s active, il basculera
    tout seul et le rapport le dira, au lieu de repeter une conclusion perimee."""
    ei, _ = c.appel("getEpochInfo")
    if not ei:
        return {"teste": False, "motif": "getEpochInfo indisponible"}
    types, lus = {}, 0
    s = ei["absoluteSlot"] - 300
    while lus < 4 and s > ei["absoluteSlot"] - 400:
        b, _ = c.appel("getBlock", [s, {"encoding": "json", "transactionDetails": "none",
                                        "rewards": True, "maxSupportedTransactionVersion": 0}])
        if b:
            lus += 1
            for r in (b.get("rewards") or []):
                types[r.get("rewardType")] = types.get(r.get("rewardType"), 0) + 1
        s -= 17
    return {
        "teste": True, "blocs_examines": lus, "types_de_recompense": types,
        "recompense_de_vote_par_slot": "Voting" in types,
        "verdict": ("🟢 Alpenglow semble ACTIF : des recompenses de vote apparaissent dans les "
                    "blocs ordinaires -- la methode s+8 devient testable"
                    if "Voting" in types else
                    "🔴 Alpenglow PAS actif : les blocs ordinaires ne portent que des "
                    "recompenses de frais. La methode s+8 n a pas de donnees a lire."),
    }


def instantane():
    c = Client(ENDPOINTS)
    t0 = time.time()
    controles, manquants = [], []

    ei, _ = c.appel("getEpochInfo")
    va, ep_va = c.appel("getVoteAccounts")
    for nom, v, m in (("epoque", ei, "getEpochInfo"), ("validateurs", va, "getVoteAccounts")):
        if v is None:
            manquants.append({"champ": nom, "methode": m,
                              "motif": "echec RPC definitif apres %d essais sur %d endpoint(s)"
                                       % (c.essais, len(ENDPOINTS))})
    if ei is None or va is None:
        return {"horodatage_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "complet": False, "champs_manquants": manquants,
                "appels_rpc": c.appels, "echecs_rpc": len(c.echecs),
                "detail_echecs": c.echecs[:20], "duree_s": round(time.time() - t0, 1)}

    epoque, idx = ei["epoch"], ei["slotIndex"]
    actifs, delinquants = va.get("current", []), va.get("delinquent", [])

    # --------------------------------------------------- mesure par validateur
    v_mes, sans_credit = [], 0
    for v in actifs:
        ec = v.get("epochCredits") or []
        if not ec or ec[-1][0] != epoque:
            sans_credit += 1
            continue
        gagnes = ec[-1][1] - ec[-1][2]
        par_slot = gagnes / idx if idx else None
        # 🔴 SERIE MULTI-EPOQUES : le denominateur d une epoque TERMINEE est le
        # nombre de slots de l epoque, celui de l epoque EN COURS est slotIndex.
        # Valide le 15/08 : sur les 5 epoques disponibles, le max reste sous 16.
        serie = {}
        for ep_i, cr_i, pr_i in ec:
            den = idx if ep_i == epoque else ei["slotsInEpoch"]
            if den:
                serie[ep_i] = round(100.0 * ((cr_i - pr_i) / den) / PLAFOND_CREDITS, 2)
        v_mes.append({
            "serie_pct_du_plafond": serie,
            "identite": v.get("nodePubkey"), "compte_vote": v.get("votePubkey"),
            "credits_epoque": gagnes,
            "credits_par_slot": round(par_slot, 4) if par_slot is not None else None,
            "pct_du_plafond": round(100.0 * par_slot / PLAFOND_CREDITS, 2) if par_slot else None,
            "stake_sol": round(v.get("activatedStake", 0) / LAMPORTS, 2),
            "commission_pct": v.get("commission"),
            "epoques_dans_historique": len(ec),
        })

    ps = [x["credits_par_slot"] for x in v_mes if x["credits_par_slot"] is not None]
    max_obs = max(ps) if ps else None

    # 🔴 LE CONTROLE QUI DECIDE SI ON A LE DROIT DE PARLER DE LATENCE
    pondere = max_obs is not None and 8.0 <= max_obs <= PLAFOND_CREDITS + 0.01
    controles.append(controle(
        "credits ponderes par la latence (max/slot proche de %d sans le depasser)" % PLAFOND_CREDITS,
        pondere,
        "max observe = %s" % (round(max_obs, 4) if max_obs is not None else "—")))

    for x in v_mes:
        x["latence_implicite_slots"] = (round(PLAFOND_CREDITS + 1 - x["credits_par_slot"], 3)
                                        if pondere and x["credits_par_slot"] is not None else None)

    stake_total = sum(x["stake_sol"] for x in v_mes)
    degrades = sorted(
        [x for x in v_mes
         if x["pct_du_plafond"] is not None and x["pct_du_plafond"] < 100 * SEUIL_DEGRADE],
        key=lambda x: (x["pct_du_plafond"], -x["stake_sol"]))
    degrades_etablis = [x for x in degrades if x["epoques_dans_historique"] >= 2]
    stake_degrade = sum(x["stake_sol"] for x in degrades)

    controles.append(controle("controle du zero : au moins 100 validateurs mesures",
                              len(v_mes) >= 100, "%d mesures, %d sans credit cette epoque"
                              % (len(v_mes), sans_credit)))
    controles.append(controle("aucun credit par slot negatif",
                              all(x["credits_par_slot"] >= 0 for x in v_mes if x["credits_par_slot"] is not None),
                              "min = %s" % (round(min(ps), 4) if ps else "—")))
    controles.append(controle("aucun validateur au-dessus du plafond theorique",
                              max_obs is None or max_obs <= PLAFOND_CREDITS + 0.01,
                              "max = %s / %d" % (round(max_obs, 4) if max_obs else "—", PLAFOND_CREDITS)))
    controles.append(controle("epoque : slots ecoules > 0",
                              idx > 0, "slotIndex = %d" % idx))

    # ------------------------------------------------ CHRONIQUE OU ACCIDENT ?
    # 🔴 Ce bloc existe parce qu un verdict a ete presente le 15/08 sur UNE SEULE
    # epoque. Verifie ensuite : sur 12 validateurs annonces degrades, 10 seulement
    # etaient chroniques, 3 chroniques avaient ete MANQUES, et le cas vedette
    # (6,59 M SOL) etait un accident. Le stake annonce etait 9,7 fois trop grand.
    # La classification est desormais faite par l outil, pas par le lecteur.
    epoques_dispo = sorted({e for x in v_mes for e in x["serie_pct_du_plafond"]})
    assez = len(epoques_dispo) >= 3
    chroniques, intermittents, accidentels, sains = [], [], [], 0
    if assez:
        for x in v_mes:
            s = x["serie_pct_du_plafond"]
            sous = [e for e, p in s.items() if p < 100 * SEUIL_DEGRADE]
            x["epoques_mesurees"] = len(s)
            x["epoques_sous_seuil"] = len(sous)
            if not sous:
                x["chronicite"] = "sain"; sains += 1
            elif len(sous) > len(s) / 2.0:
                x["chronicite"] = "chronique"; chroniques.append(x)
            elif sous == [epoque]:
                x["chronicite"] = "accidentel"; accidentels.append(x)
            else:
                x["chronicite"] = "intermittent"; intermittents.append(x)
    controles.append(controle(
        "assez d epoques pour trancher chronique / accident (>= 3)",
        assez, "%d epoque(s) disponible(s) : %s" % (len(epoques_dispo), epoques_dispo)))
    if assez:
        controles.append(controle(
            "aucune epoque ne depasse le plafond (denominateur correct)",
            all(p <= 100.01 for x in v_mes for p in x["serie_pct_du_plafond"].values()),
            "max serie = %.2f %% du plafond"
            % max((p for x in v_mes for p in x["serie_pct_du_plafond"].values()), default=0)))
    somme = lambda lot: round(sum(y["stake_sol"] for y in lot), 2)
    chronicite = {
        "tranchable": assez,
        "motif_si_non": None if assez else
            "moins de 3 epoques dans epochCredits -- la robustesse temporelle "
            "n est PAS prouvee et aucun verdict chronique/accident n est rendu",
        "epoques_disponibles": epoques_dispo,
        "chroniques": len(chroniques), "intermittents": len(intermittents),
        "accidentels": len(accidentels), "sains": sains,
        "stake_chronique_sol": somme(chroniques),
        "stake_intermittent_sol": somme(intermittents),
        "stake_accidentel_sol": somme(accidentels),
        "part_stake_chronique_pct": (round(100 * somme(chroniques) / stake_total, 4)
                                     if stake_total else None),
        "liste_chroniques": sorted(chroniques, key=lambda x: -x["stake_sol"])[:25],
        "liste_accidentels": sorted(accidentels, key=lambda x: -x["stake_sol"])[:10],
    }

    # ============ PROFONDEUR AU-DELA DES 5 EPOQUES DU RPC ====================
    # 🔴 epochCredits plafonne a 5 epoques : un validateur degrade depuis 6 mois et
    # un autre depuis une semaine y sont indiscernables. Cherche le 16/08 :
    #   - Dune (solana.rewards) a bien l historique des recompenses Voting sur des
    #     ANNEES, mais TESTE puis REJETE : la recompense vaut commission x stake x
    #     credits, la commission domine, et recompense/stake ne reproduit PAS la
    #     performance (correlation -0,02, ecart median 95 pct). Voir le registre D31.
    #   - stakewiz expose first_epoch_with_stake sans cle. Combine aux credits
    #     CUMULES du RPC, il donne une moyenne de TOUTE LA VIE du validateur.
    #
    # 🔴 ET LE PIEGE QUI A FAILLI PASSER : cette moyenne de vie est un ARTEFACT
    # D AGE si on ne la borne pas. Correlation age <-> moyenne de vie = -0,954.
    # Des validateurs SAINS aujourd hui affichent 99 pct s ils sont nes il y a
    # 200-400 epoques, mais 41 pct s ils sont nes il y a 700-1100 : avant SIMD-0033
    # un vote valait 1 credit, pas 16. La moyenne de vie n est donc comparable au
    # plafond de 16 QUE pour les validateurs nes apres la bascule.
    EPOQUE_BASCULE_BAREME = 700   # prudent : a 700+ les sains retrouvent 99 pct
    AGE_MINIMAL = 20              # en dessous, une -moyenne de vie- ne veut rien dire
    profondeur = {"source": "stakewiz (api.stakewiz.com/validators), sans cle",
                  "epoque_bascule_retenue": EPOQUE_BASCULE_BAREME,
                  "age_minimal_epoques": AGE_MINIMAL,
                  "disponible": False}
    try:
        import urllib.request
        req = urllib.request.Request("https://api.stakewiz.com/validators",
                                     headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        sw = {x["vote_identity"]: x for x in json.loads(
            urllib.request.urlopen(req, timeout=30).read().decode())}
    except Exception as ex:
        sw = {}
        profondeur["motif_indisponible"] = "%s : %s" % (type(ex).__name__, str(ex)[:120])
    if sw:
        cum = {v["votePubkey"]: (v.get("epochCredits") or [[0, 0, 0]])[-1][1] for v in actifs}
        ecarts = [abs(sw[k]["credits"] - cum[k]) / max(1, cum[k])
                  for k in cum if k in sw and sw[k].get("credits")]
        accord = statistics.median(ecarts) if ecarts else None
        controles.append(controle(
            "stakewiz et le RPC s accordent sur les credits cumules (< 0,01 %)",
            accord is not None and accord < 0.0001,
            "ecart relatif median %.6f %% sur %d validateurs"
            % (100 * accord, len(ecarts)) if accord is not None else "aucun appariement"))
        if accord is not None and accord < 0.0001:
            profondeur["disponible"] = True
            profondeur["accord_credits_cumules_pct"] = round(100 * accord, 6)
            hors, dedans = 0, []
            for x in v_mes:
                v = next((k for k in actifs if k.get("nodePubkey") == x["identite"]), None)
                s = sw.get(v["votePubkey"]) if v else None
                e0 = (s or {}).get("first_epoch_with_stake")
                x["ne_a_l_epoque"] = e0
                if not e0 or e0 < EPOQUE_BASCULE_BAREME or (epoque - e0) < AGE_MINIMAL:
                    x["moyenne_vie_pct"] = None
                    x["profondeur_exploitable"] = False
                    hors += 1
                    continue
                n_ep = epoque - e0
                tot = cum.get(v["votePubkey"], 0)
                vie = 100.0 * (tot / (n_ep * ei["slotsInEpoch"] + idx)) / PLAFOND_CREDITS
                x["moyenne_vie_pct"] = round(vie, 2)
                x["profondeur_exploitable"] = True
                x["age_epoques"] = n_ep
                # duree de degradation, SOUS HYPOTHESE D UN CHANGEMENT EN MARCHE
                # D ESCALIER : combien d epoques au niveau recent expliqueraient
                # l ecart entre la moyenne de vie et un niveau sain de reference ?
                med_rec = statistics.median(x["serie_pct_du_plafond"].values()) \
                    if x["serie_pct_du_plafond"] else None
                SAIN = 99.5
                # 🔴 seuil a 15 points : en dessous, l estimation de duree est
                # dominee par le bruit (un ecart de 5 points donnait -150 jours-
                # sur un validateur a 94,45 pct, ce qui n est pas defendable).
                if med_rec is not None and SAIN - med_rec > 15 and vie < SAIN:
                    x["degrade_depuis_epoques_estime"] = round(n_ep * (SAIN - vie) / (SAIN - med_rec))
                    x["degrade_depuis_jours_estime"] = round(
                        x["degrade_depuis_epoques_estime"] * 2.0)
                else:
                    x["degrade_depuis_epoques_estime"] = None
                dedans.append(x)
            # ---- REFERENCE DE COHORTE : sauve les validateurs nes AVANT la bascule
            # Deux validateurs nes la meme epoque ont vecu le MEME melange de baremes,
            # donc le biais est PARTAGE et l ecart a la cohorte reste interpretable.
            # Controle integre : sur les validateurs sains, cet ecart doit valoir ~0.
            coh = {}
            for x in v_mes:
                e0 = x.get("ne_a_l_epoque")
                if not e0 or (epoque - e0) < AGE_MINIMAL:
                    continue
                n_ep = epoque - e0
                tot = cum.get(next((k["votePubkey"] for k in actifs
                                    if k.get("nodePubkey") == x["identite"]), None), 0)
                x["_vie_brute"] = 100.0 * (tot / (n_ep * ei["slotsInEpoch"] + idx)) / PLAFOND_CREDITS
                x["_cohorte"] = (e0 // 25) * 25
                coh.setdefault(x["_cohorte"], []).append(x)
            ref = {}
            for k, lot in coh.items():
                sains = [y["_vie_brute"] for y in lot
                         if y["serie_pct_du_plafond"]
                         and statistics.median(y["serie_pct_du_plafond"].values()) >= 99]
                if len(sains) >= 5:
                    ref[k] = statistics.median(sains)
            # 🔴 REPLI POUR LES TROP VIEUX : si la cohorte stricte n a pas 5 sains,
            # on elargit a +/- 50 epoques de naissance. Largeur choisie par CONTROLE
            # DE BIAIS le 16/08 : a +/-50 l ecart median des sains vaut +0,00 pt
            # (ecart-type 2,91) ; a +/-300 il derive a -2,36 et le bruit monte a 5,82,
            # donc la largeur est bornee. Le resultat est marque CONFIANCE REDUITE et
            # jamais fondu avec les references strictes.
            LARGEUR_ELARGIE = 50
            for x in v_mes:
                if "_vie_brute" not in x or x["_cohorte"] in ref:
                    continue
                e0 = x.get("ne_a_l_epoque")
                voisins = [y["_vie_brute"] for y in v_mes
                           if "_vie_brute" in y and y.get("ne_a_l_epoque")
                           and abs(y["ne_a_l_epoque"] - e0) <= LARGEUR_ELARGIE
                           and y["serie_pct_du_plafond"]
                           and statistics.median(y["serie_pct_du_plafond"].values()) >= 99]
                if len(voisins) >= 5:
                    x["reference_cohorte_pct"] = round(statistics.median(voisins), 2)
                    x["ecart_cohorte_pt"] = round(x["_vie_brute"] - statistics.median(voisins), 2)
                    x["cohorte_elargie"] = True
                    x["confiance"] = "reduite -- reference elargie a +/-%d epoques" % LARGEUR_ELARGIE
            ecarts_sains = []
            for x in v_mes:
                if "_vie_brute" not in x or x["_cohorte"] not in ref:
                    # ne PAS ecraser un ecart deja calcule par la cohorte elargie
                    if not x.get("cohorte_elargie"):
                        x["ecart_cohorte_pt"] = None
                    continue
                x["reference_cohorte_pct"] = round(ref[x["_cohorte"]], 2)
                x["ecart_cohorte_pt"] = round(x["_vie_brute"] - ref[x["_cohorte"]], 2)
                if statistics.median(x["serie_pct_du_plafond"].values()) >= 99:
                    ecarts_sains.append(x["ecart_cohorte_pt"])
            med_sains = statistics.median(ecarts_sains) if ecarts_sains else None
            controles.append(controle(
                "reference de cohorte non biaisee (ecart median des sains proche de 0)",
                med_sains is not None and abs(med_sains) < 1.0,
                "mediane %+.2f pt sur %d validateurs sains, %d cohortes"
                % (med_sains, len(ecarts_sains), len(ref)) if med_sains is not None
                else "pas assez de cohortes"))
            profondeur["cohortes_utilisables"] = len(ref)
            profondeur["ecart_cohorte_median_des_sains_pt"] = (round(med_sains, 3)
                                                              if med_sains is not None else None)
            profondeur["resolus_par_cohorte"] = sum(
                1 for x in v_mes if x.get("ecart_cohorte_pt") is not None
                and not x.get("profondeur_exploitable"))
            profondeur["validateurs_exploitables"] = len(dedans)
            profondeur["validateurs_hors_domaine"] = hors
            profondeur["degrades_avec_profondeur"] = sorted(
                [x for x in dedans
                 if x["serie_pct_du_plafond"] and
                 statistics.median(x["serie_pct_du_plafond"].values()) < 100 * SEUIL_DEGRADE],
                key=lambda x: -x["stake_sol"])[:15]

    # -------------------------------------- recoupement sur un second endpoint
    autres = [e for e in ENDPOINTS if e != ep_va]
    rec = {"fait": False, "motif": "aucun second endpoint disponible"}
    if autres:
        va2, _ = c.appel("getVoteAccounts", None, endpoint=autres[0])
        ei2, _ = c.appel("getEpochInfo", None, endpoint=autres[0])
        if va2 and ei2:
            m2 = {}
            for v in va2.get("current", []):
                ec = v.get("epochCredits") or []
                if ec and ec[-1][0] == ei2["epoch"]:
                    m2[v.get("nodePubkey")] = ec[-1][1] - ec[-1][2]
            communs = [x for x in v_mes if x["identite"] in m2]
            ecarts = [abs(x["credits_epoque"] - m2[x["identite"]]) / max(1, x["credits_epoque"])
                      for x in communs]
            rec = {"fait": True, "endpoint_1": ep_va, "endpoint_2": autres[0],
                   "validateurs_communs": len(communs),
                   "ecart_relatif_median_pct": round(100 * statistics.median(ecarts), 5) if ecarts else None,
                   "ecart_relatif_max_pct": round(100 * max(ecarts), 5) if ecarts else None}
            controles.append(controle(
                "deux endpoints : ecart median des credits < 0,5 %",
                ecarts and statistics.median(ecarts) < 0.005,
                "median %s %% sur %d validateurs communs"
                % (rec["ecart_relatif_median_pct"], len(communs))))
        else:
            rec = {"fait": False, "motif": "le second endpoint n a pas repondu"}

    # -------------------------------------- recoupement sur RugAlert (tiers reellement independant)
    # 🔴 Ajoute le 17/08/2026, trouvaille de Spap (pumpkinspool.com). Les deux
    # ENDPOINTS ci-dessus sont deux RPC PUBLICS -- rien ne prouve qu ils ne
    # partagent pas la meme infrastructure en amont (deja ecrit dans les
    # limites_declarees). RugAlert est opere par un tiers (Pumpkin's Pool),
    # sans cle, CORS ouvert -- une source d origine differente.
    # VERIFIE le 17/08 en l appelant en direct (profil Shinobi Systems) :
    # RugAlert n expose QUE le voteCredits de l EPOQUE EN COURS -- pas
    # d historique multi-epoques, pas de classe chronique/accidentel/sain.
    # Donc ce recoupement ne peut porter QUE sur l epoque en cours, et
    # UNIQUEMENT sur les validateurs deja signales ici (chroniques + degrades),
    # pas sur tout le parc : rate limit 60 requetes/min, un profil = un appel,
    # et le but est de verifier les cas qu on s apprete a publier, pas un
    # sondage exhaustif qu on n a pas les moyens de faire tenir dans un run.
    RUGALERT_BASE = "https://rugalert.pumpkinspool.com/api/v1"
    rugalert = {"fait": False, "motif": "non tente"}
    try:
        rep_ep = requests.get(RUGALERT_BASE + "/epoch", timeout=15)
        rep_ep.raise_for_status()
        epoque_ra = (rep_ep.json().get("data") or {}).get("epoch")
        if epoque_ra != epoque:
            rugalert = {"fait": False,
                       "motif": "epoque RugAlert (%s) != epoque RPC (%s) -- pas comparable a cet instant"
                                % (epoque_ra, epoque)}
        else:
            vus, cibles = set(), []
            for x in (chronicite.get("liste_chroniques", []) + degrades[:15]):
                cv = x.get("compte_vote")
                if cv and cv not in vus:
                    vus.add(cv); cibles.append(x)
            cibles = cibles[:30]     # plafond dur -- rate limit 60/min, marge large
            communs, ecarts, echecs_ra = [], [], []
            for x in cibles:
                try:
                    rp = requests.get(RUGALERT_BASE + "/validators/" + x["compte_vote"], timeout=15)
                    if rp.status_code != 200:
                        echecs_ra.append({"compte_vote": x["compte_vote"], "statut": rp.status_code})
                        continue
                    perf = (rp.json().get("data") or {}).get("performance") or {}
                    if perf.get("epoch") != epoque or perf.get("voteCredits") is None:
                        echecs_ra.append({"compte_vote": x["compte_vote"],
                                          "motif": "pas de voteCredits pour cette epoque cote RugAlert"})
                        continue
                    ec = abs(x["credits_epoque"] - perf["voteCredits"]) / max(1, x["credits_epoque"])
                    ecarts.append(ec); communs.append(x["compte_vote"])
                except Exception as ex:
                    echecs_ra.append({"compte_vote": x["compte_vote"],
                                      "motif": "%s : %s" % (type(ex).__name__, str(ex)[:100])})
                time.sleep(1.1)   # 60 req/min max -- marge large
            rugalert = {
                "fait": True,
                "source": "rugalert.pumpkinspool.com (operateur tiers independant, sans cle)",
                "portee": "epoque en cours SEULE, validateurs deja signales ici seulement -- pas tout le parc",
                "cibles_testees": len(cibles), "validateurs_communs": len(communs),
                "echecs": echecs_ra,
                "ecart_relatif_median_pct": round(100 * statistics.median(ecarts), 4) if ecarts else None,
                "ecart_relatif_max_pct": round(100 * max(ecarts), 4) if ecarts else None,
            }
            controles.append(controle(
                "recoupement RugAlert (tiers independant) sur les validateurs signales : ecart median < 1 %",
                bool(ecarts) and statistics.median(ecarts) < 0.01,
                "median %s %% sur %d validateur(s) commun(s) / %d cible(s), %d echec(s)"
                % (rugalert.get("ecart_relatif_median_pct"), len(communs), len(cibles), len(echecs_ra))))
    except Exception as ex:
        rugalert = {"fait": False, "motif": "%s : %s" % (type(ex).__name__, str(ex)[:150])}

    alpen = sonder_alpenglow(c)
    gate = sonder_feature_gate(c)
    alpen["feature_gate"] = gate
    controles.append(controle(
        "feature-gate Alpenglow (SIMD-0384) non actif -- le mecanisme mesure est intact",
        not gate.get("actif"), gate["verdict"][:150]))

    v_mes.sort(key=lambda x: (x["credits_par_slot"] is None, x["credits_par_slot"]))
    return {
        "horodatage_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "complet": len(manquants) == 0,
        "champs_manquants": manquants,
        "epoque": epoque, "slots_ecoules": idx, "slots_par_epoque": ei["slotsInEpoch"],
        "validateurs_actifs": len(actifs), "validateurs_delinquants": len(delinquants),
        "validateurs_mesures": len(v_mes), "sans_credit_cette_epoque": sans_credit,
        "credits_ponderes_par_latence": pondere,
        "plafond_credits": PLAFOND_CREDITS,
        "reseau": {
            "credits_par_slot_median": round(statistics.median(ps), 4) if ps else None,
            "credits_par_slot_max": round(max_obs, 4) if max_obs else None,
            "credits_par_slot_min": round(min(ps), 4) if ps else None,
            "pct_du_plafond_median": round(100 * statistics.median(ps) / PLAFOND_CREDITS, 2) if ps else None,
            "latence_implicite_mediane_slots": (round(PLAFOND_CREDITS + 1 - statistics.median(ps), 3)
                                                if pondere and ps else None),
            "deciles_credits_par_slot": [round(x, 4) for x in statistics.quantiles(ps, n=10)] if len(ps) >= 10 else None,
        },
        "_v_mes_pour_serie": v_mes,
        "chronicite": chronicite,
        "profondeur_historique": profondeur,
        "degrades": {
            "seuil_pct_du_plafond": 100 * SEUIL_DEGRADE,
            "nombre": len(degrades),
            "dont_avec_historique": len(degrades_etablis),
            "dont_potentiellement_neufs": len(degrades) - len(degrades_etablis),
            "stake_concerne_sol": round(stake_degrade, 2),
            "part_du_stake_mesure_pct": round(100 * stake_degrade / stake_total, 4) if stake_total else None,
            "liste": degrades[:40],
        },
        "meilleurs": v_mes[-10:][::-1],
        "alpenglow": alpen,
        "recoupement_second_endpoint": rec,
        "recoupement_rugalert": rugalert,
        "controles": controles,
        "controles_passes": sum(1 for x in controles if x["passe"]),
        "controles_total": len(controles),
        "limites_declarees": [
            "La latence implicite conflue DEUX causes : un vote lent et un vote manque font "
            "baisser la moyenne de la meme facon. Ce chiffre ne les separe pas et ne pretend pas le faire.",
            "epochCredits ne conserve qu un nombre limite d epoques (5 observees). Le filtre "
            "-validateur neuf- qui en decoule est donc grossier, pas exact.",
            "Le bloc -degrades- ci-dessous porte sur l epoque EN COURS SEULE : plus elle est "
            "jeune, plus le bruit est grand. C est le bloc -chronicite- qui tranche entre un "
            "probleme durable et un accident, et c est LUI qu il faut citer.",
            "Les deux endpoints du recoupement sont publics : leur accord ecarte une panne locale, "
            "il ne prouve pas l independance des sources.",
            "Le recoupement RugAlert porte sur l EPOQUE EN COURS SEULE et sur les validateurs "
            "deja signales ici, pas sur tout le parc (rate limit de l API tierce) -- il ne "
            "remplace pas la classification chronique/accident, qui n existe que dans cet outil.",
            "Ceci mesure le schema de credits ACTUEL (SIMD-0033), pas Alpenglow. Le jour ou "
            "Alpenglow s active, la sonde incluse le detectera et cette mesure devra etre refaite.",
        ],
        "appels_rpc": c.appels, "echecs_rpc": len(c.echecs), "detail_echecs": c.echecs[:20],
        "latence_rpc_mediane_ms": round(1000 * statistics.median(c.latences)) if c.latences else None,
        "duree_s": round(time.time() - t0, 1),
    }


def nb(v, dec=None):
    if v is None:
        return "—"
    if isinstance(v, float) and dec is not None:
        v = round(v, dec)
    return "{:,}".format(v).replace(",", " ") if isinstance(v, (int, float)) else str(v)


def rendre_markdown(e):
    L = []; A = L.append
    A("# Solana — précision et latence de vote par validateur")
    A("")
    A("*Instantané du **%s** · époque **%s**, %s slots écoulés · lecture RPC directe.*"
      % (e["horodatage_utc"], e.get("epoque"), nb(e.get("slots_ecoules"))))
    A("")
    if not e["complet"]:
        A("> 🔴 **INSTANTANÉ INCOMPLET — %d champ(s) manquant(s), non comblés.**" % len(e["champs_manquants"]))
        for m in e["champs_manquants"]:
            A("> - `%s` (%s) : %s" % (m["champ"], m["methode"], m["motif"]))
        return "\n".join(L)
    a = e["alpenglow"]
    A("## 🔴 D'abord : la méthode « récompenses de vote au bloc s+8 » ne marche pas encore")
    A("")
    A("**%s**" % a.get("verdict", "sonde non exécutée"))
    A("")
    A("*Sondé à cette exécution : %s bloc(s) ordinaire(s) examiné(s), types de récompense trouvés : `%s`.*"
      % (a.get("blocs_examines"), a.get("types_de_recompense")))
    A("")
    A("Les récompenses `Voting` existent, mais **groupées dans le premier bloc de chaque époque** — "
      "c'est l'ancien schéma, pas le mécanisme par slot d'Alpenglow. **Cette sonde est refaite à chaque "
      "exécution** : le jour où Alpenglow s'active, ce rapport le dira tout seul.")
    A("")
    r = e["reseau"]
    A("## Ce qu'on mesure à la place, et qui fonctionne")
    A("")
    A("**Les crédits de vote pondérés par la latence (SIMD-0033).** Un vote qui arrive 1 slot après sa cible "
      "vaut %d crédits ; 2 slots, 15 ; … ; 16 slots ou plus, 1. Donc `crédits ÷ slots écoulés` **est** une "
      "mesure de latence." % e["plafond_credits"])
    A("")
    A("| | |")
    A("|---|---|")
    A("| validateurs mesurés | **%s** *(sur %s actifs · %s sans crédit cette époque)* |"
      % (nb(e["validateurs_mesures"]), nb(e["validateurs_actifs"]), nb(e["sans_credit_cette_epoque"])))
    A("| crédits/slot — médiane | **%s** — soit **%s %%** du plafond |"
      % (nb(r["credits_par_slot_median"]), nb(r["pct_du_plafond_median"])))
    A("| crédits/slot — max observé | **%s** / %d |" % (nb(r["credits_par_slot_max"]), e["plafond_credits"]))
    A("| crédits/slot — min observé | **%s** |" % nb(r["credits_par_slot_min"]))
    if r["latence_implicite_mediane_slots"] is not None:
        A("| **latence de vote implicite, médiane réseau** | **%s slot(s)** |" % nb(r["latence_implicite_mediane_slots"]))
    A("| validateurs délinquants | %s |" % nb(e["validateurs_delinquants"]))
    A("")
    ch = e.get("chronicite", {})
    A("## 🔴 Chronique ou accident — la question qui décide de tout")
    A("")
    if not ch.get("tranchable"):
        A("> 🔴 **NON TRANCHÉ : %s**" % ch.get("motif_si_non", ""))
        A("")
    else:
        A("**Classé sur %d époques (%s), pas sur une seule.** Un validateur est dit *chronique* s'il "
          "passe sous le seuil sur la majorité des époques disponibles, *accidentel* s'il n'y passe "
          "qu'à l'époque en cours." % (len(ch["epoques_disponibles"]), ch["epoques_disponibles"]))
        A("")
        A("| | validateurs | stake (SOL) |")
        A("|---|---|---|")
        A("| 🔴 **chroniques** — signal réel | **%s** | **%s** |"
          % (nb(ch["chroniques"]), nb(ch["stake_chronique_sol"], 0)))
        A("| 🟠 intermittents | %s | %s |" % (nb(ch["intermittents"]), nb(ch["stake_intermittent_sol"], 0)))
        A("| 🟢 accidentels — dégradés seulement maintenant | %s | %s |"
          % (nb(ch["accidentels"]), nb(ch["stake_accidentel_sol"], 0)))
        A("| sains sur toutes les époques | %s | |" % nb(ch["sains"]))
        A("")
        A("> ### **Le chiffre à citer est le stake CHRONIQUE : %s SOL, soit %s %% du stake mesuré.** "
          "Le stake dégradé à l'instant t est plus gros et trompeur — il gonfle avec le premier "
          "gros validateur qui a une mauvaise époque."
          % (nb(ch["stake_chronique_sol"], 0), nb(ch["part_stake_chronique_pct"])))
        A("")
        if ch["liste_chroniques"]:
            eps = ch["epoques_disponibles"]
            A("| validateur chronique | " + " | ".join(str(x) for x in eps) + " | stake (SOL) | sous seuil |")
            A("|---" * (len(eps) + 3) + "|")
            for x in ch["liste_chroniques"]:
                cases = " | ".join(("%s" % nb(x["serie_pct_du_plafond"].get(p)))
                                   for p in eps)
                A("| `%s…%s` | %s | %s | %s/%s |" % (
                    x["identite"][:8], x["identite"][-4:], cases, nb(x["stake_sol"], 0),
                    nb(x["epoques_sous_seuil"]), nb(x["epoques_mesurees"])))
            A("")
        if ch["liste_accidentels"]:
            A("**Accidentels — normaux sur les époques précédentes, dégradés seulement maintenant. "
              "Les citer comme un problème serait une erreur :**")
            A("")
            eps = ch["epoques_disponibles"]
            A("| validateur | " + " | ".join(str(x) for x in eps) + " | stake (SOL) |")
            A("|---" * (len(eps) + 2) + "|")
            for x in ch["liste_accidentels"]:
                cases = " | ".join(("%s" % nb(x["serie_pct_du_plafond"].get(p))) for p in eps)
                A("| `%s…%s` | %s | %s |" % (x["identite"][:8], x["identite"][-4:], cases,
                                             nb(x["stake_sol"], 0)))
            A("")
    pr = e.get("profondeur_historique", {})
    A("## Depuis quand ? — au-delà du plafond de 5 époques du RPC")
    A("")
    if not pr.get("disponible"):
        A("> 🔴 **Non disponible cette exécution** — %s" % pr.get("motif_indisponible", "source tierce muette"))
        A("")
    else:
        A("`epochCredits` plafonne à 5 époques. Les crédits **cumulés depuis toujours** (RPC) divisés par "
          "l'âge du validateur (`first_epoch_with_stake`, source **%s**) donnent une moyenne de vie. "
          "L'écart entre cette moyenne et les 5 dernières époques dit si la dégradation est **ancienne ou récente**."
          % pr.get("source"))
        A("")
        A("🔴 **Et le piège que ça cache :** cette moyenne est un **artefact d'âge** si on ne la borne pas. "
          "Avant SIMD-0033 un vote valait 1 crédit, pas 16 — mesuré : la corrélation entre l'âge et la moyenne "
          "de vie vaut **−0,95**, et des validateurs *sains aujourd'hui* affichent 99 %% s'ils sont nés il y a "
          "200-400 époques mais **41 %%** s'ils sont nés il y a 700-1100. **La moyenne de vie n'est donc calculée "
          "que pour les validateurs nés après l'époque %s et âgés d'au moins %s époques** : "
          "**%s exploitables, %s hors domaine.**"
          % (pr.get("epoque_bascule_retenue"), pr.get("age_minimal_epoques"),
             nb(pr.get("validateurs_exploitables")), nb(pr.get("validateurs_hors_domaine"))))
        A("")
        A("*Contrôle : stakewiz et le RPC s'accordent sur les crédits cumulés à %s %% près.*"
          % nb(pr.get("accord_credits_cumules_pct")))
        A("")
        lot = pr.get("degrades_avec_profondeur") or []
        if lot:
            A("| validateur | né à l'époque | âge | moyenne de vie | 5 époques | dégradé depuis ~ | stake (SOL) |")
            A("|---|---|---|---|---|---|---|")
            for x in lot:
                med = statistics.median(x["serie_pct_du_plafond"].values())
                dep = x.get("degrade_depuis_epoques_estime")
                A("| `%s…%s` | %s | %s ép. | %s %% | %s %% | %s | %s |" % (
                    x["identite"][:8], x["identite"][-4:], nb(x.get("ne_a_l_epoque")),
                    nb(x.get("age_epoques")), nb(x.get("moyenne_vie_pct")), nb(round(med, 2)),
                    ("**%s époques (~%s jours)**" % (nb(dep), nb(x.get("degrade_depuis_jours_estime"))))
                    if dep else "—", nb(x["stake_sol"], 0)))
            A("")
        # --- ce que la reference de cohorte rattrape
        cohortes = sorted([x for x in e.get("_v_mes_pour_serie", [])
                           if x.get("ecart_cohorte_pt") is not None
                           and not x.get("profondeur_exploitable")
                           and x["serie_pct_du_plafond"]
                           and statistics.median(x["serie_pct_du_plafond"].values()) < 100 * 0.95],
                          key=lambda x: x["ecart_cohorte_pt"])
        if cohortes:
            A("### Les trop vieux, rattrapés par leur cohorte de naissance")
            A("")
            A("Pour un validateur né avant la bascule, la moyenne de vie ne se compare pas au plafond de 16 — "
              "mais elle se compare à **celle des validateurs nés la même époque**, qui ont vécu le même mélange "
              "de barèmes. Le biais est partagé, donc l'écart reste interprétable.")
            A("")
            A("*Contrôle : sur les validateurs sains, cet écart vaut **%s pt** en médiane sur %s cohortes — "
              "la référence est donc non biaisée.*"
              % (nb(pr.get("ecart_cohorte_median_des_sains_pt")), nb(pr.get("cohortes_utilisables"))))
            A("")
            A("| validateur | né à l'époque | sa vie | sa cohorte | **écart** | 5 époques | stake (SOL) |")
            A("|---|---|---|---|---|---|---|")
            for x in cohortes[:15]:
                med = statistics.median(x["serie_pct_du_plafond"].values())
                d = x["ecart_cohorte_pt"]
                A("| `%s…%s` | %s | %s %% | %s %% | **%s pt** %s | %s %% | %s |" % (
                    x["identite"][:8], x["identite"][-4:], nb(x.get("ne_a_l_epoque")),
                    nb(round(x.get("_vie_brute", 0), 2)), nb(x.get("reference_cohorte_pct")),
                    nb(d), "🔴" if d < -3 else "🟠 dans la norme",
                    nb(round(med, 2)), nb(x["stake_sol"], 0)))
            A("")
            A("⚠️ **La colonne « dégradé depuis » suppose un changement en marche d'escalier** — un validateur "
              "sain puis brusquement dégradé. Une dérive progressive donnerait un chiffre trop grand. Elle n'est "
              "calculée que si l'écart avec un niveau sain dépasse **15 points** ; en dessous elle serait "
              "dominée par le bruit et reste vide.")
            A("")
    d = e["degrades"]
    A("## L'époque en cours seule — à ne PAS citer sans les tableaux ci-dessus")
    A("")
    A("> **La médiane est à %s %% du plafond : classer les « meilleurs » validateurs n'apprend rien, "
      "ils sont tous collés au maximum. Ce qui se voit, ce sont les traînards.**" % nb(r["pct_du_plafond_median"]))
    A("")
    A("| | |")
    A("|---|---|")
    A("| validateurs sous %s %% du plafond | **%s** sur %s |" % (nb(d["seuil_pct_du_plafond"]), nb(d["nombre"]), nb(e["validateurs_mesures"])))
    A("| dont avec historique *(donc pas nouvellement activés)* | **%s** |" % nb(d["dont_avec_historique"]))
    A("| **stake derrière un vote dégradé** | **%s SOL** — %s %% du stake mesuré |"
      % (nb(d["stake_concerne_sol"], 0), nb(d["part_du_stake_mesure_pct"])))
    A("")
    if d["liste"]:
        A("| validateur | crédits/slot | % du plafond | latence implicite | stake (SOL) | époques |")
        A("|---|---|---|---|---|---|")
        for x in d["liste"][:20]:
            A("| `%s…%s` | %s | %s %% | %s | %s | %s |" % (
                x["identite"][:8], x["identite"][-4:], nb(x["credits_par_slot"]),
                nb(x["pct_du_plafond"]), nb(x["latence_implicite_slots"]),
                nb(x["stake_sol"], 0), nb(x["epoques_dans_historique"])))
        A("")
    A("## Contrôles — %d / %d passés" % (e["controles_passes"], e["controles_total"]))
    A("")
    A("| contrôle | | détail |")
    A("|---|---|---|")
    for ct in e["controles"]:
        A("| %s | %s | %s |" % (ct["controle"], "🟢" if ct["passe"] else "🔴", ct["detail"]))
    A("")
    rc = e["recoupement_second_endpoint"]
    if rc.get("fait"):
        A("**Recoupement sur un second endpoint :** `%s` vs `%s` — %s validateurs communs, "
          "écart relatif médian des crédits **%s %%**, max %s %%."
          % (rc["endpoint_1"], rc["endpoint_2"], nb(rc["validateurs_communs"]),
             nb(rc["ecart_relatif_median_pct"]), nb(rc["ecart_relatif_max_pct"])))
    else:
        A("🔴 **Recoupement non fait** — %s" % rc.get("motif", ""))
    A("")
    ra = e.get("recoupement_rugalert", {})
    if ra.get("fait"):
        A("**Recoupement RugAlert (tiers indépendant, epoque en cours, validateurs signalés) :** "
          "%s cible(s), %s validateur(s) commun(s), écart relatif médian **%s %%**, max %s %%, %s échec(s)."
          % (nb(ra.get("cibles_testees")), nb(ra.get("validateurs_communs")),
             nb(ra.get("ecart_relatif_median_pct")), nb(ra.get("ecart_relatif_max_pct")),
             len(ra.get("echecs", []))))
    else:
        A("🔴 **Recoupement RugAlert non fait** — %s" % ra.get("motif", ""))
    A("")
    A("## Ce que cette mesure ne prouve pas")
    A("")
    for lim in e["limites_declarees"]:
        A("- %s" % lim)
    A("")
    A("---")
    A("")
    A("*%s appels RPC, %s échec(s), latence médiane %s ms, %s s. Endpoints publics sans clé. "
      "Aucune valeur interpolée.*" % (nb(e["appels_rpc"]), nb(e["echecs_rpc"]),
                                      nb(e["latence_rpc_mediane_ms"]), nb(e["duree_s"])))
    return "\n".join(L)


def rendre_html(e):
    if not e["complet"]:
        corps = ('<div class="alerte"><b>Instantané incomplet — %d champ(s) manquant(s), non comblés.</b><br>%s</div>'
                 % (len(e["champs_manquants"]),
                    "<br>".join("<code>%s</code> : %s" % (m["champ"], m["motif"]) for m in e["champs_manquants"])))
        cartes = tab_deg = tab_ctrl = chron_html = ""
        lims = ""
        rugalert_html = ""
    else:
        r, d, a = e["reseau"], e["degrades"], e["alpenglow"]
        # 🔴 CORRIGE le 17/08/2026 : ce generateur HTML n'avait JAMAIS recu la
        # correction "chronique / accident" du 15/08 (voir le bloc plus haut,
        # "CHRONIQUE OU ACCIDENT ?"). Le RAPPORT.md (markdown) l'a depuis le
        # debut, mais index.html continuait d'afficher "Stake concerne" --
        # l'ancien chiffre a l'epoque en cours seule -- comme SEUL chiffre,
        # sans le stake CHRONIQUE (le bon a citer) ni le tableau de repartition.
        # Trouve en verifiant la page deja publiee sur GitHub Pages : elle
        # affichait 7 220 970 SOL (chiffre dementi d'un facteur 9,7 le 15/08 au
        # soir) comme metrique vedette, sans aucune mention du chiffre corrige
        # (747 628 SOL). Meme donnee que le markdown, meme dict `chronicite`
        # deja calcule plus haut -- il manquait seulement d'etre rendu ici.
        ch = e.get("chronicite", {})
        corps = ('<div class="%s"><b>%s</b><br><span class="s">Sondé à cette exécution : %s bloc(s) ordinaire(s), '
                 'types de récompense trouvés : <code>%s</code>. Les récompenses <code>Voting</code> existent mais '
                 'sont groupées dans le premier bloc de chaque époque — ancien schéma, pas le mécanisme par slot '
                 'd\'Alpenglow. Cette sonde est refaite à chaque exécution.</span></div>'
                 % ("alerte" if not a.get("recompense_de_vote_par_slot") else "ok-box",
                    a.get("verdict", ""), a.get("blocs_examines"), a.get("types_de_recompense")))
        def carte(t, v, n_):
            return '<div class="c"><div class="t">%s</div><div class="v">%s</div><div class="n">%s</div></div>' % (t, v, n_)
        cartes_liste = [
            carte("Latence de vote médiane", "%s slot" % nb(r["latence_implicite_mediane_slots"]),
                  "médiane réseau, %s validateurs" % nb(e["validateurs_mesures"])),
            carte("Crédits/slot médians", nb(r["credits_par_slot_median"]),
                  "%s %% du plafond de %d" % (nb(r["pct_du_plafond_median"]), e["plafond_credits"])),
            carte("Vote dégradé (époque en cours)", nb(d["nombre"]),
                  "validateurs sous %s %% du plafond — instantané, pas un verdict" % nb(d["seuil_pct_du_plafond"])),
            carte("Stake concerné (époque en cours)", "%s SOL" % nb(d["stake_concerne_sol"], 0),
                  "%s %% — trompeur seul, voir stake CHRONIQUE ci-dessous" % nb(d["part_du_stake_mesure_pct"])),
        ]
        if ch.get("tranchable"):
            cartes_liste.insert(0, carte(
                "🔴 Stake chronique — chiffre à citer",
                "%s SOL" % nb(ch.get("stake_chronique_sol", 0), 0),
                "%s %% du stake, %s validateur(s) chroniques sur %d époques"
                % (nb(ch.get("part_stake_chronique_pct")), nb(ch.get("chroniques", 0)),
                   len(ch.get("epoques_disponibles", [])))))
        cartes_liste += [
            carte("Délinquants", nb(e["validateurs_delinquants"]), "ne votent plus du tout"),
            carte("Époque", str(e["epoque"]), "%s slots écoulés" % nb(e["slots_ecoules"])),
        ]
        cartes = "".join(cartes_liste)
        # ── LE BLOC CHRONIQUE/ACCIDENT, PORTE DEPUIS rendre_markdown() ──────
        if not ch.get("tranchable"):
            chron_html = ('<div class="alerte"><b>🔴 Chronique ou accident — NON TRANCHÉ</b><br>'
                          '<span class="s">%s</span></div>' % (ch.get("motif_si_non", "")))
        else:
            eps = ch.get("epoques_disponibles", [])
            lignes_chron = "".join(
                '<tr><td class="m">%s…%s</td>%s<td class="r">%s</td><td class="r">%s/%s</td></tr>' % (
                    x["identite"][:8], x["identite"][-4:],
                    "".join('<td class="r">%s</td>' % nb(x["serie_pct_du_plafond"].get(p)) for p in eps),
                    nb(x["stake_sol"], 0), nb(x["epoques_sous_seuil"]), nb(x["epoques_mesurees"]))
                for x in ch.get("liste_chroniques", []))
            entetes_eps = "".join("<th class=\"r\">%s</th>" % p for p in eps)
            tab_chron = ('<div class="tw"><table><thead><tr><th>validateur chronique</th>%s'
                        '<th class="r">stake (SOL)</th><th class="r">sous seuil</th></tr></thead>'
                        '<tbody>%s</tbody></table></div>' % (entetes_eps, lignes_chron)) if lignes_chron else ""
            chron_html = (
                '<div class="ok-box"><b>Classé sur %d époques (%s), pas sur une seule.</b><br>'
                '<span class="s">Un validateur est dit <i>chronique</i> s\'il passe sous le seuil sur la majorité '
                'des époques disponibles, <i>accidentel</i> s\'il n\'y passe qu\'à l\'époque en cours.</span></div>'
                '<div class="g" style="margin-top:12px">%s%s%s</div>'
                '<div class="enc" style="margin-top:12px"><b>🔴 Le chiffre à citer est le stake CHRONIQUE : '
                '%s SOL, soit %s %% du stake mesuré.</b><br><span class="s">Le stake dégradé à l\'instant t '
                '(carte ci-dessus) est plus gros et trompeur — il gonfle avec le premier gros validateur qui a '
                'une mauvaise époque.</span></div>%s'
                % (len(eps), ", ".join(str(p) for p in eps),
                   carte("🔴 chroniques — signal réel", nb(ch.get("chroniques", 0)),
                         "%s SOL" % nb(ch.get("stake_chronique_sol", 0), 0)),
                   carte("🟠 intermittents", nb(ch.get("intermittents", 0)),
                         "%s SOL" % nb(ch.get("stake_intermittent_sol", 0), 0)),
                   carte("🟢 accidentels — dégradés seulement maintenant", nb(ch.get("accidentels", 0)),
                         "%s SOL" % nb(ch.get("stake_accidentel_sol", 0), 0)),
                   nb(ch.get("stake_chronique_sol", 0), 0), nb(ch.get("part_stake_chronique_pct")),
                   tab_chron))
        tab_deg = "".join(
            '<tr><td class="m">%s…%s</td><td class="r">%s</td><td class="r">%s %%</td>'
            '<td class="r">%s</td><td class="r">%s</td><td class="r">%s</td></tr>' % (
                x["identite"][:8], x["identite"][-4:], nb(x["credits_par_slot"]),
                nb(x["pct_du_plafond"]), nb(x["latence_implicite_slots"]),
                nb(x["stake_sol"], 0), nb(x["epoques_dans_historique"]))
            for x in d["liste"][:25])
        tab_ctrl = "".join('<tr><td>%s</td><td class="r">%s</td><td class="d">%s</td></tr>'
                           % (c["controle"], "🟢" if c["passe"] else "🔴", c["detail"])
                           for c in e["controles"])
        lims = "".join("<li>%s</li>" % l for l in e["limites_declarees"])
        ra = e.get("recoupement_rugalert", {})
        if ra.get("fait"):
            rugalert_html = (
                '<div class="ok-box"><b>Recoupement RugAlert (tiers ind&eacute;pendant).</b><br>'
                '<span class="s">&Eacute;poque en cours, validateurs d&eacute;j&agrave; signal&eacute;s ici seulement '
                '(pas tout le parc &mdash; limite de d&eacute;bit de l\'API tierce) : %s cible(s), %s validateur(s) '
                'commun(s), &eacute;cart relatif m&eacute;dian <b>%s %%</b>, max %s %%, %s &eacute;chec(s).</span></div>'
                % (nb(ra.get("cibles_testees")), nb(ra.get("validateurs_communs")),
                   nb(ra.get("ecart_relatif_median_pct")), nb(ra.get("ecart_relatif_max_pct")),
                   len(ra.get("echecs", []))))
        else:
            rugalert_html = ('<div class="alerte"><b>Recoupement RugAlert non fait.</b><br>'
                             '<span class="s">%s</span></div>' % (ra.get("motif", "")))

    g = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solana &mdash; pr&eacute;cision de vote par validateur</title><style>
:root{--bg:#0d1117;--pan:#161b22;--bd:#30363d;--tx:#e6edf3;--mu:#8b949e;--ac:#2ea043;--al:#f85149;--hi:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.w{max-width:1080px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:25px;margin:0 0 6px}h2{font-size:18px;margin:36px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--bd)}
.s{color:var(--mu);font-size:13px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:18px}
.c{background:var(--pan);border:1px solid var(--bd);border-radius:10px;padding:14px 16px}
.c .t{color:var(--mu);font-size:12px;text-transform:uppercase;letter-spacing:.5px}
.c .v{font-size:26px;font-weight:650;margin:6px 0 2px;color:var(--hi)}
.c .n{color:var(--mu);font-size:12px}
.tw{overflow-x:auto;margin-top:10px}table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:8px 10px;border-bottom:1px solid var(--bd);text-align:left;white-space:nowrap}
th{color:var(--mu);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
td.r,th.r{text-align:right}td.m{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--mu)}
td.d{color:var(--mu);font-size:12.5px;white-space:normal}
.alerte{background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.4);border-radius:10px;padding:14px 16px;margin-top:18px}
.ok-box{background:rgba(46,160,67,.1);border:1px solid rgba(46,160,67,.4);border-radius:10px;padding:14px 16px;margin-top:18px}
.enc{background:var(--pan);border-left:3px solid var(--hi);padding:12px 16px;margin-top:16px;border-radius:0 8px 8px 0}
code{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--hi)}
ul.s li{margin-bottom:6px}
footer{margin-top:42px;padding-top:16px;border-top:1px solid var(--bd);color:var(--mu);font-size:12.5px}
</style></head><body><div class="w">
<h1>Solana &mdash; pr&eacute;cision et latence de vote par validateur</h1>
<p class="s">Instantan&eacute; du <b>@QUAND@</b> &middot; &eacute;poque <b>@EPOQUE@</b> &middot; lecture RPC directe,
sans indexeur tiers, sans cl&eacute; API.</p>
@ALPEN@
<div class="enc"><b>Ce qu'on mesure, et pourquoi c'est la mesure disponible.</b><br>
<span class="s">Les cr&eacute;dits de vote sont pond&eacute;r&eacute;s par la latence (SIMD-0033) : un vote arrivant
1 slot apr&egrave;s sa cible vaut 16 cr&eacute;dits, 2 slots 15, &hellip; 16 slots ou plus 1.
Donc <code>cr&eacute;dits &divide; slots &eacute;coul&eacute;s</code> <b>est</b> une mesure de latence de vote.
L'hypoth&egrave;se est test&eacute;e &agrave; chaque ex&eacute;cution, pas suppos&eacute;e.</span></div>
<div class="g">@CARTES@</div>
<h2>🔴 Chronique ou accident — la question qui décide de tout</h2>
@CHRON@
<h2>Le signal est dans la queue, pas dans le classement</h2>
<p class="s">La m&eacute;diane du r&eacute;seau colle au plafond : classer les &laquo;&nbsp;meilleurs&nbsp;&raquo;
validateurs n'apprend rien. Ce qui se voit, ce sont les tra&icirc;nards &mdash; et le stake derri&egrave;re eux.</p>
<div class="tw"><table><thead><tr><th>validateur</th><th class="r">cr&eacute;dits/slot</th>
<th class="r">% du plafond</th><th class="r">latence implicite</th><th class="r">stake (SOL)</th>
<th class="r">&eacute;poques</th></tr></thead><tbody>@DEG@</tbody></table></div>
<h2>Contr&ocirc;les &mdash; @COK@ / @CTOT@ pass&eacute;s</h2>
<div class="tw"><table><thead><tr><th>contr&ocirc;le</th><th class="r"></th><th>d&eacute;tail</th></tr></thead>
<tbody>@CTRL@</tbody></table></div>
@RUGALERT@
<h2>Ce que cette mesure ne prouve pas</h2>
<ul class="s">@LIMS@</ul>
<footer>@APPELS@ appels RPC &middot; @ECHECS@ &eacute;chec(s) &middot; @DUREE@ s &middot; endpoints publics sans cl&eacute;.
Aucune valeur interpol&eacute;e : un appel qui &eacute;choue laisse un trou d&eacute;clar&eacute;.</footer>
</div></body></html>"""
    for k, v in {"@QUAND@": e["horodatage_utc"], "@EPOQUE@": str(e.get("epoque", "—")),
                 "@ALPEN@": corps, "@CARTES@": cartes, "@CHRON@": chron_html,
                 "@DEG@": tab_deg, "@CTRL@": tab_ctrl,
                 "@COK@": str(e.get("controles_passes", 0)), "@CTOT@": str(e.get("controles_total", 0)),
                 "@LIMS@": lims, "@RUGALERT@": rugalert_html,
                 "@APPELS@": nb(e["appels_rpc"]), "@ECHECS@": nb(e["echecs_rpc"]),
                 "@DUREE@": nb(e["duree_s"])}.items():
        g = g.replace(k, v)
    return g


def main():
    ap = argparse.ArgumentParser(description="Précision et latence de vote par validateur Solana")
    ap.add_argument("--sortie", default=os.path.join(RACINE, "sortie_vote"))
    a = ap.parse_args()
    os.makedirs(a.sortie, exist_ok=True)
    e = instantane()

    if e["complet"]:
        # 🔴 SERIE PAR VALIDATEUR -- le seul moyen de depasser un jour le plafond de
        # 5 epoques du RPC. ELLE COMMENCE AUJOURD HUI ET NE REMONTE PAS DANS LE PASSE :
        # tant qu elle est jeune, elle n apporte RIEN de plus que les 5 epoques deja
        # lisibles. Deduplication par (epoque, validateur) : deux executions dans la
        # meme fenetre n ecrivent pas deux fois la meme epoque.
        chemin_serie = os.path.join(a.sortie, "serie_validateurs.jsonl")
        deja = set()
        if os.path.exists(chemin_serie):
            with open(chemin_serie, encoding="utf-8") as f:
                for l in f:
                    if l.strip():
                        try:
                            o = json.loads(l); deja.add((o["epoque"], o["identite"]))
                        except Exception:
                            pass          # ligne illisible : ignoree, jamais reparee en silence
        neuves = 0
        with open(chemin_serie, "a", encoding="utf-8") as f:
            for x in e.get("_v_mes_pour_serie", []):
                for ep_i, pct in x["serie_pct_du_plafond"].items():
                    if (ep_i, x["identite"]) in deja:
                        continue
                    if ep_i == e["epoque"]:
                        continue          # epoque EN COURS : incomplete, on ne la fige pas
                    f.write(json.dumps({
                        "releve_le_utc": e["horodatage_utc"], "epoque": ep_i,
                        "identite": x["identite"], "compte_vote": x["compte_vote"],
                        "pct_du_plafond": pct, "stake_sol_au_releve": x["stake_sol"],
                    }, ensure_ascii=False) + "\n")
                    neuves += 1
        e["serie_validateurs"] = {
            "fichier": "serie_validateurs.jsonl",
            "lignes_ajoutees": neuves, "lignes_deja_presentes": len(deja),
            "note": ("cette serie COMMENCE le 16/08/2026 et ne remonte PAS dans le passe. "
                     "Tant qu elle n a pas plus de 5 epoques distinctes, elle n apporte "
                     "RIEN de plus que ce que le RPC donne deja. L epoque en cours n y "
                     "entre jamais : elle est incomplete par construction."),
        }
        with open(os.path.join(a.sortie, "historique.jsonl"), "a", encoding="utf-8") as f:
            leger = {k: v for k, v in e.items() if k not in ("degrades", "meilleurs", "detail_echecs")}
            leger["degrades_nombre"] = e["degrades"]["nombre"]
            leger["degrades_stake_sol"] = e["degrades"]["stake_concerne_sol"]
            f.write(json.dumps(leger, ensure_ascii=False) + "\n")
    with open(os.path.join(a.sortie, "etat.json"), "w", encoding="utf-8") as f:
        json.dump(e, f, ensure_ascii=False, indent=2)
    with open(os.path.join(a.sortie, "RAPPORT.md"), "w", encoding="utf-8") as f:
        f.write(rendre_markdown(e) + "\n")
    with open(os.path.join(a.sortie, "index.html"), "w", encoding="utf-8") as f:
        f.write(rendre_html(e))

    print("%s · contrôles %s/%s · %d appels, %d échec(s) · %s s"
          % ("🟢 COMPLET" if e["complet"] else "🔴 INCOMPLET",
             e.get("controles_passes", "—"), e.get("controles_total", "—"),
             e["appels_rpc"], e["echecs_rpc"], e["duree_s"]))
    if e["complet"]:
        r, d, ch = e["reseau"], e["degrades"], e.get("chronicite", {})
        print("   latence médiane %s slot sur %d validateurs" % (
            r["latence_implicite_mediane_slots"], e["validateurs_mesures"]))
        if ch.get("tranchable"):
            print("   🔴 CHRONIQUES : %d validateurs, %s SOL (%s %% du stake) — c'est LE chiffre à citer"
                  % (ch["chroniques"], nb(ch["stake_chronique_sol"], 0), ch["part_stake_chronique_pct"]))
            print("      intermittents %d (%s SOL) · accidentels %d (%s SOL) · sains %d"
                  % (ch["intermittents"], nb(ch["stake_intermittent_sol"], 0),
                     ch["accidentels"], nb(ch["stake_accidentel_sol"], 0), ch["sains"]))
            print("      (epoque en cours seule : %d degrades, %s SOL — trompeur, ne pas citer seul)"
                  % (d["nombre"], nb(d["stake_concerne_sol"], 0)))
        else:
            print("   🔴 chronique/accident NON TRANCHE : %s" % ch.get("motif_si_non"))
        print("   Alpenglow : %s" % e["alpenglow"]["verdict"])
    print("   écrit : %s" % a.sortie)
    return 0 if e["complet"] else 1


if __name__ == "__main__":
    sys.exit(main())
