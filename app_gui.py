from platforms.common import safe_error, secret_values
from platforms.network import Operation, Cancelled, scope
"""
Folio — la tua biblioteca, offline.
Porting Python dei downloader di https://github.com/Leone25
"""
import os
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from platforms import PLATFORMS, BY_KEY

import brand as B
from library import Library
from storage import download_folder
from version import VERSION

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class PageNavigation:
    """Navigazione laterale indipendente dal caricamento degli account."""
    def __init__(self, app):
        self.app = app
        self.current = "Libri e download"

    def set(self, name):
        self.current = name
        if name == "Scaricati":
            self.app._refresh_downloaded()
        for key, frame in self.app.page_frames.items():
            if key == name:
                frame.grid()
            else:
                frame.grid_remove()
        for key, button in self.app.nav_buttons.items():
            button.configure(fg_color=B.NAV_HOVER if key == name else "transparent",
                             text_color=B.WHITE if key == name else B.NAV_TEXT)
        if name == "Scaricati":
            self.app.connection_label.grid_remove()
        else:
            self.app.connection_label.grid()
        self.app.page_title.configure(text={"Scaricati": "Biblioteca", "Libri e download": "Nuovi download", "Account e credenziali": "Account"}[name])
        self.app.page_description.configure(text=(
            "I PDF scaricati presenti sul dispositivo." if name == "Scaricati" else
            "Scegli un titolo dalla piattaforma e scaricalo." if name == "Libri e download"
            else "Un accesso separato per ogni piattaforma."))


