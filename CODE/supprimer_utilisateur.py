import db_manager

db_manager.initialiser_bdd()  # s'assure que la table utilisateurs existe

print("=== Suppression d'un compte utilisateur ===\n")

# Affiche la liste des comptes existants pour aider à choisir le bon nom
conn = db_manager.get_connection()
cur = conn.cursor()
cur.execute("SELECT nom_utilisateur, date_creation FROM utilisateurs ORDER BY id")
comptes = cur.fetchall()
conn.close()

if not comptes:
    print("Aucun compte utilisateur trouvé dans la base.")
    exit()

print("Comptes existants :")
for compte in comptes:
    print(f"  - {compte['nom_utilisateur']} (créé le {compte['date_creation']})")

print()
nom_utilisateur = input("Nom d'utilisateur à supprimer : ").strip()

# Petite confirmation pour éviter une suppression accidentelle
confirmation = input(f"Confirmer la suppression de '{nom_utilisateur}' ? (o/n) : ").strip().lower()

if confirmation != "o":
    print("Suppression annulée.")
    exit()

if db_manager.supprimer_utilisateur(nom_utilisateur):
    print(f"\nUtilisateur '{nom_utilisateur}' supprimé avec succès.")
else:
    print(f"\nAucun utilisateur nommé '{nom_utilisateur}' trouvé (rien n'a été supprimé).")