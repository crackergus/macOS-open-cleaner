import argparse
import hashlib
import shutil
import sys
import threading
import webbrowser
from collections import defaultdict
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


COLORS = {
	"background": "#081222",
	"surface": "#101F34",
	"raised": "#14263E",
	"text": "#EDF3FC",
	"muted": "#A9BAD0",
	"accent": "#8BC5FF",
	"line": "#2D405B",
}


def file_hash(path):
	digest = hashlib.sha256()
	with path.open("rb") as file:
		for chunk in iter(lambda: file.read(1024 * 1024), b""):
			digest.update(chunk)
	return digest.hexdigest()


def find_duplicates(root):
	files_by_size = defaultdict(list)
	for path in sorted(root.rglob("*")):
		try:
			if path.is_symlink() or not path.is_file():
				continue
			files_by_size[path.stat().st_size].append(path)
		except OSError as error:
			print(f"Impossibile leggere {path}: {error}")

	duplicates = []
	for size, paths in files_by_size.items():
		if len(paths) < 2:
			continue

		paths_by_hash = defaultdict(list)
		for path in paths:
			try:
				paths_by_hash[file_hash(path)].append(path)
			except OSError as error:
				print(f"Impossibile calcolare l'hash di {path}: {error}")

		for digest, matching_paths in paths_by_hash.items():
			if len(matching_paths) < 2:
				continue

			unique_files = []
			seen_inodes = set()
			for path in matching_paths:
				try:
					info = path.stat()
					identity = (info.st_dev, info.st_ino)
					if identity not in seen_inodes:
						unique_files.append(path)
						seen_inodes.add(identity)
				except OSError as error:
					print(f"Impossibile controllare {path}: {error}")

			if len(unique_files) > 1:
				duplicates.append((size, digest, unique_files))

	return duplicates


def remove_duplicates(duplicates, assume_yes):
	removed = 0
	for size, digest, paths in duplicates:
		keeper, *candidates = paths
		for candidate in candidates:
			if not assume_yes:
				answer = input(f"Eliminare {candidate}? [s/N] ").strip().lower()
				if answer not in {"s", "si", "sì"}:
					continue

			try:
				if keeper.is_symlink() or file_hash(keeper) != digest:
					print(f"Saltato: il file da conservare è cambiato: {keeper}")
					break
				if candidate.is_symlink() or candidate.stat().st_size != size:
					print(f"Saltato: il duplicato è cambiato: {candidate}")
					continue
				if file_hash(candidate) != digest:
					print(f"Saltato: il duplicato è cambiato: {candidate}")
					continue

				candidate.unlink()
				print(f"Eliminato: {candidate}")
				removed += 1
			except OSError as error:
				print(f"Impossibile eliminare {candidate}: {error}")

	return removed


def macos_cleanup_targets(home=None):
	home = Path.home() if home is None else Path(home)
	return [
		("Cache utente", home / "Library" / "Caches"),
		("Log utente", home / "Library" / "Logs"),
		("Cestino", home / ".Trash"),
	]


def find_cleanup_items(targets):
	items = []
	errors = []
	for label, root in targets:
		try:
			if root.is_symlink() or not root.is_dir():
				continue
			for path in sorted(root.iterdir()):
				if not path.is_symlink():
					items.append((label, path))
		except OSError as error:
			errors.append((root, error))
	return items, errors


def clean_macos_items(items, assume_yes):
	if not assume_yes:
		answer = input("Eliminare tutti gli elementi elencati? [s/N] ").strip().lower()
		if answer not in {"s", "si", "sì"}:
			print("Pulizia annullata.")
			return 0, []

	removed = 0
	errors = []
	for label, path in items:
		try:
			if path.is_symlink():
				continue
			if path.is_dir():
				shutil.rmtree(path)
			elif path.is_file():
				path.unlink()
			else:
				continue
			removed += 1
		except OSError as error:
			errors.append((label, path, error))
	return removed, errors