class App(ctk.CTk):
    def __init__(self):
        import gc
        gc.collect()  # Gli oggetti Tk dei precedenti root si liberano nel thread principale.
        super().__init__()
        self.title(f"Folio {VERSION} — Biblioteca offline")
        self.geometry("1180x820")
        self.minsize(1020, 720)
        self.configure(fg_color=B.PAPER)
        self._brand_icon = tk.PhotoImage(master=self, width=32, height=32)
        self._brand_icon.put(B.NAV, to=(0, 0, 32, 32))
        for rectangle in ((8, 7, 12, 26), (12, 7, 25, 11), (12, 15, 22, 19)):
            self._brand_icon.put(B.PAPER, to=rectangle)
        self.iconphoto(True, self._brand_icon)
        self.local_library = Library()
        self.local_selected = None
        self._edit_tag = f"FolioEdit{id(self)}"
        self.session_state = None
        self.books = []
        self.selected_id = None
        self.platform_key = PLATFORMS[0]["key"]
        self.auth_vars = {}
        self.auth_widgets = {}
        self.opt_vars = {}
        self.remember_var = tk.BooleanVar(value=False)
        self.account_drafts = {}
        self.platform_sessions = {}
        self.last_path = None
        self.operation_buttons = []
        self.busy = False
        self.closing = False
        self.cancel_event = threading.Event()
        self.remember_choices = {}
        self.events = queue.Queue()
        try:
            import vault as _vault
            self.vault = _vault
            try:
                _vault.get_creds("__probe__")
            except OSError:
                pass
        except Exception:
            self.vault = None
        self._build()
        self._event_timer = self.after(50, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._close_requested)

    # ---------- layout ----------
    def _label(self, parent, text, font=B.FONT, color=B.INK, **kwargs):
        return ctk.CTkLabel(parent, text=text, font=font, text_color=color,
                            anchor="w", justify="left", **kwargs)

    def _button(self, parent, text, command, primary=False, **kwargs):
        return ctk.CTkButton(parent, text=text, command=command, height=40,
            corner_radius=6, font=B.STRONG, fg_color=B.ACCENT if primary else B.WHITE,
            hover_color=B.HOVER if primary else B.TINT,
            text_color=B.WHITE if primary else B.INK,
            text_color_disabled="#85938F", border_width=0 if primary else 1,
            border_color=B.LINE, **kwargs)

    def _field(self, parent, **kwargs):
        field = ctk.CTkEntry(parent, height=42, corner_radius=5, font=B.FONT,
            fg_color=B.WHITE, border_color=B.LINE, text_color=B.INK, **kwargs)
        self._attach_edit_tag(field)
        return field

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=B.NAV)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(5, weight=1)
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=24, pady=(28, 32))
        self._label(brand, "folio", ("Georgia", 35, "bold"), B.WHITE).pack(anchor="w")
        self._label(brand, "BIBLIOTECA OFFLINE", ("Segoe UI", 10, "bold"), B.NAV_TEXT).pack(anchor="w")
        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=14)
        self.nav_buttons = {}
        for name, title in (("Scaricati", "Biblioteca"), ("Libri e download", "Nuovi download"), ("Account e credenziali", "Account e accessi")):
            button = ctk.CTkButton(nav, text=title, height=42, anchor="w", corner_radius=6,
                font=B.STRONG, fg_color="transparent", hover_color=B.NAV_HOVER,
                command=lambda n=name: self.pages.set(n))
            button.pack(fill="x", pady=3)
            self.nav_buttons[name] = button
        self._label(sidebar, "PIATTAFORME", ("Segoe UI", 10, "bold"), B.NAV_TEXT).grid(
            row=2, column=0, sticky="w", padx=26, pady=(30, 12))
        platforms = ctk.CTkFrame(sidebar, fg_color="transparent")
        platforms.grid(row=3, column=0, sticky="ew", padx=14)
        self.plat_buttons = {}
        for entry in PLATFORMS:
            key = entry["key"]
            button = ctk.CTkButton(platforms, text=B.PLATFORM_NAMES[key], anchor="w",
                height=37, corner_radius=5, font=B.FONT, fg_color="transparent",
                hover_color=B.NAV_HOVER, text_color=B.NAV_TEXT,
                command=lambda k=key: self._select_platform(k))
            button.pack(fill="x", pady=2)
            self.plat_buttons[key] = button
        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=6, column=0, sticky="ew", padx=24, pady=24)
        self._label(bottom, B.TAGLINE, B.SMALL, B.NAV_TEXT).pack(anchor="w")
        self._label(bottom, "Libri personali. Sempre con te.", ("Segoe UI", 10), B.NAV_TEXT).pack(anchor="w", pady=(6, 0))

        main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=30, pady=24)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        heading = ctk.CTkFrame(main, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        heading.grid_columnconfigure(0, weight=1)
        self.page_title = self._label(heading, "Biblioteca", B.HEADING)
        self.page_title.grid(row=0, column=0, sticky="w")
        self.page_description = self._label(heading, "I tuoi libri, pronti da portare con te.", color=B.MUTED)
        self.page_description.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.connection_label = self._label(heading, "Account da collegare", B.SMALL, B.MUTED)
        self.connection_label.grid(row=0, column=1, sticky="e", padx=8)
        self.page_frames = {}
        for name in ("Scaricati", "Libri e download", "Account e credenziali"):
            frame = ctk.CTkFrame(main, fg_color="transparent", corner_radius=0)
            frame.grid(row=1, column=0, sticky="nsew")
            self.page_frames[name] = frame
        self.pages = PageNavigation(self)
        self._build_downloaded(self.page_frames["Scaricati"])
        self._build_library(self.page_frames["Libri e download"])
        self._build_accounts(self.page_frames["Account e credenziali"])

        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        footer.grid_columnconfigure(0, weight=1)
        self.cancel_button = self._button(footer, "Annulla", self.cancel_event.set, width=90)
        self.cancel_button.grid(row=1, column=2, padx=10)
        self.cancel_button.configure(state="disabled")
        self.prog = ctk.CTkProgressBar(footer, height=4, fg_color=B.LINE, progress_color=B.ACCENT)
        self.prog.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.prog.set(0)
        self.status_var = tk.StringVar(value="Collega un account per caricare la biblioteca.")
        self.status_label = ctk.CTkLabel(footer, textvariable=self.status_var, font=B.SMALL,
            text_color=B.MUTED, anchor="w", justify="left", wraplength=600)
        self.status_label.grid(row=1, column=0, sticky="w")
        self.log_btn = self._button(footer, "Dettagli", self._toggle_log, width=85)
        self.log_btn.grid(row=1, column=1, sticky="e")
        self.log = ctk.CTkTextbox(footer, height=100, font=("Consolas", 11),
            fg_color=B.INK, text_color="#DCE5EB", corner_radius=5)
        self._attach_edit_tag(self.log)
        self._add_edit_bindings()
        self._select_platform(self.platform_key)
        self.pages.set("Scaricati")

    def _build_downloaded(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(3, weight=1)
        toolbar = ctk.CTkFrame(page, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        toolbar.grid_columnconfigure(0, weight=1)
        self._label(toolbar, "LIBRI SUL DISPOSITIVO", B.STRONG).grid(row=0, column=0, sticky="w")
        self._button(toolbar, "Aggiungi PDF", self._import_pdfs).grid(row=0, column=1, padx=8)
        self._button(toolbar, "Aggiorna", self._refresh_downloaded).grid(row=0, column=2)
        self.local_search = tk.StringVar()
        self.local_search.trace_add("write", lambda *a: self._search_local())
        self._label(page, "CERCA TRA I PDF SCARICATI", B.SMALL, B.MUTED).grid(row=1, column=0, sticky="w", pady=(0, 5))
        self._field(page, textvariable=self.local_search).grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.local_box = ctk.CTkScrollableFrame(page, fg_color=B.WHITE, border_color=B.LINE, border_width=1, corner_radius=8)
        self.local_box.grid(row=3, column=0, sticky="nsew")
        self.local_count = self._label(page, "", B.SMALL, B.MUTED)
        self.local_count.grid(row=4, column=0, sticky="w", pady=12)
        self.bind("<FocusIn>", self._local_focus, add="+")

    def _local_focus(self, event):
        if not self.closing and event.widget is self and hasattr(self, "pages") and self.pages.current == "Scaricati":
            self._refresh_downloaded()

    def _search_local(self):
        if hasattr(self, "_search_timer"):
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(180, self._refresh_downloaded)

    def _refresh_downloaded(self):
        if self.closing or not hasattr(self, "local_box"):
            return
        if hasattr(self, "_library_timer"):
            self.after_cancel(self._library_timer)
        self._library_pending = True
        self._library_timer = self.after(80, self._scan_library)

    def _scan_library(self):
        if getattr(self, "_library_scanning", False):
            self._library_timer = self.after(80, self._scan_library)
            return
        self._library_scanning = True
        self._library_pending = False
        folder = self.out_var.get() if hasattr(self, "out_var") else download_folder()
        store = self.local_library
        def worker():
            records, error = [], None
            try:
                store.discover(folder)
                records = store.available()
            except Exception as ex:
                error = safe_error(ex)
            def complete():
                self._library_scanning = False
                if store is self.local_library and not self.closing:
                    if error:
                        self._log(error)
                    if store.warning:
                        self._log(store.warning)
                    self._render_downloaded(records)
            self.events.put(complete)
        self._library_thread = threading.Thread(target=worker, daemon=True)
        self._library_thread.start()

    def _render_downloaded(self, available):
        query = self.local_search.get().strip().lower()
        records = [r for r in available if query in r["title"].lower()]
        for child in self.local_box.winfo_children():
            child.destroy()
        self.local_count.configure(text=f"{len(records)} PDF disponibili sul dispositivo")
        for record in records[:100]:
            row = ctk.CTkFrame(self.local_box, fg_color=B.WHITE, border_width=1, border_color=B.LINE, corner_radius=6)
            row.pack(fill="x", padx=12, pady=6)
            row.grid_columnconfigure(0, weight=1)
            self._label(row, record.get("title") or os.path.basename(record["path"]), B.STRONG, wraplength=490).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))
            self._label(row, record["path"], B.SMALL, B.MUTED, wraplength=490).grid(row=1, column=0, sticky="w", padx=16, pady=(4, 12))
            self._button(row, "Apri PDF", lambda p=record["path"]: self._open_local(p), primary=True, width=90).grid(row=0, column=1, padx=12, pady=8)
            self._button(row, "Cartella", lambda p=record["path"]: self._open_local(p, folder=True), width=90).grid(row=1, column=1, padx=12, pady=8)
        if len(records) > 100:
            self._label(self.local_box, "Mostrati i primi 100 risultati. Usa la ricerca per trovare un titolo.", color=B.MUTED).pack(pady=12)
        if not records:
            self._label(self.local_box, "Nessun risultato" if query else "La tua biblioteca offline", ("Georgia", 26)).pack(anchor="w", padx=28, pady=(45, 12))
            self._label(self.local_box, "Prova un altro titolo." if query else "Qui compaiono i PDF scaricati, finché il file esiste.\nPuoi aggiungere anche PDF scaricati in precedenza.", color=B.MUTED, wraplength=550).pack(anchor="w", padx=28, pady=8)
            self._button(self.local_box, "Scarica un libro", lambda: self.pages.set("Libri e download"), primary=True).pack(anchor="w", padx=28, pady=18)

    def _import_pdfs(self):
        files = filedialog.askopenfilenames(title="Aggiungi libri alla biblioteca", filetypes=[("Libri PDF", "*.pdf")])
        try:
            for file in files:
                self.local_library.add(file)
        except OSError as ex:
            self._popup("Indice biblioteca", str(ex))
        self._refresh_downloaded()

    def _open_local(self, path, folder=False):
        if not os.path.isfile(path):
            self._refresh_downloaded()
            self._popup("File non disponibile", "Il PDF è stato spostato o eliminato. Puoi aggiungerlo di nuovo dalla sua nuova cartella.")
            return
        import subprocess
        import sys
        target = os.path.dirname(path) if folder else path
        try:
            if sys.platform == "win32":
                os.startfile(target)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target])
        except OSError as ex:
            self._popup("Apertura non riuscita", str(ex))

    def _build_library(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, minsize=284)
        page.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(page, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        toolbar.grid_columnconfigure(0, weight=1)
        self.platform_title = self._label(toolbar, "", B.SECTION)
        self.platform_title.grid(row=0, column=0, sticky="w")
        self.connect_button = self._button(toolbar, "Collega account", self._library_connect)
        self.connect_button.grid(row=0, column=1)
        self.operation_buttons.append(self.connect_button)
        library = ctk.CTkFrame(page, fg_color=B.WHITE, border_color=B.LINE, border_width=1, corner_radius=8)
        library.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        library.grid_columnconfigure(0, weight=1)
        library.grid_rowconfigure(3, weight=1)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_books())
        self.search_entry = self._field(library, textvariable=self.search_var, placeholder_text="Cerca titolo o codice libro")
        self._label(library, "CERCA NELLA BIBLIOTECA", ("Segoe UI", 10, "bold"), B.MUTED).grid(row=0, column=0, sticky="w", padx=20, pady=(14, 0))
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 8))
        self.book_count = self._label(library, "", B.SMALL, B.MUTED)
        self.book_count.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 8))
        self.book_box = ctk.CTkScrollableFrame(library, fg_color=B.WHITE, corner_radius=0,
            scrollbar_button_color=B.LINE, scrollbar_button_hover_color=B.MUTED)
        self.book_box.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self.book_rows = []

        inspector = ctk.CTkScrollableFrame(page, width=260, fg_color="#EAEDE7", corner_radius=8)
        inspector.grid(row=1, column=1, sticky="nsew")
        self._label(inspector, "PREPARA IL DOWNLOAD", ("Segoe UI", 10, "bold"), B.MUTED).pack(anchor="w", padx=16, pady=(20, 22))
        self.selection_label = self._label(inspector, "Seleziona un libro", ("Georgia", 23), wraplength=235)
        self.selection_label.pack(anchor="w", padx=16)
        self.selection_meta = self._label(inspector, "I dettagli compariranno qui.", B.SMALL, B.MUTED, wraplength=230)
        self.selection_meta.pack(anchor="w", padx=16, pady=(8, 24))
        self._label(inspector, "CARTELLA DI DESTINAZIONE", ("Segoe UI", 10, "bold"), B.MUTED).pack(anchor="w", padx=16)
        self.out_var = tk.StringVar(value=download_folder())
        self._field(inspector, textvariable=self.out_var).pack(fill="x", padx=16, pady=(8, 6))
        self._button(inspector, "Scegli cartella", self._browse).pack(fill="x", padx=16)
        self.opt_frame = ctk.CTkFrame(inspector, fg_color="transparent")
        self.opt_frame.pack(fill="x", padx=16, pady=(20, 10))
        self.dl_btn = self._button(inspector, "Scarica PDF", self._download_thread, primary=True, state="disabled")
        self.dl_btn.pack(fill="x", padx=16, pady=12)
        self.download_hint = self._label(inspector, "Seleziona un titolo dalla biblioteca per continuare.", B.SMALL, B.MUTED, wraplength=225)
        self.download_hint.pack(anchor="w", padx=16, pady=(0, 18))
        self.open_button = self._button(inspector, "Apri cartella del download", self._open_output)
        self._label(inspector, "Per copie personali dei libri a cui hai accesso.", B.SMALL, B.MUTED, wraplength=225).pack(anchor="w", padx=16, pady=(18, 20))

    def _build_accounts(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, minsize=250)
        page.grid_rowconfigure(1, weight=1)
        self.account_platform = ctk.CTkOptionMenu(page,
            values=[p["label"] for p in PLATFORMS], command=self._choose_account,
            height=40, font=B.STRONG, fg_color=B.WHITE, text_color=B.INK,
            button_color=B.ACCENT, button_hover_color=B.HOVER,
            dropdown_fg_color=B.WHITE, dropdown_text_color=B.INK,
            dropdown_hover_color=B.TINT)
        self.account_platform.grid(row=0, column=0, sticky="ew", padx=(0, 22), pady=(0, 16))
        self.auth_frame = ctk.CTkScrollableFrame(page, fg_color=B.WHITE, corner_radius=8,
            border_width=1, border_color=B.LINE)
        self.auth_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 22))
        privacy = ctk.CTkFrame(page, fg_color="transparent", width=250)
        privacy.grid(row=1, column=1, sticky="nsew")
        self._label(privacy, "Il controllo resta tuo.", ("Georgia", 23), wraplength=230).pack(anchor="w", pady=(14, 18))
        for title, description in (
            ("Solo per questa sessione", "Di base, email, password e token restano in memoria e non vengono salvati."),
            ("Salvataggio facoltativo", "Scegli tu se conservarli nel portachiavi sicuro del dispositivo."),
            ("Un account alla volta", "Ogni piattaforma mantiene il proprio accesso. Puoi rimuoverlo in qualsiasi momento.")):
            self._label(privacy, title, B.STRONG).pack(anchor="w", pady=(12, 4))
            self._label(privacy, description, color=B.MUTED, wraplength=225).pack(anchor="w")

    def _library_connect(self):
        if self.session_state is not None:
            self._load_books_thread()
        else:
            self.pages.set("Account e credenziali")
            if "email" in self.auth_widgets:
                self.auth_widgets["email"].focus_set()

    def _open_output(self):
        if not self.last_path:
            return
        import subprocess
        import sys
        folder = os.path.dirname(os.path.abspath(self.last_path))
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])
        except OSError as ex:
            self._popup("Cartella non disponibile", str(ex))

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
        if isinstance(w, (ctk.CTkTextbox, tk.Text)):
            return bool(w.tag_ranges("sel"))
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
                text = w.selection_get()
                self.clipboard_clear()
                self.clipboard_append(text)
            elif op == "cut":
                text = w.selection_get()
                self.clipboard_clear()
                self.clipboard_append(text)
                w.delete("sel.first", "sel.last")
            elif op == "all":
                if isinstance(w, (ctk.CTkTextbox, tk.Text)):
                    w.tag_add("sel", "1.0", "end-1c")
                else:
                    w.select_range(0, "end")
            return True
        except tk.TclError:
            return False

    def _attach_edit_tag(self, widget):
        if isinstance(widget, (tk.Entry, tk.Text)):
            widget.bindtags((self._edit_tag,) + tuple(t for t in widget.bindtags() if t != self._edit_tag))
        for child in widget.winfo_children():
            self._attach_edit_tag(child)

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
            self.bind_class(self._edit_tag, seq, on_paste_key)
        for seq in ("<Control-c>", "<Control-C>", "<Command-c>"):
            self.bind_class(self._edit_tag, seq, on_copycut_key("copy"))
        for seq in ("<Control-x>", "<Control-X>", "<Command-x>"):
            self.bind_class(self._edit_tag, seq, on_copycut_key("cut"))
        for seq in ("<Control-a>", "<Control-A>", "<Command-a>"):
            self.bind_class(self._edit_tag, seq, on_all_key)
        self.bind_class(self._edit_tag, "<<Paste>>", on_paste_key)
        self.bind_class(self._edit_tag, "<<Copy>>", on_copycut_key("copy"))
        self.bind_class(self._edit_tag, "<<Cut>>", on_copycut_key("cut"))
        self.bind_all("<Button-3>", on_right_click, add="+")

    # ---------- passo 1 ----------
    def _entry(self):
        return BY_KEY[self.platform_key]

    def _choose_account(self, label):
        self._select_platform(next(p["key"] for p in PLATFORMS if p["label"] == label))
        self.pages.set("Account e credenziali")
        self.account_platform.set(self._entry()["label"])

    def _select_platform(self, key):
        if self.busy:
            self._set_status("Attendi il completamento dell’operazione in corso.")
            return
        if self.auth_vars:
            self.account_drafts[self.platform_key] = {k: v.get() for k, v in self.auth_vars.items()}
        self.platform_sessions[self.platform_key] = (self.session_state, self.books, self.selected_id)
        self.platform_key = key
        self.pages.set("Libri e download")
        self.account_platform.set(self._entry()["label"])
        self.platform_title.configure(text=B.PLATFORM_NAMES[key])
        for k, button in self.plat_buttons.items():
            button.configure(fg_color=B.NAV_HOVER if k == key else "transparent",
                             text_color=B.WHITE if k == key else B.NAV_TEXT)
        self.session_state, self.books, self.selected_id = self.platform_sessions.get(key, (None, [], None))
        self.search_var.set("")
        self._render_auth()
        self._filter_books()
        self._refresh_connection()
        self._update_selection()
        self._set_status("Seleziona un libro da scaricare." if self.session_state is not None
                         else "Collega il tuo account per vedere i libri disponibili.", 0)

    def _refresh_connection(self):
        connected = self.session_state is not None
        self.connection_label.configure(text="Account collegato" if connected else "Account da collegare",
            text_color=B.ACCENT if connected else B.MUTED)
        self.connect_button.configure(text="Aggiorna biblioteca" if connected else "Collega account")

    def _render_auth(self):
        self.operation_buttons = [self.connect_button]
        for widget in self.auth_frame.winfo_children():
            widget.destroy()
        self.auth_vars = {}
        self.auth_widgets = {}
        entry = self._entry()
        mod = entry["mod"]
        self._label(self.auth_frame, "Credenziali", B.SECTION).pack(anchor="w", padx=22, pady=(16, 8))
        try:
            saved = self.vault.get_creds(entry["key"]) if self.vault else {}
        except OSError as ex:
            saved = {}
            self._log(safe_error(ex))
        self.remember_var.set(self.remember_choices.get(entry["key"], bool(saved)))
        values = self.account_drafts.get(entry["key"], saved)
        optional = []
        for key, label, secret, required in mod.AUTH_FIELDS:
            if not required:
                optional.append((key, label, secret, required))
                continue
            self._account_field(self.auth_frame, key, "Email" if key == "email" else label, secret, values)
        if optional:
            self.advanced_frame = ctk.CTkFrame(self.auth_frame, fg_color="transparent")
            self.advanced_button = self._button(self.auth_frame, "Accesso con token o cookie", self._toggle_advanced)
            self.advanced_button.pack(fill="x", padx=22, pady=(16, 4))
            for key, label, secret, required in optional:
                self._account_field(self.advanced_frame, key, "Cookie di sessione" if key == "cookie" else "Token di sessione", True, values)
            self._label(self.advanced_frame, getattr(mod, "AUTH_HELP", ""), B.SMALL, B.MUTED,
                        wraplength=370).pack(anchor="w", padx=22, pady=8)
            if any(values.get(key) for key, *_ in optional):
                self.advanced_frame.pack(fill="x")
        connect = self._button(self.auth_frame, "Collega e carica biblioteca", self._load_books_thread, primary=True)
        connect.pack(fill="x", padx=22, pady=(8, 12))
        self.account_note = tk.StringVar(value="Credenziali già presenti nel portachiavi." if saved
                                        else "Nessuna credenziale salvata sul dispositivo.")
        ctk.CTkLabel(self.auth_frame, textvariable=self.account_note, font=B.SMALL, text_color=B.MUTED,
            anchor="w", wraplength=370).pack(fill="x", padx=22, pady=(8, 6))
        ctk.CTkCheckBox(self.auth_frame, text="Conserva le credenziali su questo dispositivo",
            variable=self.remember_var, font=B.SMALL, fg_color=B.ACCENT, hover_color=B.HOVER,
            text_color=B.INK, border_color=B.MUTED, checkbox_width=20, checkbox_height=20).pack(anchor="w", padx=22, pady=8)
        self._label(self.auth_frame, "Senza questa scelta, i dati inseriti restano solo in memoria.\nSalvare senza spunta rimuove la copia già conservata.",
            B.SMALL, B.MUTED, wraplength=380).pack(anchor="w", padx=22, pady=(0, 12))
        save = self._button(self.auth_frame, "Salva preferenze", self._save_account)
        save.pack(fill="x", padx=22, pady=4)
        delete = self._button(self.auth_frame, "Rimuovi account e credenziali", self._delete_account)
        delete.configure(text_color=B.ERROR)
        delete.pack(fill="x", padx=22, pady=(0, 22))
        self.operation_buttons.extend([save, connect, delete])
        if self.vault and self.vault.legacy_exists():
            self._label(self.auth_frame, "Vecchio archivio Linux in chiaro rilevato.\nRimuovilo e reinserisci gli account nel portachiavi sicuro.", B.SMALL, B.ERROR, wraplength=420).pack(padx=22, pady=8)
            self._button(self.auth_frame, "Elimina vecchio archivio", self._remove_legacy).pack(fill="x", padx=22, pady=4)
        self._render_opts()

    def _account_field(self, parent, key, label, secret, values):
        self._label(parent, label, B.STRONG).pack(anchor="w", padx=22, pady=(8, 5))
        var = tk.StringVar(value=values.get(key, ""))
        field = self._field(parent, textvariable=var, show="•" if secret else "")
        field.pack(fill="x", padx=22, pady=(0, 6))
        self.auth_vars[key] = var
        self.auth_widgets[key] = field

    def _toggle_advanced(self):
        if self.advanced_frame.winfo_manager():
            self.advanced_frame.pack_forget()
            self.advanced_button.configure(text="Accesso con token o cookie")
        else:
            self.advanced_frame.pack(fill="x", after=self.advanced_button)
            self.advanced_button.configure(text="Nascondi accesso avanzato")

    def _render_opts(self):
        for widget in self.opt_frame.winfo_children():
            widget.destroy()
        self.opt_vars = {}
        for key, label, default in self._entry()["mod"].OPTIONS:
            var = tk.BooleanVar(value=default)
            ctk.CTkCheckBox(self.opt_frame, text=label, variable=var, font=B.SMALL,
                fg_color=B.ACCENT, hover_color=B.HOVER, text_color=B.INK,
                checkbox_width=18, checkbox_height=18).pack(anchor="w", pady=4)
            self.opt_vars[key] = var
            var.trace_add("write", lambda *a: self._update_selection())

    def _filter_books(self):
        if not hasattr(self, "book_box"):
            return
        for widget in self.book_box.winfo_children():
            widget.destroy()
        self.book_rows = []
        query = self.search_var.get().strip().lower()
        matches = [book for book in self.books if not query or query in f"{book['id']} {book['title']}".lower()]
        self.book_count.configure(text=f"{len(matches)} titoli" if not query else f"{len(matches)} risultati su {len(self.books)} titoli")
        for book in matches[:300]:
            title = book["title"]
            text = title if len(title) <= 64 else title[:61] + "…"
            if book.get("ok") is False:
                text += " · Non disponibile"
            row = ctk.CTkButton(self.book_box, text=text, anchor="w", font=B.FONT,
                fg_color=B.WHITE, text_color=B.INK, hover_color=B.TINT, height=54,
                corner_radius=5, border_width=1, border_color=B.LINE,
                state="disabled" if book.get("ok") is False else "normal",
                command=lambda bid=book["id"]: self._pick(bid))
            row.pack(fill="x", padx=6, pady=4)
            self.book_rows.append((book["id"], row))
        if len(matches) > 300:
            self._label(self.book_box, "Mostrati i primi 300 titoli. Affina la ricerca.", B.SMALL, B.MUTED).pack(pady=14)
        if not matches:
            empty = ctk.CTkFrame(self.book_box, fg_color="transparent")
            empty.pack(fill="x", padx=22, pady=45)
            self._label(empty, "Nessun risultato" if query else "La tua biblioteca\ninizia qui.", ("Georgia", 26)).pack(anchor="w")
            message = ("Prova un titolo o un codice diverso." if query else
                "Stiamo caricando i tuoi libri." if self.busy else
                "Questo account non contiene libri disponibili." if self.session_state is not None else
                "Collega il tuo account per visualizzare i libri della piattaforma.")
            self._label(empty, message, color=B.MUTED, wraplength=320).pack(anchor="w", pady=(12, 18))
            if not query and self.session_state is None and not self.busy:
                self._button(empty, "Configura account", lambda: self.pages.set("Account e credenziali"), primary=True).pack(anchor="w")
        self._highlight()

    def _pick(self, book_id):
        if self.busy:
            return
        book = next((b for b in self.books if b["id"] == book_id), None)
        if book and book.get("ok") is False:
            return
        self.selected_id = book_id
        self._highlight()
        self._update_selection()
        self._set_status("Libro selezionato. Scegli la destinazione e avvia il download.")

    def _update_selection(self):
        book = next((b for b in self.books if b["id"] == self.selected_id), None)
        ready = bool(self.selected_id and (self.session_state is not None or not self._entry()["mod"].NEEDS_LOGIN))
        self.selection_label.configure(text=book["title"] if book else "Seleziona un libro")
        self.selection_meta.configure(text=f"{B.PLATFORM_NAMES[self.platform_key]} · {book['id']}" if book
            else "I dettagli compariranno qui.")
        resources = bool(self.opt_vars.get("resources") and self.opt_vars["resources"].get())
        self.dl_btn.configure(text="Scarica allegati" if resources else "Scarica PDF",
            state="normal" if ready and not self.busy else "disabled")
        self.download_hint.configure(text="Operazione in corso. Attendi il completamento." if self.busy else
            "Le risorse verranno salvate nella cartella scelta." if resources and ready else
            "Il PDF verrà salvato nella cartella scelta." if ready else
            "Seleziona un titolo dalla biblioteca per continuare.")

    def _highlight(self):
        for book_id, row in self.book_rows:
            row.configure(fg_color=B.TINT if book_id == self.selected_id else B.WHITE,
                          border_color=B.ACCENT if book_id == self.selected_id else B.LINE)

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
            self.status_label.configure(text_color=B.MUTED)
            if pct is not None:
                if pct > 0:
                    self.prog.stop()
                    self.prog.configure(mode="determinate")
                self.prog.set(max(0.0, min(1.0, pct / 100.0)))
            self.update_idletasks()
        except Exception:
            pass

    def _toggle_log(self):
        if self.log.winfo_manager():
            self.log.grid_remove()
            self.log_btn.configure(text="Dettagli")
        else:
            self.log.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
            self.log_btn.configure(text="Chiudi dettagli")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get())
        if d:
            self.out_var.set(d)

    def _progress(self, done, total, msg):
        pct = (done / total * 100) if total else 0
        self.events.put(lambda: self._set_status(msg, pct))

    # I worker comunicano esclusivamente tramite la coda; Tk resta nel thread principale.
    def destroy(self):
        self.closing = True
        self.cancel_event.set()
        self.unbind("<FocusIn>")
        worker = getattr(self, "_library_thread", None)
        if worker and worker.is_alive():
            worker.join(timeout=2)
        with self.events.mutex:
            self.events.queue.clear()
        for timer in self.tk.call("after", "info"):
            self.tk.call("after", "cancel", timer)
        super().destroy()

    def _close_requested(self):
        if self.busy:
            self.closing = True
            self.cancel_event.set()
            self._set_status("Annullamento in corso, poi chiusura…")
        else:
            self.destroy()

    def _drain_events(self):
        try:
            for _ in range(100):
                try:
                    callback = self.events.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback()
                except Exception as ex:
                    try:
                        self._log("Errore interfaccia: " + safe_error(ex))
                        self._set_status("Errore interfaccia: " + safe_error(ex))
                    except Exception:
                        pass
        finally:
            if self.closing and not self.busy:
                self.destroy()
            elif self.winfo_exists():
                self._event_timer = self.after(50, self._drain_events)

    def _post_result(self, callback):
        def dispatch():
            try:
                callback()
            except Exception as ex:
                self._operation_error("Errore interfaccia", safe_error(ex))
            finally:
                if self.busy:
                    self._finish_operation()
        self.events.put(dispatch)

    def _save_account(self):
        if self.busy:
            return
        values = {k: v.get() for k, v in self.auth_vars.items()}
        try:
            if self.remember_var.get():
                if not self.vault:
                    raise RuntimeError("Portachiavi sicuro non disponibile: usa i dati solo per questa sessione.")
                self.vault.set_account(self.platform_key, values)
            elif self.vault:
                self.vault.del_creds(self.platform_key)
            self.remember_choices[self.platform_key] = self.remember_var.get()
            self.account_drafts[self.platform_key] = values
            self.account_note.set("Credenziali salvate nel portachiavi." if self.remember_var.get()
                                  else "Credenziali disponibili solo per questa sessione.")
            self._set_status(self.account_note.get())
        except Exception as ex:
            self._popup("Errore salvataggio", safe_error(ex))

    def _remove_legacy(self):
        if not self.busy and messagebox.askyesno("Vecchie credenziali", "Eliminare il vecchio archivio in chiaro di tutti gli account Linux? Gli account nel portachiavi sicuro restano disponibili."):
            try:
                self.vault.remove_legacy()
                self._render_auth()
            except OSError as ex:
                self._popup("Errore eliminazione", safe_error(ex))

    def _delete_account(self):
        if self.busy:
            return
        try:
            if self.vault:
                self.vault.del_creds(self.platform_key)
        except Exception as ex:
            self._popup("Errore eliminazione", safe_error(ex))
            return
        self.remember_choices[self.platform_key] = False
        self.account_drafts.pop(self.platform_key, None)
        for var in self.auth_vars.values():
            var.set("")
        self.remember_var.set(False)
        self.session_state = None
        self.books = []
        self.selected_id = None
        self._filter_books()
        self.dl_btn.configure(state="disabled")
        self.platform_sessions.pop(self.platform_key, None)
        self._refresh_connection()
        self._update_selection()
        self.account_note.set("Credenziali eliminate e sessione chiusa.")
        self._set_status(self.account_note.get())

    def _start_operation(self):
        if self.busy:
            return False
        self.cancel_event.clear()
        self.busy = True
        self.cancel_button.configure(state="normal")
        self.prog.configure(mode="indeterminate")
        self.prog.start()
        for button in self.operation_buttons:
            button.configure(state="disabled")
        for field in self.auth_widgets.values():
            field.configure(state="disabled")
        self._update_selection()
        for button in self.plat_buttons.values():
            button.configure(state="disabled")
        self.account_platform.configure(state="disabled")
        self.dl_btn.configure(state="disabled")
        return True

    def _finish_operation(self):
        self.busy = False
        self.cancel_button.configure(state="disabled")
        self.prog.stop()
        self.prog.configure(mode="determinate")
        for button in self.operation_buttons:
            button.configure(state="normal")
        for field in self.auth_widgets.values():
            field.configure(state="normal")
        self._update_selection()
        for button in self.plat_buttons.values():
            button.configure(state="normal")
        self.account_platform.configure(state="normal")
        ready = self.selected_id and (self.session_state is not None or not self._entry()["mod"].NEEDS_LOGIN)
        self.dl_btn.configure(state="normal" if ready else "disabled")

    def _load_books_thread(self):
        if self.busy:
            return
        entry = self._entry()
        creds = {"_site": entry["site"]}
        for key, label, _pw, required in entry["mod"].AUTH_FIELDS:
            value = self.auth_vars[key].get()
            if key != "password":
                value = value.strip()
            if required and not value and not any(self.auth_vars.get(k) and self.auth_vars[k].get().strip() for k in ("token", "cookie")):
                self._popup("Dati mancanti", f"Scrivi: {label}")
                return
            creds[key] = value
        if not self._start_operation():
            return
        self.session_state = None
        self.books = []
        self.selected_id = None
        self._filter_books()
        self._update_selection()
        self._refresh_connection()
        self._set_status("Accesso in corso…", 0)
        threading.Thread(target=self._load_books, args=(entry, creds), daemon=True).start()

    def _load_books(self, entry, creds):
        try:
            with scope(Operation(self.cancel_event)):
                state = entry["mod"].login(creds)
                books = entry["mod"].list_books(state)
            def complete():
                self.session_state = state
                self.books = books
                for line in state.get("_debug", []):
                    self._log(f"[diagnostica] {safe_error(RuntimeError(line))}")
                self._filter_books()
                self._set_status(f"Trovati {len(books)} libri. Scegli il tuo libro.", 0)
                self._finish_operation()
                self._refresh_connection()
                self._update_selection()
                self.pages.set("Libri e download")
            self._post_result(complete)
        except Exception as ex:
            self._post_result(lambda error=safe_error(ex, secret_values(creds)): self._operation_error("Errore accesso", error))

    def _operation_error(self, title, error):
        self._log(f"ERRORE: {error}")
        self._set_status(error, 0)
        self._finish_operation()
        self._refresh_connection()
        self._filter_books()
        self.status_label.configure(text_color=B.ERROR)
        if not self.closing and not self.cancel_event.is_set():
            self._popup(title, error)

    def _popup(self, title, msg):
        messagebox.showinfo(title, msg)

    def _download_thread(self):
        if self.busy:
            return
        entry = self._entry()
        if entry["mod"].NEEDS_LOGIN and self.session_state is None:
            self._popup("Non connesso", "Verifica l’accesso nella pagina Account e credenziali.")
            return
        if not self.selected_id:
            return
        destination = os.path.expanduser(self.out_var.get().strip())
        if not destination:
            self._popup("Destinazione mancante", "Scegli una cartella in cui salvare il download.")
            return
        title = next((b["title"] for b in self.books if b["id"] == self.selected_id), str(self.selected_id))
        args = (entry, self.session_state, self.selected_id, destination,
                {k: v.get() for k, v in self.opt_vars.items()}, title)
        if self._start_operation():
            threading.Thread(target=self._download, args=args, daemon=True).start()

    def _download(self, entry, state, book_id, out_dir, opts, title):
        try:
            state = state if state is not None else entry["mod"].login({})
            os.makedirs(out_dir, exist_ok=True)
            with scope(Operation(self.cancel_event)):
                path = entry["mod"].download(state, book_id, out_dir, opts, self._progress)
            index_warning = None
            try:
                self.local_library.add(path, title, entry["key"], book_id)
            except Exception as ex:
                index_warning = safe_error(ex)
            def complete():
                self._log(f"Salvato in: {path}")
                self._set_status("Download completato.", 100)
                self._finish_operation()
                if index_warning:
                    self._log("PDF salvato; indice biblioteca non aggiornato: " + index_warning)
                self._refresh_downloaded()
                self.last_path = path
                self.open_button.pack(fill="x", padx=16, pady=8)
            self._post_result(complete)
        except Exception as ex:
            self._post_result(lambda error=safe_error(ex, secret_values(state)): self._operation_error("Errore download", error))


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        import json
        from pathlib import Path
        vault_file = os.path.join(os.environ["FOLIO_SMOKE_HOME"], "vault.dat")
        import vault
        vault._vault_path = lambda: vault_file
        vault.get_creds = lambda key: {}
        app = App()
        def smoke():
            app.pages.set("Account e credenziali")
            app.pages.set("Libri e download")
            Path(os.environ["FOLIO_SMOKE_HOME"], "success.json").write_text(json.dumps({"version": VERSION, "platforms": len(PLATFORMS), "gui": True}))
            app.destroy()
        app.after(700, smoke)
        app.mainloop()
    else:
        App().mainloop()
