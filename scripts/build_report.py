"""Construit le rapport Go/NoGo (.docx) à partir du canevas fourni. Deux passes : la 2e injecte les numéros de page
(table des matières et listes) calculés sur le PDF de la 1re. Usage : python scripts/build_report.py <pages.json|-> <sortie.docx>"""
import copy
import csv
import json
import re
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = "/mnt/user-data/attachments/ac42533e-20ce-5987-864b-7e61a38c27ab/a2cc0ab7-Canevas-Rapport.docx"
FIG = ROOT / "docs/figures"
NAVY = "1F3A5F"

cal = json.loads((ROOT / "data/generated/calibration_report.json").read_text(encoding="utf-8"))
gen = json.loads((ROOT / "data/generated/genericity_test.json").read_text(encoding="utf-8"))
chal = json.loads((ROOT / "data/generated/go_nogo_challenge/challenge_results.json").read_text(encoding="utf-8"))
val_rows = list(csv.DictReader(open(ROOT / "journals/journal_validation.csv", encoding="utf-8")))
M = cal["seuils_config_actuels"]["metrics"]
CP = cal["cross_profile"]

pages = {}
if sys.argv[1] != "-":
    pages = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
OUT = sys.argv[2]

d = docx.Document(TEMPLATE)
body = d.element.body
children = list(body)
cover = children[0]
sect = children[-1]
for el in children[1:-1]:
    body.remove(el)


# ---------------------------------------------------------------- page de garde
def set_text(p, text):
    runs = p.findall(qn("w:r"))
    first = True
    for r in runs:
        t = r.find(qn("w:t"))
        if t is None:
            continue
        if first:
            t.text = text
            first = False
        else:
            t.text = ""

ps = list(cover.iter(qn("w:p")))
set_text(ps[3], "5ème année – Cybersécurité")
set_text(ps[4], "Rapport de Projet 3pH « PIC »")
set_text(ps[5], "Sujet : ")
r7 = ps[7].findall(qn("w:r"))
r7[0].find(qn("w:t")).text = "Threat Hunting à l’échelle africaine, modèle multi-sources augmenté par l’IA. "
r7[1].find(qn("w:t")).text = "Dossier Go/noGo"
set_text(ps[16], "")
set_text(ps[17], "Wassim Nafid")
set_text(ps[18], "Encadrant : [à compléter]")
set_text(ps[19], "[Membres à compléter]")
set_text(ps[20], "")
set_text(ps[21], "[Chef de projet]")
set_text(ps[23], "")
for k in (8, 10, 11, 12, 13, 14, 22, 24, 25, 26):   # paragraphes vides : on resserre la page de garde pour tenir sur une page
    pp = ps[k]
    if not "".join(t.text or "" for t in pp.iter(qn("w:t"))).strip() and pp.getparent() is not None and not list(pp.iter(qn("w:drawing"))) and not list(pp.iter(qn("w:pict"))):
        pp.getparent().remove(pp)

for sec in d.sections:
    for part in (sec.footer, sec.first_page_footer, sec.header, sec.first_page_header):
        for t in part._element.iter(qn("w:t")):
            if t.text and "2024" in t.text: t.text = t.text.replace("2024", "2026")
            if t.text and "2025" in t.text: t.text = t.text.replace("2025", "2027")
for t in cover.iter(qn("w:t")):
    if t.text and "2024" in t.text:
        t.text = t.text.replace("2024", "2026")
    elif t.text and "2025" in t.text:
        t.text = t.text.replace("2025", "2027")

# ---------------------------------------------------------------- aides de mise en forme
def new_p(style=None, align=None):
    p = d.add_paragraph(style=style)
    body.remove(p._p)
    body.insert(len(body) - 1, p._p)
    if align:
        p.alignment = align
    return p


def runs(p, text, size=None, color=None, mono=False):
    for i, seg in enumerate(re.split(r"(\*\*.+?\*\*|`.+?`)", text)):
        if not seg:
            continue
        if seg.startswith("**"):
            r = p.add_run(seg[2:-2]); r.bold = True
        elif seg.startswith("`"):
            r = p.add_run(seg[1:-1]); r.font.name = "Consolas"; r.font.size = Pt((size or 11) - 1.5)
        else:
            r = p.add_run(seg)
        if size and not seg.startswith("`"):
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
        if mono:
            r.font.name = "Consolas"
    return p


def H(level, text):
    p = new_p(f"Heading {level}")
    p.add_run(text)
    return p


def P(text, after=6, justify=True):
    p = new_p("Normal")
    runs(p, text)
    p.paragraph_format.space_after = Pt(after)
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def B(items, style_marker="•"):
    for it in items:
        p = new_p("Normal")
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.45)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        runs(p, f"{style_marker}  " + it)
    new_p("Normal").paragraph_format.space_after = Pt(2)


def pagebreak():
    p = new_p("Normal")
    p.add_run().add_break(WD_BREAK.PAGE)


def shade(cell, hex_):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_)
    tcPr.append(sh)


captions = {"fig": [], "tab": []}


def caption(kind, text):
    label = "Figure" if kind == "fig" else "Table"
    n = len(captions[kind]) + 1
    captions[kind].append(f"{label} {n}. {text}")
    p = new_p("Caption", align=WD_ALIGN_PARAGRAPH.CENTER)
    r = p.add_run(f"{label} {n}. {text}")
    p.paragraph_format.keep_with_next = kind == "tab"
    return p


def T(headers, rows, widths, title, size=8.5, first_bold=False):
    caption("tab", title)
    t = d.add_table(rows=1, cols=len(headers))
    body.remove(t._tbl); body.insert(len(body) - 1, t._tbl)
    t.style = "Table Grid"
    t.autofit = False
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.width = Cm(widths[i]); shade(c, NAVY)
        c.paragraphs[0].text = ""
        r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(size); r.font.color.rgb = RGBColor(255, 255, 255)
    trPr = t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); trPr.append(th)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].width = Cm(widths[i])
            p = cells[i].paragraphs[0]
            runs(p, str(v), size=size)
            p.paragraph_format.space_after = Pt(0)
            if first_bold and i == 0:
                for r in p.runs: r.bold = True
            if ri % 2 == 1:
                shade(cells[i], "EEF2F7")
        cs = t.rows[-1]._tr.get_or_add_trPr(); cs.append(OxmlElement("w:cantSplit"))
    if len(rows) <= 8:
        for row in t.rows[:-1]:
            for c in row.cells:
                for pp in c.paragraphs:
                    pp.paragraph_format.keep_with_next = True
    new_p("Normal").paragraph_format.space_after = Pt(4)
    return t


def FIGURE(name, title, width=15.5):
    p = new_p("Normal", align=WD_ALIGN_PARAGRAPH.CENTER)
    p.add_run().add_picture(str(FIG / name), width=Cm(width))
    p.paragraph_format.keep_with_next = True
    caption("fig", title)


def CALLOUT(text, color="FFF4DC"):
    t = d.add_table(rows=1, cols=1)
    body.remove(t._tbl); body.insert(len(body) - 1, t._tbl)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]; shade(c, color)
    c.paragraphs[0].text = ""
    runs(c.paragraphs[0], text, size=10)
    new_p("Normal").paragraph_format.space_after = Pt(4)


def CODE(lines):
    for ln in lines:
        p = new_p("Normal")
        r = p.add_run(ln); r.font.name = "Consolas"; r.font.size = Pt(8)
        p.paragraph_format.space_after = Pt(0); p.paragraph_format.left_indent = Cm(0.6)
    new_p("Normal").paragraph_format.space_after = Pt(4)


