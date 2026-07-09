import socket
from tkinter import Tk, filedialog, simpledialog, Button
import os
import hashlib

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    client.connect(("192.168.88.36", 5000))
    print("Connecté au serveur.")
except ConnectionRefusedError:
    print("Impossible de se connecter : le serveur n'est pas demarre.")
    exit()

# ---------------- Login / Creation compte ----------------
def creer_compte():
    nouvel_utilisateur = simpledialog.askstring(
        "Creation compte",
        "Nom utilisateur :"
    )

    nouveau_mot_de_passe = simpledialog.askstring(
        "Creation compte",
        "Mot de passe :",
        show="*"
    )

    if nouvel_utilisateur is None or nouveau_mot_de_passe is None:
        print("Creation annule.")
        client.close()
        exit()

    client.send(
        f"REGISTER|{nouvel_utilisateur}|{nouveau_mot_de_passe}\n".encode()
    )
    reponse = client.recv(4096).decode()
    print(reponse)

    if not reponse.startswith("OK"):
        print("Creation compte refuse.")
        client.close()
        exit()
    print("Compte cree avec succes.")

def login():
    utilisateur = simpledialog.askstring(
        "Connexion",
        "Nom utilisateur :"
    )

    mot_de_passe = simpledialog.askstring(
        "Connexion",
        "Mot de passe :",
        show="*"
    )

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

root = Tk()
root.title("Connexion")

def bouton_login():
    root.destroy()
    login()

def bouton_register():
    root.destroy()
    creer_compte()
    login()
    
bouton1 = Button(
    root,
    text="Login",
    command=bouton_login
)

bouton1.pack(
    pady=10
)

bouton2 = Button(
    root,
    text="Registre",
    command=bouton_register
)

bouton2.pack(
    pady=10
)

root.mainloop()
# ---------------- Fonction hash ----------------

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
    
    # ---------------- Pour la liste ----------------
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
     
    # ---------------- Pour envoyer un fichier ----------------       
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
        client.send(
            f"UPLOAD|{nom}|{taille}\n".encode()
        )
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

    # ---------------- Pour telecharger un fichier ----------------
    elif choix == "3":
        
        nom = input("Nom du fichier a telecharger : ")
        client.send(
            f"DOWNLOAD|{nom}\n".encode()
        )

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

    # ---------------- Pour quitter le serveur ----------------
    elif choix == "4":
        
        client.send("Quitter".encode())
        
        client.close()
        
        print("Connexion fermee.")
        
        break

    # ---------------- Pour les choix en dehors de 1-4 ----------------
    else:
        
        print("Choix invalide.")