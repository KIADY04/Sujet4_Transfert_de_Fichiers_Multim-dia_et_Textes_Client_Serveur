import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    client.connect(("10.164.40.2", 5000))
    print("Connecté au serveur.")
except ConnectionRefusedError:
    print("Impossible de se connecter : le serveur n'est pas demarre.")
    exit()

while True:
    print("\n -Menu- ")
    print("1. List")
    print("2. Envoyer")
    print("3. Telecharger")
    print("4. Quitter")

    choix = input("votre choix : ")

    if choix == "1":
        client.send("List".encode())
        reponse = client.recv(4096).decode()
        print(reponse)

    elif choix == "2":
        nom = input("Nom du fichier a envoyer : ")

        client.send(f"Envoyer {nom}".encode())

        with open(nom, "rb") as f:
            client.send(f.read())

        print("Fichier envoye.")

    elif choix == "3":
        nom = input("Nom du fichier a telecharger : ")

        client.send(f"Telecharger {nom}".encode())

        data = client.recv(4096)

        with open(nom, "wb") as f:
            while True:
                data = client.recv(4096)

                if not data:
                    break

                f.write(data)

        print("Telechargement termine.")

    elif choix == "4":
        client.send("Quitter".encode())
        client.close()
        print("Connexion fermee.")
        break

    else:
        print("Choix invalide.")