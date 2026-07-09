import socket
from tkinter import Tk, filedialog, simpledialog
import os
import hashlib


client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    client.connect(("192.168.88.36", 5000))
    print("Connecte au serveur.")
except ConnectionRefusedError:
    print("Impossible de se connecter : le serveur n'est pas demarre.")
    exit()
# ---------------- Login ----------------
root = Tk()
root.withdraw()

utilisateur = simpledialog.askstring(
    "Connexion",
    "Nom utilisateur :"
)

mot_de_passe = simpledialog.askstring(
    "Connexion",
    "Mot de passe :",
    show="*"
)

root.destroy()


if utilisateur is None or mot_de_passe is None:
    print("Connexion annule.")
    client.close()
    exit()


client.send(
    f"LOGIN|{utilisateur}|{mot_de_passe}\n".encode()
)
reponse = client.recv(4096).decode()

print(reponse)

if not reponse.startswith("OK"):
    print("Connexion refuse.")
    client.close()
    exit()

print("Connexion reussi.")

def calculer_hash(chemin):

    sha256 = hashlib.sha256()

    with open(chemin, "rb") as f:

        while True:

            data = f.read(4096)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()

while True:
    print("\n -Menu- ")
    print("1. List")
    print("2. Envoyer")
    print("3. Telecharger")
    print("4. Quitter")

    choix = input("votre choix : ")

    if choix == "1":
        client.send("LIST\n".encode())

        reponse = client.recv(4096).decode()

        if reponse.startswith("LISTING|"):
            fichiers = reponse.split("|")[1]

            print("\n - Fichiers disponibles -")

            for fichier in fichiers.split(";"):
                if fichier:
                    print("- " + fichier)

        else:
            print(reponse)


    elif choix == "2":

        root = Tk()
        root.withdraw()

        chemin = filedialog.askopenfilename(
            title="Choisir un fichier a envoyer"
        )

        root.destroy()

        if not chemin:
            print("Aucun fichier selectionne.")
            continue

        nom = os.path.basename(chemin)

        taille = os.path.getsize(chemin)

        client.send(f"UPLOAD|{nom}|{taille}\n".encode())


        reponse = client.recv(4096).decode()

        print(reponse)

        if not reponse.startswith("OK"):
            print("Le serveur refuse l'envoi.")
            continue

        with open(chemin, "rb") as f:

            while True:

                data = f.read(4096)

                if not data:
                    break

                client.sendall(data)
                
        reponse = client.recv(4096).decode()

        print(reponse)

        print("Fichier envoye :", nom)

    elif choix == "3":

        nom = input("Nom du fichier a telecharger : ")

        client.send(f"DOWNLOAD|{nom}\n".encode())

        reponse = client.recv(4096).decode()

        if reponse.startswith("ERROR"):
            print(reponse)
            continue

        parties = reponse.strip().split("|")

        if parties[0] == "FILE":

            taille = int(parties[2])
            hash_attendu = parties[3]

            recu = 0

            with open(nom, "wb") as f:

                while recu < taille:
                    
                    data = client.recv(
                        min(4096, taille - recu)
                    )

                    if not data:
                        break

                    f.write(data)

                    recu += len(data)

            print("Telechargement termine.")

            print("Taille reçue :", recu, "octets")

            hash_local = calculer_hash(nom)
            if hash_local == hash_attendu:

                print("Verification integrite reussi.")

            else:

                print("Erreur : fichier corrompu.")
    elif choix == "4":

        client.send("Quitter".encode())

        client.close()

        print("Connexion fermee.")

        break

    else:

        print("Choix invalide.")