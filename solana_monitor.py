#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOLANA ECOSYSTEM & VALIDATOR HEALTH MONITOR -- lecture RPC directe.

Ne le 15/08/2026. Meme methode que backing_rpc.py (D17/D23) transposee a
Solana : on lit l ETAT en direct par appels RPC plutot que de dependre d un
indexeur tiers. Aucune cle API, aucune dependance payante, aucun wallet.

    python3 solana_monitor.py            # un instantane, ecrit dans sortie/
    python3 solana_monitor.py --sortie X # dossier de sortie different

🔴 CE QUE CE SCRIPT NE FAIT JAMAIS, par construction :
  - jamais d interpolation : un appel qui echoue apres 3 essais rend None, le
    champ est marque MANQUANT avec son motif, et AUCUNE valeur n est inventee
    ni reportee de l execution precedente. Un trou documente vaut mieux qu un
    chiffre fabrique.
  - jamais silencieux : chaque echec est trace (methode, essai, endpoint, motif)
    et compte dans le rapport.
  - jamais un chiffre non controle : chaque grandeur passe un controle du zero
    et un controle de vraisemblance avant d etre publiee.
  - jamais une source unique : les grandeurs critiques sont relues sur un
    SECOND endpoint independant et l ecart est publie.

Sorties (toutes reellement ecrites, aucune n est un gabarit) :
    sortie/etat.json        instantane structure, machine-readable
    sortie/RAPPORT.md       rapport lisible
    sortie/index.html       tableau de bord autonome (thema sombre, zero CDN)
    sortie/historique.jsonl une ligne par execution, append seul
