"""Construit data/annotated/publications_annotated.csv.

ATTENTION - JEU SYNTHÉTIQUE : les 70 publications sont rédigées par l'équipe à partir de faits publics
(rapports INTERPOL 2025/2026, CybelAngel 2025, bulletins éditeurs) mais ne sont PAS des copies d'articles ;
les victimes sont anonymisées ("une banque d'Afrique du Nord"). Elles servent à tester les composants, pas à
mesurer des performances réelles. Le jeu sera enrichi d'items réels collectés (journal de collecte) avant le mi-parcours.

Protocole d'annotation (labels `action_<profil>`) : règles ci-dessous, écrites avant le calibrage des seuils,
à faire relire par un second membre de l'équipe (accord inter-annotateurs prévu).
"""
import csv
from datetime import date, timedelta
from pathlib import Path

TODAY = date(2026, 11, 8)
HIGH = {"ransomware", "vuln_exploit", "data_leak_sale", "mobile_money_fraud"}

# (catégorie, secteur, région, technologies, cotation, âge en jours, titre, texte)
ITEMS = [
 # --- ransomware
 ("ransomware","banque","MAGHREB",[],"B2",12,"Un groupe de rançongiciel revendique une banque régionale d'Afrique du Nord","Un affilié rançongiciel affirme avoir chiffré les serveurs d'une banque de détail d'Afrique du Nord et menace de publier 300 Go de données de clients si la rançon n'est pas payée."),
 ("ransomware","telecom","WEST",[],"B2",20,"Ransomware group lists a West African mobile operator on its leak site","A ransomware crew added a West African mobile operator to its leak site, claiming theft of subscriber records and billing data before encryption."),
 ("ransomware","telecom","EAST",[],"B3",33,"Rançongiciel : un opérateur d'Afrique de l'Est perturbé","Un opérateur de télécommunications d'Afrique de l'Est signale une interruption de ses systèmes de facturation après une attaque de rançongiciel."),
 ("ransomware","sante","EAST",[],"A2",40,"Hospital network in East Africa hit by ransomware","A hospital network in East Africa restored patient systems from backups after a ransomware incident that disrupted appointment scheduling."),
 ("ransomware","gouv","SOUTH",[],"B2",25,"Ransomware attack on a southern African government agency","A government agency in Southern Africa confirmed a ransomware attack; attackers claim 1.6 TB of internal documents."),
 ("ransomware","banque","GLOBAL",["VMware"],"B3",18,"Ransomware targeting ESXi hypervisors in financial institutions","Operators deploy a Linux encryptor against VMware ESXi hosts in financial institutions after stealing domain admin credentials; shadow copies and backups are deleted first."),
 ("ransomware","general","AFRICA",[],"C3",28,"Rançongiciels en Afrique : hausse des revendications","Les revendications de rançongiciels visant des entreprises africaines progressent, tous secteurs confondus, selon un éditeur de sécurité."),
 ("ransomware","energie","EAST",[],"B2",60,"Suspected ransomware hits power transmission company","A suspected ransomware attack compromised monitoring systems of an electricity transmission company; backups kept supply running."),
 ("ransomware","banque","CI",[],"C3",22,"Banque ivoirienne : alerte sur une tentative de chiffrement","Une banque d'Abidjan indique avoir stoppé une tentative de chiffrement détectée dans la nuit ; une enquête est en cours."),
 ("ransomware","telecom","CI",[],"D4",15,"Opérateur en Côte d'Ivoire : revendication non confirmée","Un groupe revendique l'attaque d'un opérateur mobile en Côte d'Ivoire ; l'opérateur n'a pas confirmé et aucune preuve n'a été publiée."),
 # --- phishing / BEC
 ("phishing_bec","banque","MA",[],"B2",10,"Campagne de phishing imitant des banques marocaines","Une campagne de phishing par SMS et e-mail imite des banques marocaines et redirige vers de faux sites e-banking afin de voler identifiants et OTP."),
 ("phishing_bec","banque","AFRICA",[],"A2",35,"Business email compromise: finance is the most targeted sector","Business email compromise remains the most damaging vector; finance was the most frequently targeted sector, and attackers increasingly use AI to craft convincing emails."),
 ("phishing_bec","telecom","CI",[],"B2",14,"Faux SMS d'opérateur et de mobile money en Côte d'Ivoire","Des SMS imitant un opérateur mobile ivoirien annoncent un gain ou un blocage de compte mobile money et poussent à communiquer un code OTP."),
 ("phishing_bec","general","WEST",[],"A2",30,"BEC activity concentrated in West Africa","Most business email compromise originating in Africa is concentrated in a handful of countries including Nigeria, Ghana and Côte d'Ivoire, with targets in Europe and North America."),
 ("phishing_bec","retail","GLOBAL",[],"C3",50,"Phishing kit targets online shops","A phishing kit clones checkout pages of e-commerce shops to harvest card numbers."),
 ("phishing_bec","banque","EAST",[],"B3",45,"Fake supplier invoices target Kenyan finance teams","Fraudsters send fake invoice change requests to finance teams of Kenyan companies to divert supplier payments."),
 ("phishing_bec","sante","SOUTH",[],"C3",70,"Phishing campaign against hospital staff","A phishing campaign impersonates a health ministry to steal webmail credentials from hospital employees."),
 ("phishing_bec","general","GLOBAL",["Microsoft 365"],"B2",21,"Adversary-in-the-middle phishing against Microsoft 365","An adversary-in-the-middle phishing kit bypasses multifactor authentication on Microsoft 365 accounts and is sold as a service."),
 ("phishing_bec","banque","MA",[],"C3",5,"Faux conseiller bancaire par téléphone (vishing)","Des escrocs se font passer pour le service fraude d'une banque au Maroc et demandent le code reçu par SMS pour annuler un virement."),
 ("phishing_bec","gouv","WEST",[],"C4",80,"Tentative de détournement de paiement dans une administration","Une administration d'Afrique de l'Ouest signale une tentative de détournement de paiement via un faux courriel de fournisseur."),
 # --- fraude mobile money / SIM swap
 ("mobile_money_fraud","telecom","EAST",[],"A2",8,"SIM swap fraud up 327% in Kenya","SIM swap fraud rose 327% in 2025 with more than 123,000 fraudulent SIM cards issued and an estimated USD 3.8 million drained from mobile wallets."),
 ("mobile_money_fraud","telecom","WEST",[],"A2",9,"Mobile money fraud reported by 97% of countries","Nearly all surveyed countries report mobile money fraud; West Africa is a hotspot for account takeover through social engineering of agents."),
 ("mobile_money_fraud","telecom","CI",[],"B3",6,"Fraude mobile money : des agents soupçonnés de complicité","Des agents de distribution d'un opérateur ivoirien sont soupçonnés d'avoir réalisé des échanges de SIM frauduleux pour vider des portefeuilles mobile money."),
 ("mobile_money_fraud","banque","WEST",[],"C3",26,"Faux profils KYC pour ouvrir des comptes mobiles","Des fraudeurs utilisent de faux profils KYC pour ouvrir des comptes et recevoir les fonds de victimes d'arnaques."),
 ("mobile_money_fraud","telecom","EAST",[],"B2",38,"Tanzania SIM swap attempts fall after stricter registration","Attempts fell 19% after stricter SIM registration and biometric checks in Tanzania."),
 ("mobile_money_fraud","telecom","GLOBAL",["USSD"],"B3",44,"USSD session hijacking weakness","A weakness in USSD session handling lets attackers redirect mobile money transactions on some gateways."),
 ("mobile_money_fraud","banque","MA",[],"C3",17,"Hausse des clonages de cartes bancaires au Maroc","Hausse des fraudes par clonage de cartes et captation de codes 3D Secure signalée par des établissements marocains."),
 ("mobile_money_fraud","general","SOUTH",[],"B3",55,"Synthetic identities used to open accounts","AI-generated synthetic identities combining real and fabricated data are used to open bank accounts and register SIM cards."),
 ("mobile_money_fraud","telecom","WEST",[],"B2",12,"Ghana: citizens lost USD 1.3 million to mobile money fraud in a quarter","Ghanaian citizens lost USD 1.3 million to mobile money fraud in the first quarter."),
 ("mobile_money_fraud","retail","EAST",[],"C4",75,"Escroqueries aux paiements sur places de marché","Les arnaques au paiement mobile sur des places de marché en ligne se multiplient chez des vendeurs particuliers."),
 # --- fuite / vente de données
 ("data_leak_sale","banque","MA",[],"B1",11,"Fuite revendiquée sur Telegram visant des institutions marocaines","Un collectif hacktiviste revendique sur Telegram la fuite de documents d'institutions marocaines contenant des données d'employés et d'entreprises, dont des banques, republiés sur des forums."),
 ("data_leak_sale","telecom","CI",[],"C3",7,"Base d'abonnés proposée à la vente","Une base de plusieurs centaines de milliers d'abonnés d'un opérateur d'Afrique de l'Ouest serait proposée sur un forum, avec numéros et pièces d'identité."),
 ("data_leak_sale","banque","GLOBAL",["Fortinet"],"B2",19,"Initial access broker sells VPN access to a bank","An initial access broker advertises Fortinet SSL VPN credentials for a financial institution; price in cryptocurrency."),
 ("data_leak_sale","general","AFRICA",[],"B3",36,"African-origin content on dark web forums up 62%","African-origin content on dark web forums rose 62% year over year, mostly identity documents, SIM PINs, banking credentials and mobile money details."),
 ("data_leak_sale","sante","EAST",[],"C3",52,"Patient records leaked after hospital breach","A hospital in East Africa had patient records published after a breach claimed by an extortion group."),
 ("data_leak_sale","gouv","MAGHREB",[],"B2",65,"Fuite de données dans une administration d'Afrique du Nord","Des fichiers d'une administration nord-africaine sont publiés sur un forum avec 50 000 documents PDF."),
 ("data_leak_sale","telecom","WEST",[],"B3",31,"Stealer logs include operator dealer portal accounts","Infostealer logs sold on a Telegram shop include credentials for operator dealer portals in West Africa."),
 ("data_leak_sale","banque","MAGHREB",[],"B3",23,"Identifiants d'employés de banques du Maghreb dans des logs de stealers","Des journaux d'infostealers mis en vente contiennent des identifiants d'employés de banques du Maghreb."),
 ("data_leak_sale","retail","GLOBAL",[],"C3",58,"Customer database of an online retailer dumped","A customer database of an international online retailer was dumped on a forum."),
 ("data_leak_sale","energie","SOUTH",[],"B3",68,"Employee credentials from a utility on sale","Employee credentials from a southern African utility are advertised on an underground forum."),
 # --- hacktivisme / DDoS
 ("hacktivism_ddos","banque","MA",[],"B2",13,"DDoS revendiqué contre des sites bancaires marocains","Un collectif revendique des attaques DDoS contre des portails de banques marocaines ; les services en ligne ont été ralentis quelques heures."),
 ("hacktivism_ddos","telecom","EAST",[],"A2",42,"46,786 DDoS attacks in Kenya, mostly against telecoms","Kenya recorded more than 46,786 DDoS attacks in the first half of 2025, mostly against telecom infrastructure."),
 ("hacktivism_ddos","gouv","MAGHREB",[],"B3",27,"Défiguration de sites gouvernementaux","Plusieurs sites d'administrations d'Afrique du Nord ont été défigurés par un groupe hacktiviste."),
 ("hacktivism_ddos","general","SOUTH",[],"B3",47,"312 Gbps DDoS recorded in South Africa","A record DDoS of 312 Gbps was observed against organizations in South Africa."),
 ("hacktivism_ddos","telecom","CI",[],"C3",9,"DDoS sur le portail client d'un opérateur ivoirien","Le portail client d'un opérateur mobile ivoirien a été indisponible plusieurs heures suite à une attaque DDoS."),
 ("hacktivism_ddos","banque","WEST",[],"C3",34,"Hacktivist group targets West African banks","A hacktivist group announces a campaign against West African banks over political grievances."),
 ("hacktivism_ddos","education","MAGHREB",[],"C3",62,"Fuite de données d'universités","Des données d'universités sont publiées par un groupe qui revendique une action politique."),
 ("hacktivism_ddos","energie","GLOBAL",[],"B3",72,"Hacktivists claim attacks on industrial control systems","Hacktivists claim intrusions into exposed industrial control systems of water utilities."),
 ("hacktivism_ddos","banque","MA",[],"B2",4,"Revendications contre le Maroc en hausse","Les revendications publiques d'attaques visant des actifs marocains passent de 63 à 88 en deux mois et demi, surtout finance, gouvernement et éducation."),
 ("hacktivism_ddos","general","CI",[],"E4",78,"Appel à des attaques coordonnées sans preuve","Un appel à des attaques coordonnées circule sur un canal de messagerie, sans preuve d'exécution."),
 # --- exploitation de vulnérabilités
 ("vuln_exploit","general","GLOBAL",["Fortinet"],"A1",16,"Actively exploited vulnerability in Fortinet SSL VPN","CISA adds a Fortinet SSL VPN vulnerability to its known exploited list; attackers use it for initial access and ransomware deployment."),
 ("vuln_exploit","general","GLOBAL",["Citrix"],"A1",24,"Citrix gateway flaw exploited in the wild","A critical flaw in Citrix gateways is exploited in the wild to bypass authentication."),
 ("vuln_exploit","general","GLOBAL",["Palo Alto"],"A1",29,"Palo Alto GlobalProtect exploitation observed","Exploitation of a Palo Alto GlobalProtect gateway vulnerability is observed against telecom and government networks."),
 ("vuln_exploit","general","GLOBAL",["Exchange"],"A2",41,"Microsoft Exchange server flaw exploited","Attackers exploit an on-premise Exchange vulnerability to deploy web shells."),
 ("vuln_exploit","general","GLOBAL",["WordPress"],"B2",53,"WordPress plugin vulnerability mass exploited","A popular WordPress plugin flaw is mass exploited to implant backdoors."),
 ("vuln_exploit","general","GLOBAL",["VMware"],"A1",37,"VMware ESXi authentication bypass exploited by ransomware","An ESXi authentication bypass is used by ransomware affiliates to encrypt virtual machines."),
 ("vuln_exploit","telecom","EAST",[],"B3",49,"Ethiopia ranks fifth for vulnerability detections","Ethiopia ranks fifth in Africa for vulnerabilities detected on exposed systems."),
 ("vuln_exploit","general","GLOBAL",["Oracle"],"B3",64,"Oracle application server remote code execution","A remote code execution flaw in an application server is exploited by botnets."),
 ("vuln_exploit","banque","GLOBAL",["SWIFT"],"C3",66,"Trojanized SWIFT client update targets bank staff","Attackers distribute a trojanized SWIFT client update to bank staff."),
 ("vuln_exploit","general","GLOBAL",["Linux"],"B2",57,"OpenSSH flaw under attack","A vulnerability in a widely deployed SSH server is probed by scanners across the internet."),
 # --- hors sujet (dont "négatifs difficiles" : mentionnent un pays ou un secteur sans lien avec la menace)
 ("hors_sujet","none","NONE",[],"C3",3,"New smartphone launch","A manufacturer announces a new smartphone with improved camera and battery life."),
 ("hors_sujet","none","NONE",[],"C3",6,"Résultats sportifs","Le championnat continental débute ce week-end avec plusieurs matchs décisifs."),
 ("hors_sujet","none","NONE",[],"C3",9,"Cloud provider opens a new region","A cloud provider opens a new data center region in Europe."),
 ("hors_sujet","none","NONE",[],"C3",11,"Mise à jour de suite bureautique","Une suite bureautique ajoute de nouvelles fonctions de mise en page et de collaboration."),
 ("hors_sujet","none","NONE",[],"C3",14,"Recette de tajine aux légumes","Une recette de tajine aux légumes de saison pour quatre personnes."),
 ("hors_sujet","none","NONE",[],"C3",18,"Salon du tourisme à Casablanca","Un salon du tourisme s'ouvre à Casablanca avec des exposants venus de plusieurs régions du Maroc."),
 ("hors_sujet","none","NONE",[],"C3",21,"Kenya athletes win marathon","Kenyan athletes won the marathon in Nairobi in record time."),
 ("hors_sujet","none","NONE",[],"C3",26,"Fidélisation : les banques misent sur le cashback","Comment les banques fidélisent leurs clients avec des offres de cashback et des cartes partenaires."),
 ("hors_sujet","none","NONE",[],"C3",30,"Nouveaux forfaits data","Un opérateur mobile lance de nouveaux forfaits data à prix réduit pour les étudiants."),
 ("hors_sujet","none","NONE",[],"C3",35,"Festival de musique à Abidjan","Un festival de musique réunira des artistes ivoiriens à Abidjan le mois prochain."),
]