headings = []  # (niveau, texte)


def HH(level, text):
    headings.append((level, text))
    return H(level, text)

# ================================================================ CONTENU
# --- listes (placeholder remplacé ensuite) : on réserve la place après la page de garde
marker_front = new_p("Normal")  # sera remplacé par TOC + listes

pagebreak()
HH(1, "Introduction")
P("Ce document est le dossier remis pour la **séance de suivi n°1 (Go/noGo)** du projet 3pH « Threat Hunting à l’échelle africaine : modèle multi-sources augmenté par l’IA, applicable à toute entreprise » (PIC, 5ème année, S9). Il présente l’état réel du projet : ce qui est **réalisé et testé**, ce qui est **rédigé mais non déployé**, et ce qui **reste à faire**. Il suit la liste de revue de la séance 2 : planification, architecture, pipeline de collecte, journal de collecte dark web, profils et données des entreprises fictives, choix des modèles d’IA, défi Go/noGo et premier test de généricité.")
P("Le contexte est celui d’un consulting auprès d’un groupement d’entreprises africaines de secteurs différents, exposées à des menaces qui visent le continent (phishing et BEC, rançongiciels, fraude mobile money et SIM swap, revente de données, hacktivisme) mais qui disposent de peu de renseignement adapté à leur contexte. Notre réponse est un modèle de chasse **piloté par un profil d’entreprise** : changer d’entreprise revient à changer un fichier de configuration, pas le code.")
CALLOUT("**Lecture du statut.** Trois niveaux sont utilisés tout au long du rapport. **Réalisé** : code ou donnée produit et vérifié par des tests exécutés (31 tests automatisés passent). **Rédigé** : fichier écrit mais jamais exécuté dans l’environnement cible (stack Docker, règles Wazuh) faute de laboratoire à ce stade. **À faire** : non commencé. Aucune fonctionnalité « en cours » n’est présentée comme acquise.")
P("Le plan est le suivant : le chapitre 1 fixe le cadre éthique et légal ; le chapitre 2 cartographie la menace africaine pour les deux secteurs retenus ; le chapitre 3 décrit l’architecture et les choix d’outils et d’IA ; le chapitre 4 présente les profils et le premier test de généricité ; le chapitre 5 traite du pipeline de collecte, de la cotation et du TLP ; le chapitre 6 du scoring ; le chapitre 7 du défi Go/noGo ; le chapitre 8 de la planification ; le chapitre 9 de l’état d’avancement, des risques et de l’auto-évaluation.")

pagebreak()
HH(1, "Cadre éthique, légal et règles du projet")
HH(2, "Règles d’usage du dark web")
P("Le dark web n’est utilisé qu’en **observation passive**, depuis la VM de collecte isolée (Whonix), pour les seuls besoins du projet. Sont interdits : tout compte, toute interaction, tout achat, tout téléchargement de données volées, toute navigation à titre personnel. Toute collecte directe est validée au préalable par l’encadrant et consignée dans un journal horodaté. Tout contenu illicite rencontré entraîne l’arrêt immédiat et un signalement à l’encadrant. Toute violation est éliminatoire.")
P("**État à ce jour : aucune session de collecte directe n’a eu lieu.** Le journal de collecte (`journals/journal_collecte_darkweb.csv`) ne contient donc que son en-tête. Les informations « dark web » utilisées dans ce dossier sont des informations **secondaires**, issues de rapports publics (INTERPOL, CybelAngel) ; elles sont marquées comme telles. La première session directe n’aura lieu qu’après validation écrite de l’encadrant.")
HH(2, "Cadre légal applicable")
T(["Pays", "Textes à respecter", "Autorité"],
  [["Maroc (Zellige Bank)", "Loi 05-20 (cybersécurité) ; loi 09-08 (protection des données personnelles) ; loi 07-03 (atteintes aux systèmes de traitement automatisé de données)", "DGSSI, maCERT, CNDP"],
   ["Côte d’Ivoire (Harmattan Télécom)", "Loi n° 2013-451 (lutte contre la cybercriminalité) ; loi n° 2013-450 (données à caractère personnel)", "ARTCI, CI-CERT"],
   ["Kenya (profil de test)", "Computer Misuse and Cybercrimes Act 2018 ; Data Protection Act 2019", "ODPC, KE-CIRT/CC"]],
  [3.6, 9.2, 3.6], "Textes de référence par pays (à faire confirmer avec l’encadrant)")
P("Les lois 09-08 et 05-20 sont imposées par la fiche de projet ; les textes ivoiriens et kényans ont été relevés en ligne (Conseil de l’Europe, INTERPOL) et doivent être confirmés avec l’encadrant avant toute utilisation juridique. Nous ne sommes pas juristes : ce tableau est une aide à la conformité, pas un avis.")
HH(2, "Données et garde-fous techniques")
B(["**Aucune donnée personnelle réelle.** Les deux entreprises sont fictives ; leurs domaines sont en `.example` (RFC 2606), jamais résolus sur Internet. Un test automatique refuse tout profil dont un domaine n’est pas en `.example`.",
   "**Jeu de fuite simulé.** Les comptes `prenom.nom@<domaine>.example` et leurs « hachages » sont aléatoires ; chaque ligne porte `synthetic=true`.",
   "**Registre de sources.** `config/sources.yaml` liste neuf sources ; aucune n’est marquée validée, et le code refuse (exception avant toute requête réseau) de collecter une source non validée, un canal Telegram absent de la liste validée, ou tout accès Tor hors procédure.",
   "**Journal à validation obligatoire.** La fonction d’écriture du journal de collecte lève une erreur si la validation de l’encadrant n’est pas renseignée.",
   "**IA locale.** Aucun modèle n’appelle de service externe ; toute sortie de l’IA est une hypothèse « candidate » validée par un analyste."])

pagebreak()
HH(1, "Cartographie de la menace africaine")
P("Cette cartographie sert à choisir les deux secteurs et à pondérer les techniques ATT&CK des modules sectoriels. Les chiffres cités proviennent des rapports publics indiqués ; ils ont été relevés en ligne et **doivent être revérifiés dans le document d’origine avant la présentation orale** (les numéros de page sont indicatifs).")
HH(2, "Panorama continental")
B(["**Phishing et BEC.** Le phishing représente environ un tiers des incidents détectés en Afrique (34 %, [1]). La finance est le secteur le plus visé par la BEC en 2024 ; l’activité BEC d’origine africaine est concentrée dans un petit nombre de pays dont le Nigeria, le Ghana, la Côte d’Ivoire et l’Afrique du Sud, et des réseaux structurés comme Black Axe y sont associés [1].",
   "**Rançongiciels.** Parmi les vecteurs d’attaque cités par un acteur du paiement, les rançongiciels pèsent 28 % [2]. Des télécoms ont été touchés : Telecom Namibia (Hunters International, décembre 2024) [1] et un opérateur lié à Akira [2].",
   "**Fraude mobile money et SIM swap.** Elle est signalée par 97 % des pays répondants ; au Kenya, le SIM swap a progressé de 327 % en 2025 (plus de 123 000 SIM frauduleuses, environ 3,8 M USD vidés) [2].",
   "**DDoS et vulnérabilités.** Le Kenya a subi plus de 46 786 attaques DDoS au premier semestre 2025, surtout contre les télécoms ; l’Éthiopie se classe 5ème du continent pour les vulnérabilités détectées [2].",
   "**Dark web.** Les contenus d’origine africaine sur les forums ont augmenté de 62 % sur un an (données S2W citées par INTERPOL) : documents d’identité, PIN de SIM, identifiants bancaires, données mobile money [2].",
   "**Hacktivisme en Afrique du Nord.** La fuite de la CNSS marocaine, revendiquée sur Telegram le 8 avril 2025, a été republiée sur des forums ; plus de 5 To de données ont été publiés entre avril et juin 2025 (1,61 To sur toute l’année 2024), et les revendications visant des actifs marocains sont passées de 63 à 88 en environ deux mois et demi [3]."])
