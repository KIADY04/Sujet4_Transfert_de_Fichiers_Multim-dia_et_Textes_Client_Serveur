import socket
import os
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

BUFFER_SIZE = 8192
client = None  # Le socket sera initialisé dynamiquement au moment de la connexion

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

# ----------------------- Interface Graphique Client -----------------------
class ClientStorageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Configuration & Connexion")
        self.root.geometry("720x480")
        self.root.configure(bg="#1E1E24")
        
        self.fichiers_cloud_complet = []
        self.annulation_event = threading.Event()
        self.transfert_en_cours = False

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

        #Configuration serveur
    def creer_ecran_connexion(self):
        self.frame_auth = tk.Frame(self.root, bg="#1E1E24")
        self.frame_auth.place(relx=0.5, rely=0.5, anchor="center")

        lbl_sec = tk.Label(self.frame_auth, text="CONFIGURATION SERVEUR", fg="#007AFF", bg="#1E1E24", font=("Helvetica", 10, "bold"))
        lbl_sec.pack(anchor="w", pady=(0, 10))

        frame_net = tk.Frame(self.frame_auth, bg="#1E1E24")
        frame_net.pack(pady=(0, 15))

        # Champ d'hôte (IP)
        sub_f1 = tk.Frame(frame_net, bg="#1E1E24")
        sub_f1.pack(side="left", padx=(0, 10))
        tk.Label(sub_f1, text="Adresse IP (Host) :", fg="#AEAEB2", bg="#1E1E24", font=("Helvetica", 9)).pack(anchor="w")
        self.ent_host = tk.Entry(sub_f1, bg="#2A2A32", fg="#FFFFFF", bd=0, font=("Helvetica", 10), width=18)
        self.ent_host.insert(0, "127.0.0.1")  
        self.ent_host.pack(pady=5, ipady=4)

        # Champ de Port
        sub_f2 = tk.Frame(frame_net, bg="#1E1E24")
        sub_f2.pack(side="left")
        tk.Label(sub_f2, text="Port :", fg="#AEAEB2", bg="#1E1E24", font=("Helvetica", 9)).pack(anchor="w")
        self.ent_port = tk.Entry(sub_f2, bg="#2A2A32", fg="#FFFFFF", bd=0, font=("Helvetica", 10), width=8)
        self.ent_port.insert(0, "5000") 
        self.ent_port.pack(pady=5, ipady=4)

        canvas_line = tk.Canvas(self.frame_auth, height=1, bg="#2A2A32", highlightthickness=0)
        canvas_line.pack(fill="x", pady=15)

        #Identifiant
        tk.Label(self.frame_auth, text="IDENTIFIANTS COMPTE", fg="#007AFF", bg="#1E1E24", font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 10))

        tk.Label(self.frame_auth, text="Nom d'utilisateur :", fg="#AEAEB2", bg="#1E1E24", font=("Helvetica", 9)).pack(anchor="w")
        self.ent_user = tk.Entry(self.frame_auth, bg="#2A2A32", fg="#FFFFFF", bd=0, font=("Helvetica", 11), width=30)
        self.ent_user.pack(pady=5, ipady=5)

        tk.Label(self.frame_auth, text="Mot de passe :", fg="#AEAEB2", bg="#1E1E24", font=("Helvetica", 9)).pack(anchor="w")
        self.ent_pass = tk.Entry(self.frame_auth, bg="#2A2A32", fg="#FFFFFF", bd=0, font=("Helvetica", 11), show="*", width=30)
        self.ent_pass.pack(pady=5, ipady=5)

        self.var_afficher_mdp = tk.BooleanVar()
        self.chk_afficher = tk.Checkbutton(
            self.frame_auth, text="Afficher le mot de passe", variable=self.var_afficher_mdp,
            bg="#1E1E24", fg="#AEAEB2", selectcolor="#2A2A32", activebackground="#1E1E24",
            font=("Helvetica", 9), command=self.basculer_visibilite_mdp
        )
        self.chk_afficher.pack(anchor="w", pady=5)

        btn_frame = tk.Frame(self.frame_auth, bg="#1E1E24")
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="S'authentifier", bg="#30D158", fg="#FFFFFF", font=("Helvetica", 10, "bold"), bd=0, padx=15, pady=8, command=self.action_login).pack(side="left", padx=5)
        tk.Button(btn_frame, text="S'enregistrer", bg="#2A2A32", fg="#FFFFFF", font=("Helvetica", 10, "bold"), bd=0, padx=15, pady=8, command=self.action_register).pack(side="left", padx=5)

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
            # Connexion réseau à la volée
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

    # Fonctions d'envoi et de réception encapsulées
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
        style.configure("TProgressbar", thickness=15, troughcolor="#2A2A32", background="#007AFF", bordercolor="#2A2A32")

        frame_top = tk.Frame(self.root, bg="#2A2A32", height=60)
        frame_top.pack(fill="x", padx=15, pady=10)
        tk.Label(frame_top, text=f"Espace Cloud Personnel — Membre : {utilisateur}", fg="#30D158", bg="#2A2A32", font=("Helvetica", 11, "bold")).pack(side="left", padx=15, pady=15)
        tk.Button(frame_top, text="Déconnexion", bg="#FF3B30", fg="#FFFFFF", font=("Helvetica", 9, "bold"), bd=0, padx=10, command=self.root.quit).pack(side="right", padx=15, pady=15)

        frame_body = tk.Frame(self.root, bg="#1E1E24")
        frame_body.pack(fill="both", expand=True, padx=15)

        frame_left = tk.Frame(frame_body, bg="#1E1E24")
        frame_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        frame_filtre = tk.Frame(frame_left, bg="#1E1E24")
        frame_filtre.pack(fill="x", pady=(0, 5))
        tk.Label(frame_filtre, text="Filtrer par type :", fg="#AEAEB2", bg="#1E1E24", font=("Helvetica", 10)).pack(side="left", padx=(0, 5))
        
        self.combo_type = ttk.Combobox(frame_filtre, values=["Tous", "Image", "Vidéo", "Audio", "Texte", "Autre"], state="readonly", width=12)
        self.combo_type.current(0)
        self.combo_type.pack(side="left")
        self.combo_type.bind("<<ComboboxSelected>>", lambda e: self.appliquer_filtre_affichage())

        self.listbox_files = tk.Listbox(frame_left, bg="#2A2A32", fg="#FFFFFF", bd=0, highlightthickness=0, font=("Helvetica", 10), selectbackground="#007AFF")
        self.listbox_files.pack(fill="both", expand=True)

        frame_actions = tk.Frame(frame_left, bg="#1E1E24")
        frame_actions.pack(fill="x", pady=10)
        tk.Button(frame_actions, text="🔄 Actualiser", bg="#2A2A32", fg="#FFFFFF", bd=0, pady=6, command=self.action_rafraichir_liste).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(frame_actions, text="📤 Importer / Envoyer", bg="#30D158", fg="#FFFFFF", bd=0, pady=6, font=("Helvetica", 9, "bold"), command=self.action_upload).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(frame_actions, text="📥 Télécharger sous...", bg="#007AFF", fg="#FFFFFF", bd=0, pady=6, font=("Helvetica", 9, "bold"), command=self.action_download).pack(side="left", fill="x", expand=True, padx=2)

        frame_right = tk.Frame(frame_body, bg="#1E1E24")
        frame_right.pack(side="right", fill="both", expand=True)

        self.frame_progress = tk.LabelFrame(frame_right, text=" Transfert en cours ", fg="#FFFFFF", bg="#1E1E24", font=("Helvetica", 9, "bold"), padx=10, pady=10)
        self.frame_progress.pack(fill="x", pady=(0, 10))
        
        self.lbl_progress_statut = tk.Label(self.frame_progress, text="Aucun transfert actif", fg="#AEAEB2", bg="#1E1E24", font=("Helvetica", 9))
        self.lbl_progress_statut.pack(anchor="w", pady=(0, 5))
        
        self.progress_bar = ttk.Progressbar(self.frame_progress, style="TProgressbar", orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", side="left", expand=True, padx=(0, 10))
        
        self.btn_annuler = tk.Button(self.frame_progress, text="✕ Annuler", bg="#FF3B30", fg="#FFFFFF", font=("Helvetica", 9, "bold"), bd=0, padx=10, pady=3, state="disabled", command=self.action_annuler_transfert)
        self.btn_annuler.pack(side="right")

        tk.Label(frame_right, text="Console d'activité réseau :", fg="#AEAEB2", bg="#1E1E24", font=("Helvetica", 10, "bold")).pack(anchor="w", pady=5)
        self.txt_logs = ScrolledText(frame_right, bg="#2A2A32", fg="#30D158", font=("Consolas", 9), bd=0, highlightthickness=0)
        self.txt_logs.pack(fill="both", expand=True)

        self.action_rafraichir_liste()

    def action_annuler_transfert(self):
        if self.transfert_en_cours:
            self.annulation_event.set()
            self.ajouter_log("[ALERTE] Demande d'annulation envoyée...")

    def appliquer_filtre_affichage(self):
        filtre = self.combo_type.get()
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
            
            self.root.after(0, lambda: self.lbl_progress_statut.config(text=f"Envoi : {nom}", fg="#30D158"))
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
            self.root.after(0, lambda: self.lbl_progress_statut.config(text=f"Téléchargement : {nom_fichier}", fg="#007AFF"))
            
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
        self.root.after(0, lambda: self.lbl_progress_statut.config(text="Aucun transfert actif", fg="#AEAEB2"))


if __name__ == "__main__":
    root = tk.Tk()
    app = ClientStorageGUI(root)
    root.mainloop()
    try:
        if client:
            client.sendall("Quitter\n".encode("utf-8"))
            client.close()
    except OSError: pass