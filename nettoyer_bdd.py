import os
import db_manager

fichiers = db_manager.lister_fichiers()
supprimes = 0

for f in fichiers:
    if not os.path.isfile(f["chemin"]):
        print(f"Entrée orpheline trouvée : {f['nom_fichier']} (chemin manquant : {f['chemin']})")
        db_manager.supprimer_fichier(f["id"])
        supprimes += 1

if supprimes == 0:
    print("Aucune entrée orpheline trouvée. La base est déjà propre.")
else:
    print(f"\n{supprimes} entrée(s) orpheline(s) supprimée(s) de la base.")