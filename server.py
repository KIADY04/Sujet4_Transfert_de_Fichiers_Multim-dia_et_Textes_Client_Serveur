import socket
import threading
import os

# ----------------------- Configuration -----------------------
HOST = "10.164.40.2"      
PORT = 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "fichiers_serveur")

BUFFER_SIZE = 4096


# ------------------------ Déconnection du client après 5 min d'inactivité -----------------------
CLIENT_TIMEOUT = 300  # 5 minutes
# ----------------------- Communication réseau (aide) -----------------------
def envoyer_ligne(conn_socket, texte):
    """Envoie une ligne de texte terminée par \\n."""
    conn_socket.sendall((texte + "\n").encode("utf-8"))


def recevoir_ligne(conn_socket):
    """Reçoit une ligne de texte terminée par \\n (en-tête du protocole)."""
    ligne = b""
    while True:
        octet = conn_socket.recv(1)
        if not octet:
            return None
        if octet == b"\n":
            break
        ligne += octet
    return ligne.decode("utf-8")


def recevoir_fichier(conn_socket, chemin_destination, taille):
    """Reçoit exactement `taille` octets et les écrit dans un fichier,
    en affichant la progression du transfert."""
    recu = 0
    with open(chemin_destination, "wb") as f:
        while recu < taille:
            morceau = conn_socket.recv(min(BUFFER_SIZE, taille - recu))
            if not morceau:
                break
            f.write(morceau)
            recu += len(morceau)
            pourcentage = (recu / taille) * 100 if taille > 0 else 100
            print(f"\r  Réception de {os.path.basename(chemin_destination)} : {pourcentage:5.1f}%", end="")
    print()
    return recu


def envoyer_fichier(conn_socket, chemin_source):
    """Envoie le contenu d'un fichier par morceaux, avec affichage de la progression."""
    taille = os.path.getsize(chemin_source)
    envoye = 0
    with open(chemin_source, "rb") as f:
        while True:
            morceau = f.read(BUFFER_SIZE)
            if not morceau:
                break
            conn_socket.sendall(morceau)
            envoye += len(morceau)
            pourcentage = (envoye / taille) * 100 if taille > 0 else 100
            print(f"\r  Envoi de {os.path.basename(chemin_source)} : {pourcentage:5.1f}%", end="")
    print()


# ----------------------- Gestion d'un client -----------------------
def gerer_client(conn_socket, adresse):
    client_id = f"{adresse[0]}:{adresse[1]}"
    print(f"[+] Nouveau client connecté : {client_id}")
    try:
        conn_socket.settimeout(CLIENT_TIMEOUT)  # Définir le délai d'inactivité
    except ConnectionResetError:
        pass
    finally:
        conn_socket.close()  
        print(f"[-] Client déconnecté immédiatement : {client_id}")
        conn_socket.close()
        return
        
    try:
        while True:
            entete = recevoir_ligne(conn_socket)
            if entete is None:
                break  # client déconnecté

            print(f"[{client_id}] Commande reçue : {entete}")
            parties = entete.split("|")
            commande = parties[0]

            # ---------------- LIST ----------------
            if commande == "LIST":
                fichiers = os.listdir(STORAGE_DIR) if os.path.exists(STORAGE_DIR) else []
                envoyer_ligne(conn_socket, "LISTING|" + ";".join(fichiers))

            # ---------------- UPLOAD ----------------
            elif commande == "UPLOAD" and len(parties) == 3:
                nom_fichier = os.path.basename(parties[1])  # sécurité : pas de chemin
                try:
                    taille = int(parties[2])
                except ValueError:
                    envoyer_ligne(conn_socket, "ERROR|Taille de fichier invalide")
                    continue

                os.makedirs(STORAGE_DIR, exist_ok=True)
                chemin_dest = os.path.join(STORAGE_DIR, nom_fichier)

                envoyer_ligne(conn_socket, "OK|Prêt à recevoir")
                recu = recevoir_fichier(conn_socket, chemin_dest, taille)

                envoyer_ligne(conn_socket, f"OK|Fichier '{nom_fichier}' reçu ({recu} octets)")
                print(f"[{client_id}] Upload terminé : {nom_fichier} ({recu} octets)")

            # ---------------- DOWNLOAD ----------------
            elif commande == "DOWNLOAD" and len(parties) == 2:
                nom_fichier = os.path.basename(parties[1])
                chemin_source = os.path.join(STORAGE_DIR, nom_fichier)

                if not os.path.isfile(chemin_source):
                    envoyer_ligne(conn_socket, "ERROR|Fichier introuvable sur le serveur")
                    continue

                taille = os.path.getsize(chemin_source)
                envoyer_ligne(conn_socket, f"FILE|{nom_fichier}|{taille}")
                envoyer_fichier(conn_socket, chemin_source)
                print(f"[{client_id}] Download terminé : {nom_fichier} ({taille} octets)")

            else:
                envoyer_ligne(conn_socket, "ERROR|Commande inconnue")

    except ConnectionResetError:
        pass
    finally:
        conn_socket.close()
        print(f"[-] Client déconnecté : {client_id}")




# ----------------------- Démarrage du serveur -----------------------
def demarrer_serveur():
    os.makedirs(STORAGE_DIR, exist_ok=True)

    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur_socket.bind((HOST, PORT))
    serveur_socket.listen(5)

    print(f"=== Serveur démarré sur {HOST}:{PORT} ===")
    print(f"Dossier de stockage : {STORAGE_DIR}")
    print("En attente de connexions... (Ctrl+C pour arrêter)\n")

    try:
        while True:
            conn_socket, adresse = serveur_socket.accept()
            thread = threading.Thread(target=gerer_client, args=(conn_socket, adresse), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\nArrêt du serveur demandé (Ctrl+C).")
    finally:
        serveur_socket.close()


if __name__ == "__main__":
    demarrer_serveur()