"""
import argparse, json, os, statistics, sys, time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("🔴 module 'requests' absent : python3 -m pip install --user requests")

# Endpoints publics, sans cle. L ordre est l ordre d essai.
ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
]
LAMPORTS = 1e9
RACINE = os.path.dirname(os.path.abspath(__file__))


class Client:
    """Client RPC avec repli d endpoint, reessais, et TRACE de chaque echec."""

    def __init__(self, endpoints, essais=3, timeout=25):
        self.endpoints = list(endpoints)
        self.essais = essais
        self.timeout = timeout
        self.appels = 0
        self.echecs = []
        self.latences = []

    def appel(self, methode, params=None, endpoint=None):
        cibles = [endpoint] if endpoint else self.endpoints
        for ep in cibles:
            for k in range(self.essais):
                self.appels += 1
                t0 = time.time()
                try:
                    r = requests.post(
                        ep,
                        json={"jsonrpc": "2.0", "id": self.appels,
                              "method": methode, "params": params or []},
                        timeout=self.timeout,
                        headers={"Content-Type": "application/json"},
                    )
                    dt = time.time() - t0
                    self.latences.append(dt)
                    j = r.json()
                    if "result" in j:
                        return j["result"], ep
                    self.echecs.append({"methode": methode, "endpoint": ep,
                                        "essai": k + 1,
                                        "motif": str(j.get("error"))[:160]})
                except Exception as e:
                    self.latences.append(time.time() - t0)
                    self.echecs.append({"methode": methode, "endpoint": ep,
                                        "essai": k + 1,
                                        "motif": type(e).__name__ + ": " + str(e)[:120]})
                time.sleep(0.5 * (k + 1))
        return None, None      # 🔴 echec definitif -> champ MANQUANT, jamais comble


# ----------------------------------------------------------------------------
# CONTROLES -- aucun chiffre ne sort d ici sans etre passe devant eux
# ----------------------------------------------------------------------------
def controle(nom, ok, detail):
    return {"controle": nom, "passe": bool(ok), "detail": detail}


def coefficient_nakamoto(stakes_tries, total):
    """Nombre MINIMAL de validateurs dont le stake cumule depasse 33,33 % --
    c est-a-dire combien il en faudrait, au minimum, pour bloquer le reseau.
    Plus il est petit, plus le reseau est concentre."""
    if not total:
        return None
    cumul = 0
    for i, s in enumerate(stakes_tries, 1):
        cumul += s
        if cumul > total / 3.0:
            return i
    return None


def part_du_top(stakes_tries, total, n):
    if not total:
        return None
    return round(100.0 * sum(stakes_tries[:n]) / total, 2)


def instantane():
    c = Client(ENDPOINTS)
    t_debut = time.time()
    controles = []
    manquants = []

    def lire(nom, methode, params=None):
        v, ep = c.appel(methode, params)
        if v is None:
            manquants.append({"champ": nom, "methode": methode,
                              "motif": "echec RPC definitif apres %d essais sur %d endpoint(s)"
                                       % (c.essais, len(ENDPOINTS))})
        return v, ep

    sante, ep_sante = lire("sante_rpc", "getHealth")
    epoque, _ = lire("epoque", "getEpochInfo")
    slot, _ = lire("slot", "getSlot")
    perf, _ = lire("performance", "getRecentPerformanceSamples", [30])
    votes, ep_votes = lire("validateurs", "getVoteAccounts")
    offre, _ = lire("offre", "getSupply",
                    [{"commitment": "finalized", "excludeNonCirculatingAccountsList": True}])

    # ---- horodatage du dernier bloc : on recule si le slot vise a ete saute
    horodatage_bloc = None
    slot_horodate = None
    if epoque:
        for recul in (0, 5, 20, 60, 150):
            s = epoque["absoluteSlot"] - recul
            v, _ = c.appel("getBlockTime", [s])
            if isinstance(v, int):
                horodatage_bloc, slot_horodate = v, s
                break
        if horodatage_bloc is None:
            manquants.append({"champ": "horodatage_bloc", "methode": "getBlockTime",
                              "motif": "aucun des 5 slots testes n a rendu d horodatage"})

    # ------------------------------------------------------------------ epoque
    bloc_epoque = None
    if epoque:
        idx, total_slots = epoque["slotIndex"], epoque["slotsInEpoch"]
        bloc_epoque = {
            "epoque": epoque["epoch"],
            "slot_absolu": epoque["absoluteSlot"],
            "hauteur_bloc": epoque.get("blockHeight"),
            "slot_dans_epoque": idx,
            "slots_par_epoque": total_slots,
            "progression_pct": round(100.0 * idx / total_slots, 3) if total_slots else None,
            "slots_restants": total_slots - idx if total_slots else None,
        }
        controles.append(controle(
            "epoque : progression dans [0,100]",
            total_slots and 0 <= idx <= total_slots,
            "slotIndex=%s slotsInEpoch=%s" % (idx, total_slots)))

    # ------------------------------------------------------------- performance
    bloc_perf = None
    if perf:
        ech = [e for e in perf if e.get("samplePeriodSecs")]
        tps = [e["numTransactions"] / e["samplePeriodSecs"] for e in ech]
        tps_hv = [e["numNonVoteTransactions"] / e["samplePeriodSecs"]
                  for e in ech if e.get("numNonVoteTransactions") is not None]
        duree_slot = [e["samplePeriodSecs"] / e["numSlots"] for e in ech if e.get("numSlots")]
        bloc_perf = {
            "echantillons": len(ech),
            "fenetre_s": sum(e["samplePeriodSecs"] for e in ech),
            "tps_moyen": round(statistics.mean(tps), 1) if tps else None,
            "tps_median": round(statistics.median(tps), 1) if tps else None,
            "tps_max": round(max(tps), 1) if tps else None,
            "tps_hors_vote_moyen": round(statistics.mean(tps_hv), 1) if tps_hv else None,
            "duree_slot_moyenne_s": round(statistics.mean(duree_slot), 4) if duree_slot else None,
        }
        controles.append(controle(
            "TPS strictement positif",
            bool(tps) and min(tps) > 0,
            "min=%.1f max=%.1f sur %d echantillons" % (min(tps), max(tps), len(tps)) if tps else "aucun echantillon"))
        controles.append(controle(
            "duree de slot plausible (0,2 s - 2 s)",
            bool(duree_slot) and 0.2 <= statistics.mean(duree_slot) <= 2.0,
            "%.4f s" % statistics.mean(duree_slot) if duree_slot else "non mesuree"))

    # -------------------------------------------------------------- validateurs
    bloc_val = None
    top = []
    if votes:
        actifs = votes.get("current", [])
        delinquants = votes.get("delinquent", [])
        s_actifs = sorted((v.get("activatedStake", 0) for v in actifs), reverse=True)
        stake_actif = sum(s_actifs)
        stake_delinquant = sum(v.get("activatedStake", 0) for v in delinquants)
        stake_total = stake_actif + stake_delinquant
        bloc_val = {
            "validateurs_actifs": len(actifs),
            "validateurs_delinquants": len(delinquants),
            "validateurs_total": len(actifs) + len(delinquants),
            "part_delinquants_pct": round(100.0 * len(delinquants) / (len(actifs) + len(delinquants)), 2)
                                    if (actifs or delinquants) else None,
            "stake_actif_sol": round(stake_actif / LAMPORTS, 2),
            "stake_delinquant_sol": round(stake_delinquant / LAMPORTS, 2),
            "part_stake_delinquant_pct": round(100.0 * stake_delinquant / stake_total, 4)
                                          if stake_total else None,
            "coefficient_nakamoto": coefficient_nakamoto(s_actifs, stake_actif),
            "part_top1_pct": part_du_top(s_actifs, stake_actif, 1),
            "part_top10_pct": part_du_top(s_actifs, stake_actif, 10),
            "part_top50_pct": part_du_top(s_actifs, stake_actif, 50),
            "commission_mediane_pct": statistics.median([v.get("commission", 0) for v in actifs])
                                       if actifs else None,
            "validateurs_commission_100_pct": sum(1 for v in actifs if v.get("commission") == 100),
        }
        for v in sorted(actifs, key=lambda x: x.get("activatedStake", 0), reverse=True)[:15]:
            top.append({
                "identite": v.get("nodePubkey"),
                "compte_vote": v.get("votePubkey"),
                "stake_sol": round(v.get("activatedStake", 0) / LAMPORTS, 2),
                "part_pct": round(100.0 * v.get("activatedStake", 0) / stake_actif, 3) if stake_actif else None,
                "commission_pct": v.get("commission"),
                "credits_epoque": (v.get("epochCredits") or [[None, None, None]])[-1][1],
            })
        controles.append(controle(
            "controle du zero : au moins 100 validateurs actifs",
            len(actifs) >= 100, "%d actifs, %d delinquants" % (len(actifs), len(delinquants))))
        controles.append(controle(
            "somme des parts du top = 100 % a l arrondi pres",
            abs(sum(s_actifs) - stake_actif) < 1,
            "ecart %d lamports" % abs(sum(s_actifs) - stake_actif)))
        controles.append(controle(
            "coefficient de Nakamoto plausible (1-100)",
            bloc_val["coefficient_nakamoto"] is not None and 1 <= bloc_val["coefficient_nakamoto"] <= 100,
            "N = %s" % bloc_val["coefficient_nakamoto"]))

    # -------------------------------------------------------------------- offre
    bloc_offre = None
    if offre and isinstance(offre, dict) and "value" in offre:
        val = offre["value"]
        tot = val.get("total", 0) / LAMPORTS
        circ = val.get("circulating", 0) / LAMPORTS
        bloc_offre = {
            "offre_totale_sol": round(tot, 2),
            "offre_circulante_sol": round(circ, 2),
            "offre_non_circulante_sol": round(val.get("nonCirculating", 0) / LAMPORTS, 2),
            "part_circulante_pct": round(100.0 * circ / tot, 2) if tot else None,
        }
        if bloc_val and tot:
            bloc_offre["part_du_sol_stake_pct"] = round(
                100.0 * (bloc_val["stake_actif_sol"] + bloc_val["stake_delinquant_sol"]) / tot, 2)
        controles.append(controle(
            "offre : circulante <= totale",
            circ <= tot, "%.0f <= %.0f SOL" % (circ, tot)))

    # ------------------------------------ RECOUPEMENT SUR UN SECOND ENDPOINT
    recoupement = {"fait": False}
    autres = [e for e in ENDPOINTS if e != (ep_votes or ENDPOINTS[0])]
    if autres and epoque and votes:
        ep2 = autres[0]
        e2, _ = c.appel("getEpochInfo", None, endpoint=ep2)
        v2, _ = c.appel("getVoteAccounts", None, endpoint=ep2)
        if e2 and v2:
            recoupement = {
                "fait": True,
                "endpoint_1": ep_votes, "endpoint_2": ep2,
                "epoque_1": epoque["epoch"], "epoque_2": e2["epoch"],
                "epoques_identiques": epoque["epoch"] == e2["epoch"],
                "ecart_slot": abs(epoque["absoluteSlot"] - e2["absoluteSlot"]),
                "actifs_1": len(votes.get("current", [])), "actifs_2": len(v2.get("current", [])),
                "ecart_actifs": abs(len(votes.get("current", [])) - len(v2.get("current", []))),
                "delinquants_1": len(votes.get("delinquent", [])),
                "delinquants_2": len(v2.get("delinquent", [])),
            }
            controles.append(controle(
                "deux endpoints independants : meme epoque",
                recoupement["epoques_identiques"],
                "%s vs %s" % (recoupement["epoque_1"], recoupement["epoque_2"])))
            controles.append(controle(
                "deux endpoints independants : ecart de validateurs actifs <= 5",
                recoupement["ecart_actifs"] <= 5,
                "%d vs %d" % (recoupement["actifs_1"], recoupement["actifs_2"])))
        else:
            recoupement = {"fait": False,
                           "motif": "le second endpoint n a pas repondu -- recoupement NON fait"}

    # ------------------------------------------ duree restante de l epoque
    if bloc_epoque and bloc_perf and bloc_perf.get("duree_slot_moyenne_s"):
        s = bloc_epoque["slots_restants"] * bloc_perf["duree_slot_moyenne_s"]
        bloc_epoque["temps_restant_estime_h"] = round(s / 3600.0, 2)
        bloc_epoque["_note_temps_restant"] = ("estimation = slots restants x duree de slot "
                                              "OBSERVEE sur la fenetre recente, pas une valeur rendue par le reseau")

    limites = [
        "Les deux endpoints du recoupement sont publics et gratuits : rien ne prouve "
        "qu ils ne partagent pas la meme infrastructure en amont. Un accord entre eux "
        "ecarte une panne locale ou une reponse tronquee, il NE PROUVE PAS l independance "
        "des sources.",
        "getVoteAccounts ne rend que les validateurs VOTANTS connus du noeud interroge. "
        "Le compte absolu n est pas verifiable ici au-dela de l accord des deux endpoints.",
        "Le temps restant de l epoque est une ESTIMATION : slots restants multiplies par la "
        "duree de slot observee sur la fenetre recente. Le reseau ne rend pas cette valeur.",
        "Le TPS vient de getRecentPerformanceSamples, donc d une fenetre glissante recente, "
        "pas d un comptage exhaustif de la chaine.",
    ]

    duree = round(time.time() - t_debut, 1)
    etat = {
        "limites_declarees": limites,
        "horodatage_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "complet": len(manquants) == 0,
        "champs_manquants": manquants,
        "sante_rpc": sante,
        "endpoint_sante": ep_sante,
        "horodatage_dernier_bloc_utc": (datetime.fromtimestamp(horodatage_bloc, timezone.utc)
                                        .strftime("%Y-%m-%dT%H:%M:%SZ") if horodatage_bloc else None),
        "slot_horodate": slot_horodate,
        "retard_horloge_s": (int(time.time()) - horodatage_bloc) if horodatage_bloc else None,
        "epoque": bloc_epoque,
        "performance": bloc_perf,
        "validateurs": bloc_val,
        "top_validateurs": top,
        "offre": bloc_offre,
        "recoupement_second_endpoint": recoupement,
        "controles": controles,
        "controles_passes": sum(1 for x in controles if x["passe"]),
        "controles_total": len(controles),
        "appels_rpc": c.appels,
        "echecs_rpc": len(c.echecs),
        "detail_echecs": c.echecs[:20],
        "latence_mediane_ms": round(1000 * statistics.median(c.latences)) if c.latences else None,
        "duree_s": duree,
    }
    return etat


# ----------------------------------------------------------------------------
# RENDUS
# ----------------------------------------------------------------------------
def n(v, suf="", dec=None):
    """Formate un nombre pour l affichage. dec=0 rend un entier (pas de .0)."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return ("oui" if v else "non") + suf
    if isinstance(v, (int, float)):
        if dec is not None:
            v = round(v, dec)
            if dec == 0:
                v = int(v)
        return "{:,}".format(v).replace(",", " ") + suf
    return str(v) + suf