HH(2, "Pourquoi une banque marocaine et un opérateur ivoirien")
P("Les deux secteurs ont des menaces dominantes différentes, ce qui rend le test de généricité significatif. Une **banque au Maroc** est exposée à la fraude financière (T1657), à la BEC, aux fuites et DDoS hacktivistes régionaux et aux rançongiciels. Un **opérateur mobile en Côte d’Ivoire** est exposé au SIM swap par ingénierie sociale des agents (T1656), à la fraude mobile money, à l’exfiltration de bases d’abonnés et aux DDoS. Les langues (français, arabe, anglais) et les cadres légaux diffèrent aussi.")
HH(2, "Acteurs, campagnes et TTP retenus")
T(["Entreprise", "Acteur / campagne (source)", "TTP ATT&CK principales"],
  [["Zellige Bank (banque, MA)", "Collectifs hacktivistes régionaux : fuites + DDoS (CybelAngel 2025) ; affiliés rançongiciel opportunistes (Qilin, Akira, Hunters International, INTERPOL) ; réseaux BEC ouest-africains ; courtiers d’accès initiaux", "T1657 vol financier ; T1078 comptes valides ; T1110 force brute ; T1190 service exposé ; T1566 phishing ; T1486 chiffrement ; T1498 DDoS ; T1656 usurpation"],
   ["Harmattan Télécom (télécom, CI)", "Fraudeurs SIM swap et mules mobile money ; Hunters International (télécoms, INTERPOL 2025) ; acteur lié à Akira (INTERPOL 2026) ; DDoS contre portails", "T1656 usurpation (SIM swap) ; T1657 vol financier ; T1078 comptes d’agents ; T1199 relation de confiance ; T1190 portails OSS/BSS ; T1530/T1567/T1048 exfiltration ; T1499 DoS"]],
  [3.3, 7.4, 5.7], "Acteurs et TTP par entreprise fictive")
P("**Limite.** Les noms d’acteurs sont ceux cités par les rapports publics ; nous n’avons pas encore corroboré leur activité réelle sur le dark web (aucune collecte directe). L’attribution reste donc une hypothèse de travail. Une analyse selon le **Diamond Model** est prévue pour le mi-parcours.")

pagebreak()
HH(1, "Architecture du modèle et de la plateforme")
HH(2, "Modèle fonctionnel en sept étapes")
FIGURE("fig2_modele_7_etapes.png", "Modèle fonctionnel en sept étapes", 15.5)
P("Le profil d’entreprise (1) pilote tout le reste : il fournit les mots-clés de veille, les actifs à surveiller et les pondérations. La collecte (2) est passive. Chaque renseignement reçoit une cotation Amirauté et un niveau TLP (3), puis est normalisé en STIX 2.1 et stocké dans MISP (4). Le scoring et l’IA locale (5) calculent la priorité ; une hypothèse de chasse reliée à une technique ATT&CK (6) est proposée puis validée par l’analyste ; la chasse est conduite dans Wazuh et les cas sont gérés dans DFIR-IRIS (7). Les résultats reviennent alimenter les pondérations.")
HH(2, "Architecture technique en quatre zones")
FIGURE("fig1_architecture.png", "Segmentation en quatre zones", 15.5)
P("La **zone 1** (collecte isolée : VM Whonix et collecteurs OSINT) n’a aucun accès au laboratoire. Elle ne produit que des fichiers STIX/JSON déposés dans un export en lecture seule, relu avant import par la **zone 2** (plateforme CTI : MISP, scoring, IA locale, profils). La **zone 3** (SOC : Wazuh, DFIR-IRIS, tableau de bord) reçoit les IOC et hypothèses. La **zone 4** (entreprises fictives : agents Wazuh sur VM Windows/Linux et générateurs de journaux) alimente le SIEM. Le sens unique de la zone 1 vers la zone 2 est une règle d’architecture ; sa mise en œuvre réseau (réseaux VirtualBox/Proxmox séparés) est **à faire**.")
HH(2, "Choix des outils")
T(["Fonction", "Outil (open source)", "Raison du choix", "Statut"],
  [["Collecte Tor", "Whonix (Gateway + Workstation)", "Isole le trafic Tor ; fuite d’IP impossible par conception", "À déployer"],
   ["CTI", "MISP", "Stockage STIX, taxonomies TLP et Amirauté intégrées, partage", "À déployer"],
   ["SIEM / chasse", "Wazuh (indexeur OpenSearch)", "Règles, listes CDB, requêtes sur les journaux des agents", "À déployer"],
   ["Gestion de cas", "DFIR-IRIS", "Cas, IOC, chronologie ; gratuit", "À déployer"],
   ["IA locale", "Ollama + Mistral 7B ; scikit-learn ; sentence-transformers ; spaCy ; Argos Translate", "Exécution 100 % locale, licences permissives", "scikit-learn réalisé ; le reste à installer"],
   ["Scripts", "Python 3, PyYAML, pytest", "Reproductible, testé", "Réalisé"]],
  [2.8, 4.6, 6.2, 2.8], "Outils retenus et état de déploiement")
P("Les versions précises sont **à épingler au laboratoire** le jour de l’installation (dernière version stable de chaque projet) et consignées dans `.env`. Nous évitons de figer ici des numéros non vérifiés sur machine.")
HH(2, "Choix des modèles d’IA")
T(["Tâche", "Modèle", "Pourquoi", "Statut / mesure"],
  [["Classer les publications (7 catégories)", "TF-IDF + régression logistique, puis lexique FR/EN + repli ML", "Léger, explicable, exécutable sans GPU", "Réalisé : exactitude 0,50 (ML seul), 0,90 (hybride, optimiste)"],
   ["Pertinence (similarité profil/renseignement)", "TF-IDF + cosinus ; ensuite sentence-transformers multilingue", "Le multilingue est nécessaire (FR/EN/AR)", "TF-IDF réalisé ; embeddings à faire"],
   ["Extraction d’IOC", "Expressions régulières (+ défangage)", "Déterministe, vérifiable", "Réalisé, testé"],
   ["Hypothèses ATT&CK", "Règles ; puis LLM local (Mistral 7B via Ollama)", "Repli déterministe si le LLM est indisponible ; liste blanche d’ID de techniques", "Règles réalisées ; LLM garde-fous testés, qualité non évaluée"],
   ["Traduction", "Argos Translate", "Hors ligne", "À faire"],
   ["Anomalies sur journaux", "Isolation Forest (scikit-learn)", "Non supervisé, adapté aux journaux simulés", "À faire (mi-parcours)"]],
  [3.4, 4.2, 4.6, 4.2], "Modèles d’IA, justification et état")

