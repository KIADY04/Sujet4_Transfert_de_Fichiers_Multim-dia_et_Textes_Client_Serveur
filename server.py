import socket
import threading
import os
import logging
import glob

import db_manager

# ----------------------- Configuration -----------------------
HOST = "192.168.88.36"
PORT = 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "stockage")
LOG_PATH = os.path.join(BASE_DIR, "serveur.log")

BUFFER_SIZE = 4096

# Taille maximale acceptée pour un fichier envoyé par un client (1.5  G)
MAX_TAILLE_FICHIER = int(1.5 * 1024 * 1024 * 1024)  # 1.5 Go


# ------------------------ Déconnexion du client après 5 min d'inactivité -----------------------
CLIENT_TIMEOUT = 300  # 5 minutes


# ----------------------- Logs (fichier + console) -----------------------
logger = logging.getLogger("serveur")
logger.setLevel(logging.INFO)

_formatteur = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_handler_fichier = logging.FileHandler(LOG_PATH, encoding="utf-8")
_handler_fichier.setFormatter(_formatteur)

_handler_console = logging.StreamHandler()
_handler_console.setFormatter(_formatteur)

logger.addHandler(_handler_fichier)
logger.addHandler(_handler_console)


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
    en affichant la progression du transfert. Nettoie le fichier partiel
    en cas d'erreur disque (ex: disque plein)."""
    recu = 0
    try:
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
    except OSError as e:
        # Erreur d'écriture disque (ex: disque plein, permissions...) :
        # on nettoie le fichier partiel pour ne pas laisser de déchet
        print()
        logger.error(f"Erreur disque pendant la réception de {chemin_destination} : {e}")
        if os.path.exists(chemin_destination):
            os.remove(chemin_destination)
        raise
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


def nettoyer_fichiers_temporaires():
    """Supprime les fichiers .tmp_* laissés par des uploads interrompus
    (ex: serveur arrêté ou client déconnecté en plein transfert).
    À appeler une seule fois, au démarrage du serveur."""
    motif = os.path.join(STORAGE_DIR, "**", ".tmp_*")
    fichiers_temp = glob.glob(motif, recursive=True)
    for chemin in fichiers_temp:
        try:
            os.remove(chemin)
            logger.info(f"Fichier temporaire orphelin supprimé : {chemin}")
        except OSError as e:
            logger.warning(f"Impossible de supprimer le fichier temporaire {chemin} : {e}")
    if fichiers_temp:
        logger.info(f"{len(fichiers_temp)} fichier(s) temporaire(s) nettoyé(s) au démarrage.")


