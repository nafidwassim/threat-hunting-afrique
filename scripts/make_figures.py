"""Figures du rapport (matplotlib)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent.parent / "docs/figures"
NAVY, TEAL, ORANGE, GREY, RED = "#1F3A5F", "#2A9D8F", "#E9A23B", "#5C6773", "#C44536"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


def box(ax, x, y, w, h, text, fc, tc="white", fs=8.5, ec=None, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec or fc, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc, fontsize=fs, weight="bold" if bold else "normal", wrap=True)


def arrow(ax, p, q, c=GREY, style="-|>", ls="-", lw=1.4):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=12, color=c, lw=lw, ls=ls))


def architecture():
    fig, ax = plt.subplots(figsize=(8.2, 4.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 5.6); ax.axis("off")
    zones = [(0.1, 0.3, 2.2, 4.6, "ZONE 1\nCollecte isolée", RED), (2.9, 0.3, 2.6, 4.6, "ZONE 2\nPlateforme CTI", TEAL),
             (6.1, 2.55, 3.7, 2.35, "ZONE 3  SOC", NAVY), (6.1, 0.3, 3.7, 2.0, "ZONE 4  Entreprises fictives", ORANGE)]
    for x, y, w, h, t, c in zones:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1", fc=c, alpha=0.10, ec=c, lw=1.8))
        if "fictives" in t:
            ax.text(x + w / 2, y + 0.12, t, ha="center", va="bottom", color=c, weight="bold", fontsize=9)
        else:
            ax.text(x + w / 2, y + h - 0.22, t, ha="center", va="top", color=c, weight="bold", fontsize=9)
    box(ax, 0.3, 2.9, 1.8, 0.7, "VM Whonix\n(Tor, observation\npassive)", RED, fs=7.5)
    box(ax, 0.3, 1.9, 1.8, 0.7, "Collecteurs OSINT\ncrt.sh, InternetDB,\ndnstwist, flux CTI", "#8C3B31", fs=7.2)
    box(ax, 0.3, 0.8, 1.8, 0.75, "Export contrôlé\n(fichiers STIX/JSON\nen lecture seule)", GREY, fs=7.2)
    box(ax, 3.1, 3.55, 2.2, 0.65, "MISP\n(stockage, TLP, partage)", TEAL, fs=7.5)
    box(ax, 3.1, 2.55, 2.2, 0.7, "Scoring + IA locale\n(Ollama, scikit-learn)", "#1F7A70", fs=8)
    box(ax, 3.1, 1.6, 2.2, 0.7, "Profils & modules\n(fichiers YAML)", "#35B3A3", fs=8)
    box(ax, 3.1, 0.55, 2.2, 0.7, "Dépôt GitHub\n(code, journaux)", GREY, fs=8)
    box(ax, 6.3, 3.4, 1.6, 0.75, "Wazuh\n(SIEM, chasse)", NAVY, fs=8)
    box(ax, 8.05, 3.4, 1.6, 0.75, "DFIR-IRIS\n(gestion de cas)", "#2F5D8C", fs=8)
    box(ax, 6.3, 2.7, 3.35, 0.5, "Tableau de bord\n(délai renseignement → chasse)", "#4A6FA5", fs=7)
    box(ax, 6.3, 0.8, 1.6, 0.7, "Agents Wazuh\n(VM Win/Linux)", ORANGE, tc="black", fs=8)
    box(ax, 8.05, 0.8, 1.6, 0.7, "Générateurs de\njournaux / fuites", ORANGE, tc="black", fs=8)
    arrow(ax, (1.2, 1.9), (1.2, 1.55)); arrow(ax, (1.2, 2.9), (1.2, 2.6))
    arrow(ax, (2.1, 1.17), (3.1, 3.8), c=RED, ls="--")
    ax.text(2.35, 2.1, "sens unique\n(sas)", fontsize=7, color=RED, rotation=62, ha="center")
    arrow(ax, (4.2, 3.55), (4.2, 3.27)); arrow(ax, (4.2, 2.55), (4.2, 2.3), c=GREY)
    arrow(ax, (5.3, 2.9), (6.3, 3.6), c=NAVY)
    arrow(ax, (7.1, 1.5), (7.1, 3.4), c=ORANGE); arrow(ax, (7.9, 3.78), (8.05, 3.78), c=NAVY)
    ax.text(5.0, 5.25, "Aucun accès de la zone 1 vers le laboratoire (zones 2-4)", ha="center", fontsize=8.5, color=RED, weight="bold")
    fig.savefig(OUT / "fig1_architecture.png", dpi=200, bbox_inches="tight"); plt.close(fig)


def pipeline():
    fig, ax = plt.subplots(figsize=(8.2, 3.0)); ax.set_xlim(0, 14); ax.set_ylim(0, 4); ax.axis("off")
    steps = ["1\nProfil\nd'entreprise", "2\nCollecte\npassive", "3\nCotation\nAmirauté\n+ TLP", "4\nSTIX 2.1\n+ MISP", "5\nScoring\n+ IA locale", "6\nHypothèse\nATT&CK", "7\nChasse\nWazuh\n+ IRIS"]
    cols = [NAVY, RED, ORANGE, TEAL, "#1F7A70", "#6C5B9E", NAVY]
    for i, (s, c) in enumerate(zip(steps, cols)):
        x = 0.1 + i * 1.95
        box(ax, x, 1.4, 1.7, 1.7, s, c, tc="black" if c == ORANGE else "white", fs=7.5, bold=True)
        if i < 6:
            arrow(ax, (x + 1.7, 2.25), (x + 1.95, 2.25))
    arrow(ax, (12.9, 1.4), (12.9, 0.7), c=GREY, style="-"); arrow(ax, (12.9, 0.7), (1.0, 0.7), c=GREY, style="-"); arrow(ax, (1.0, 0.7), (1.0, 1.4), c=GREY)
    ax.text(7, 0.3, "Retour d'expérience : résultats de chasse → pondérations, hypothèses, profil", ha="center", fontsize=8, color=GREY)
    ax.text(7, 3.5, "Contrôle permanent d'un analyste : toute sortie de l'IA est une hypothèse candidate", ha="center", fontsize=8.5, color=RED, weight="bold")
    fig.savefig(OUT / "fig2_modele_7_etapes.png", dpi=200, bbox_inches="tight"); plt.close(fig)


def gantt():
    weeks = ["S1\n27/10", "S2\n03/11", "S3\n10/11", "S4\n17/11", "S5\n24/11", "S6\n01/12", "S7\n08/12", "S8\n15/12", "S9\n22/12", "S10\n29/12", "S11\n05/01"]
    tasks = [("Cadrage, profils, sources, dépôt", 0, 2, NAVY), ("Architecture + infra (VM, Docker)", 1, 4, NAVY), ("Collecte OSINT + cotation/TLP", 1, 5, RED),
             ("Collecte passive dark web (après validation)", 3, 7, RED), ("Scoring + IA locale + métriques", 2, 7, TEAL), ("Générateurs + chasses Wazuh", 2, 8, ORANGE),
             ("DFIR-IRIS, tableau de bord, partage TLP", 6, 9, "#6C5B9E"), ("Tests de généricité", 3, 10, GREY), ("Rapport final + soutenance", 7, 11, "#2F5D8C")]
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    for i, (t, a, b, c) in enumerate(tasks):
        ax.barh(len(tasks) - 1 - i, b - a, left=a, color=c, height=0.55)
    ax.set_yticks(range(len(tasks))); ax.set_yticklabels([t[0] for t in tasks][::-1], fontsize=8)
    ax.set_xticks([i + 0.5 for i in range(11)]); ax.set_xticklabels(weeks, fontsize=7); ax.set_xlim(0, 11)
    for x, lab in [(3.5, "Go/NoGo"), (6.5, "Mi-parcours"), (10.5, "Soutenance")]:
        ax.axvline(x, color=RED, ls="--", lw=1); ax.text(x, len(tasks) - 0.35, lab, ha="center", fontsize=8, color=RED, weight="bold")
    ax.axvline(1.0 + 0.0, color="none"); ax.spines[["top", "right"]].set_visible(False); ax.grid(axis="x", alpha=0.2)
    fig.savefig(OUT / "fig3_gantt.png", dpi=200, bbox_inches="tight"); plt.close(fig)


def results():
    d = json.load(open(OUT.parent.parent / "data/generated/calibration_report.json", encoding="utf-8"))
    m = d["seuils_config_actuels"]["metrics"]
    fig, axs = plt.subplots(1, 2, figsize=(8.2, 3.2))
    cls = ["chasse", "surveillance", "archivage"]; x = range(3)
    axs[0].bar([i - 0.2 for i in x], [m[c]["precision"] for c in cls], 0.4, label="précision", color=TEAL)
    axs[0].bar([i + 0.2 for i in x], [m[c]["recall"] for c in cls], 0.4, label="rappel", color=ORANGE)
    axs[0].set_xticks(list(x)); axs[0].set_xticklabels(cls); axs[0].set_ylim(0, 1.05); axs[0].legend(fontsize=7, loc="upper right", ncol=2)
    axs[0].set_title("Décision de scoring (seuils 50 / 38)", fontsize=9)
    axs[1].bar(["TF-IDF + LR\n(ML seul)", "Lexique + ML\n(hybride)*"], [0.50, 0.90], color=[GREY, TEAL])
    axs[1].set_ylim(0, 1.05); axs[1].set_title("Classification des 7 catégories\n(exactitude, validation croisée)", fontsize=9)
    for i, v in enumerate([0.50, 0.90]): axs[1].text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    for a in axs: a.spines[["top", "right"]].set_visible(False)
    fig.text(0.99, -0.02, "* optimiste : lexique écrit en connaissant le jeu", ha="right", fontsize=7, color=RED)
    fig.tight_layout(); fig.savefig(OUT / "fig4_resultats.png", dpi=200, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    architecture(); pipeline(); gantt(); results(); print("figures ok")