pagebreak()
HH(1, "Profils d’entreprise et modules sectoriels")
HH(2, "Principe de généricité")
P("Le code ne contient **aucune connaissance sectorielle ou nationale**. Le profil de menace est calculé par `thab/profile.py` à partir de cinq couches de configuration : le **socle commun** (identifiants exposés, phishing, rançongiciels, surface d’attaque), un **module sectoriel** (`config/sectors/`), un **module pays** (`config/countries/`), une **table technologies → TTP** (`config/tech_map.yaml`) et le **profil** lui-même. Un secteur sans module bascule sur le socle commun avec un avertissement explicite ; les technologies du profil adaptent quand même les priorités.")
HH(2, "Les deux entreprises fictives")
T(["", "Zellige Bank", "Harmattan Télécom"],
  [["Secteur / pays", "Banque / Maroc", "Télécom et mobile money / Côte d’Ivoire"],
   ["Taille", "4 500 employés, 220 agences", "2 200 employés, 6 M d’abonnés"],
   ["Domaines (fictifs)", "zellige-bank.example, zelligepay.example", "harmattan-telecom.example, harmattanpay.example"],
   ["Marques", "Zellige Bank, ZelligePay, Zellige Mobile", "Harmattan Télécom, HarmattanPay, Harmattan Money"],
   ["Systèmes critiques", "Core banking, SWIFT, monétique, Active Directory", "OSS/BSS, plateforme mobile money, HLR/HSS, base abonnés (KYC)"],
   ["Technologies", "Fortinet, Microsoft 365, Active Directory, VMware, Oracle, SWIFT, Citrix", "Palo Alto, Linux, Oracle, mobile money, USSD, VMware, WordPress"],
   ["Fournisseurs", "Intégrateur core banking, prestataire monétique, opérateur télécom", "Intégrateur OSS/BSS, réseau d’agents et revendeurs, agrégateur SMS"]],
  [3.0, 6.7, 6.7], "Profils des deux entreprises fictives", first_bold=True)
P("Les noms sont inventés ; toute ressemblance avec une entreprise réelle est fortuite. Chaque profil est un fichier YAML (`config/profiles/`), qui contient aussi une section `simulation` utilisée par les générateurs de journaux.")
HH(2, "Profil de menace généré")
def top(pf, n=6):
    return "; ".join(f"{a} ({b})" for a, b in gen["profils"][pf]["top5_weights"][:n])
T(["Profil", "Module sectoriel / pays", "TTP prioritaires (poids 0-1)", "Hypothèses de départ"],
  [["Zellige Bank", "banque / MA", top("zellige_bank_ma"), ", ".join(gen["profils"]["zellige_bank_ma"]["hypotheses"])],
   ["Harmattan Télécom", "telecom / CI", top("harmattan_telecom_ci"), ", ".join(gen["profils"]["harmattan_telecom_ci"]["hypotheses"])]],
  [3.0, 2.8, 6.4, 4.2], "Profils de menace produits par le code (sortie réelle)")
P("Chaque module fournit au moins cinq hypothèses de départ (par exemple HB-01 password spraying sur e-banking/VPN, HB-03 réutilisation de comptes issus d’une fuite, HB-04 fraude au virement ; HT-01 abus des outils d’activation SIM par des comptes d’agents, HT-03 exfiltration de la base d’abonnés). Les hypothèses `HX-…` sont ajoutées automatiquement selon les technologies exposées du profil (ici Fortinet et Citrix pour la banque). Les fichiers sont dans `hunts/hypotheses/` ; **toutes sont au statut « candidate »**, à valider par un analyste.")
HH(2, "Premier test de généricité")
P("En attendant le profil inédit de l’encadrant, nous avons écrit nous-mêmes un profil de **santé au Kenya** (`test_inedit_sante_ke.yaml`), secteur pour lequel aucun module n’existe. Même code, même configuration.")
sim = gen["similarite"]
T(["Comparaison", "Jaccard TTP top-10", "Jaccard hypothèses"],
  [[k.replace("_", " ").replace(" vs ", "  vs  "), v["jaccard_top10_ttps"], v["jaccard_hypotheses"]] for k, v in sim.items()],
  [9.4, 3.5, 3.5], "Différence entre profils produits par un code identique")
P("Résultat : le profil de santé fonctionne, avec l’avertissement « Aucun module sectoriel pour sante : repli sur le socle commun », et produit des priorités (T1078, T1190, T1566, T1486, T1133, …) et des hypothèses (HG-01 à HG-03 et HX-fortinet) différentes de celles des deux autres profils ; les hypothèses de la banque et du télécom n’ont aucune hypothèse commune. **Limites** : le profil de test est écrit par nous, donc le vrai profil inédit reste à passer ; sans module santé les hypothèses sont plus génériques, ce qui est attendu mais montre l’intérêt d’ajouter des modules.")

pagebreak()
HH(1, "Pipeline de collecte, cotation et TLP")
HH(2, "Registre des sources")
T(["ID", "Source", "Type", "Accès", "Fiabilité prévue", "Statut"],
  [["SRC-001", "crt.sh (Certificate Transparency)", "OSINT surface", "clearnet, passif", "B", "proposée"],
   ["SRC-002", "Shodan InternetDB", "OSINT surface", "clearnet, passif", "B", "proposée"],
   ["SRC-003", "dnstwist / permutations locales", "OSINT surface", "local", "B", "proposée"],
   ["SRC-004", "INTERPOL – rapports africains", "CTI institutionnelle", "clearnet", "A", "proposée"],
   ["SRC-005", "CybelAngel – publications", "CTI éditeur", "clearnet", "B", "proposée"],
   ["SRC-006", "CERT nationaux (maCERT, CI-CERT, KE-CIRT/CC)", "CTI institutionnelle", "clearnet", "A", "proposée"],
   ["SRC-007", "Flux ouverts (CISA KEV, abuse.ch, CERT-EU)", "CTI ouverte", "clearnet", "B", "proposée"],
   ["SRC-008", "Canaux Telegram publics (liste à fixer)", "Telegram public", "clearnet, passif", "F", "proposée, 0 canal"],
   ["SRC-009", "Ahmia (index de services .onion)", "Index dark web", "métadonnées seules", "F", "proposée"]],
  [1.6, 5.2, 2.7, 2.7, 1.8, 2.4], "Registre des sources et statut de validation")
P("**Aucune source n’est encore « validée »** : la validation appartient à l’encadrant et sera demandée à la séance 2. C’est un **point bloquant assumé** : tant qu’elle n’est pas donnée, le code refuse de collecter. Les sources 008 et 009 touchent au dark web ou à Telegram ; elles demandent une validation explicite de la liste de canaux et du protocole.")
HH(2, "Collecteurs implémentés")
T(["Collecteur", "Fonction", "Test réalisé", "Test réseau réel"],
  [["crtsh.py", "Sous-domaines et certificats ; détection de noms nouveaux par rapport à une base de référence", "Analyse d’un jeu JSON simulé ; absence de doublons", "Non (réseau sortant désactivé)"],
   ["internetdb.py", "Ports, CVE et priorité d’une IP", "Résumé d’un enregistrement simulé", "Non"],
   ["typosquat.py", "Génération de domaines proches (omission, homoglyphes, TLD…)", "Plus de 50 variantes pour un domaine, aucune malformée", "Sans objet (local)"],
   ["rss.py", "Flux RSS/Atom avec analyse XML durcie (DTD/entités refusées)", "Flux valide ; attaque par entité XML refusée", "Non"],
   ["telegram_public.py", "Analyse de l’aperçu web public d’un canal", "Analyse d’un HTML simulé ; appel `fetch` bloqué (source non validée)", "Non, volontairement"]],
  [2.9, 5.6, 5.0, 2.9], "Collecteurs et niveau de test")
