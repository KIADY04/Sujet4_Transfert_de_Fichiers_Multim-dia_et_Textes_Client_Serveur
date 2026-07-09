import sqlite3
from datetime import datetime
import os
import threading
import hashlib
import hmac

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "transferts.db")

_lock = threading.Lock()


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10) 
    conn.row_factory = sqlite3.Row  
    conn.execute("PRAGMA journal_mode=WAL;") 
    return conn


def initialiser_bdd():
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

    try:
        cur.execute("ALTER TABLE fichiers ADD COLUMN hash TEXT")
    except sqlite3.OperationalError:
        pass  

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_utilisateur TEXT NOT NULL UNIQUE,
            sel TEXT NOT NULL,
            hash_mot_de_passe TEXT NOT NULL,
            date_creation TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    for sous_dossier in ["videos", "audios", "textes", "images"]:
        os.makedirs(os.path.join(BASE_DIR, "stockage", sous_dossier), exist_ok=True)

    print("Base de données initialisée avec succès.")


def nom_disponible(nom_fichier):
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
    with _lock:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE transferts SET statut = ? WHERE id = ?", (statut, transfert_id))
        conn.commit()
        conn.close()


def lister_fichiers(type_fichier=None):
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
    sha256 = hashlib.sha256()
    with open(chemin_fichier, "rb") as f:
        for morceau in iter(lambda: f.read(65536), b""):
            sha256.update(morceau)
    return sha256.hexdigest()


def obtenir_fichier_par_hash(hash_fichier):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fichiers WHERE hash = ?", (hash_fichier,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def obtenir_fichier_par_nom(nom_fichier):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fichiers WHERE nom_fichier = ?", (nom_fichier,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def supprimer_fichier(fichier_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM transferts WHERE fichier_id = ?", (fichier_id,))
    cur.execute("DELETE FROM fichiers WHERE id = ?", (fichier_id,))
    conn.commit()
    conn.close()


def mettre_a_jour_fichier(fichier_id, **kwargs):
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
    ext = os.path.splitext(nom_fichier)[1].lower()
    extensions_video = [".mp4", ".avi", ".mkv", ".mov"]
    extensions_audio = [".mp3", ".wav", ".ogg", ".flac", ".m4a"]
    extensions_texte = [".txt", ".doc", ".docx", ".pdf"]
    extensions_image = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".ico", ".heic", ".heif", ".jfif"]

    if ext in extensions_video: return "video"
    elif ext in extensions_audio: return "audio"
    elif ext in extensions_texte: return "texte"
    elif ext in extensions_image: return "image"
    return "autre"


def _hacher_mot_de_passe(mot_de_passe, sel=None):
    if sel is None:
        sel = os.urandom(16).hex()
    hash_calcule = hashlib.pbkdf2_hmac(
        "sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel), 100_000
    ).hex()
    return sel, hash_calcule


def creer_utilisateur(nom_utilisateur, mot_de_passe):
    sel, hash_mdp = _hacher_mot_de_passe(mot_de_passe)
    date_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO utilisateurs (nom_utilisateur, sel, hash_mot_de_passe, date_creation)
                VALUES (?, ?, ?, ?)
            """, (nom_utilisateur, sel, hash_mdp, date_creation))
            conn.commit()
            succes = True
        except sqlite3.IntegrityError:
            succes = False
        conn.close()
    return succes


def obtenir_utilisateur(nom_utilisateur):
    """Vérifie si un utilisateur existe et retourne ses infos."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM utilisateurs WHERE nom_utilisateur = ?", (nom_utilisateur,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def verifier_utilisateur(nom_utilisateur, mot_de_passe):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT sel, hash_mot_de_passe FROM utilisateurs WHERE nom_utilisateur = ?",
        (nom_utilisateur,)
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return False 
    _, hash_calcule = _hacher_mot_de_passe(mot_de_passe, sel=row["sel"])
    return hmac.compare_digest(hash_calcule, row["hash_mot_de_passe"])

verifier_identifiants = verifier_utilisateur


def nombre_utilisateurs():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM utilisateurs")
    total = cur.fetchone()["total"]
    conn.close()
    return total