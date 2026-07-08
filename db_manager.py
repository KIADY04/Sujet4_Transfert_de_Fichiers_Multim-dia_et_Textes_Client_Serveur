import sqlite3
from datetime import datetime
import os
import threading
import hashlib

DB_PATH = "transferts.db"

# Verrou global : empêche deux threads (= deux clients connectés en même
# temps) d'écrire dans la BDD exactement au même instant.
# Indispensable car le serveur va gérer plusieurs clients avec des threads.
_lock = threading.Lock()


def get_connection():
    """Retourne une connexion à la base de données, configurée pour le multi-thread."""
    conn = sqlite3.connect(DB_PATH, timeout=10)  # attend jusqu'à 10s si la base est occupée
    conn.row_factory = sqlite3.Row  # permet d'accéder aux colonnes par nom
    conn.execute("PRAGMA journal_mode=WAL;")  # autorise lectures/écritures simultanées
    return conn


def initialiser_bdd():
    """
    Crée les tables si elles n'existent pas encore.
    À appeler une seule fois au démarrage du serveur.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fichiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_fichier TEXT NOT NULL,
            type_fichier TEXT NOT NULL,
            taille INTEGER NOT NULL,
            chemin TEXT NOT NULL,
            date_ajout TEXT NOT NULL,
            hash TEXT
        )
    """)

    # Migration : ajoute la colonne 'hash' si la table existait déjà sans elle
    try:
        cur.execute("ALTER TABLE fichiers ADD COLUMN hash TEXT")
    except sqlite3.OperationalError:
        pass  # la colonne existe déjà

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transferts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fichier_id INTEGER NOT NULL,
            client TEXT NOT NULL,
            action TEXT NOT NULL,
            date_transfert TEXT NOT NULL,
            statut TEXT NOT NULL,
            FOREIGN KEY (fichier_id) REFERENCES fichiers (id)
        )
    """)

    conn.commit()
    conn.close()

    # Crée aussi les dossiers de stockage physique s'ils n'existent pas
    for sous_dossier in ["videos", "audios", "textes", "images"]:
        os.makedirs(os.path.join("stockage", sous_dossier), exist_ok=True)

    print("Base de données initialisée avec succès.")


def nom_disponible(nom_fichier):
    """
    Si nom_fichier existe déjà en base, retourne un nouveau nom unique
    en ajoutant un suffixe numérique (ex: video.mp4 -> video_1.mp4).
    Sinon retourne le nom tel quel.
    Évite que 2 clients qui envoient un fichier du même nom s'écrasent.
    """
    base, ext = os.path.splitext(nom_fichier)
    nom_essai = nom_fichier
    compteur = 1
    with _lock:
        conn = get_connection()
        cur = conn.cursor()
        while True:
            cur.execute("SELECT 1 FROM fichiers WHERE nom_fichier = ?", (nom_essai,))
            if cur.fetchone() is None:
                break
            nom_essai = f"{base}_{compteur}{ext}"
            compteur += 1
        conn.close()
    return nom_essai


def ajouter_fichier(nom_fichier, type_fichier, taille, chemin, hash_fichier=None):
    """
    Enregistre un nouveau fichier dans la table 'fichiers'.
    Retourne l'id du fichier créé.

    type_fichier doit être : "video", "audio" ou "texte"
    hash_fichier : empreinte SHA-256 du contenu (utilisée pour détecter les doublons)

    Thread-safe : utilise un verrou car plusieurs clients peuvent
    envoyer des fichiers en même temps (threads différents côté serveur).
    """
    date_ajout = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fichiers (nom_fichier, type_fichier, taille, chemin, date_ajout, hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nom_fichier, type_fichier, taille, chemin, date_ajout, hash_fichier))
        conn.commit()
        fichier_id = cur.lastrowid
        conn.close()

    return fichier_id


def enregistrer_transfert(fichier_id, client, action, statut="succès"):
    """
    Enregistre un événement de transfert (upload ou download).

    action : "UPLOAD" ou "DOWNLOAD"
    statut : "en cours", "succès" ou "échec"

    Astuce : appeler une première fois avec statut="en cours" quand le
    transfert démarre, puis appeler mettre_a_jour_transfert() à la fin
    avec le statut final. Optionnel : si la progression est gérée
    uniquement en mémoire côté serveur/interface, un seul appel final
    avec statut="succès" suffit.
    """
    date_transfert = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transferts (fichier_id, client, action, date_transfert, statut)
            VALUES (?, ?, ?, ?, ?)
        """, (fichier_id, client, action, date_transfert, statut))
        conn.commit()
        transfert_id = cur.lastrowid
        conn.close()

    return transfert_id


def mettre_a_jour_transfert(transfert_id, statut):
    """Met à jour le statut d'un transfert existant (ex: 'en cours' -> 'succès')."""
    with _lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE transferts SET statut = ? WHERE id = ?", (statut, transfert_id))
        conn.commit()
        conn.close()


