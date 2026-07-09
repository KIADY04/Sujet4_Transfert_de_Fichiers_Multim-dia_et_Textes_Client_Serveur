import threading

import server              
import CODE.watcher_register as watcher_register    


def main():
    # Le serveur tourne dans un thread daemon : il s'arrête automatiquement
    # quand le programme principal se termine (donc un seul Ctrl+C suffit).
    thread_serveur = threading.Thread(target=server.demarrer_serveur, daemon=True)
    thread_serveur.start()

    print("=== Serveur + watcher REGISTER démarrés dans le même terminal ===\n")

    # Le watcher tourne dans le thread principal : c'est lui qui reçoit
    # le Ctrl+C et arrête proprement les deux.
    try:
        watcher_register.main()
    except KeyboardInterrupt:
        print("\nArrêt demandé (Ctrl+C). Fermeture du serveur et du watcher.")


if __name__ == "__main__":
    main()