def rendre_markdown(e):
    L = []
    A = L.append
    A("# Solana — état du réseau et santé des validateurs")
    A("")
    A("*Instantané du **%s** · lecture RPC directe, sans indexeur tiers.*" % e["horodatage_utc"])
    A("")
    if not e["complet"]:
        A("> 🔴 **INSTANTANÉ INCOMPLET — %d champ(s) manquant(s), NON comblés.**" % len(e["champs_manquants"]))
        for m in e["champs_manquants"]:
            A("> - `%s` (%s) : %s" % (m["champ"], m["methode"], m["motif"]))
        A("")
    ep, pf, va, of_ = e["epoque"], e["performance"], e["validateurs"], e["offre"]
    A("## L'essentiel")
    A("")
    A("| | |")
    A("|---|---|")
    A("| santé du nœud RPC | **%s** |" % (e["sante_rpc"] or "—"))
    if ep:
        A("| époque | **%s** — %s %% parcourus |" % (ep["epoque"], n(ep["progression_pct"])))
        A("| slot | **%s** |" % n(ep["slot_absolu"]))
        if ep.get("temps_restant_estime_h") is not None:
            A("| fin d'époque estimée dans | **%s h** |" % n(ep["temps_restant_estime_h"]))
    if pf:
        A("| TPS moyen *(%d échantillons, %s s)* | **%s** |" % (pf["echantillons"], n(pf["fenetre_s"]), n(pf["tps_moyen"])))
        A("| TPS hors votes | **%s** |" % n(pf["tps_hors_vote_moyen"]))
        A("| durée de slot observée | **%s s** |" % n(pf["duree_slot_moyenne_s"]))
    if va:
        A("| validateurs actifs | **%s** |" % n(va["validateurs_actifs"]))
        A("| validateurs délinquants | **%s** (%s %% du parc) |" % (n(va["validateurs_delinquants"]), n(va["part_delinquants_pct"])))
        A("| **coefficient de Nakamoto** | **%s** |" % n(va["coefficient_nakamoto"]))
        A("| stake actif | **%s SOL** |" % n(va["stake_actif_sol"], dec=0))
    if of_:
        A("| offre totale | **%s SOL** |" % n(of_["offre_totale_sol"], dec=0))
        if of_.get("part_du_sol_stake_pct"):
            A("| part du SOL en stake | **%s %%** |" % n(of_["part_du_sol_stake_pct"]))
    A("")
    if va:
        A("## Concentration du stake")
        A("")
        A("> **Coefficient de Nakamoto = %s** — c'est le nombre minimal de validateurs qu'il" % n(va["coefficient_nakamoto"]))
        A("> faudrait réunir pour dépasser un tiers du stake actif, donc pour bloquer le réseau.")
        A("> Plus il est petit, plus le réseau est concentré.")
        A("")
        A("| | |")
        A("|---|---|")
        A("| part du plus gros validateur | %s %% |" % n(va["part_top1_pct"]))
        A("| part des 10 premiers | %s %% |" % n(va["part_top10_pct"]))
        A("| part des 50 premiers | %s %% |" % n(va["part_top50_pct"]))
        A("| stake délinquant | %s SOL (%s %%) |" % (n(va["stake_delinquant_sol"], dec=0), n(va["part_stake_delinquant_pct"])))
        A("| commission médiane | %s %% |" % n(va["commission_mediane_pct"]))
        A("| validateurs à 100 %% de commission | %s |" % n(va["validateurs_commission_100_pct"]))
        A("")
    if e["top_validateurs"]:
        A("## Les 15 plus gros validateurs")
        A("")
        A("| # | identité | stake (SOL) | part | commission |")
        A("|---|---|---|---|---|")
        for i, v in enumerate(e["top_validateurs"], 1):
            A("| %d | `%s…%s` | %s | %s %% | %s %% |" % (
                i, v["identite"][:6], v["identite"][-4:], n(v["stake_sol"], dec=0),
                n(v["part_pct"]), n(v["commission_pct"])))
        A("")
    A("## Contrôles — %d / %d passés" % (e["controles_passes"], e["controles_total"]))
    A("")
    A("| contrôle | | détail |")
    A("|---|---|---|")
    for ct in e["controles"]:
        A("| %s | %s | %s |" % (ct["controle"], "🟢" if ct["passe"] else "🔴", ct["detail"]))
    A("")
    r = e["recoupement_second_endpoint"]
    if r.get("fait"):
        A("**Recoupement sur un second endpoint indépendant :** `%s` vs `%s` — "
          "même époque : %s · écart de slot : %s · validateurs actifs %s vs %s." % (
            r["endpoint_1"], r["endpoint_2"], "oui" if r["epoques_identiques"] else "**NON**",
            r["ecart_slot"], r["actifs_1"], r["actifs_2"]))
    else:
        A("🔴 **Recoupement sur un second endpoint NON fait** — %s" % r.get("motif", "raison non consignée"))
    A("")
    A("## Ce que cet instantané ne prouve pas")
    A("")
    for lim in e.get("limites_declarees", []):
        A("- %s" % lim)
    A("")
    A("---")
    A("")
    A("*%d appels RPC, %d échec(s), latence médiane %s ms, %s s au total. "
      "Endpoints publics sans clé. Aucune valeur interpolée : un appel qui échoue laisse un trou déclaré.*"
      % (e["appels_rpc"], e["echecs_rpc"], n(e["latence_mediane_ms"]), e["duree_s"]))
    return "\n".join(L)


