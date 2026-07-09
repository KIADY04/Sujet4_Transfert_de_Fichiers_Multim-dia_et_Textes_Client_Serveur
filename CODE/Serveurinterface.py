import socket
import threading
import os
import logging
import glob
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import traceback

import db_manager

# ----------------------- Configuration -----------------------
HOST = "0.0.0.0"  
PORT = 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "stockage")
LOG_PATH = os.path.join(BASE_DIR, "serveur.log")

BUFFER_SIZE = 4096
MAX_TAILLE_FICHIER = int(5 * 1024 * 1024 * 1024)  
CLIENT_TIMEOUT = 3600

COMPTE_PAR_DEFAUT_UTILISATEUR = "admin"
COMPTE_PAR_DEFAUT_MOT_DE_PASSE = "admin123"

# ----------------------- Logs -----------------------
logger = logging.getLogger("serveur")
logger.setLevel(logging.INFO)
_formatteur = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_handler_fichier = logging.FileHandler(LOG_PATH, encoding="utf-8")
_handler_fichier.setFormatter(_formatteur)
_handler_console = logging.StreamHandler()
_handler_console.setFormatter(_formatteur)

logger.addHandler(_handler_fichier)
logger.addHandler(_handler_console)

serveur_socket = None
serveur_actif = False
lbl_statut = None       
btn_demarrer = None     
btn_arreter = None      

# ----------------------- Réseau -----------------------
def envoyer_ligne(conn_socket, texte):
    conn_socket.sendall((texte + "\n").encode("utf-8"))

def recevoir_ligne(conn_socket):
    ligne = b""
    while True:
        try:
            octet = conn_socket.recv(1)
            if not octet: return None
            if octet == b"\n": break
            ligne += octet
        except (socket.timeout, OSError): return None
    return ligne.decode("utf-8")

def recevoir_fichier(conn_socket, chemin_destination, taille, nom_fichier=""):
    recu = 0
    seuil_suivant = 10
    try:
        with open(chemin_destination, "wb") as f:
            while recu < taille:
                morceau = conn_socket.recv(min(BUFFER_SIZE, taille - recu))
                if not morceau: break
                f.write(morceau)
                recu += len(morceau)

                if taille > 0:
                    pourcentage = int((recu / taille) * 100)
                    if pourcentage >= seuil_suivant:
                        logger.info(f"[UPLOAD] '{nom_fichier}' : {pourcentage}% reçu ({recu}/{taille} octets)")
                        seuil_suivant += 10
    except OSError:
        if os.path.exists(chemin_destination): os.remove(chemin_destination)
        raise
    return recu

def envoyer_fichier(conn_socket, chemin_source, taille, nom_fichier=""):
    envoye = 0
    seuil_suivant = 10
    with open(chemin_source, "rb") as f:
        while True:
            morceau = f.read(BUFFER_SIZE)
            if not morceau: break
            conn_socket.sendall(morceau)
            envoye += len(morceau)

            if taille > 0:
                pourcentage = int((envoye / taille) * 100)
                if pourcentage >= seuil_suivant:
                    logger.info(f"[DOWNLOAD] '{nom_fichier}' : {pourcentage}% envoyé ({envoye}/{taille} octets)")
                    seuil_suivant += 10

def nettoyer_fichiers_temporaires():
    motif = os.path.join(STORAGE_DIR, "**", ".tmp_*")
    for chemin in glob.glob(motif, recursive=True):
        try: os.remove(chemin)
        except OSError: pass