HH(2, "Cotation des renseignements (système de l’Amirauté)")
P("Chaque renseignement reçoit une cotation à deux caractères : la **fiabilité de la source** (A à F) et la **crédibilité de l’information** (1 à 6) ; le code refuse toute cotation invalide. La cotation est convertie en valeur numérique F (0 à 1) pour le score et en étiquettes MISP (`admiralty-scale:source-reliability`, `admiralty-scale:information-credibility`).")
T(["Lettre", "Fiabilité de la source", "Chiffre", "Crédibilité de l’information"],
  [["A", "Totalement fiable", "1", "Confirmée par d’autres sources"], ["B", "Habituellement fiable", "2", "Probablement vraie"],
   ["C", "Assez fiable", "3", "Possiblement vraie"], ["D", "Pas habituellement fiable", "4", "Douteuse"],
   ["E", "Non fiable", "5", "Improbable"], ["F", "Fiabilité non évaluable", "6", "Véracité non évaluable"]],
  [1.8, 5.6, 1.8, 7.2], "Échelles de cotation Amirauté")
HH(2, "Classification TLP 2.0")
P("Les niveaux TLP 2.0 sont TLP:RED, TLP:AMBER+STRICT, TLP:AMBER, TLP:GREEN et TLP:CLEAR (qui remplace TLP:WHITE) [5]. Le code normalise ces niveaux, rejette tout niveau inconnu et décide si un renseignement peut être partagé avec une audience donnée. Marquage par défaut selon la source : tout contenu public (CTI, OSINT) est TLP:CLEAR ; un canal Telegram public démarre à TLP:GREEN ; un index dark web à TLP:AMBER ; une observation directe sur le dark web à TLP:AMBER+STRICT. L’analyste peut rendre le marquage plus restrictif, pas plus ouvert, sans justification.")
HH(2, "Normalisation STIX 2.1 et stockage MISP")
P("`thab/stix.py` produit un bundle STIX 2.1 par renseignement : un objet `report`, des `indicator` pour chaque IOC extrait (IP, domaine, URL, e-mail, hachage), un producteur d’identité, et les étiquettes TLP/Amirauté. Les identifiants sont des UUIDv5 **déterministes** : rejouer la collecte ne crée pas de doublon dans MISP. Les six bundles du défi Go/noGo passent le contrôle de conformité minimal. Le validateur officiel et l’import dans MISP sont **à faire** au laboratoire.")
HH(2, "Journal de collecte dark web et données des entreprises fictives")
P("Le journal de collecte a les colonnes suivantes : horodatage, membre, objectif, sources consultées, environnement, **validation de l’encadrant**, constats, contenu illicite rencontré. Il est **vide** à ce jour (voir 1.1). Les **données générées** pour les entreprises fictives sont, pour une semaine d’activité simulée et reproductible (graine fixe) :")
T(["Entreprise", "auth.log (SSH, sudo, cron)", "VPN", "Web (nginx)", "Windows 4624/4625", "Étiquettes d’attaque"],
  [["Zellige Bank", "151 lignes", "108", "1 041", "149", "47"], ["Harmattan Télécom", "139 lignes", "80", "916", "123", "47"]],
  [3.4, 3.6, 1.8, 2.4, 2.8, 2.4], "Journaux synthétiques générés (7 jours, graine 1)")
P("Deux scénarios sont injectés et étiquetés : un **password spraying** (45 comptes testés depuis une IP de documentation RFC 5737 en 9 minutes, puis un succès) et une **connexion VPN nocturne depuis un pays inhabituel**. Un jeu de 200 comptes de fuite **simulés** et la liste CDB Wazuh correspondante sont aussi produits. Les rejeux d’attaques réelles (Kali, Atomic Red Team) et l’import de jeux publics (OTRF, EVTX-ATTACK-SAMPLES) sont **à faire** au laboratoire.")

pagebreak()
HH(1, "Scoring et intelligence artificielle")
HH(2, "Formule et paramètres")
P("Le score de priorisation combine la pertinence pour le profil (P), la fiabilité Amirauté (F) et la criticité (C) : **score = 100 × (0,55·P + 0,15·F + 0,30·C)**. La pertinence mélange (60 %) une correspondance d’entités avec le profil (marque ou domaine exact = 1,0 ; technologie = 0,6 ; secteur et pays = 0,5 ; secteur = 0,3 ; pays = 0,25 ; Afrique = 0,1) et (40 %) une similarité sémantique. La criticité dépend de la catégorie (rançongiciel 0,95 ; exploitation de vulnérabilité 0,90 ; fuite ou vente de données et fraude mobile money 0,85 ; phishing/BEC 0,70 ; hacktivisme 0,55) et décroît avec l’ancienneté (demi-vie 45 jours). Une **barrière de fiabilité** plafonne à « surveillance » toute décision de chasse dont F < 0,35. Tous les paramètres sont dans `config/scoring.yaml`.")
HH(2, "Jeu annoté et protocole")
P("Le jeu annoté compte **70 publications** (7 catégories × 10, françaises et anglaises) étiquetées, pour chaque profil, « chasse », « surveillance » ou « archivage ». **Il est entièrement synthétique** : les textes sont rédigés par nous à partir de faits publics, avec des victimes anonymisées, et incluent 10 « négatifs difficiles » (qui mentionnent un pays ou un secteur sans lien avec une menace). Les étiquettes résultent d’un protocole de règles écrit avant le calibrage ; il doit encore être relu par un second membre (accord inter-annotateurs prévu). **Ce jeu valide le bon fonctionnement des composants ; il ne mesure pas une performance réelle.**")
HH(2, "Calibrage des seuils et résultats")
P(f"Les seuils (chasse ≥ 50, surveillance ≥ 38) sont obtenus par recherche en grille maximisant le F1 macro. Pour éviter d’évaluer sur les données de calibrage, nous calibrons sur un profil et testons sur l’autre. Sur l’ensemble, avec les seuils retenus : exactitude **{M['accuracy']}**, F1 macro **{M['macro_f1']}**.")
rows = []
for k, v in CP.items():
    rows.append([k.replace("calibré sur", "calibré sur").replace("->", "→"), f"{v['seuils']['chasse']} / {v['seuils']['surveillance']}", v["test"]["macro_f1"], v["test"]["accuracy"]])
T(["Protocole", "Seuils chasse / surveillance", "F1 macro (test)", "Exactitude (test)"], rows, [8.0, 3.2, 2.6, 2.6], "Validation croisée entre profils")
FIGURE("fig4_resultats.png", "Résultats du scoring et de la classification (jeu synthétique)", 15.0)
T(["Décision", "Précision", "Rappel", "F1", "Support"],
  [[c, M[c]["precision"], M[c]["recall"], M[c]["f1"], M[c]["support"]] for c in ["chasse", "surveillance", "archivage"]],
  [4.0, 3.0, 3.0, 3.0, 3.0], "Métriques par décision (seuils 50 / 38, les deux profils)")
