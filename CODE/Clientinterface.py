import socket
import os
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

BUFFER_SIZE = 8192
client = None 

# Palette façon page web iOS (mode sombre)
COULEUR_FOND = "#1E1E24"
COULEUR_PANNEAU = "#26262E"
COULEUR_CHAMP = "#2C2C34"
COULEUR_TEXTE_ATTENUE = "#9A9AA5"
COULEUR_BLEU = "#0A84FF"
COULEUR_VERT = "#30D158"
COULEUR_ROUGE = "#FF453A"


def calculer_hash(chemin):
    sha256 = hashlib.sha256()
    with open(chemin, "rb") as f:
        while True:
            data = f.read(BUFFER_SIZE)
            if not data: break
            sha256.update(data)
    return sha256.hexdigest()

def deviner_type_extension(nom_fichier):
    ext = os.path.splitext(nom_fichier)[1].lower()
    if ext in [".mp4", ".avi", ".mkv", ".mov"]: return "Vidéo"
    elif ext in [".mp3", ".wav", ".ogg", ".flac", ".m4a"]: return "Audio"
    elif ext in [".txt", ".doc", ".docx", ".pdf"]: return "Texte"
    elif ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]: return "Image"
    return "Autre"


def dessiner_rectangle_arrondi(canvas, x1, y1, x2, y2, r, **kwargs):
    """Dessine (sur un Canvas) un rectangle aux coins totalement arrondis."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def eclaircir(couleur_hex, facteur=1.15):
    couleur_hex = couleur_hex.lstrip("#")
    r, g, b = int(couleur_hex[0:2], 16), int(couleur_hex[2:4], 16), int(couleur_hex[4:6], 16)
    r, g, b = min(255, int(r * facteur)), min(255, int(g * facteur)), min(255, int(b * facteur))
    return f"#{r:02X}{g:02X}{b:02X}"


# - Bouton en pilule (style bouton web iOS) -
class BoutonArrondi(tk.Canvas):
    def __init__(self, parent, texte, commande=None, bg_couleur=COULEUR_BLEU, fg_couleur="#FFFFFF",
                 largeur=120, hauteur=40, police=("Helvetica", 10, "bold"), etat="normal"):
        bg_parent = parent.cget("bg")
        super().__init__(parent, width=largeur, height=hauteur, bg=bg_parent,
                          highlightthickness=0, bd=0, cursor="hand2")
        self.commande = commande
        self.texte = texte
        self.bg_couleur = bg_couleur
        self.fg_couleur = fg_couleur
        self.police = police
        self.largeur = largeur
        self.hauteur = hauteur
        self.etat = etat

        self._dessiner(self.bg_couleur)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._survol(True))
        self.bind("<Leave>", lambda e: self._survol(False))
        self.bind("<Configure>", self._on_resize)

    def _dessiner(self, couleur_fond):
        self.delete("all")
        rayon = self.hauteur / 2  
        actif = self.etat != "disabled"
        couleur_reelle = couleur_fond if actif else "#3A3A42"
        couleur_texte = self.fg_couleur if actif else "#75757D"
        dessiner_rectangle_arrondi(self, 1, 1, self.largeur - 1, self.hauteur - 1, rayon,
                                    fill=couleur_reelle, outline="")
        self.create_text(self.largeur / 2, self.hauteur / 2, text=self.texte,
                          fill=couleur_texte, font=self.police)

    def _survol(self, entree):
        if self.etat == "disabled": return
        self._dessiner(eclaircir(self.bg_couleur) if entree else self.bg_couleur)

    def _on_resize(self, event):
        if event.width > 1 and event.height > 1:
            self.largeur, self.hauteur = event.width, event.height
            self._dessiner(self.bg_couleur)

    def _on_click(self, event):
        if self.etat != "disabled" and self.commande:
            self.commande()

    def set_couleur(self, nouvelle_couleur):
        self.bg_couleur = nouvelle_couleur
        self._dessiner(self.bg_couleur)

    def config(self, **kwargs):
        if "state" in kwargs:
            self.etat = kwargs.pop("state")
            self._dessiner(self.bg_couleur)
        if kwargs:
            super().config(**kwargs)

    configure = config


# - Panneau a coins arrondis (carte façon web iOS) -
class PanneauArrondi(tk.Canvas):
    def __init__(self, parent, bg_panneau=COULEUR_PANNEAU, rayon=18, **kwargs):
        bg_parent = parent.cget("bg")
        super().__init__(parent, bg=bg_parent, highlightthickness=0, bd=0, **kwargs)
        self.bg_panneau = bg_panneau
        self.rayon = rayon
        self.interior = tk.Frame(self, bg=bg_panneau)
        self._id_win = None
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        w, h = event.width, event.height
        if w < 2 or h < 2: return
        self.delete("fond")
        dessiner_rectangle_arrondi(self, 1, 1, w - 1, h - 1, self.rayon,
                                    fill=self.bg_panneau, outline="", tags="fond")
        self.tag_lower("fond")
        if self._id_win is None:
            self._id_win = self.create_window(0, 0, anchor="nw", window=self.interior)
        self.coords(self._id_win, 2, 2)
        self.itemconfig(self._id_win, width=w - 4, height=h - 4)


# - Interrupteur façon iOS (remplace la case a cocher) -
class InterrupteurIOS(tk.Canvas):
    def __init__(self, parent, variable, commande=None, largeur=46, hauteur=26):
        bg_parent = parent.cget("bg")
        super().__init__(parent, width=largeur, height=hauteur, bg=bg_parent,
                          highlightthickness=0, bd=0, cursor="hand2")
        self.variable = variable
        self.commande = commande
        self.largeur = largeur
        self.hauteur = hauteur
        self._dessiner()
        self.bind("<Button-1>", self._on_click)

    def _dessiner(self):
        self.delete("all")
        actif = self.variable.get()
        couleur_fond = COULEUR_VERT if actif else "#3A3A42"
        dessiner_rectangle_arrondi(self, 1, 1, self.largeur - 1, self.hauteur - 1, self.hauteur / 2,
                                    fill=couleur_fond, outline="")
        rb = self.hauteur / 2 - 3
        cx = self.largeur - self.hauteur / 2 if actif else self.hauteur / 2
        cy = self.hauteur / 2
        self.create_oval(cx - rb, cy - rb, cx + rb, cy + rb, fill="#FFFFFF", outline="")

    def _on_click(self, event):
        self.variable.set(not self.variable.get())
        self._dessiner()
        if self.commande:
            self.commande()


# - Interface Graphique Client -
class ClientStorageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Configuration & Connexion")
        self.root.geometry("720x480")
        self.root.configure(bg=COULEUR_FOND)

        self.fichiers_cloud_complet = []
        self.annulation_event = threading.Event()
        self.transfert_en_cours = False
        self.filtre_actuel = "Tous"
        self.boutons_filtre = {}

        self.creer_ecran_connexion()

    def ajouter_log(self, texte):
        if hasattr(self, 'txt_logs') and self.txt_logs.winfo_exists():
            self.txt_logs.insert(tk.END, texte + "\n")
            self.txt_logs.see(tk.END)

    def basculer_visibilite_mdp(self):
        if self.var_afficher_mdp.get():
            self.ent_pass.config(show="")
        else:
            self.ent_pass.config(show="*")

    
    def creer_champ_arrondi(self, parent, largeur, hauteur=42, **entry_kwargs):
        panneau = PanneauArrondi(parent, bg_panneau=COULEUR_CHAMP, rayon=hauteur // 2,
                                  width=largeur, height=hauteur)
        entree = tk.Entry(panneau.interior, bg=COULEUR_CHAMP, fg="#FFFFFF", bd=0,
                           highlightthickness=0, insertbackground="#FFFFFF",
                           font=("Helvetica", 11), **entry_kwargs)
        entree.pack(fill="both", expand=True, padx=14, pady=6)
        return panneau, entree

        #Configuration serveur
    def creer_ecran_connexion(self):
        self.frame_auth = tk.Frame(self.root, bg=COULEUR_FOND)
        self.frame_auth.place(relx=0.5, rely=0.5, anchor="center")

        lbl_sec = tk.Label(self.frame_auth, text="CONFIGURATION SERVEUR", fg=COULEUR_BLEU, bg=COULEUR_FOND,
                            font=("Helvetica", 10, "bold"))
        lbl_sec.pack(anchor="w", pady=(0, 10))

        frame_net = tk.Frame(self.frame_auth, bg=COULEUR_FOND)
        frame_net.pack(pady=(0, 15))

        sub_f1 = tk.Frame(frame_net, bg=COULEUR_FOND)
        sub_f1.pack(side="left", padx=(0, 10))
        tk.Label(sub_f1, text="Adresse IP (Host) :", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_FOND,
                 font=("Helvetica", 9)).pack(anchor="w", pady=(0, 5))
        panneau_host, self.ent_host = self.creer_champ_arrondi(sub_f1, largeur=200)
        self.ent_host.insert(0, "127.0.0.1")
        panneau_host.pack()

        sub_f2 = tk.Frame(frame_net, bg=COULEUR_FOND)
        sub_f2.pack(side="left")
        tk.Label(sub_f2, text="Port :", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_FOND,
                 font=("Helvetica", 9)).pack(anchor="w", pady=(0, 5))
        panneau_port, self.ent_port = self.creer_champ_arrondi(sub_f2, largeur=90)
        self.ent_port.insert(0, "5000")
        panneau_port.pack()

        canvas_line = tk.Canvas(self.frame_auth, height=1, bg="#34343D", highlightthickness=0)
        canvas_line.pack(fill="x", pady=15)

        tk.Label(self.frame_auth, text="IDENTIFIANTS COMPTE", fg=COULEUR_BLEU, bg=COULEUR_FOND,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 10))

        tk.Label(self.frame_auth, text="Nom d'utilisateur :", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_FOND,
                 font=("Helvetica", 9)).pack(anchor="w", pady=(0, 5))
        panneau_user, self.ent_user = self.creer_champ_arrondi(self.frame_auth, largeur=340)
        panneau_user.pack(pady=(0, 12))

        tk.Label(self.frame_auth, text="Mot de passe :", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_FOND,
                 font=("Helvetica", 9)).pack(anchor="w", pady=(0, 5))
        panneau_pass, self.ent_pass = self.creer_champ_arrondi(self.frame_auth, largeur=340, show="*")
        panneau_pass.pack()

        ligne_toggle = tk.Frame(self.frame_auth, bg=COULEUR_FOND)
        ligne_toggle.pack(anchor="w", pady=12)
        self.var_afficher_mdp = tk.BooleanVar()
        InterrupteurIOS(ligne_toggle, self.var_afficher_mdp,
                         commande=self.basculer_visibilite_mdp).pack(side="left")
        tk.Label(ligne_toggle, text="Afficher le mot de passe", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_FOND,
                 font=("Helvetica", 9)).pack(side="left", padx=8)

        btn_frame = tk.Frame(self.frame_auth, bg=COULEUR_FOND)
        btn_frame.pack(pady=15)

        BoutonArrondi(btn_frame, "S'authentifier", commande=self.action_login,
                      bg_couleur=COULEUR_VERT, largeur=150, hauteur=42).pack(side="left", padx=5)
        BoutonArrondi(btn_frame, "S'enregistrer", commande=self.action_register,
                      bg_couleur=COULEUR_PANNEAU, largeur=150, hauteur=42).pack(side="left", padx=5)

    def tenter_connexion_socket(self):
        global client
        host_saisi = self.ent_host.get().strip()
        port_saisi = self.ent_port.get().strip()

        if not host_saisi or not port_saisi:
            messagebox.showerror("Configuration invalide", "Veuillez remplir l'Hôte IP et le Port.")
            return False

        try:
            port_int = int(port_saisi)
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((host_saisi, port_int))
            return True
        except ValueError:
            messagebox.showerror("Erreur de type", "Le port doit être un nombre valide.")
            return False
        except Exception as e:
            messagebox.showerror("Échec Réseau", f"Connexion impossible vers {host_saisi}:{port_saisi}\nVérifiez que le serveur tourne.")
            return False

    def action_login(self):
        user = self.ent_user.get().strip()
        password = self.ent_pass.get().strip()
        if not user or not password: return

        def _thread_login():
            if not self.tenter_connexion_socket(): return

            self.envoyer_ligne_interne(f"LOGIN|{user}|{password}")
            reponse = self.recevoir_ligne_interne()
            if reponse and reponse.startswith("OK"):
                self.root.after(0, lambda: self.finaliser_connexion(user))
            else:
                msg = reponse.split("|")[1] if reponse and "|" in reponse else "Identifiants incorrects."
                self.root.after(0, lambda: messagebox.showerror("Échec", msg))

        threading.Thread(target=_thread_login, daemon=True).start()

    def finaliser_connexion(self, user):
        self.frame_auth.destroy()
        self.creer_espace_principal(user)

    def action_register(self):
        user = self.ent_user.get().strip()
        password = self.ent_pass.get().strip()
        if not user or not password: return

        def _thread_register():
            if not self.tenter_connexion_socket(): return

            self.envoyer_ligne_interne(f"REGISTER|{user}|{password}")
            reponse = self.recevoir_ligne_interne()
            if reponse and reponse.startswith("OK"):
                self.root.after(0, lambda: messagebox.showinfo("Succès", "Compte créé ! Cliquez maintenant sur S'authentifier."))
            else:
                msg = reponse.split("|")[1] if reponse and "|" in reponse else "Nom déjà pris."
                self.root.after(0, lambda: messagebox.showerror("Erreur", msg))

        threading.Thread(target=_thread_register, daemon=True).start()

    # Fonctions d'envoi et de reception encapsulees
    def envoyer_ligne_interne(self, texte):
        global client
        if client: client.sendall((texte + "\n").encode("utf-8"))

    def recevoir_ligne_interne(self):
        global client
        if not client: return None
        ligne = b""
        while True:
            try:
                octet = client.recv(1)
                if not octet: return None
                if octet == b"\n": break
                ligne += octet
            except OSError: return None
        return ligne.decode("utf-8")

    def creer_espace_principal(self, utilisateur):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TProgressbar", thickness=12, troughcolor=COULEUR_CHAMP,
                         background=COULEUR_BLEU, bordercolor=COULEUR_CHAMP)

        # - Bandeau supérieur (carte arrondie) -
        panneau_top = PanneauArrondi(self.root, bg_panneau=COULEUR_PANNEAU, rayon=16, height=60)
        panneau_top.pack(fill="x", padx=15, pady=10)
        tk.Label(panneau_top.interior, text=f"Espace Cloud Personnel — Membre : {utilisateur}",
                 fg=COULEUR_VERT, bg=COULEUR_PANNEAU, font=("Helvetica", 11, "bold")).pack(side="left", padx=15, pady=15)
        BoutonArrondi(panneau_top.interior, "Déconnexion", commande=self.root.quit, bg_couleur=COULEUR_ROUGE,
                      largeur=120, hauteur=32, police=("Helvetica", 9, "bold")).pack(side="right", padx=15, pady=14)

        frame_body = tk.Frame(self.root, bg=COULEUR_FOND)
        frame_body.pack(fill="both", expand=True, padx=15)

        # - Colonne gauche -
        frame_left = tk.Frame(frame_body, bg=COULEUR_FOND)
        frame_left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tk.Label(frame_left, text="Filtrer par type", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_FOND,
                 font=("Helvetica", 9)).pack(anchor="w", pady=(0, 5))
        panneau_filtre = tk.Frame(frame_left, bg=COULEUR_FOND)
        panneau_filtre.pack(fill="x", pady=(0, 8))
        for nom in ["Tous", "Image", "Vidéo", "Audio", "Texte", "Autre"]:
            couleur = COULEUR_BLEU if nom == self.filtre_actuel else COULEUR_PANNEAU
            b = BoutonArrondi(panneau_filtre, nom, commande=lambda n=nom: self.definir_filtre(n),
                               bg_couleur=couleur, largeur=64, hauteur=30, police=("Helvetica", 8, "bold"))
            b.pack(side="left", padx=3)
            self.boutons_filtre[nom] = b

        panneau_liste = PanneauArrondi(frame_left, bg_panneau=COULEUR_PANNEAU, rayon=18)
        panneau_liste.pack(fill="both", expand=True)
        self.listbox_files = tk.Listbox(panneau_liste.interior, bg=COULEUR_PANNEAU, fg="#FFFFFF", bd=0,
                                         highlightthickness=0, font=("Helvetica", 10),
                                         selectbackground=COULEUR_BLEU, activestyle="none")
        self.listbox_files.pack(fill="both", expand=True, padx=8, pady=8)

        frame_actions = tk.Frame(frame_left, bg=COULEUR_FOND)
        frame_actions.pack(fill="x", pady=10)
        BoutonArrondi(frame_actions, "🔄 Actualiser", commande=self.action_rafraichir_liste, bg_couleur=COULEUR_PANNEAU,
                      largeur=130, hauteur=38, police=("Helvetica", 9, "bold")).pack(side="left", fill="x", expand=True, padx=2)
        BoutonArrondi(frame_actions, "📤 Importer / Envoyer", commande=self.action_upload, bg_couleur=COULEUR_VERT,
                      largeur=170, hauteur=38, police=("Helvetica", 9, "bold")).pack(side="left", fill="x", expand=True, padx=2)
        BoutonArrondi(frame_actions, "📥 Télécharger sous...", commande=self.action_download, bg_couleur=COULEUR_BLEU,
                      largeur=170, hauteur=38, police=("Helvetica", 9, "bold")).pack(side="left", fill="x", expand=True, padx=2)

        # - Colonne droite -
        frame_right = tk.Frame(frame_body, bg=COULEUR_FOND)
        frame_right.pack(side="right", fill="both", expand=True)

        self.frame_progress = PanneauArrondi(frame_right, bg_panneau=COULEUR_PANNEAU, rayon=16, height=90)
        self.frame_progress.pack(fill="x", pady=(0, 10))
        interieur_progress = self.frame_progress.interior
        tk.Label(interieur_progress, text="TRANSFERT EN COURS", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_PANNEAU,
                 font=("Helvetica", 8, "bold")).pack(anchor="w", padx=14, pady=(10, 0))

        self.lbl_progress_statut = tk.Label(interieur_progress, text="Aucun transfert actif",
                                             fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_PANNEAU, font=("Helvetica", 9))
        self.lbl_progress_statut.pack(anchor="w", padx=14, pady=(3, 8))

        ligne_bar = tk.Frame(interieur_progress, bg=COULEUR_PANNEAU)
        ligne_bar.pack(fill="x", padx=14, pady=(0, 10))
        self.progress_bar = ttk.Progressbar(ligne_bar, style="TProgressbar", orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", side="left", expand=True, padx=(0, 10))

        self.btn_annuler = BoutonArrondi(ligne_bar, "✕ Annuler", commande=self.action_annuler_transfert,
                                          bg_couleur=COULEUR_ROUGE, largeur=90, hauteur=28,
                                          police=("Helvetica", 9, "bold"), etat="disabled")
        self.btn_annuler.pack(side="right")

        tk.Label(frame_right, text="Console d'activité réseau :", fg=COULEUR_TEXTE_ATTENUE, bg=COULEUR_FOND,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=5)
        panneau_console = PanneauArrondi(frame_right, bg_panneau="#151519", rayon=16)
        panneau_console.pack(fill="both", expand=True)
        self.txt_logs = ScrolledText(panneau_console.interior, bg="#151519", fg=COULEUR_VERT,
                                      font=("Consolas", 9), bd=0, highlightthickness=0)
        self.txt_logs.pack(fill="both", expand=True, padx=8, pady=8)

        self.action_rafraichir_liste()

    def definir_filtre(self, nom):
        self.filtre_actuel = nom
        for cle, bouton in self.boutons_filtre.items():
            bouton.set_couleur(COULEUR_BLEU if cle == nom else COULEUR_PANNEAU)
        self.appliquer_filtre_affichage()

    def action_annuler_transfert(self):
        if self.transfert_en_cours:
            self.annulation_event.set()
            self.ajouter_log("[ALERTE] Demande d'annulation envoyée...")

    def appliquer_filtre_affichage(self):
        filtre = self.filtre_actuel
        self.listbox_files.delete(0, tk.END)
        for f in self.fichiers_cloud_complet:
            if filtre == "Tous" or deviner_type_extension(f) == filtre:
                self.listbox_files.insert(tk.END, f)

    def action_rafraichir_liste(self):
        if self.transfert_en_cours: return
        def _thread():
            self.envoyer_ligne_interne("LIST")
            reponse = self.recevoir_ligne_interne()
            if reponse and reponse.startswith("LISTING|"):
                fichiers = reponse.split("|")[1]
                self.fichiers_cloud_complet = [f for f in fichiers.split(";") if f]
                self.root.after(0, self.appliquer_filtre_affichage)
                self.root.after(0, lambda: self.ajouter_log("[INFO] Liste cloud mise à jour."))
        threading.Thread(target=_thread, daemon=True).start()

    def action_upload(self):
        if self.transfert_en_cours:
            messagebox.showwarning("Veuillez patienter", "Un transfert est déjà en cours.")
            return

        chemin = filedialog.askopenfilename(title="Importer un fichier dans le Cloud")
        if not chemin: return

        def _thread_upload():
            global client
            self.transfert_en_cours = True
            self.annulation_event.clear()
            self.root.after(0, lambda: self.btn_annuler.config(state="normal"))

            nom = os.path.basename(chemin)
            taille = os.path.getsize(chemin)

            self.root.after(0, lambda: self.lbl_progress_statut.config(text=f"Envoi : {nom}", fg=COULEUR_VERT))
            self.root.after(0, lambda: self.ajouter_log(f"[UPLOAD] Préparation : '{nom}'..."))

            self.envoyer_ligne_interne(f"UPLOAD|{nom}|{taille}")
            reponse = self.recevoir_ligne_interne()
            if not reponse or not reponse.startswith("OK"):
                self.root.after(0, lambda: self.ajouter_log("[REJET] Le serveur a refusé l'envoi."))
                self.terminer_transfert_gui()
                return

            envoyé = 0
            interrompu = False
            with open(chemin, "rb") as f:
                while envoyé < taille:
                    if self.annulation_event.is_set():
                        interrompu = True
                        break
                    data = f.read(BUFFER_SIZE)
                    if not data: break
                    client.sendall(data)
                    envoyé += len(data)

                    pourcentage = int((envoyé / taille) * 100)
                    self.root.after(0, lambda p=pourcentage: self.progress_bar.config(value=p))

            if interrompu:
                self.root.after(0, lambda: self.ajouter_log("[ANNULÉ] Envoi interrompu par l'utilisateur."))
                client.close()
                messagebox.showerror("Interrompu", "Connexion réinitialisée suite à l'annulation.")
                self.root.quit()
                return

            reponse_finale = self.recevoir_ligne_interne()
            self.root.after(0, lambda: self.ajouter_log(f"[SERVEUR] {reponse_finale}"))
            self.terminer_transfert_gui()
            self.action_rafraichir_liste()

        threading.Thread(target=_thread_upload, daemon=True).start()

    def action_download(self):
        if self.transfert_en_cours:
            messagebox.showwarning("Veuillez patienter", "Un transfert est déjà en cours.")
            return

        selection = self.listbox_files.curselection()
        if not selection:
            messagebox.showwarning("Sélection requise", "Choisissez un fichier dans la liste.")
            return

        nom_fichier = self.listbox_files.get(selection[0])
        chemin_destination = filedialog.asksaveasfilename(title="Enregistrer le fichier sous...", initialfile=nom_fichier)
        if not chemin_destination: return

        def _thread_download():
            global client
            self.transfert_en_cours = True
            self.annulation_event.clear()
            self.root.after(0, lambda: self.btn_annuler.config(state="normal"))
            self.root.after(0, lambda: self.lbl_progress_statut.config(text=f"Téléchargement : {nom_fichier}", fg=COULEUR_BLEU))

            self.envoyer_ligne_interne(f"DOWNLOAD|{nom_fichier}")
            reponse = self.recevoir_ligne_interne()
            if not reponse or reponse.startswith("ERROR"):
                self.root.after(0, lambda: self.ajouter_log("[REJET] Fichier introuvable sur le serveur."))
                self.terminer_transfert_gui()
                return

            parties = reponse.strip().split("|")
            if parties[0] == "FILE":
                taille = int(parties[2])
                hash_attendu = parties[3]
                recu = 0
                interrompu = False

                with open(chemin_destination, "wb") as f:
                    while recu < taille:
                        if self.annulation_event.is_set():
                            interrompu = True
                            break
                        data = client.recv(min(BUFFER_SIZE, taille - recu))
                        if not data: break
                        f.write(data)
                        recu += len(data)

                        pourcentage = int((recu / taille) * 100)
                        self.root.after(0, lambda p=pourcentage: self.progress_bar.config(value=p))

                if interrompu:
                    if os.path.exists(chemin_destination): os.remove(chemin_destination)
                    self.root.after(0, lambda: self.ajouter_log("[ANNULÉ] Téléchargement annulé."))
                    client.close()
                    messagebox.showerror("Interrompu", "Connexion réinitialisée suite à l'annulation.")
                    self.root.quit()
                    return

                self.root.after(0, lambda: self.ajouter_log("[DOWNLOAD] Réception finie. Contrôle SHA-256..."))
                if calculer_hash(chemin_destination) == hash_attendu:
                    self.root.after(0, lambda: self.ajouter_log("[SUCCÈS] Fichier téléchargé et intègre."))
                else:
                    self.root.after(0, lambda: self.ajouter_log("[CORRUPTION] Signatures différentes !"))

                self.terminer_transfert_gui()

        threading.Thread(target=_thread_download, daemon=True).start()

    def terminer_transfert_gui(self):
        self.transfert_en_cours = False
        self.root.after(0, lambda: self.progress_bar.config(value=0))
        self.root.after(0, lambda: self.btn_annuler.config(state="disabled"))
        self.root.after(0, lambda: self.lbl_progress_statut.config(text="Aucun transfert actif", fg=COULEUR_TEXTE_ATTENUE))


if __name__ == "__main__":
    root = tk.Tk()
    app = ClientStorageGUI(root)
    root.mainloop()
    try:
        if client:
            client.sendall("Quitter\n".encode("utf-8"))
            client.close()
    except OSError: pass

