import time
import re
import os
import db_manager

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serveur.log")

# Repère les lignes du type :
# ... Commande refusée (non authentifié) : REGISTER|nom|motdepasse
MOTIF_REGISTER = re.compile(r"Commande refus\u00e9e \(non authentifi\u00e9\) : REGISTER\|([^|]+)\|([^|\n]+)")


def suivre_log(chemin):
    """Générateur type 'tail -f' : lit les nouvelles lignes ajoutées au fichier."""
    with open(chemin, "r", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)  # ne traite que les nouvelles lignes, pas l'historique
        while True:
            ligne = f.readline()
            if not ligne:
                time.sleep(0.5)
                continue
            yield ligne


def main():
    print(f"Surveillance de {LOG_PATH} pour les tentatives REGISTER...")
    print("(Ctrl+C pour arrêter)")

    db_manager.initialiser_bdd()  # au cas où, ne fait rien si déjà fait

    for ligne in suivre_log(LOG_PATH):
        match = MOTIF_REGISTER.search(ligne)
        if not match:
            continue

        nom_utilisateur = match.group(1).strip()
        mot_de_passe = match.group(2).strip()

        if db_manager.creer_utilisateur(nom_utilisateur, mot_de_passe):
            print(f"[+] Compte créé automatiquement : '{nom_utilisateur}' "
                  f"(le client peut maintenant se reconnecter avec LOGIN)")
        else:
            print(f"[!] Compte '{nom_utilisateur}' existe déjà, ignoré")


if __name__ == "__main__":
    main()