P("**Lecture critique.** La décision « chasse » est correcte (précision 0,86, rappel 0,83). La classe **« surveillance » est faible** (précision 0,41, rappel 0,50) : elle regroupe des cas intermédiaires où le jugement humain est lui-même flou. Les seuils calibrés sur un profil donnent 0,69 puis 0,60 de F1 macro sur l’autre, donc la stabilité est moyenne. Ces valeurs ont été obtenues après trois itérations consignées dans le journal de validation (1ère version : F1 macro 0,60). Elles seront **recalibrées avec des items réels** avant le mi-parcours.")
HH(2, "Classification des publications")
P("Un classifieur TF-IDF + régression logistique seul atteint une exactitude de **0,50** en validation croisée à 5 plis : il est insuffisant avec 10 exemples par classe et un jeu bilingue. Un **lexique bilingue** avec repli sur le modèle atteint **0,90** (F1 macro 0,90), mais ce chiffre est **optimiste** car le lexique a été écrit en connaissant le jeu. Nous ne le présentons pas comme une performance ; la vraie mesure se fera sur des items réels. Voie d’amélioration : embeddings multilingues, traduction préalable et jeu de 300 items ou plus.")
HH(2, "Hypothèses de chasse et garde-fous du LLM")
P("`thab/hypotheses.py` produit une hypothèse **par règles** (catégorie du renseignement → techniques ATT&CK candidates, filtrées par le profil de menace) ou **par LLM local**. Le LLM reçoit une liste blanche d’identifiants de techniques ; toute technique hors liste est rejetée, une sortie non JSON ou un serveur injoignable renvoie « aucune hypothèse » et le repli par règles prend le relais (testé avec des réponses simulées). **Aucun vrai modèle n’a été interrogé** à ce stade (Ollama non installé) : la qualité des hypothèses du LLM n’est pas évaluée. Les requêtes de chasse associées sont des **pseudo-requêtes** ; seules deux versions exécutables sont rédigées (`hunts/wazuh/`) et elles restent à valider avec `wazuh-logtest`.")

pagebreak()
HH(1, "Défi Go/noGo : du renseignement à l’hypothèse de chasse")
P("Trois renseignements **réels** et publics sont suivis de la source à l’hypothèse. Le texte est notre résumé des faits publiés (pas une copie) ; la catégorie est prédite par le classifieur ; le score est calculé par le code pour trois profils. Les bundles STIX correspondants sont dans `data/generated/go_nogo_challenge/`. **Les captures (page archivée, empreinte SHA-256) restent à réaliser par l’équipe** ; elles sont obligatoires avant la séance.")
def srow(r):
    z, h, s = r["profiles"]["zellige_bank_ma"], r["profiles"]["harmattan_telecom_ci"], r["profiles"]["test_inedit_sante_ke"]
    f = lambda e: f"{e['score']} → {e['action']}"
    return [r["id"], r["title"], f"{r['cotation']} ; {r['tlp']}", r["category_predicted"], f(z), f(h), f(s)]
T(["ID", "Renseignement", "Cotation ; TLP", "Catégorie prédite", "Zellige Bank", "Harmattan Télécom", "Santé KE (test)"],
  [srow(r) for r in chal], [1.6, 4.5, 2.1, 2.0, 2.0, 2.2, 2.0], "Défi Go/noGo : scores par profil", size=8)
HH(2, "Renseignement principal : fuite CNSS (INTEL-001)")
r1 = chal[0]; h1 = r1["profiles"]["zellige_bank_ma"]["hypothesis"]
T(["Élément", "Contenu"],
  [["Source", "CybelAngel, « Escalating Cyber Hostilities in North Africa [A CNSS Breach Update] » [3]"],
   ["Date", "2025-06-15 (dernière donnée citée ; date exacte du billet à confirmer lors de la capture)"],
   ["Cotation", "**B1** : éditeur reconnu (B) ; faits corroborés par la presse marocaine et un CERT européen (1)"],
   ["TLP", "TLP:CLEAR (source publique) ; contenu Telegram/dark web obtenu de façon secondaire, aucune collecte directe"],
   ["Catégorie", "fuite ou vente de données (prédite)"],
   ["Score Zellige Bank", f"**{r1['profiles']['zellige_bank_ma']['score']}** (P = {r1['profiles']['zellige_bank_ma']['P']}, F = {r1['profiles']['zellige_bank_ma']['F']}, C = {r1['profiles']['zellige_bank_ma']['C']}) → **chasse** ; correspondance : secteur + pays. Le score est proche du seuil (50) : décision à confirmer par l’analyste"],
   ["Score Harmattan Télécom", f"{r1['profiles']['harmattan_telecom_ci']['score']} → archivage (aucun lien avec le profil)"],
   ["Hypothèse", f"{h1['hypothesis_id']} : {h1['statement']}"],
   ["Techniques ATT&CK", ", ".join(f"{t['id']} {t['name']}" for t in h1["techniques"])],
   ["Chasse", "HB-01 : une même IP échoue sur au moins 8 comptes distincts en 10 minutes (requête OpenSearch `hunts/wazuh/hb01_password_spraying.opensearch.json`) ; HB-03 : connexion réussie d’un compte présent dans la liste CDB d’identifiants exposés (`hb03_leaked_accounts.rule.xml`)"]],
  [3.6, 12.8], "Suivi de bout en bout du renseignement INTEL-001", first_bold=True)
P("**Résultat de la chasse sur les données synthétiques.** Sur les journaux simulés de Zellige Bank, la logique HB-01 détecte les 45 tentatives injectées (rappel 1,0, précision 1,0, aucune fausse alerte sur l’activité normale) et la logique HB-03 détecte la connexion VPN nocturne injectée. **Ce résultat prouve que le banc d’essai fonctionne, pas que la détection est performante** : les scénarios sont volontairement évidents. Le rejeu avec Wazuh et des attaques réelles de laboratoire reste **à faire**.")
HH(2, "Deux autres renseignements")
P("**INTEL-002 (SIM swap, Kenya, INTERPOL 2026, A2)** : chasse prioritaire pour Harmattan Télécom (score " + str(chal[1]['profiles']['harmattan_telecom_ci']['score']) + ") avec l’hypothèse « abus des outils d’activation SIM par des comptes d’agents » (T1656, T1657, T1078) ; archivage pour la banque. **INTEL-003 (contenus africains sur les forums, +62 %, S2W via INTERPOL, B2)** : chasse pour Harmattan Télécom (" + str(chal[2]['profiles']['harmattan_telecom_ci']['score']) + ") et surveillance pour la banque (" + str(chal[2]['profiles']['zellige_bank_ma']['score']) + "). Cette différence de décision sur un même renseignement, selon le profil, est l’effet recherché.")

pagebreak()
HH(1, "Planification et répartition des tâches")
HH(2, "Calendrier")
P("Le calendrier suit la fiche de projet : lancement en S1 (27/10/2026), Go/noGo en S4 (17/11), mi-parcours environ trois semaines plus tard (S7, 08/12) et soutenance environ quatre semaines après (S11, 05/01/2027). Les dates exactes de séances sont **à confirmer avec l’encadrant**.")
FIGURE("fig3_gantt.png", "Planning prévisionnel du projet", 15.5)
HH(2, "Répartition des tâches (qui fait quoi)")
CALLOUT("**À compléter par le chef de projet.** Je ne connais ni la composition du groupe ni son chef de projet : la colonne « Responsable » contient une proposition à ajuster. Le document de planification est sous la responsabilité du chef de projet.")
T(["Lot", "Contenu", "Livrables", "Responsable (proposé)", "Échéance"],
  [["L1 Architecture et infra", "VM et réseaux isolés, Docker Compose, déploiement MISP, Wazuh, DFIR-IRIS", "Plateforme reproductible, schémas", "[Membre A]", "S5"],
   ["L2 Collecte et sources", "Validation des sources, collecteurs, protocole dark web, journal", "Pipeline, journal à jour", "[Membre B]", "S6"],
   ["L3 Profils, scoring, cotation", "Profils, modules, scoring, Amirauté/TLP, STIX", "Config, code, jeu annoté", "Wassim Nafid", "S4 puis S7"],
   ["L4 IA locale", "Classifieur, similarité, LLM local, anomalies, métriques", "Modèles évalués", "Wassim Nafid", "S7"],
   ["L5 Chasse et réponse", "Générateurs, hypothèses ATT&CK, requêtes Wazuh, DFIR-IRIS, tableau de bord", "Chasses validées, cas", "[Membre C]", "S8-S9"],
   ["L6 Qualité et rapport", "Dépôt GitHub, tests de généricité, rapport, soutenance", "Rapport PDF, support", "[Chef de projet]", "S10-S11"]],
  [3.0, 5.2, 3.2, 3.0, 2.0], "Lots de travail, livrables et responsables (proposition)", size=8)