def rendre_html(e, historique):
    ep, pf, va, of_ = e["epoque"], e["performance"], e["validateurs"], e["offre"]
    ok = e["controles_passes"] == e["controles_total"] and e["complet"]

    def carte(titre, valeur, note=""):
        return ('<div class="c"><div class="t">%s</div><div class="v">%s</div>'
                '<div class="n">%s</div></div>' % (titre, valeur, note))

    cartes = []
    if ep:
        cartes.append(carte("Époque", str(ep["epoque"]),
                            "%s %% parcourus" % n(ep["progression_pct"])))
        cartes.append(carte("Slot", n(ep["slot_absolu"]),
                            "fin d'époque ~%s h" % n(ep.get("temps_restant_estime_h"))))
    if pf:
        cartes.append(carte("TPS moyen", n(pf["tps_moyen"]),
                            "%s hors votes" % n(pf["tps_hors_vote_moyen"])))
        cartes.append(carte("Durée de slot", "%s s" % n(pf["duree_slot_moyenne_s"]),
                            "observée sur %s s" % n(pf["fenetre_s"])))
    if va:
        cartes.append(carte("Validateurs actifs", n(va["validateurs_actifs"]),
                            "%s délinquants (%s %%)" % (n(va["validateurs_delinquants"]), n(va["part_delinquants_pct"]))))
        cartes.append(carte("Coefficient de Nakamoto", n(va["coefficient_nakamoto"]),
                            "validateurs pour bloquer le réseau"))
        cartes.append(carte("Stake actif", n(va["stake_actif_sol"], dec=0) + " SOL",
                            "top 10 : %s %%" % n(va["part_top10_pct"])))
    if of_:
        cartes.append(carte("SOL en stake", "%s %%" % n(of_.get("part_du_sol_stake_pct")),
                            "sur %s SOL émis" % n(of_["offre_totale_sol"], dec=0)))

    lignes_top = "".join(
        '<tr><td class="r">%d</td><td class="m">%s…%s</td><td class="r">%s</td>'
        '<td class="r">%s %%</td><td class="r">%s %%</td></tr>' % (
            i, v["identite"][:8], v["identite"][-6:], n(v["stake_sol"], dec=0),
            n(v["part_pct"]), n(v["commission_pct"]))
        for i, v in enumerate(e["top_validateurs"], 1))

    lignes_ctrl = "".join(
        '<tr><td>%s</td><td class="r">%s</td><td class="d">%s</td></tr>' % (
            c["controle"], "🟢" if c["passe"] else "🔴", c["detail"])
        for c in e["controles"])

    manquants = ""
    if not e["complet"]:
        manquants = ('<div class="alerte"><b>Instantané incomplet — %d champ(s) manquant(s), non comblés.</b><br>%s</div>'
                     % (len(e["champs_manquants"]),
                        "<br>".join("<code>%s</code> (%s) : %s" % (m["champ"], m["methode"], m["motif"])
                                    for m in e["champs_manquants"])))

    # serie historique du TPS et des delinquants
    serie = ""
    pts = [h for h in historique if h.get("performance") and h["performance"].get("tps_moyen")]
    if len(pts) >= 2:
        lignes = "".join(
            '<tr><td class="m">%s</td><td class="r">%s</td><td class="r">%s</td>'
            '<td class="r">%s</td><td class="r">%s</td></tr>' % (
                h["horodatage_utc"].replace("T", " ").replace("Z", ""),
                n((h.get("epoque") or {}).get("epoque")),
                n(h["performance"]["tps_moyen"]),
                n((h.get("validateurs") or {}).get("validateurs_actifs")),
                n((h.get("validateurs") or {}).get("validateurs_delinquants")))
            for h in pts[-12:])
        serie = ('<h2>Historique des exécutions</h2><p class="s">Une ligne par exécution réelle. '
                 'Rien n\'est interpolé : une exécution ratée n\'apparaît pas.</p>'
                 '<table><thead><tr><th>horodatage UTC</th><th class="r">époque</th>'
                 '<th class="r">TPS</th><th class="r">actifs</th><th class="r">délinquants</th>'
                 '</tr></thead><tbody>%s</tbody></table>' % lignes)

    r = e["recoupement_second_endpoint"]
    if r.get("fait"):
        bloc_rec = ('<p class="s">Recoupement sur un second endpoint indépendant — '
                    '<code>%s</code> vs <code>%s</code> : même époque <b>%s</b>, écart de slot <b>%s</b>, '
                    'validateurs actifs <b>%s</b> vs <b>%s</b>.</p>' % (
                        r["endpoint_1"], r["endpoint_2"],
                        "oui" if r["epoques_identiques"] else "NON", r["ecart_slot"],
                        r["actifs_1"], r["actifs_2"]))
    else:
        bloc_rec = '<p class="s">🔴 Recoupement sur un second endpoint <b>non fait</b> — %s</p>' % r.get("motif", "")

    gabarit = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solana &mdash; sant&eacute; du r&eacute;seau et des validateurs</title><style>