PROFILES = {
    "zellige": {"sector": "banque", "country": "MA", "sub": "MAGHREB",
                "tech": {"Fortinet", "Microsoft 365", "Active Directory", "VMware", "Oracle", "SWIFT", "Citrix"}},
    "harmattan": {"sector": "telecom", "country": "CI", "sub": "WEST",
                  "tech": {"Palo Alto", "Linux", "Oracle", "Mobile money", "USSD", "VMware", "WordPress"}},
}


def region_level(region, p):
    if region == p["country"]:
        return 2
    if region == p["sub"]:
        return 1
    if region in ("AFRICA", "GLOBAL"):
        return 0
    return -1


def label(cat, sector, region, techs, p):
    if cat == "hors_sujet":
        return "archivage"
    lvl = region_level(region, p)
    tech = any(t in p["tech"] for t in techs)
    if tech and cat in ("ransomware", "vuln_exploit", "data_leak_sale"):
        return "chasse"
    if sector == p["sector"]:
        return "chasse" if lvl >= 1 else "surveillance"
    if sector == "general":
        if lvl >= 1:
            return "chasse" if cat in ("ransomware", "vuln_exploit", "data_leak_sale") else "surveillance"
        if lvl == 0:
            return "surveillance" if (cat in HIGH or cat == "phishing_bec") else "archivage"
        return "surveillance" if cat in ("ransomware", "vuln_exploit") else "archivage"
    if lvl == 2:
        return "surveillance" if cat in HIGH else "archivage"
    if lvl == 1:
        return "surveillance" if cat in ("ransomware", "data_leak_sale", "vuln_exploit") else "archivage"
    return "archivage"


def main():
    out = Path(__file__).with_name("publications_annotated.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "published", "category", "sector_tag", "region_tag", "technologies", "admiralty",
                    "title", "text", "action_zellige", "action_harmattan", "synthetic"])
        for i, (cat, sec, reg, techs, adm, age, title, text) in enumerate(ITEMS, 1):
            w.writerow([f"PUB-{i:03d}", (TODAY - timedelta(days=age)).isoformat(), cat, sec, reg, ";".join(techs), adm,
                        title, text, label(cat, sec, reg, techs, PROFILES["zellige"]),
                        label(cat, sec, reg, techs, PROFILES["harmattan"]), "true"])
    print(f"{len(ITEMS)} publications écrites dans {out}")


if __name__ == "__main__":
    main()