# ----------------------- Traitement Client -----------------------
def gerer_client(conn_socket, adresse):
    client_id = f"{adresse[0]}:{adresse[1]}"
    logger.info(f"[+] Nouveau client connecté : {client_id}")
    conn_socket.settimeout(CLIENT_TIMEOUT)

    authentifie = False
    nom_utilisateur = None

    try:
        while True:
            entete = recevoir_ligne(conn_socket)
            if entete is None: break

            parties = entete.split("|")
            commande = parties[0]

            # 1. LOGIN
            if commande == "LOGIN" and len(parties) == 3:
                utilisateur_essai = parties[1]
                mot_de_passe_essai = parties[2]
                if db_manager.verifier_identifiants(utilisateur_essai, mot_de_passe_essai):
                    authentifie = True
                    nom_utilisateur = utilisateur_essai
                    envoyer_ligne(conn_socket, "OK|Connexion réussie")
                else:
                    envoyer_ligne(conn_socket, "ERROR|Identifiants incorrects")
                continue

            # 2. REGISTER
            if commande == "REGISTER" and len(parties) == 3:
                utilisateur_creation = parties[1]
                mot_de_passe_creation = parties[2]
                if db_manager.obtenir_utilisateur(utilisateur_creation) is not None:
                    envoyer_ligne(conn_socket, "ERROR|Ce nom d'utilisateur est déjà pris")
                else:
                    db_manager.creer_utilisateur(utilisateur_creation, mot_de_passe_creation)
                    envoyer_ligne(conn_socket, "OK|Compte créé")
                continue

            # 3. Sécurité
            if not authentifie:
                envoyer_ligne(conn_socket, "ERROR|Authentification requise")
                continue

            # 4. Commandes Cloud
            if commande == "LIST":
                fichiers_disponibles = []
                for f in db_manager.lister_fichiers():
                    if os.path.isfile(f["chemin"]): fichiers_disponibles.append(f["nom_fichier"])
                    else: db_manager.supprimer_fichier(f["id"])
                envoyer_ligne(conn_socket, "LISTING|" + ";".join(fichiers_disponibles))

            elif commande == "UPLOAD" and len(parties) == 3:
                nom_fichier_original = os.path.basename(parties[1])  
                try: taille = int(parties[2])
                except ValueError:
                    envoyer_ligne(conn_socket, "ERROR|Taille invalide")
                    continue

                if taille > MAX_TAILLE_FICHIER:
                    envoyer_ligne(conn_socket, "ERROR|Fichier trop volumineux")
                    continue

                type_fichier = db_manager.deviner_type_fichier(nom_fichier_original)
                sous_dossier = {"video": "videos", "audio": "audios", "texte": "textes", "image": "images"}.get(type_fichier, "textes")
                dossier_dest = os.path.join(STORAGE_DIR, sous_dossier)
                os.makedirs(dossier_dest, exist_ok=True)

                nom_temp = f".tmp_{client_id.replace(':', '_')}_{nom_fichier_original}"
                chemin_temp = os.path.join(dossier_dest, nom_temp)
                envoyer_ligne(conn_socket, "OK|Prêt")

                try: recu = recevoir_fichier(conn_socket, chemin_temp, taille, nom_fichier_original)
                except OSError:
                    envoyer_ligne(conn_socket, "ERROR|Erreur d'écriture")
                    continue

                hash_fichier = db_manager.calculer_hash(chemin_temp)
                existant = db_manager.obtenir_fichier_par_hash(hash_fichier)

                if existant is not None:
                    os.remove(chemin_temp)
                    envoyer_ligne(conn_socket, f"OK|Fichier déjà présent sous le nom '{existant['nom_fichier']}'")
                    continue

                nom_fichier = db_manager.nom_disponible(nom_fichier_original)
                chemin_dest = os.path.join(dossier_dest, nom_fichier)
                os.rename(chemin_temp, chemin_dest)

                fichier_id = db_manager.ajouter_fichier(nom_fichier, type_fichier, recu, chemin_dest, hash_fichier)
                db_manager.enregistrer_transfert(fichier_id, client_id, "UPLOAD")
                envoyer_ligne(conn_socket, f"OK|Fichier '{nom_fichier}' reçu")

            elif commande == "DOWNLOAD" and len(parties) == 2:
                nom_fichier = os.path.basename(parties[1])
                infos = db_manager.obtenir_fichier_par_nom(nom_fichier)
                if infos is None or not os.path.isfile(infos["chemin"]):
                    envoyer_ligne(conn_socket, "ERROR|Fichier introuvable")
                    continue

                chemin_source = infos["chemin"]
                taille = os.path.getsize(chemin_source)
                hash_fichier = infos.get("hash") or ""
                envoyer_ligne(conn_socket, f"FILE|{nom_fichier}|{taille}|{hash_fichier}")
                envoyer_fichier(conn_socket, chemin_source, taille, nom_fichier)
                db_manager.enregistrer_transfert(infos["id"], client_id, "DOWNLOAD")

    except Exception as e:
        logger.error(f"[ERREUR] Exception levée pour le client {client_id} : {e}")
        traceback.print_exc()
    finally:
        conn_socket.close()
        logger.info(f"[-] Client déconnecté : {client_id}")