class CleanerApp:
	def __init__(self, root, home=None):
		self.root = root
		self.root.title("MACOS OPEN CLEANER")
		self.root.geometry("1000x700")
		self.root.minsize(760, 560)
		self.root.configure(background=COLORS["background"])
		self.items = {}
		self.category_vars = {}
		self.busy = False
		self.cleanup_targets = macos_cleanup_targets(home)

		style = ttk.Style(root)
		try:
			style.theme_use("clam")
		except tk.TclError:
			pass
		style.configure("App.TFrame", background=COLORS["background"])
		style.configure("Header.TFrame", background=COLORS["background"])
		style.configure("Surface.TFrame", background=COLORS["surface"])
		style.configure("Title.TLabel", background=COLORS["background"], foreground=COLORS["text"], font=("Helvetica Neue", 25, "bold"))
		style.configure("Eyebrow.TLabel", background=COLORS["background"], foreground=COLORS["accent"], font=("Helvetica Neue", 9, "bold"))
		style.configure("Subtitle.TLabel", background=COLORS["background"], foreground=COLORS["muted"], font=("Helvetica Neue", 11))
		style.configure("Section.TLabelframe", background=COLORS["surface"], bordercolor=COLORS["line"], relief="solid")
		style.configure("Section.TLabelframe.Label", background=COLORS["surface"], foreground=COLORS["accent"], font=("Helvetica Neue", 10, "bold"))
		style.configure("App.TCheckbutton", background=COLORS["surface"], foreground=COLORS["text"], font=("Helvetica Neue", 10))
		style.map("App.TCheckbutton", background=[("active", COLORS["surface"])], foreground=[("disabled", COLORS["muted"])])
		style.configure("App.TButton", background=COLORS["raised"], foreground=COLORS["text"], bordercolor=COLORS["line"], font=("Helvetica Neue", 10), padding=(12, 8))
		style.map("App.TButton", background=[("active", COLORS["line"]), ("disabled", COLORS["surface"])], foreground=[("disabled", COLORS["muted"])])
		style.configure("Accent.TButton", background=COLORS["accent"], foreground=COLORS["background"], bordercolor=COLORS["accent"], font=("Helvetica Neue", 10, "bold"), padding=(14, 8))
		style.map("Accent.TButton", background=[("active", "#B5DCFF"), ("disabled", COLORS["raised"])], foreground=[("disabled", COLORS["muted"])])
		style.configure("Treeview", background=COLORS["surface"], foreground=COLORS["text"], fieldbackground=COLORS["surface"], bordercolor=COLORS["line"], rowheight=32, font=("Helvetica Neue", 10))
		style.map("Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", COLORS["background"])])
		style.configure("Treeview.Heading", background=COLORS["raised"], foreground=COLORS["accent"], bordercolor=COLORS["line"], relief="flat", font=("Helvetica Neue", 9, "bold"), padding=(8, 8))
		style.map("Treeview.Heading", background=[("active", COLORS["line"])])
		style.configure("Vertical.TScrollbar", background=COLORS["raised"], troughcolor=COLORS["surface"], bordercolor=COLORS["surface"], arrowcolor=COLORS["muted"])

		container = ttk.Frame(root, style="App.TFrame", padding=(28, 22, 28, 16))
		container.pack(fill="both", expand=True)
		container.columnconfigure(0, weight=1)
		container.rowconfigure(3, weight=1)

		header = ttk.Frame(container, style="Header.TFrame")
		header.grid(row=0, column=0, sticky="ew", pady=(0, 22))
		header.columnconfigure(0, weight=1)
		intro = ttk.Frame(header, style="Header.TFrame")
		intro.grid(row=0, column=0, sticky="w", pady=(8, 8))
		ttk.Label(intro, text="AP INFOSEC / MACOS UTILITY", style="Eyebrow.TLabel").pack(anchor="w", pady=(0, 10))
		ttk.Label(intro, text="MACOS OPEN CLEANER", style="Title.TLabel").pack(anchor="w")
		ttk.Label(intro, text="Pulizia controllata di cache, log e Cestino.", style="Subtitle.TLabel").pack(anchor="w", pady=(8, 0))
		orbit = tk.Canvas(header, width=174, height=132, background=COLORS["background"], highlightthickness=0)
		orbit.grid(row=0, column=1, sticky="e", padx=(18, 8))
		orbit.create_oval(22, 10, 148, 126, outline=COLORS["line"], width=1)
		orbit.create_oval(8, 28, 162, 108, outline=COLORS["line"], width=1)
		orbit.create_arc(13, 9, 161, 130, start=205, extent=124, outline=COLORS["accent"], width=1, style="arc")
		orbit.create_oval(28, 22, 36, 30, fill=COLORS["accent"], outline="")
		orbit.create_oval(139, 99, 145, 105, fill=COLORS["text"], outline="")
		orbit.create_text(85, 68, text="AP", fill=COLORS["text"], font=("Helvetica Neue", 33, "normal"))

		categories = ttk.LabelFrame(container, text="AREE DA ANALIZZARE", style="Section.TLabelframe", padding=(14, 11))
		categories.grid(row=1, column=0, sticky="ew", pady=(0, 14))
		for label, _ in self.cleanup_targets:
			variable = tk.BooleanVar(value=True)
			self.category_vars[label] = variable
			ttk.Checkbutton(categories, text=label.upper(), variable=variable, style="App.TCheckbutton").pack(side="left", padx=(0, 20))

		controls = ttk.Frame(container, style="App.TFrame")
		controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
		self.scan_button = ttk.Button(controls, text="Analizza", style="App.TButton", command=self.scan)
		self.scan_button.pack(side="left")
		self.select_all_button = ttk.Button(controls, text="Seleziona tutto", style="App.TButton", command=self.select_all)
		self.select_all_button.pack(side="left", padx=(8, 0))
		self.clear_button = ttk.Button(controls, text="Deseleziona", style="App.TButton", command=self.clear_selection)
		self.clear_button.pack(side="left", padx=(8, 0))
		self.clean_button = ttk.Button(controls, text="Pulisci selezionati", style="Accent.TButton", command=self.clean_selected)
		self.clean_button.pack(side="right")

		listing = ttk.Frame(container, style="Surface.TFrame", padding=1)
		listing.grid(row=3, column=0, sticky="nsew")
		listing.columnconfigure(0, weight=1)
		listing.rowconfigure(0, weight=1)
		self.tree = ttk.Treeview(
			listing,
			columns=("category", "path", "kind"),
			displaycolumns=("category", "path", "kind"),
			selectmode="extended",
			height=12,
		)
		self.tree.heading("category", text="Categoria")
		self.tree.heading("path", text="Elemento")
		self.tree.heading("kind", text="Tipo")
		self.tree.column("category", width=140, stretch=False)
		self.tree.column("path", width=560, minwidth=220)
		self.tree.column("kind", width=90, stretch=False)
		self.tree.grid(row=0, column=0, sticky="nsew")
		vertical = ttk.Scrollbar(listing, orient="vertical", command=self.tree.yview)
		vertical.grid(row=0, column=1, sticky="ns")
		horizontal = ttk.Scrollbar(listing, orient="horizontal", command=self.tree.xview)
		horizontal.grid(row=1, column=0, sticky="ew")
		self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

		self.status = tk.StringVar(value="Pronto. Analizza per visualizzare gli elementi.")
		ttk.Label(container, textvariable=self.status, anchor="w", style="Subtitle.TLabel").grid(
			row=4, column=0, sticky="ew", pady=(12, 8)
		)

		footer = ttk.Frame(container, style="App.TFrame")
		footer.grid(row=5, column=0, sticky="ew", pady=(4, 0))
		credit = ttk.Label(footer, text='Powered by Agostino "APInfoSec" Pellegirno', foreground=COLORS["accent"], background=COLORS["background"], cursor="pointinghand")
		credit.pack(side="left")
		credit.bind("<Button-1>", lambda _event: webbrowser.open("https://www.apinfosec.com"))
		credit.bind("<Enter>", lambda _event: credit.configure(foreground="#B5DCFF"))
		credit.bind("<Leave>", lambda _event: credit.configure(foreground=COLORS["accent"]))

	def selected_targets(self):
		return [
			(label, path)
			for label, path in self.cleanup_targets
			if self.category_vars[label].get()
		]

	def set_busy(self, busy, message):
		self.busy = busy
		self.status.set(message)
		state = "disabled" if busy else "normal"
		self.scan_button.configure(state=state)
		self.clean_button.configure(state=state)
		self.select_all_button.configure(state=state)
		self.clear_button.configure(state=state)

	def scan(self):
		if self.busy:
			return
		targets = self.selected_targets()
		if not targets:
			messagebox.showinfo("Nessuna area selezionata", "Seleziona almeno un'area da analizzare.")
			return

		self.set_busy(True, "Analisi in corso…")
		threading.Thread(target=self._scan_worker, args=(targets,), daemon=True).start()

	def _scan_worker(self, targets):
		items, errors = find_cleanup_items(targets)
		self.root.after(0, self._show_items, items, errors)

	def _show_items(self, items, errors):
		self.tree.delete(*self.tree.get_children())
		self.items.clear()
		for index, (category, path) in enumerate(items):
			kind = "Cartella" if path.is_dir() else "File"
			item_id = str(index)
			self.tree.insert("", "end", iid=item_id, values=(category, str(path), kind))
			self.items[item_id] = (category, path)
		message = f"Anteprima: {len(items)} elementi. Nessun file è stato modificato."
		if errors:
			blocked = ", ".join(str(path) for path, _ in errors)
			message += f" Aree non accessibili: {blocked}"
			permission_error = any(isinstance(error, PermissionError) for _, error in errors)
			details = "\n".join(f"{path}: {error}" for path, error in errors)
			if permission_error:
				details += (
					"\n\nPer consentire l'accesso, apri Impostazioni di Sistema > "
					"Privacy e sicurezza > Accesso completo al disco, abilita "
					"MACOS OPEN CLEANER (oppure Terminale/VS Code se avvii lo script) "
					"e riavviala."
				)
			messagebox.showwarning("Accesso limitato", details)
		self.set_busy(False, message)

	def select_all(self):
		self.tree.selection_set(self.tree.get_children())

	def clear_selection(self):
		self.tree.selection_remove(self.tree.selection())

	def clean_selected(self):
		if self.busy:
			return
		selected = self.tree.selection()
		if not selected:
			messagebox.showinfo("Nessuna selezione", "Seleziona gli elementi da rimuovere.")
			return

		items = [self.items[item_id] for item_id in selected]
		confirmed = messagebox.askyesno(
			"Conferma pulizia",
			f"Rimuovere {len(items)} elementi selezionati? Questa operazione non si può annullare.",
			icon="warning",
		)
		if not confirmed:
			return

		self.set_busy(True, "Pulizia in corso…")
		threading.Thread(target=self._clean_worker, args=(items,), daemon=True).start()

	def _clean_worker(self, items):
		removed, errors = clean_macos_items(items, assume_yes=True)
		self.root.after(0, self._clean_finished, removed, errors)

	def _clean_finished(self, removed, errors):
		if errors:
			details = "\n".join(f"{path}: {error}" for _, path, error in errors[:8])
			if len(errors) > 8:
				details += f"\n… e altri {len(errors) - 8} errori."
			details += "\n\nControlla queste cartelle prima di ripetere la pulizia: potrebbero essere state elaborate solo in parte."
			messagebox.showwarning(
				"Pulizia parziale",
				f"Elementi rimossi: {removed}. Elementi non rimossi: {len(errors)}.\n\n{details}",
			)
			status = f"Pulizia parziale: {removed} rimossi, {len(errors)} non rimossi."
		else:
			status = f"Pulizia completata: {removed} elementi rimossi."
		self.set_busy(False, status)
		self.scan()