# ----------------------- Gestion d'un client -----------------------
def gerer_client(conn_socket, adresse):
    client_id = f"{adresse[0]}:{adresse[1]}"
    logger.info(f"[+] Nouveau client connecté : {client_id}")

    # Le socket lèvera une exception socket.timeout s'il ne reçoit rien pendant ce délai
    conn_socket.settimeout(CLIENT_TIMEOUT)

    # Tant que ce client ne s'est pas authentifié avec succès (commande LOGIN),
    # aucune autre commande (LIST, UPLOAD, DOWNLOAD, DELETE) n'est autorisée.
    authentifie = False
    nom_utilisateur = None

    try:
        while True:
            entete = recevoir_ligne(conn_socket)
            if entete is None:
                break  # client déconnecté

            logger.info(f"[{client_id}] Commande reçue : {entete}")
            parties = entete.split("|")
            commande = parties[0]

            # ---------------- LOGIN ----------------
            if commande == "LOGIN" and len(parties) == 3:
                utilisateur_essai = parties[1]
                mot_de_passe_essai = parties[2]

                if db_manager.verifier_identifiants(utilisateur_essai, mot_de_passe_essai):
                    authentifie = True
                    nom_utilisateur = utilisateur_essai
                    envoyer_ligne(conn_socket, "OK|Connexion réussie")
                    logger.info(f"[{client_id}] Authentification réussie : utilisateur='{nom_utilisateur}'")
                else:
                    envoyer_ligne(conn_socket, "ERROR|Identifiants incorrects")
                    logger.warning(f"[{client_id}] Échec d'authentification : utilisateur='{utilisateur_essai}'")
                continue

            # Bloque toute commande tant que le client n'est pas authentifié
            if not authentifie:
                envoyer_ligne(conn_socket, "ERROR|Authentification requise (envoyez LOGIN|utilisateur|mot_de_passe)")
                logger.warning(f"[{client_id}] Commande refusée (non authentifié) : {entete}")
                continue

            # ---------------- LIST ----------------
            if commande == "LIST":
                fichiers_disponibles = []
                for f in db_manager.lister_fichiers():
                    if os.path.isfile(f["chemin"]):
                        fichiers_disponibles.append(f["nom_fichier"])
                    else:
                        # Fichier supprimé manuellement du disque : on nettoie
                        # l'entrée orpheline pour qu'elle n'apparaisse plus
                        db_manager.supprimer_fichier(f["id"])
                        logger.info(f"[{client_id}] Entrée orpheline nettoyée (LIST) : {f['nom_fichier']}")
                envoyer_ligne(conn_socket, "LISTING|" + ";".join(fichiers_disponibles))

            # ---------------- UPLOAD ----------------
            elif commande == "UPLOAD" and len(parties) == 3:
                nom_fichier_original = os.path.basename(parties[1])  # sécurité : pas de chemin
                try:
                    taille = int(parties[2])
                except ValueError:
                    envoyer_ligne(conn_socket, "ERROR|Taille de fichier invalide")
                    continue

                # Refus si le fichier annoncé dépasse la taille maximale autorisée
                if taille > MAX_TAILLE_FICHIER:
                    envoyer_ligne(
                        conn_socket,
                        f"ERROR|Fichier trop volumineux (max {MAX_TAILLE_FICHIER // (1024*1024)} Mo)"
                    )
                    logger.warning(
                        f"[{client_id}] Upload refusé (trop volumineux) : "
                        f"{nom_fichier_original} ({taille} octets)"
                    )
                    continue

                type_fichier = db_manager.deviner_type_fichier(nom_fichier_original)
                sous_dossier = {
                    "video": "videos",
                    "audio": "audios",
                    "texte": "textes",
                    "image": "images",
                }.get(type_fichier, "textes")

                dossier_dest = os.path.join(STORAGE_DIR, sous_dossier)
                os.makedirs(dossier_dest, exist_ok=True)

                # Réception dans un fichier temporaire, le temps de vérifier
                # s'il s'agit d'un doublon (même contenu déjà stocké)
                nom_temp = f".tmp_{client_id.replace(':', '_')}_{nom_fichier_original}"
                chemin_temp = os.path.join(dossier_dest, nom_temp)

                envoyer_ligne(conn_socket, "OK|Prêt à recevoir")

                try:
                    recu = recevoir_fichier(conn_socket, chemin_temp, taille)
                except OSError:
                    envoyer_ligne(conn_socket, "ERROR|Erreur du serveur pendant la réception du fichier")
                    continue

                # Calcule l'empreinte du contenu reçu et cherche un doublon
                hash_fichier = db_manager.calculer_hash(chemin_temp)
                existant = db_manager.obtenir_fichier_par_hash(hash_fichier)

                if existant is not None:
                    # Contenu déjà présent sur le serveur : pas de doublon créé
                    os.remove(chemin_temp)
                    envoyer_ligne(
                        conn_socket,
                        f"OK|Fichier déjà présent sur le serveur sous le nom "
                        f"'{existant['nom_fichier']}' (aucun doublon créé)"
                    )
                    logger.info(f"[{client_id}] Upload ignoré (doublon) : "
                                f"{nom_fichier_original} == {existant['nom_fichier']}")
                    continue

                # Pas de doublon : on choisit un nom final disponible et on
                # renomme le fichier temporaire vers son emplacement définitif
                nom_fichier = db_manager.nom_disponible(nom_fichier_original)
                chemin_dest = os.path.join(dossier_dest, nom_fichier)
                os.rename(chemin_temp, chemin_dest)

                # Enregistrement en base de données
                fichier_id = db_manager.ajouter_fichier(
                    nom_fichier, type_fichier, recu, chemin_dest, hash_fichier
                )
                db_manager.enregistrer_transfert(fichier_id, client_id, "UPLOAD")

                envoyer_ligne(conn_socket, f"OK|Fichier '{nom_fichier}' reçu ({recu} octets)")
                logger.info(f"[{client_id}] Upload terminé : {nom_fichier} ({recu} octets)")

            # ---------------- DOWNLOAD ----------------
            elif commande == "DOWNLOAD" and len(parties) == 2:
                nom_fichier = os.path.basename(parties[1])
                infos = db_manager.obtenir_fichier_par_nom(nom_fichier)

                if infos is None:
                    envoyer_ligne(conn_socket, "ERROR|Fichier introuvable sur le serveur")
                    continue

                if not os.path.isfile(infos["chemin"]):
                    # Le fichier a été supprimé manuellement du disque : on
                    # nettoie l'entrée orpheline pour qu'elle disparaisse du LIST
                    db_manager.supprimer_fichier(infos["id"])
                    envoyer_ligne(conn_socket, "ERROR|Fichier introuvable sur le serveur (entrée supprimée)")
                    logger.info(f"[{client_id}] Entrée orpheline nettoyée : {nom_fichier}")
                    continue

                chemin_source = infos["chemin"]
                taille = os.path.getsize(chemin_source)

                # Le hash est transmis dans l'en-tête pour permettre au client
                # de vérifier l'intégrité du fichier après réception
                hash_fichier = infos.get("hash") or ""
                envoyer_ligne(conn_socket, f"FILE|{nom_fichier}|{taille}|{hash_fichier}")
                envoyer_fichier(conn_socket, chemin_source)

                db_manager.enregistrer_transfert(infos["id"], client_id, "DOWNLOAD")
                logger.info(f"[{client_id}] Download terminé : {nom_fichier} ({taille} octets)")

            # ---------------- DELETE ----------------
            elif commande == "DELETE" and len(parties) == 2:
                nom_fichier = os.path.basename(parties[1])
                infos = db_manager.obtenir_fichier_par_nom(nom_fichier)

                if infos is None:
                    envoyer_ligne(conn_socket, "ERROR|Fichier introuvable sur le serveur")
                    continue

                chemin_fichier = infos["chemin"]

                # Supprime le fichier physique s'il existe encore sur le disque
                if os.path.isfile(chemin_fichier):
                    try:
                        os.remove(chemin_fichier)
                    except OSError as e:
                        envoyer_ligne(conn_socket, f"ERROR|Impossible de supprimer le fichier : {e}")
                        continue

                # Supprime l'entrée en base (fichier + historique associé)
                db_manager.supprimer_fichier(infos["id"])

                envoyer_ligne(conn_socket, f"OK|Fichier '{nom_fichier}' supprimé")
                logger.info(f"[{client_id}] Suppression effectuée : {nom_fichier}")

            else:
                envoyer_ligne(conn_socket, "ERROR|Commande inconnue")

    except socket.timeout:
        logger.info(f"[!] Client inactif depuis {CLIENT_TIMEOUT // 60} min, connexion coupée : {client_id}")
    except ConnectionResetError:
        pass
    finally:
        conn_socket.close()
        logger.info(f"[-] Client déconnecté : {client_id}")


# ----------------------- Démarrage du serveur -----------------------
def demarrer_serveur():
    db_manager.initialiser_bdd()  # crée les tables + les sous-dossiers de stockage
    nettoyer_fichiers_temporaires()  # supprime les .tmp_* laissés par des uploads interrompus

    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur_socket.bind((HOST, PORT))
    serveur_socket.listen(5)

    logger.info(f"=== Serveur démarré sur {HOST}:{PORT} ===")
    logger.info(f"Dossier de stockage : {STORAGE_DIR}")
    logger.info(f"Fichier de logs     : {LOG_PATH}")
    logger.info("En attente de connexions... (Ctrl+C pour arrêter)")

    try:
        while True:
            conn_socket, adresse = serveur_socket.accept()
            thread = threading.Thread(target=gerer_client, args=(conn_socket, adresse), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        logger.info("Arrêt du serveur demandé (Ctrl+C).")
    finally:
        serveur_socket.close()


if __name__ == "__main__":
    demarrer_serveur()