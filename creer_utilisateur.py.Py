import db_manager

db_manager.initialiser_bdd()  # s'assure que la table utilisateurs existe

nom_utilisateur = input("Nom d'utilisateur à créer : ").strip()
mot_de_passe = input("Mot de passe : ").strip()

if db_manager.creer_utilisateur(nom_utilisateur, mot_de_passe):
    print(f"Utilisateur '{nom_utilisateur}' créé avec succès.")
else:
    print(f"Impossible de créer '{nom_utilisateur}' : ce nom d'utilisateur existe déjà.")