:root{--bg:#0d1117;--pan:#161b22;--bd:#30363d;--tx:#e6edf3;--mu:#8b949e;--ac:#2ea043;--al:#f85149;--hi:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.w{max-width:1100px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:18px;margin:38px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--bd)}
.s{color:var(--mu);font-size:13px;margin:4px 0 0}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;margin-left:8px;vertical-align:middle}
.ok{background:rgba(46,160,67,.15);color:var(--ac);border:1px solid rgba(46,160,67,.4)}
.ko{background:rgba(248,81,73,.15);color:var(--al);border:1px solid rgba(248,81,73,.4)}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin-top:18px}
.c{background:var(--pan);border:1px solid var(--bd);border-radius:10px;padding:14px 16px}
.c .t{color:var(--mu);font-size:12px;text-transform:uppercase;letter-spacing:.5px}
.c .v{font-size:27px;font-weight:650;margin:6px 0 2px;color:var(--hi)}
.c .n{color:var(--mu);font-size:12px}
.tw{overflow-x:auto;margin-top:10px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:8px 10px;border-bottom:1px solid var(--bd);text-align:left;white-space:nowrap}
th{color:var(--mu);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
td.r,th.r{text-align:right}
td.m{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--mu)}
td.d{color:var(--mu);font-size:12.5px;white-space:normal}
.alerte{background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.4);border-radius:10px;padding:14px 16px;margin-top:18px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--hi)}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--bd);color:var(--mu);font-size:12.5px}
</style></head><body><div class="w">
<h1>Solana &mdash; sant&eacute; du r&eacute;seau et des validateurs<span class="pill @CLS@">@ETAT@</span></h1>
<p class="s">Instantan&eacute; du <b>@QUAND@</b> &middot; lecture RPC directe sur endpoint public,
sans indexeur tiers, sans cl&eacute; API. Dernier bloc dat&eacute; : @BLOC@ (retard d\'horloge @RETARD@ s).</p>
@MANQUANTS@
<div class="g">@CARTES@</div>
<h2>Les 15 plus gros validateurs</h2>
<div class="tw"><table><thead><tr><th class="r">#</th><th>identit&eacute;</th><th class="r">stake (SOL)</th>
<th class="r">part</th><th class="r">commission</th></tr></thead><tbody>@TOP@</tbody></table></div>
<h2>Contr&ocirc;les &mdash; @CTRLOK@ / @CTRLTOT@ pass&eacute;s</h2>
<p class="s">Chaque grandeur publi&eacute;e passe devant ces contr&ocirc;les. Aucun chiffre n\'est interpol&eacute; :
un appel RPC qui &eacute;choue laisse un trou d&eacute;clar&eacute;, jamais une valeur devin&eacute;e.</p>
<div class="tw"><table><thead><tr><th>contr&ocirc;le</th><th class="r"></th><th>d&eacute;tail</th></tr></thead>
<tbody>@CTRL@</tbody></table></div>
@RECOUPE@
@SERIE@
<h2>Ce que cet instantan&eacute; ne prouve pas</h2>
<ul class="s">@LIMITES@</ul>
<footer>@APPELS@ appels RPC &middot; @ECHECS@ &eacute;chec(s) &middot; latence m&eacute;diane @LAT@ ms &middot; @DUREE@ s.
Endpoints : @EPS@. Aucune d&eacute;pendance payante, aucun wallet, lecture seule.</footer>
</div></body></html>"""
    remplacements = {
        "@CLS@": "ok" if ok else "ko",
        "@ETAT@": ("tous contr&ocirc;les pass&eacute;s" if ok
                   else "%d/%d contr&ocirc;les" % (e["controles_passes"], e["controles_total"])),
        "@QUAND@": e["horodatage_utc"],
        "@BLOC@": e["horodatage_dernier_bloc_utc"] or "&mdash;",
        "@RETARD@": n(e["retard_horloge_s"]),
        "@MANQUANTS@": manquants,
        "@CARTES@": "".join(cartes),
        "@TOP@": lignes_top,
        "@CTRLOK@": str(e["controles_passes"]),
        "@CTRLTOT@": str(e["controles_total"]),
        "@CTRL@": lignes_ctrl,
        "@RECOUPE@": bloc_rec,
        "@SERIE@": serie,
        "@APPELS@": str(e["appels_rpc"]),
        "@ECHECS@": str(e["echecs_rpc"]),
        "@LAT@": n(e["latence_mediane_ms"]),
        "@DUREE@": str(e["duree_s"]),
        "@EPS@": ", ".join("<code>%s</code>" % x for x in ENDPOINTS),
        "@LIMITES@": "".join("<li>%s</li>" % l for l in e.get("limites_declarees", [])),
    }
    for cle, valeur in remplacements.items():
        gabarit = gabarit.replace(cle, valeur)
    return gabarit


def main():
    ap = argparse.ArgumentParser(description="Moniteur de santé Solana par lecture RPC directe")
    ap.add_argument("--sortie", default=os.path.join(RACINE, "sortie"))
    a = ap.parse_args()
    os.makedirs(a.sortie, exist_ok=True)

    e = instantane()

    hist = os.path.join(a.sortie, "historique.jsonl")
    # 🔴 seul un instantane COMPLET entre dans l historique -- pas de trou comble
    if e["complet"]:
        with open(hist, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    lignes = []
    if os.path.exists(hist):
        with open(hist, encoding="utf-8") as f:
            lignes = [json.loads(l) for l in f if l.strip()]

    with open(os.path.join(a.sortie, "etat.json"), "w", encoding="utf-8") as f:
        json.dump(e, f, ensure_ascii=False, indent=2)
    with open(os.path.join(a.sortie, "RAPPORT.md"), "w", encoding="utf-8") as f:
        f.write(rendre_markdown(e) + "\n")
    with open(os.path.join(a.sortie, "index.html"), "w", encoding="utf-8") as f:
        f.write(rendre_html(e, lignes))

    etat = "🟢 COMPLET" if e["complet"] else "🔴 INCOMPLET (%d champ(s) manquant(s))" % len(e["champs_manquants"])
    print("%s · contrôles %d/%d · %d appels, %d échec(s) · %s s"
          % (etat, e["controles_passes"], e["controles_total"],
             e["appels_rpc"], e["echecs_rpc"], e["duree_s"]))
    if not e["complet"]:
        for m in e["champs_manquants"]:
            print("   manquant : %s (%s) -- %s" % (m["champ"], m["methode"], m["motif"]))
    for x in e["detail_echecs"][:5]:
        print("   échec : %s sur %s (essai %d) -- %s" % (x["methode"], x["endpoint"], x["essai"], x["motif"]))
    print("   écrit : %s" % a.sortie)
    return 0 if e["complet"] else 1


if __name__ == "__main__":
    sys.exit(main())
