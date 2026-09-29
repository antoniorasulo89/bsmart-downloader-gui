"""
ScaricaLibri — interfaccia facile in 3 passi.
Porting Python dei downloader di https://github.com/Leone25
"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from platforms import PLATFORMS, BY_KEY

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

EMOJI = {
    "bsmart": "📘", "digibook24": "📙", "sanoma": "📗", "zanichelli": "📚",
    "hub": "🎒", "mylim": "📖", "hoepli": "📕",
}

TITLE_FONT = ("Segoe UI", 28, "bold")
STEP_FONT = ("Segoe UI", 19, "bold")
BIG_FONT = ("Segoe UI", 16)
BUTTON_FONT = ("Segoe UI", 18, "bold")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ScaricaLibri 📚")
        self.geometry("780x860")
        self.minsize(680, 700)
        self.session_state = None
        self.books = []
        self.selected_id = None
        self.platform_key = PLATFORMS[0]["key"]
        self.auth_vars = {}
        self.auth_widgets = {}
        self.opt_vars = {}
        self.remember_var = tk.BooleanVar(value=True)
        try:
            import vault as _vault
            _vault.get_creds("__probe__")
            self.vault = _vault
        except Exception:
            self.vault = None
        self._build()

    # ---------- layout ----------
    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(head, text="📚 ScaricaLibri", font=TITLE_FONT).pack()
        ctk.CTkLabel(head, text="I tuoi libri di scuola in PDF — in 3 passi 👇",
                     font=BIG_FONT, text_color="gray70").pack()

        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=16, pady=8)

        # PASSO 1
        f1 = ctk.CTkFrame(body)
        f1.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(f1, text="1️⃣  Scegli la piattaforma", font=STEP_FONT).pack(
            anchor="w", padx=14, pady=(10, 4))
        grid = ctk.CTkFrame(f1, fg_color="transparent")
        grid.pack(fill="x", padx=10, pady=6)
        grid.columnconfigure((0, 1), weight=1)
        self.plat_buttons = {}
        for i, p in enumerate(PLATFORMS):
            b = ctk.CTkButton(grid, text=f"{EMOJI.get(p['key'], '📖')}  {p['label']}",
                              font=BIG_FONT, height=52,
                              command=lambda k=p["key"]: self._select_platform(k))
            b.grid(row=i // 2, column=i % 2, padx=5, pady=5, sticky="ew")
            self.plat_buttons[p["key"]] = b

        # PASSO 2
        self.auth_frame = ctk.CTkFrame(body)
        self.auth_frame.pack(fill="x", padx=8, pady=8)

        # PASSO 3
        f3 = ctk.CTkFrame(body)
        f3.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkLabel(f3, text="3️⃣  Scegli il libro e scarica", font=STEP_FONT).pack(
            anchor="w", padx=14, pady=(10, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_books())
        self.search_entry = ctk.CTkEntry(f3, textvariable=self.search_var, height=44,
                                         font=BIG_FONT, placeholder_text="🔍 Cerca per titolo…")
        self.search_entry.pack(fill="x", padx=14, pady=4)
        self.book_box = ctk.CTkScrollableFrame(f3, height=220)
        self.book_box.pack(fill="both", expand=True, padx=14, pady=4)
        self.book_rows = []
        out_row = ctk.CTkFrame(f3, fg_color="transparent")
        out_row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(out_row, text="📁 Salva in:", font=BIG_FONT).pack(side="left")
        self.out_var = tk.StringVar(value=os.getcwd())
        ctk.CTkEntry(out_row, textvariable=self.out_var).pack(
            side="left", padx=8, expand=True, fill="x")
        ctk.CTkButton(out_row, text="Cambia", width=90,
                      command=self._browse).pack(side="left")
        self.opt_frame = ctk.CTkFrame(f3, fg_color="transparent")
        self.opt_frame.pack(fill="x", padx=14)
        self.dl_btn = ctk.CTkButton(f3, text="⬇️  SCARICA PDF", font=BUTTON_FONT, height=60,
                                    command=self._download_thread, state="disabled")
        self.dl_btn.pack(fill="x", padx=14, pady=8)
        self.prog = ctk.CTkProgressBar(f3, height=16)
        self.prog.pack(fill="x", padx=14, pady=2)
        self.prog.set(0)
        self.status_var = tk.StringVar(value="👆 Prima scegli la piattaforma e accedi.")
        ctk.CTkLabel(f3, textvariable=self.status_var, font=BIG_FONT,
                     wraplength=640, justify="left").pack(anchor="w", padx=14, pady=2)

        # dettagli
        self.log_btn = ctk.CTkButton(body, text="🔍 Mostra dettagli", height=36,
                                     fg_color="transparent", border_width=1,
                                     command=self._toggle_log)
        self.log_btn.pack(padx=8, pady=4)
        self.log = ctk.CTkTextbox(body, height=130, font=("Consolas", 12))

        self._add_edit_bindings()
        self._select_platform(self.platform_key)

    def _edit_target(self, widget=None):
        for w in (widget, self.focus_get()):
            if isinstance(w, (ctk.CTkEntry, ctk.CTkTextbox, tk.Entry, tk.Text)):
                return w
        return None

    @staticmethod
    def _has_selection(w):
        for meth in ("select_present", "selection_present"):
            try:
                if getattr(w, meth)():
                    return True
            except (AttributeError, tk.TclError):
                continue
        return False

    def _edit_op(self, op, widget=None):
        w = self._edit_target(widget)
        if w is None:
            return False
        try:
            if op == "paste":
                try:
                    text = w.clipboard_get()
                except tk.TclError:
                    return False
                if self._has_selection(w):
                    try:
                        w.delete("sel.first", "sel.last")
                    except tk.TclError:
                        pass
                w.insert("insert", text)
            elif op == "copy":
                self.clipboard_clear()
                self.clipboard_append(w.selection_get())
            elif op == "cut":
                self.clipboard_clear()
                self.clipboard_append(w.selection_get())
                w.delete("sel.first", "sel.last")
            elif op == "all":
                if isinstance(w, (ctk.CTkTextbox, tk.Text)):
                    w.tag_add("sel", "1.0", "end-1c")
                else:
                    w.select_range(0, "end")
            return True
        except tk.TclError:
            return False

    def _add_edit_bindings(self):
        self._edit_menu = tk.Menu(self, tearoff=0)
        self._edit_menu.add_command(label="Taglia", command=lambda: self._edit_op("cut"))
        self._edit_menu.add_command(label="Copia", command=lambda: self._edit_op("copy"))
        self._edit_menu.add_command(label="Incolla", command=lambda: self._edit_op("paste"))
        self._edit_menu.add_separator()
        self._edit_menu.add_command(label="Seleziona tutto",
                                    command=lambda: self._edit_op("all"))

        def on_paste_key(e):
            if self._edit_op("paste", getattr(e, "widget", None)):
                return "break"

        def on_copycut_key(op):
            def h(e):
                if self._edit_op(op, getattr(e, "widget", None)):
                    return "break"
            return h

        def on_all_key(e):
            if self._edit_op("all", getattr(e, "widget", None)):
                return "break"

        def on_right_click(event):
            if not isinstance(event.widget, (ctk.CTkEntry, ctk.CTkTextbox,
                                             tk.Entry, tk.Text)):
                return
            try:
                event.widget.focus_set()
                self._edit_menu.tk_popup(event.x_root, event.y_root)
            except tk.TclError:
                pass
            finally:
                try:
                    self._edit_menu.grab_release()
                except tk.TclError:
                    pass

        for seq in ("<Control-v>", "<Control-V>", "<Command-v>"):
            self.bind_all(seq, on_paste_key, add="+")
        for seq in ("<Control-c>", "<Control-C>", "<Command-c>"):
            self.bind_all(seq, on_copycut_key("copy"), add="+")
        for seq in ("<Control-x>", "<Control-X>", "<Command-x>"):
            self.bind_all(seq, on_copycut_key("cut"), add="+")
        for seq in ("<Control-a>", "<Control-A>", "<Command-a>"):
            self.bind_all(seq, on_all_key, add="+")
        self.bind_all("<Button-3>", on_right_click, add="+")

    # ---------- passo 1 ----------
    def _entry(self):
        return BY_KEY[self.platform_key]

    def _select_platform(self, key):
        self.platform_key = key
        for k, b in self.plat_buttons.items():
            b.configure(fg_color=["#2CC985", "#2FA572"] if k == key else ["#3a3a3a", "#3a3a3a"])
        self.session_state = None
        self.books = []
        self.selected_id = None
        self.dl_btn.configure(state="disabled")
        self._render_auth()
        self._filter_books()
        self._set_status("👆 Ora accedi al passo 2.", 0)

    # ---------- passo 2 ----------
    def _render_auth(self):
        for w in self.auth_frame.winfo_children():
            w.destroy()
        self.auth_vars = {}
        self.auth_widgets = {}
        e = self._entry()
        mod = e["mod"]
        ctk.CTkLabel(self.auth_frame, text="2️⃣  Accedi al tuo account", font=STEP_FONT).pack(
            anchor="w", padx=14, pady=(10, 4))
        if not mod.NEEDS_LOGIN:
            ctk.CTkLabel(self.auth_frame, text="✨ Nessun login: vai pure al passo 3!",
                         font=BIG_FONT).pack(anchor="w", padx=14, pady=6)
            self._render_opts()
            return
        if getattr(mod, "AUTH_HELP", None):
            ctk.CTkLabel(self.auth_frame, text=mod.AUTH_HELP, font=("Segoe UI", 13),
                         text_color="gray70", justify="left").pack(anchor="w", padx=14)
        saved = self.vault.get_creds(e["key"]) if self.vault else {}
        for key, label, is_pw, req in mod.AUTH_FIELDS:
            ctk.CTkLabel(self.auth_frame,
                         text=label + ("" if req else "  (solo se serve)"),
                         font=BIG_FONT).pack(anchor="w", padx=14, pady=(6, 0))
            var = tk.StringVar()
            ent = ctk.CTkEntry(self.auth_frame, textvariable=var, height=44, font=BIG_FONT,
                               show="•" if is_pw else "")
            ent.pack(fill="x", padx=14, pady=2)
            self.auth_vars[key] = var
            self.auth_widgets[key] = ent
        if saved:
            if "email" in self.auth_vars:
                self.auth_vars["email"].set(saved.get("email", ""))
            if "password" in self.auth_vars:
                self.auth_vars["password"].set(saved.get("password", ""))
        if self.vault and any(f[2] for f in mod.AUTH_FIELDS):
            ctk.CTkCheckBox(self.auth_frame, text="🔑 Ricordami su questo PC",
                            variable=self.remember_var, font=BIG_FONT).pack(
                                anchor="w", padx=14, pady=4)
        ctk.CTkButton(self.auth_frame, text="🔓 ACCEDI E VEDI I MIEI LIBRI",
                      font=BUTTON_FONT, height=54,
                      command=self._load_books_thread).pack(fill="x", padx=14, pady=10)
        self._render_opts()

    def _render_opts(self):
        for w in self.opt_frame.winfo_children():
            w.destroy()
        self.opt_vars = {}
        for key, label, default in self._entry()["mod"].OPTIONS:
            var = tk.BooleanVar(value=default)
            ctk.CTkCheckBox(self.opt_frame, text=label, variable=var,
                            font=BIG_FONT).pack(anchor="w", pady=2)
            self.opt_vars[key] = var

    # ---------- passo 3 ----------
    def _filter_books(self):
        if not hasattr(self, "book_box"):
            return
        for w in self.book_box.winfo_children():
            w.destroy()
        self.book_rows = []
        q = self.search_var.get().lower()
        shown = 0
        for b in self.books:
            if q and q not in f"{b['id']} {b['title']}".lower():
                continue
            label = b["title"]
            if b.get("ok") is False:
                label += "  (non scaricabile 🙈)"
            row = ctk.CTkButton(self.book_box, text=f"📖  {label}", anchor="w",
                                fg_color="transparent", text_color=("black", "white"),
                                hover_color=("gray75", "gray25"), height=38,
                                command=lambda _id=b["id"]: self._pick(_id))
            row.pack(fill="x", padx=4, pady=2)
            self.book_rows.append((b["id"], row))
            shown += 1
            if shown >= 300:
                break
        self._highlight()

    def _pick(self, book_id):
        self.selected_id = book_id
        self._highlight()
        if self.session_state is not None or not self._entry()["mod"].NEEDS_LOGIN:
            self.dl_btn.configure(state="normal")
        self._set_status(f"✅ Libro scelto! Premi SCARICA PDF. 👇", None)

    def _highlight(self):
        for _id, row in self.book_rows:
            try:
                row.configure(fg_color=["#2CC985", "#2FA572"] if _id == self.selected_id
                              else "transparent")
            except Exception:
                pass

    # ---------- helpers ----------
    def _log(self, msg):
        try:
            self.log.insert("end", msg + "\n")
            self.log.see("end")
        except Exception:
            pass

    def _set_status(self, msg, pct=None):
        try:
            self.status_var.set(msg)
            if pct is not None:
                self.prog.set(max(0.0, min(1.0, pct / 100.0)))
            self.update_idletasks()
        except Exception:
            pass

    def _toggle_log(self):
        if self.log.winfo_manager():
            self.log.pack_forget()
            self.log_btn.configure(text="🔍 Mostra dettagli")
        else:
            self.log.pack(fill="x", padx=8, pady=4)
            self.log_btn.configure(text="🔍 Nascondi dettagli")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get())
        if d:
            self.out_var.set(d)

    def _progress(self, done, total, msg):
        pct = (done / total * 100) if total else 0
        self.after(0, lambda: self._set_status("⏳ " + msg, pct))

    # ---------- rete ----------
    def _load_books_thread(self):
        threading.Thread(target=self._load_books, daemon=True).start()

    def _load_books(self):
        e = self._entry()
        mod = e["mod"]
        creds = {"_site": e["site"]}
        for key, label, _pw, req in mod.AUTH_FIELDS:
            v = self.auth_vars[key].get().strip()
            if req and not v:
                self._popup("Dati mancanti", f"Scrivi: {label} ✏️")
                return
            creds[key] = v
        self._set_status("🔑 Accesso in corso…", 0)
        self._log(f"[{e['label']}] login…")
        try:
            self.session_state = mod.login(creds)
            if self.vault and "password" in creds and creds.get("password"):
                if self.remember_var.get():
                    self.vault.set_creds(e["key"], creds.get("email", ""), creds["password"])
                else:
                    self.vault.del_creds(e["key"])
            if mod.NEEDS_LIST:
                self._set_status("📚 Cerco i tuoi libri…", 0)
                self._log("Carico i libri…")
                self.books = mod.list_books(self.session_state)
                for line in (self.session_state.get("_debug") or []):
                    self._log(f"[diagnostica] {line}")
                n = len(self.books)
                self._log(f"Trovati {n} libri.")
                self.after(0, self._filter_books)
                if self.selected_id and any(b["id"] == self.selected_id for b in self.books):
                    self.dl_btn.configure(state="normal")
                self._set_status(f"🎉 Trovati {n} libri! Tocca il tuo 👇", 0)
            else:
                self.books = mod.list_books(self.session_state)
                if self.books:
                    bid = self.books[0]["id"]
                    self.after(0, lambda: self._pick(bid))
                self._set_status("✅ Pronto! Premi SCARICA PDF. 👇", 0)
        except Exception as ex:
            self._log(f"ERRORE: {ex}")
            self._set_status("😢 Qualcosa non va. Guarda i dettagli. 🔍", 0)
            self._popup("Errore", str(ex))

    def _popup(self, title, msg):
        self.after(0, lambda: messagebox.showinfo(title, msg))

    def _download_thread(self):
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        e = self._entry()
        mod = e["mod"]
        if mod.NEEDS_LOGIN and not self.session_state:
            self._popup("Non connesso", "Prima premi ACCEDI al passo 2 🔓")
            return
        state = self.session_state or mod.login({})
        book_id = self.selected_id
        if not book_id:
            self._popup("Scegli un libro", "Tocca un libro nella lista 👆")
            return
        opts = {k: v.get() for k, v in self.opt_vars.items()}
        self.dl_btn.configure(state="disabled")
        try:
            path = mod.download(state, book_id, self.out_var.get(), opts, self._progress)
            self._log(f"Fatto! Salvato in: {path}")
            self._set_status("🎉 Finito! Trovi il PDF nella cartella. 📁", 100)
            self._popup("Completato 🎉", f"Salvato in:\n{path}")
        except Exception as ex:
            self._log(f"ERRORE: {ex}")
            self._set_status("😢 Errore. Guarda i dettagli. 🔍", 0)
            self._popup("Errore download", str(ex))
        finally:
            self.dl_btn.configure(state="normal")


if __name__ == "__main__":
    App().mainloop()