# ----------------------- Boutons GUI -----------------------
def action_demarrer():
    global serveur_socket, serveur_actif
    if serveur_actif: return
    db_manager.initialiser_bdd()  
    nettoyer_fichiers_temporaires()  

    if db_manager.nombre_utilisateurs() == 0:
        db_manager.creer_utilisateur(COMPTE_PAR_DEFAUT_UTILISATEUR, COMPTE_PAR_DEFAUT_MOT_DE_PASSE)

    try:
        serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serveur_socket.bind((HOST, PORT))
        serveur_socket.listen(5)
        serveur_actif = True
        logger.info(f"=== Serveur démarré sur {HOST}:{PORT} ===")
        lbl_statut.config(text="● SERVEUR EN LIGNE", fg="#30D158")
        btn_demarrer.config(state="disabled")
        btn_arreter.config(state="normal")
        threading.Thread(target=boucle_acceptation, daemon=True).start()
    except Exception as e:
        logger.error(f"Impossible de démarrer : {e}")

def boucle_acceptation():
    global serveur_socket, serveur_actif
    while serveur_actif:
        try:
            conn_socket, adresse = serveur_socket.accept()
            threading.Thread(target=gerer_client, args=(conn_socket, adresse), daemon=True).start()
        except OSError: break

def action_arreter():
    global serveur_socket, serveur_actif
    if not serveur_actif: return
    serveur_actif = False
    if serveur_socket: serveur_socket.close()
    logger.info("=== Serveur arrêté ===")
    lbl_statut.config(text="○ SERVEUR ARRÊTÉ", fg="#FF3B30")
    btn_demarrer.config(state="normal")
    btn_arreter.config(state="disabled")

#Interface
class HandlerTkinter(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
    def emit(self, record):
        log_entry = self.format(record)
        def _append():
            if self.text_widget.winfo_exists():
                self.text_widget.insert(tk.END, log_entry + "\n")
                self.text_widget.see(tk.END)
        if self.text_widget.winfo_exists(): self.text_widget.after(0, _append)

def initialiser_gui():
    global lbl_statut, btn_demarrer, btn_arreter
    root = tk.Tk()
    root.title("Serveur")
    root.geometry("750x600")
    root.configure(bg="#1E1E24")

    frame_top = tk.Frame(root, bg="#2A2A32", height=65)
    frame_top.pack(fill="x", padx=15, pady=10)
    tk.Label(frame_top, text="Console Serveur de Stockage", fg="#FFFFFF", bg="#2A2A32", font=("Helvetica", 12, "bold")).pack(side="left", padx=15, pady=15)
    lbl_statut = tk.Label(frame_top, text="○ SERVEUR ARRÊTÉ", fg="#FF3B30", bg="#2A2A32", font=("Helvetica", 10, "bold"))
    lbl_statut.pack(side="right", padx=15, pady=15)

    frame_buttons = tk.Frame(root, bg="#1E1E24")
    frame_buttons.pack(fill="x", padx=15, pady=5)
    btn_demarrer = tk.Button(frame_buttons, text="▶ Démarrer le Serveur", bg="#30D158", fg="#FFFFFF", font=("Helvetica", 10, "bold"), bd=0, padx=15, pady=8, command=action_demarrer)
    btn_demarrer.pack(side="left", padx=5)
    btn_arreter = tk.Button(frame_buttons, text="■ Arrêter le Serveur", bg="#FF3B30", fg="#FFFFFF", font=("Helvetica", 10, "bold"), bd=0, padx=15, pady=8, state="disabled", command=action_arreter)
    btn_arreter.pack(side="left", padx=5)

    frame_center = tk.Frame(root, bg="#1E1E24")
    frame_center.pack(fill="both", expand=True, padx=15, pady=10)
    txt_logs = ScrolledText(frame_center, bg="#2A2A32", fg="#30D158", font=("Consolas", 10), bd=0, highlightthickness=0)
    txt_logs.pack(fill="both", expand=True)

    handler_gui = HandlerTkinter(txt_logs)
    handler_gui.setFormatter(_formatteur)
    logger.addHandler(handler_gui)
    root.mainloop()

if __name__ == "__main__":
    initialiser_gui()