HH(1, "État d’avancement, risques et auto-évaluation")
HH(2, "État d’avancement")
T(["Élément demandé en séance 2", "État", "Preuve / commentaire"],
  [["Document de planification", "Réalisé (à valider par le chef de projet)", "Chapitre 8 ; tâches nominatives à compléter"],
   ["Architecture (zones, MISP, Wazuh, IRIS)", "Conçue ; infrastructure non déployée", "Figures 1-2 ; `infra/docker-compose.yml` rédigé, non testé"],
   ["Pipeline : sources, cotation, TLP", "Code réalisé et testé ; sources non validées", "9 sources proposées ; 5 collecteurs testés hors ligne ; 0 test réseau"],
   ["Journal de collecte dark web", "Ouvert, vide", "Aucune session ; protocole et garde-fou en place"],
   ["Profils et données fictives", "Réalisé", "2 profils + 1 profil de test ; journaux et fuite simulés générés"],
   ["Modèles d’IA", "Choisis ; ML réalisé ; LLM non installé", "Tableau du 3.4 ; métriques du chapitre 6"],
   ["Défi Go/noGo", "Réalisé hors captures", "3 renseignements cotés, scorés, hypothèses, STIX ; captures à faire"],
   ["Test de généricité", "Réalisé sur un profil écrit par nous", "À refaire avec le profil de l’encadrant"],
   ["Dépôt GitHub", "Dépôt local prêt ; non publié", "Création et historique des contributions de chaque membre à faire"]],
  [5.0, 4.6, 6.8], "Avancement par rapport à la liste de revue de la séance 2", size=8)
HH(2, "Extrait du journal de validation")
T(["ID", "Artefact", "Résultat observé", "Écart", "Correction"],
  [[r["id"], r["artefact"], r["resultat_observe"], r["ecart"], r["correction"]] for r in val_rows],
  [1.2, 3.0, 4.0, 4.2, 4.0], "Journal de validation (10 entrées ; fichier complet `journals/journal_validation.csv`)", size=7)
HH(2, "Risques")
T(["Risque", "Probabilité / impact", "Mitigation"],
  [["Source dark web non validée à temps", "Moyenne / forte", "Collecte restreinte aux sources OSINT et institutionnelles ; informations dark web secondaires"],
   ["Infrastructure lourde (RAM ≈ 32 Go à répartir)", "Forte / forte", "Déploiement par zones, images épinglées, ressources dimensionnées dès la semaine 5"],
   ["Jeu annoté synthétique trop petit", "Forte / moyenne", "Enrichir avec des items réels ; double annotation ; ne pas sur-interpréter les métriques"],
   ["LLM local trop lent ou peu pertinent", "Moyenne / moyenne", "Repli par règles déjà en place ; modèle plus petit"],
   ["Échec du test de généricité sur le profil inédit", "Moyenne / forte", "Repli générique, modules supplémentaires, tests répétés sur plusieurs profils"],
   ["Violation involontaire du cadre éthique", "Faible / éliminatoire", "Garde-fous dans le code, journal obligatoire, briefing de l’équipe avant toute session"],
   ["Répartition du travail inégale", "Moyenne / moyenne", "Revue hebdomadaire, historique GitHub par membre"]],
  [5.2, 3.0, 8.2], "Principaux risques et mitigations", size=8)
HH(2, "Auto-évaluation face aux critères du Go/noGo")
T(["Critère de la fiche", "Auto-évaluation"],
  [["Pertinence de l’architecture", "Satisfaisante sur le papier (4 zones, 7 étapes) ; **non démontrée** tant que la stack n’est pas déployée"],
   ["Avancement du pipeline et des profils", "Bon côté code, données et profils ; **insuffisant côté sources validées et tests réseau**"],
   ["Qualité de la planification et des rôles", "Planning prêt ; **rôles nominatifs à compléter**"],
   ["Respect du cadre dark web et test de généricité", "Cadre respecté (aucune collecte directe) ; test de généricité partiel (profil écrit par nous)"],
   ["Travail en équipe", "Non évaluable dans ce document ; dépend de l’historique de contributions"]],
  [5.4, 11.0], "Auto-évaluation", first_bold=True)
CALLOUT("**Recommandation : GO conditionnel.** Le modèle, le code et les données sont suffisamment avancés pour passer à la phase suivante, à condition de lever quatre points avant le mi-parcours : (1) déployer la stack MISP, Wazuh et DFIR-IRIS et rejouer les chasses ; (2) obtenir la validation des sources par l’encadrant ; (3) réaliser les captures des renseignements et ouvrir le dépôt GitHub avec tous les membres ; (4) passer le profil inédit de l’encadrant et recalibrer le scoring sur des items réels.", "E3F4EC")

pagebreak()
HH(1, "Conclusion")
P("À ce stade, le projet dispose d’un **cœur logiciel fonctionnel et testé** : un profil d’entreprise pilote un profil de menace, un score de priorisation et des hypothèses ATT&CK, avec cotation Amirauté, niveau TLP 2.0 et export STIX 2.1. Deux entreprises fictives de secteurs différents et un profil de test montrent que le comportement change sans modifier le code. Un défi Go/noGo réel est suivi de la source à l’hypothèse, et des journaux synthétiques permettent de rejouer les chasses HB-01 et HB-03.")
P("Les limites sont assumées : la stack n’est pas encore déployée, aucune source n’est validée, le journal de collecte dark web est vide par choix de conformité, le jeu annoté est synthétique et la classe « surveillance » est mal discriminée, les résultats du classifieur hybride sont optimistes, et le LLM local n’a pas été évalué. Ces points structurent le plan jusqu’au mi-parcours : déploiement, validation des sources, collecte réelle encadrée, recalibrage du scoring sur données réelles, évaluation du LLM et détection d’anomalies, puis analyse selon le Diamond Model.")