def lister_fichiers(type_fichier=None):
    """
    Retourne la liste des fichiers disponibles sur le serveur.
    Si type_fichier est précisé ("video", "audio", "texte"), filtre par type.

    Retourne une liste de dictionnaires, facile à envoyer au client
    ou à afficher dans l'interface Tkinter.
    """
    conn = get_connection()
    cur = conn.cursor()

    if type_fichier:
        cur.execute("SELECT * FROM fichiers WHERE type_fichier = ?", (type_fichier,))
    else:
        cur.execute("SELECT * FROM fichiers")

    resultats = [dict(row) for row in cur.fetchall()]
    conn.close()
    return resultats


def calculer_hash(chemin_fichier):
    """
    Calcule l'empreinte SHA-256 du contenu d'un fichier.
    Lit le fichier par morceaux pour ne pas surcharger la mémoire,
    même avec des gros fichiers (vidéos, etc.).
    """
    sha256 = hashlib.sha256()
    with open(chemin_fichier, "rb") as f:
        for morceau in iter(lambda: f.read(65536), b""):
            sha256.update(morceau)
    return sha256.hexdigest()


def obtenir_fichier_par_hash(hash_fichier):
    """
    Retourne les infos d'un fichier déjà présent en base ayant la même
    empreinte (même contenu), ou None si aucun doublon n'existe.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fichiers WHERE hash = ?", (hash_fichier,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def obtenir_fichier_par_nom(nom_fichier):
    """Retourne les infos d'un fichier à partir de son nom (utile pour DOWNLOAD)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fichiers WHERE nom_fichier = ?", (nom_fichier,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def supprimer_fichier(fichier_id):
    """
    Supprime un fichier de la base (et son historique associé).
    Ne supprime PAS le fichier physique sur le disque — ça reste
    la responsabilité du serveur (Personne 1) de le faire avec os.remove().
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM transferts WHERE fichier_id = ?", (fichier_id,))
    cur.execute("DELETE FROM fichiers WHERE id = ?", (fichier_id,))
    conn.commit()
    conn.close()


def mettre_a_jour_fichier(fichier_id, **kwargs):
    """
    Met à jour un ou plusieurs champs d'un fichier existant.
    Exemple : mettre_a_jour_fichier(3, taille=999999, nom_fichier="nouveau.pdf")
    """
    if not kwargs:
        return
    champs = ", ".join(f"{cle} = ?" for cle in kwargs)
    valeurs = list(kwargs.values()) + [fichier_id]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE fichiers SET {champs} WHERE id = ?", valeurs)
    conn.commit()
    conn.close()


def historique_transferts(client=None):
    """
    Retourne l'historique des transferts, avec le nom du fichier associé.
    Si client est précisé, filtre sur ce client.
    """
    conn = get_connection()
    cur = conn.cursor()

    requete = """
        SELECT t.id, f.nom_fichier, t.client, t.action, t.date_transfert, t.statut
        FROM transferts t
        JOIN fichiers f ON t.fichier_id = f.id
    """
    params = ()
    if client:
        requete += " WHERE t.client = ?"
        params = (client,)
    requete += " ORDER BY t.date_transfert DESC"

    cur.execute(requete, params)
    resultats = [dict(row) for row in cur.fetchall()]
    conn.close()
    return resultats


def deviner_type_fichier(nom_fichier):
    """
    Fonction utilitaire : déduit le type (video/audio/texte/image) à partir
    de l'extension du fichier. Pratique pour Personne 1 et Personne 2.
    """
    ext = os.path.splitext(nom_fichier)[1].lower()

    extensions_video = [".mp4", ".avi", ".mkv", ".mov"]
    extensions_audio = [".mp3", ".wav", ".ogg", ".flac", ".m4a"]
    extensions_texte = [".txt", ".doc", ".docx", ".pdf"]
    extensions_image = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
                         ".tiff", ".tif", ".svg", ".ico", ".heic", ".heif", ".jfif"]

    if ext in extensions_video:
        return "video"
    elif ext in extensions_audio:
        return "audio"
    elif ext in extensions_texte:
        return "texte"
    elif ext in extensions_image:
        return "image"
    else:
        return "autre"


# ------------------------------------------------------------------
# Test rapide du module (exécuter directement : python db_manager.py)
# ATTENTION : ce bloc utilise une base de test séparée (test_transferts.db)
# pour ne jamais polluer la vraie base de production (transferts.db).
# ------------------------------------------------------------------
if __name__ == "__main__":
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_transferts.db")

    initialiser_bdd()

    # Exemple d'ajout d'un fichier
    fid = ajouter_fichier("exemple.mp4", "video", 2048000, "stockage/videos/exemple.mp4")
    print(f"Fichier ajouté avec id={fid}")

    # Exemple d'enregistrement de transfert
    enregistrer_transfert(fid, "192.168.1.10", "UPLOAD", "succès")
    print("Transfert enregistré.")

    # Lister les fichiers
    print("\nFichiers disponibles :")
    for f in lister_fichiers():
        print(f)

    # Historique
    print("\nHistorique des transferts :")
    for h in historique_transferts():
        print(h)

    # Test de détection de type
    print("\nType détecté pour 'chanson.mp3':", deviner_type_fichier("chanson.mp3"))