def launch_gui():
	if sys.platform != "darwin":
		raise SystemExit("macos-open-cleaner è disponibile solo su macOS.")
	root = tk.Tk()
	CleanerApp(root)
	root.mainloop()


def main():
	parser = argparse.ArgumentParser(
		prog="macos-open-cleaner",
		description="Trova duplicati o pulisce cache, log e Cestino dell'utente macOS.",
	)
	parser.add_argument(
		"cartella",
		nargs="?",
		type=Path,
		help="cartella da analizzare per i duplicati (predefinita: cartella corrente)",
	)
	parser.add_argument(
		"--gui",
		action="store_true",
		help="apre l'interfaccia grafica",
	)
	parser.add_argument(
		"--clean-macos",
		action="store_true",
		help="analizza cache utente, log utente e Cestino",
	)
	parser.add_argument(
		"--delete",
		action="store_true",
		help="esegue la pulizia dopo una conferma",
	)
	parser.add_argument(
		"--yes",
		action="store_true",
		help="elimina senza conferma (richiede anche --delete)",
	)
	args = parser.parse_args()

	if args.gui and (args.clean_macos or args.cartella is not None or args.delete or args.yes):
		parser.error("--gui non si può combinare con altre modalità")
	if args.gui or (len(sys.argv) == 1):
		launch_gui()
		return
	if args.yes and not args.delete:
		parser.error("--yes richiede anche --delete")
	if args.clean_macos:
		if sys.platform != "darwin":
			parser.error("--clean-macos è disponibile solo su macOS")
		if args.cartella is not None:
			parser.error("non specificare una cartella insieme a --clean-macos")

		items, errors = find_cleanup_items(macos_cleanup_targets())
		for path, error in errors:
			print(f"Impossibile analizzare {path}: {error}")
		if not items:
			if errors:
				print("Nessun elemento accessibile da pulire.")
			else:
				print("Nessun elemento da pulire nelle cache, nei log o nel Cestino.")
			return

		print(f"Elementi trovati: {len(items)}")
		for label, path in items:
			print(f"  {label}: {path}")
		if args.delete:
			removed, errors = clean_macos_items(items, args.yes)
			print(f"\nElementi rimossi: {removed}")
			for label, path, error in errors:
				print(f"Impossibile rimuovere ({label}) {path}: {error}")
			if errors:
				print("Controlla gli elementi segnalati prima di ripetere la pulizia: potrebbero essere stati elaborati solo in parte.")
		else:
			print("\nAnteprima: nessun elemento è stato eliminato. Usa --delete per procedere.")
		return

	root = args.cartella or Path.cwd()
	if not root.is_dir():
		parser.error(f"la cartella non esiste o non è accessibile: {root}")

	duplicates = find_duplicates(root.resolve())
	if not duplicates:
		print("Nessun file duplicato trovato.")
		return

	total = sum(len(paths) - 1 for _, _, paths in duplicates)
	print(f"Trovati {len(duplicates)} gruppi di duplicati ({total} file ridondanti):")
	for size, _, paths in duplicates:
		print(f"\nGruppo ({size} byte):")
		print(f"  Conserva: {paths[0]}")
		for path in paths[1:]:
			print(f"  Duplicato: {path}")

	if args.delete:
		removed = remove_duplicates(duplicates, args.yes)
		print(f"\nFile eliminati: {removed}")
	else:
		print("\nAnteprima: nessun file è stato eliminato. Usa --delete per procedere.")


if __name__ == "__main__":
	main()