pagebreak()
HH(1, "Bibliographie & Webographie")
refs = [
 "[1] INTERPOL, « Africa Cyberthreat Assessment Report 2025 » et communiqué « New INTERPOL report warns of sharp rise in cybercrime in Africa », 2025. [En ligne]. Disponible : https://www.interpol.int/News-and-Events/News/2025/New-INTERPOL-report-warns-of-sharp-rise-in-cybercrime-in-Africa (consulté le 08/11/2026).",
 "[2] INTERPOL, « African Cyberthreat Assessment Report 2026 », août 2026. [En ligne]. Disponible : https://www.interpol.int/fr/content/download/24663/file/INTERPOL%20AFRICAN%20CYBERTHREAT%20ASSESSMENT%20REPORT%202026%20%281%29.pdf (consulté le 08/11/2026).",
 "[3] CybelAngel, « Escalating Cyber Hostilities in North Africa [A CNSS Breach Update] », 2025. [En ligne]. Disponible : https://cybelangel.com/blog/a-cnss-breach-update/ (consulté le 08/11/2026).",
 "[4] The MITRE Corporation, « MITRE ATT&CK® », 2026. [En ligne]. Disponible : https://attack.mitre.org (consulté le 08/11/2026).",
 "[5] FIRST, « Traffic Light Protocol (TLP) Version 2.0 », 2022. [En ligne]. Disponible : https://www.first.org/tlp/ ; voir aussi CERT-EU, « TLP version 2 primer » : https://www.cert.europa.eu/blog/tlp-version-2-primer (consulté le 08/11/2026).",
 "[6] « Admiralty code », Wikipedia (système de cotation source/information, STANAG 2511 de l’OTAN). [En ligne]. Disponible : https://en.wikipedia.org/wiki/Admiralty_code (consulté le 08/11/2026).",
 "[7] OASIS, « STIX™ Version 2.1 », 2021. [En ligne]. Disponible : https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html.",
 "[8] Conseil de l’Europe, Programme Octopus, « Côte d’Ivoire – cybercriminalité et législation ». [En ligne]. Disponible : https://www.coe.int/fr/web/octopus/-/cote-ivoire (consulté le 08/11/2026).",
 "[9] HESTIM, « Fiche du projet encadré 3pH – PIC : Threat Hunting à l’échelle africaine », Cycle Ingénieur 2026/2027.",
 "[10] Wazuh Inc., « Wazuh documentation ». [En ligne]. Disponible : https://documentation.wazuh.com ; MISP Project : https://github.com/MISP/MISP ; DFIR-IRIS : https://github.com/dfir-iris/iris-web ; Ollama : https://ollama.com (consultés le 08/11/2026).",
 "[11] S. Caltagirone, A. Pendergast et C. Betz, « The Diamond Model of Intrusion Analysis », Center for Cyber Intelligence Analysis and Threat Research, 2013.",
 "[12] A. Q. Jiang et al., « Mistral 7B », arXiv:2310.06825, 2023.",
 "[13] N. Reimers et I. Gurevych, « Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks », in Proc. EMNLP-IJCNLP, 2019.",
]
for r in refs:
    p = new_p("Normal"); p.paragraph_format.left_indent = Cm(1.0); p.paragraph_format.first_line_indent = Cm(-1.0); p.paragraph_format.space_after = Pt(4)
    runs(p, r, size=10)

pagebreak()
HH(1, "Annexes")
HH(2, "Annexe A. Structure du dépôt")
CODE(["threat-hunting-afrique/", "  config/        profils (profiles/), modules sectoriels (sectors/), pays (countries/), tech_map, scoring, sources",
      "  thab/          profile, scoring, admiralty, tlp, stix, ioc, hypotheses, classify, calibrate, journal, sources, collectors/",
      "  generators/    normal_activity.py, credential_leak.py (journaux et fuite SIMULÉS)",
      "  hunts/         hypotheses/, wazuh/ (requêtes et règles brouillon), offline_eval.py",
      "  scripts/       go_nogo_challenge.py, genericity_test.py, make_figures.py, build_report.py",
      "  data/          annotated/ (jeu synthétique), intel/ (3 renseignements), generated/ (journaux, résultats, STIX)",
      "  journals/      journal_collecte_darkweb.csv (vide), journal_validation.csv",
      "  infra/         docker-compose.yml (non testé), soc/, collect/    tests/ (31 tests)"])
HH(2, "Annexe B. Commandes de reproduction")
CODE(["python -m pytest -q                                   # 31 tests",
      "python scripts/genericity_test.py                     # test de généricité (3 profils)",
      "python scripts/go_nogo_challenge.py                   # défi Go/noGo, bundles STIX",
      "python -m thab.calibrate                              # calibrage et validation croisée",
      "python generators/normal_activity.py --profile config/profiles/zellige_bank_ma.yaml \\",
      "       --days 7 --seed 1 --out data/generated/zellige --inject spray offhours_vpn",
      "python hunts/offline_eval.py data/generated/zellige --profile config/profiles/zellige_bank_ma.yaml"])
HH(2, "Annexe C. Modèle de ligne du journal de collecte dark web")
T(["Champ", "Exemple de saisie (à ne remplir qu’après validation)"],
  [["horodatage", "2026-11-24T14:05:00+00:00"], ["membre", "[Nom du membre]"], ["objectif", "Observation passive d’un index public (Ahmia) pour le secteur bancaire"],
   ["sources_consultees", "SRC-009 (métadonnées uniquement)"], ["environnement", "VM Whonix Workstation, instantané propre"],
   ["validation_encadrant", "OK encadrant, date et référence du message"], ["constats", "Titres et métadonnées notés ; aucun téléchargement"], ["contenu_illicite_rencontre", "non"]],
  [4.4, 12.0], "Format d’une ligne du journal (exemple, non réel)", first_bold=True)

# ---------------------------------------------------------------- front matter (TOC + listes)
def toc_par(text, level, page, style_name):
    p = d.add_paragraph(style=style_name)
    body.remove(p._p)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(16.0), alignment=2, leader=1)  # right + dots
    p.add_run(f"{text}\t{page}")
    return p._p


LABELS = []


def insert_front():
    anchor = marker_front._p
    els = []
    def add(el):
        anchor.addprevious(el)
    t = d.add_paragraph("Table des matières", style="TOC Heading"); body.remove(t._p); no_num(t); add(t._p)
    counters = [0, 0, 0]
    SPECIAL = ("Introduction", "Conclusion", "Bibliographie & Webographie", "Annexes")
    for level, text in headings:
        if text in SPECIAL or text.startswith("Annexe"):
            label = text
        else:
            counters[level - 1] += 1
            for k in range(level, 3): counters[k] = 0
            label = f"{'.'.join(str(c) for c in counters[:level])}  {text}"
        LABELS.append(label)
        add(toc_par(label, level, pages.get("h:" + label, ""), f"toc {level}"))
    for title, key in (("Liste des Figures", "fig"), ("Liste des Tableaux", "tab")):
        t = d.add_paragraph(title); body.remove(t._p)
        t.runs[0].bold = True; t.runs[0].font.size = Pt(16); t.runs[0].font.color.rgb = RGBColor.from_string(NAVY)
        add(t._p)
        for c in captions[key]:
            add(toc_par(c, 1, pages.get("c:" + c, ""), "table of figures"))
        pb = d.add_paragraph(); body.remove(pb._p)
        if key == "fig":
            pb.add_run().add_break(WD_BREAK.PAGE) if False else None
        add(pb._p)
    body.remove(anchor)


# le canevas numérote automatiquement les titres ; on désactive la numérotation pour les titres spéciaux
def no_num(p):
    pPr = p._p.get_or_add_pPr()
    numPr = OxmlElement("w:numPr")
    il = OxmlElement("w:ilvl"); il.set(qn("w:val"), "0"); ni = OxmlElement("w:numId"); ni.set(qn("w:val"), "0")
    numPr.append(il); numPr.append(ni); pPr.append(numPr)

for p in d.paragraphs:
    if p.style.name.startswith("Heading ") and (p.text in ("Introduction", "Conclusion", "Bibliographie & Webographie", "Annexes") or p.text.startswith("Annexe")):
        no_num(p)
insert_front()

# les entrées de la table des matières utilisent le texte numéroté : on reconstruit la clé de page avec le texte numéroté
d.save(OUT)
json.dump({"headings": LABELS, "captions": captions["fig"] + captions["tab"]},
          open(Path(OUT).with_suffix(".meta.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("ok", OUT, len(headings), "titres,", len(captions["fig"]), "figures,", len(captions["tab"]), "tableaux")
