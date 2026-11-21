from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, ttk

from main import MinesweeperGame, PRESETS
from online import OnlineClient, RoomServer


THEMES = {
	"Лес": ("#14231f", "#264a3c", "#d8ead8", "#397052", "#ffffff", "#d9aa62", "#f07167"),
	"Океан": ("#14212b", "#28516a", "#d8eaf2", "#39718a", "#ffffff", "#e8b65b", "#ff796f"),
	"Графит": ("#1c2024", "#3b4349", "#e2e5e7", "#535d64", "#ffffff", "#e2b85b", "#ff7169"),
	"Ягода": ("#281b24", "#58334a", "#f0dce8", "#75405b", "#ffffff", "#f0b660", "#ff7770"),
	"Песок": ("#29271f", "#665b3c", "#f2e7c9", "#827349", "#ffffff", "#f3c758", "#f0785d"),
	"Лёд": ("#18242a", "#3d6268", "#e0f2ed", "#517a80", "#ffffff", "#f4c767", "#ef766c"),
	"Неон": ("#1a1d24", "#353e48", "#e7e8f4", "#475363", "#f7f7ff", "#e8ce4c", "#ff5a78"),
	"Коралл": ("#29211f", "#69463c", "#f4dfd4", "#87584a", "#ffffff", "#f3c263", "#fb766c"),
}

APP_BG = "#101816"
PANEL_BG = "#192420"
TEXT = "#eef3ed"
MUTED = "#9aa9a0"
ACCENT = "#b3d36a"
PLAYER_COLORS = ("#bdd775", "#62b6aa", "#e6ad68", "#dc7a6c")
NUMBER_COLORS = ("", "#2f74ce", "#2d8a57", "#d14b43", "#764cb4", "#c06b25", "#278e9e", "#26343a", "#68727a")


class MinesweeperApp:
	CELL_SIZE = 27

	def __init__(self):
		self.root = tk.Tk()
		self.root.title("Сапёр / Arena")
		self.root.geometry("1180x800")
		self.root.minsize(850, 600)
		self.root.configure(bg=APP_BG)
		self.game: MinesweeperGame | None = None
		self.online_client: OnlineClient | None = None
		self.online_state: dict | None = None
		self.online_room_code = ""
		self.online_player_index = 0
		self.online_server_label = ""
		self.local_server: RoomServer | None = None
		self._online_events: queue.Queue = queue.Queue()
		self.theme_name = tk.StringVar(value="Лес")
		self.preset_name = tk.StringVar(value=PRESETS[0][0])
		self.size_value = tk.IntVar(value=8)
		self.player_count = tk.IntVar(value=1)
		self.player_name_vars = [tk.StringVar(value=f"Игрок {index + 1}") for index in range(4)]
		self.mine_status = tk.StringVar(value="МИНЫ  10")
		self.turn_status = tk.StringVar(value="Настройте партию")
		self.message_status = tk.StringVar(value="Первое открытие всегда безопасно")
		self.score_labels: list[tk.Label] = []
		self._configure_style()
		self._build_layout()
		self.root.protocol("WM_DELETE_WINDOW", self._close_app)
		self._event_poll_id = self.root.after(40, self._process_online_events)
		self._update_player_inputs()
		self._update_preset_from_size()
		self.start_game()

	def _configure_style(self) -> None:
		style = ttk.Style(self.root)
		style.theme_use("clam")
		style.configure("TFrame", background=APP_BG)
		style.configure("Panel.TFrame", background=PANEL_BG)
		style.configure("TLabel", background=APP_BG, foreground=TEXT, font=("Segoe UI", 10))
		style.configure("Panel.TLabel", background=PANEL_BG, foreground=TEXT, font=("Segoe UI", 10))
		style.configure("Muted.TLabel", background=PANEL_BG, foreground=MUTED, font=("Segoe UI", 9))
		style.configure("Title.TLabel", background=APP_BG, foreground=TEXT, font=("Segoe UI Semibold", 21))
		style.configure("Accent.TLabel", background=APP_BG, foreground=ACCENT, font=("Segoe UI Semibold", 10))
		style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(12, 9), background="#2c3d34", foreground=TEXT, borderwidth=0)
		style.map("TButton", background=[("active", "#3b5144")])
		style.configure("Start.TButton", background=ACCENT, foreground="#172016")
		style.map("Start.TButton", background=[("active", "#c4e47b")])
		style.configure("TCombobox", fieldbackground="#26332d", background="#26332d", foreground=TEXT, arrowcolor=TEXT, padding=6)
		style.configure("TSpinbox", fieldbackground="#26332d", background="#26332d", foreground=TEXT, arrowcolor=TEXT, padding=6)

	def _build_layout(self) -> None:
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(1, weight=1)
		header = ttk.Frame(self.root, padding=(24, 17, 24, 12))
		header.grid(row=0, column=0, sticky="ew")
		header.columnconfigure(0, weight=1)
		ttk.Label(header, text="САПЁР  /  ARENA", style="Title.TLabel").grid(row=0, column=0, sticky="w")
		ttk.Label(header, textvariable=self.turn_status, style="Accent.TLabel").grid(row=0, column=1, sticky="e", padx=(10, 0))

		body = ttk.Frame(self.root, padding=(18, 0, 18, 18))
		body.grid(row=1, column=0, sticky="nsew")
		body.columnconfigure(0, weight=0)
		body.columnconfigure(1, weight=1)
		body.rowconfigure(0, weight=1)

		sidebar = ttk.Frame(body, style="Panel.TFrame", padding=18, width=260)
		sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
		sidebar.grid_propagate(False)
		ttk.Label(sidebar, text="НОВАЯ ПАРТИЯ", style="Panel.TLabel", font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 14))
		self._field_label(sidebar, "ИГРОКИ")
		self.player_picker = ttk.Spinbox(sidebar, from_=1, to=4, textvariable=self.player_count, command=self._update_player_inputs, width=8)
		self.player_picker.pack(fill="x", pady=(5, 10))
		self.player_picker.bind("<KeyRelease>", lambda _event: self._update_player_inputs())
		self.name_entries: list[tk.Entry] = []
		for index, variable in enumerate(self.player_name_vars):
			entry = tk.Entry(sidebar, textvariable=variable, bg="#26332d", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
			entry.pack(fill="x", ipady=7, pady=3)
			entry.insert(0, "")
			self.name_entries.append(entry)

		self._field_label(sidebar, "РАЗМЕР ПОЛЯ")
		preset_names = [f"{name} · {size}×{size}" for name, size, _mines in PRESETS]
		self.preset_picker = ttk.Combobox(sidebar, state="readonly", values=preset_names, width=19)
		self.preset_picker.current(0)
		self.preset_picker.pack(fill="x", pady=(5, 5))
		self.preset_picker.bind("<<ComboboxSelected>>", self._apply_preset)
		size_row = ttk.Frame(sidebar, style="Panel.TFrame")
		size_row.pack(fill="x", pady=(3, 10))
		ttk.Label(size_row, text="Свой размер", style="Muted.TLabel").pack(side="left")
		self.size_picker = ttk.Spinbox(size_row, from_=8, to=48, textvariable=self.size_value, width=6, command=self._update_preset_from_size)
		self.size_picker.pack(side="right")
		self.size_picker.bind("<KeyRelease>", lambda _event: self._update_preset_from_size())

		self._field_label(sidebar, "ОФОРМЛЕНИЕ")
		self.theme_picker = ttk.Combobox(sidebar, state="readonly", values=list(THEMES), textvariable=self.theme_name)
		self.theme_picker.pack(fill="x", pady=(5, 14))
		self.theme_picker.bind("<<ComboboxSelected>>", lambda _event: self.draw_board())

		ttk.Button(sidebar, text="НАЧАТЬ ЗАНОВО", style="Start.TButton", command=self.start_game).pack(fill="x", pady=(2, 14))
		ttk.Separator(sidebar).pack(fill="x", pady=4)
		ttk.Label(sidebar, text="СЧЁТ И ЖИЗНИ", style="Panel.TLabel", font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(12, 7))
		self.score_frame = ttk.Frame(sidebar, style="Panel.TFrame")
		self.score_frame.pack(fill="x")
		ttk.Separator(sidebar).pack(fill="x", pady=(13, 9))
		self._field_label(sidebar, "КЛЕТКИ")
		ttk.Label(sidebar, text="ЛКМ  открыть   ·   ПКМ  флаг", style="Muted.TLabel").pack(anchor="w", pady=(5, 0))
		ttk.Label(sidebar, textvariable=self.message_status, style="Muted.TLabel", wraplength=220, justify="left").pack(anchor="w", pady=(12, 0))

		board_area = ttk.Frame(body, style="Panel.TFrame", padding=12)
		board_area.grid(row=0, column=1, sticky="nsew")
		board_area.columnconfigure(0, weight=1)
		board_area.rowconfigure(1, weight=1)
		toolbar = ttk.Frame(board_area, style="Panel.TFrame")
		toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
		ttk.Label(toolbar, textvariable=self.mine_status, style="Panel.TLabel", font=("Segoe UI Semibold", 11)).pack(side="left")
		self.online_button = ttk.Button(toolbar, text="ОНЛАЙН", command=self._online_button_action)
		self.online_button.pack(side="right", padx=(10, 0))
		ttk.Label(toolbar, text="ПЕРВОЕ ОТКРЫТИЕ БЕЗОПАСНО", style="Muted.TLabel").pack(side="right")
		grid_frame = ttk.Frame(board_area, style="Panel.TFrame")
		grid_frame.grid(row=1, column=0, sticky="nsew")
		grid_frame.rowconfigure(0, weight=1)
		grid_frame.columnconfigure(0, weight=1)
		self.canvas = tk.Canvas(grid_frame, bg=APP_BG, highlightthickness=0, xscrollincrement=self.CELL_SIZE, yscrollincrement=self.CELL_SIZE)
		x_scroll = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.canvas.xview)
		y_scroll = ttk.Scrollbar(grid_frame, orient="vertical", command=self.canvas.yview)
		self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
		self.canvas.grid(row=0, column=0, sticky="nsew")
		y_scroll.grid(row=0, column=1, sticky="ns")
		x_scroll.grid(row=1, column=0, sticky="ew")
		self.canvas.bind("<Button-1>", self._left_click)
		self.canvas.bind("<Button-3>", self._right_click)
		self.canvas.bind("<Configure>", lambda _event: self.draw_board())
		self.canvas.bind("<MouseWheel>", self._mouse_wheel)

	def _field_label(self, parent: ttk.Frame, text: str) -> None:
		ttk.Label(parent, text=text, style="Muted.TLabel", font=("Segoe UI Semibold", 8)).pack(anchor="w", pady=(8, 0))

	def _update_player_inputs(self) -> None:
		try:
			count = max(1, min(4, int(self.player_count.get())))
		except (ValueError, tk.TclError):
			count = 1
		self.player_count.set(count)
		for index, entry in enumerate(self.name_entries):
			if index < count:
				entry.pack(fill="x", ipady=7, pady=3)
			else:
				entry.pack_forget()

	def _apply_preset(self, _event=None) -> None:
		selected = self.preset_picker.current()
		if selected >= 0:
			self.size_value.set(PRESETS[selected][1])

	def _update_preset_from_size(self) -> None:
		try:
			size = max(8, min(48, int(self.size_value.get())))
		except (ValueError, tk.TclError):
			return
		self.size_value.set(size)
		for index, (_name, preset_size, _mines) in enumerate(PRESETS):
			if preset_size == size:
				self.preset_picker.current(index)
				return
		self.preset_picker.set("Своя сетка")

	def start_game(self) -> None:
		if self.online_client is not None:
			self.online_client.close()
			self.online_client = None
		if self.local_server is not None:
			self.local_server.stop()
			self.local_server = None
		self.online_state = None
		self.online_room_code = ""
		self.online_button.configure(text="ОНЛАЙН")
		try:
			size = max(8, min(48, int(self.size_value.get())))
			count = max(1, min(4, int(self.player_count.get())))
		except (ValueError, tk.TclError):
			messagebox.showerror("Проверьте настройки", "Размер и число игроков должны быть числами.", parent=self.root)
			return
		preset = next((item for item in PRESETS if item[1] == size), None)
		mines = preset[2] if preset else max(10, round(size * size * 0.16))
		mines = min(mines, size * size - 1)
		names = [variable.get().strip() or f"Игрок {index + 1}" for index, variable in enumerate(self.player_name_vars[:count])]
		self.game = MinesweeperGame(size, size, mines, names)
		self.message_status.set("Первое открытие всегда безопасно" if count == 1 else "Открывайте клетки по очереди. Мина отнимает жизнь.")
		self._refresh_status()
		self.draw_board()

	def _refresh_status(self) -> None:
		if self.online_state is not None:
			state = self.online_state
			players = state["players"]
			self.mine_status.set(f"МИНЫ  {max(0, state['mine_count'] - len(state['flags'])):02d}")
			if state["finished"]:
				if state["won"]:
					best_score = max(player["score"] for player in players)
					winners = [player["name"] for player in players if player["score"] == best_score]
					self.turn_status.set(f"ПОБЕДА  ·  {' / '.join(winners)}")
				else:
					self.turn_status.set("ПАРТИЯ ОКОНЧЕНА")
			else:
				current = players[state["current_player"]]["name"]
				self.turn_status.set(f"ХОД  ·  {current.upper()}  ·  КОМНАТА {state['room']}")
			self._refresh_scores()
			return
		if self.game is None:
			return
		game = self.game
		self.mine_status.set(f"МИНЫ  {max(0, game.remaining_mines):02d}")
		if game.finished:
			if game.won and game.multiplayer:
				best_score = max(player.score for player in game.players)
				winners = [player.name for player in game.players if player.score == best_score]
				result = " / ".join(winners)
				self.turn_status.set(f"ПОБЕДА  ·  {result}")
			else:
				self.turn_status.set("ПОЛЕ ОЧИЩЕНО" if game.won else "ПАРТИЯ ОКОНЧЕНА")
			self.message_status.set("Победа!" if game.won else "Мина. Начните новую партию, чтобы попробовать ещё раз.")
		elif game.multiplayer:
			self.turn_status.set(f"ХОД  ·  {game.current.name.upper()}")
		else:
			self.turn_status.set(f"ПОЛЕ  ·  {game.rows} × {game.columns}")
		self._refresh_scores()

	def _refresh_scores(self) -> None:
		for child in self.score_frame.winfo_children():
			child.destroy()
		self.score_labels.clear()
		if self.online_state is not None:
			players = self.online_state["players"]
			active_index = self.online_state["current_player"]
			finished = self.online_state["finished"]
			player_rows = [(player["name"], player["score"], player["lives"]) for player in players]
		elif self.game is not None:
			active_index = self.game.current_player
			finished = self.game.finished
			player_rows = [(player.name, player.score, player.lives) for player in self.game.players]
		else:
			return
		for index, (name, score, lives) in enumerate(player_rows):
			active = index == active_index and not finished
			row = tk.Frame(self.score_frame, bg="#26332d" if active else PANEL_BG, padx=8, pady=7)
			row.pack(fill="x", pady=2)
			dot = tk.Label(row, text="●", fg=PLAYER_COLORS[index], bg=row["bg"], font=("Segoe UI", 10))
			dot.pack(side="left")
			label = tk.Label(row, text=f"{name}  ·  {score} очк.  ·  {max(0, lives)} жизней", fg=TEXT if lives else MUTED, bg=row["bg"], font=("Segoe UI", 9), anchor="w")
			label.pack(side="left", padx=(7, 0))
			self.score_labels.append(label)

	def _coordinates(self, event) -> tuple[int, int] | None:
		if self.online_state is not None:
			rows = self.online_state["rows"]
			columns = self.online_state["columns"]
		elif self.game is not None:
			rows = self.game.rows
			columns = self.game.columns
		else:
			return None
		column = int(self.canvas.canvasx(event.x) // self.CELL_SIZE)
		row = int(self.canvas.canvasy(event.y) // self.CELL_SIZE)
		if 0 <= row < rows and 0 <= column < columns:
			return row, column
		return None

	def _left_click(self, event) -> None:
		cell = self._coordinates(event)
		if cell is None:
			return
		if self.online_client is not None:
			self.online_client.send_action("reveal", *cell)
			return
		if self.game is None:
			return
		result = self.game.reveal(*cell)
		if result == "mine":
			self.message_status.set("Мина! Игрок теряет жизнь и два очка.")
		elif result == "safe" and self.game.multiplayer:
			self.message_status.set("Безопасно. Ход переходит следующему игроку.")
		self._refresh_status()
		self.draw_board()
		if result == "lost" and len(self.game.players) == 1:
			messagebox.showinfo("Игра окончена", "Вы попали на мину. Попробуйте ещё раз!", parent=self.root)
		elif result == "won" and not self.game.multiplayer:
			messagebox.showinfo("Победа", "Все безопасные клетки открыты!", parent=self.root)

	def _right_click(self, event) -> None:
		cell = self._coordinates(event)
		if cell is None:
			return
		if self.online_client is not None:
			self.online_client.send_action("flag", *cell)
			return
		if self.game is None:
			return
		if not self.game.toggle_flag(*cell) and cell not in self.game.opened:
			self.message_status.set("Все флаги уже использованы.")
		self._refresh_status()
		self.draw_board()

	def _mouse_wheel(self, event) -> None:
		self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

	def draw_board(self) -> None:
		if not hasattr(self, "canvas"):
			return
		self.canvas.delete("all")
		if self.game is None and self.online_state is None:
			return
		if self.online_state is not None:
			state = self.online_state
			rows = state["rows"]
			columns = state["columns"]
			opened = {tuple(cell) for cell in state["opened"]}
			flags = {tuple(cell) for cell in state["flags"]}
			mines = {tuple(cell) for cell in state["mines"]}
			numbers = {(row, column): number for row, column, number in state["numbers"]}
			exploded = tuple(state["exploded"]) if state["exploded"] else None
			finished = state["finished"]
			won = state["won"]
			mine_count = state["mine_count"]
		else:
			game = self.game
			rows = game.rows
			columns = game.columns
			opened = game.opened
			flags = game.flags
			mines = game.mines
			numbers = None
			exploded = game.exploded
			finished = game.finished
			won = game.won
			mine_count = game.mine_count
		hidden, revealed, grid, number_text, flag_color, mine_color = THEMES[self.theme_name.get()][1:]
		board_width = columns * self.CELL_SIZE
		board_height = rows * self.CELL_SIZE
		self.canvas.configure(scrollregion=(0, 0, board_width, board_height))
		for row in range(rows):
			for column in range(columns):
				cell = (row, column)
				x1 = column * self.CELL_SIZE
				y1 = row * self.CELL_SIZE
				x2 = x1 + self.CELL_SIZE
				y2 = y1 + self.CELL_SIZE
				is_open = cell in opened or (finished and not won and cell in mines)
				fill = revealed if is_open else hidden
				if is_open and cell in mines:
					fill = mine_color
				self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=grid, width=1)
				if cell in flags and not is_open:
					self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="F", fill=flag_color, font=("Segoe UI Semibold", 11))
				elif is_open and cell in mines:
					self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="*", fill="#fff5eb", font=("Segoe UI Semibold", 12))
				elif is_open:
					number = numbers[(row, column)] if numbers is not None else game.number_at(row, column)
					if number:
						self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=str(number), fill=NUMBER_COLORS[number], font=("Segoe UI Semibold", 10))
				if exploded == cell:
					self.canvas.create_rectangle(x1 + 2, y1 + 2, x2 - 2, y2 - 2, outline="#fff5eb", width=2)

	def _online_button_action(self) -> None:
		if self.online_client is not None:
			self.start_game()
			self.message_status.set("Вы вышли из онлайн-комнаты.")
			return
		self._open_online_dialog()

	def _open_online_dialog(self) -> None:
		dialog = tk.Toplevel(self.root)
		dialog.title("Онлайн-комната")
		dialog.geometry("420x520")
		dialog.resizable(False, False)
		dialog.configure(bg=APP_BG)
		host_var = tk.StringVar(value="127.0.0.1")
		port_var = tk.StringVar(value="4444")
		name_var = tk.StringVar(value=self.player_name_vars[0].get().strip() or "Игрок")
		room_var = tk.StringVar()
		size_var = tk.IntVar(value=self.size_value.get())
		content = ttk.Frame(dialog, padding=22)
		content.pack(fill="both", expand=True)
		ttk.Label(content, text="ОНЛАЙН-ПАРТИЯ", font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(0, 14))
		ttk.Label(content, text="Создатель запускает сервер на этом ПК. Для друзей используйте Radmin-IP.", style="Muted.TLabel", wraplength=370).pack(anchor="w", pady=(0, 7))
		for label, variable in (("АДРЕС СЕРВЕРА", host_var), ("ПОРТ", port_var), ("ВАШЕ ИМЯ", name_var), ("КОД КОМНАТЫ ДЛЯ ВХОДА", room_var)):
			ttk.Label(content, text=label, style="Muted.TLabel", font=("Segoe UI Semibold", 8)).pack(anchor="w", pady=(5, 3))
			ttk.Entry(content, textvariable=variable).pack(fill="x", ipady=3)
		size_row = ttk.Frame(content)
		size_row.pack(fill="x", pady=(10, 6))
		ttk.Label(size_row, text="Размер новой комнаты").pack(side="left")
		tk.Spinbox(size_row, from_=8, to=48, textvariable=size_var, width=8).pack(side="right")
		actions = ttk.Frame(content)
		actions.pack(fill="x", pady=(10, 0))
		ttk.Button(actions, text="СОЗДАТЬ КОМНАТУ", style="Start.TButton", command=lambda: self._connect_online(dialog, host_var, port_var, name_var, room_var, size_var, True)).pack(fill="x", pady=3)
		ttk.Button(actions, text="ВОЙТИ ПО КОДУ", command=lambda: self._connect_online(dialog, host_var, port_var, name_var, room_var, size_var, False)).pack(fill="x", pady=3)

	def _connect_online(self, dialog, host_var, port_var, name_var, room_var, size_var, create: bool) -> None:
		host = host_var.get().strip()
		name = name_var.get().strip() or "Игрок"
		try:
			port = int(port_var.get())
			size = max(8, min(48, int(size_var.get())))
			if not 1 <= port <= 65535:
				raise ValueError
		except ValueError:
			messagebox.showerror("Проверьте настройки", "Укажите корректные порт и размер поля.", parent=dialog)
			return
		if not host:
			messagebox.showerror("Нужен сервер", "Укажите IP-адрес или имя сервера.", parent=dialog)
			return
		if not create and not room_var.get().strip():
			messagebox.showerror("Нужен код", "Введите код комнаты.", parent=dialog)
			return
		if self.online_client is not None:
			self.online_client.close()
		if create and self.local_server is None:
			self.local_server = RoomServer(port=port)
			try:
				self.local_server.start()
			except OSError as error:
				self.local_server = None
				messagebox.showerror("Не удалось запустить сервер", f"Не удалось занять порт {port}: {error}", parent=dialog)
				return
			except TimeoutError as error:
				self.local_server = None
				messagebox.showerror("Не удалось запустить сервер", str(error), parent=dialog)
				return
		self.online_state = None
		self.online_server_label = f"{host}:{port}"
		self.message_status.set("Подключение к серверу...")
		self.online_button.configure(text="ПОДКЛЮЧЕНИЕ...")
		request = {"type": "create", "name": name, "rows": size, "columns": size, "mine_count": next((mines for _title, preset_size, mines in PRESETS if preset_size == size), max(10, round(size * size * 0.16)))} if create else {"type": "join", "room": room_var.get().strip().upper(), "name": name}
		client = OnlineClient(
			on_state=lambda state: self._online_events.put(("state", state)),
			on_joined=lambda code, index: self._online_events.put(("joined", (code, index, dialog))),
			on_error=lambda error, fatal: self._online_events.put(("error", (error, fatal))),
		)
		self.online_client = client
		client.connect(host, port, request)

	def _process_online_events(self) -> None:
		while True:
			try:
				event, payload = self._online_events.get_nowait()
			except queue.Empty:
				break
			if event == "state":
				self._set_online_state(payload)
			elif event == "joined":
				code, player_index, dialog = payload
				self._online_joined(code, player_index, dialog)
			elif event == "error":
				error, fatal = payload
				self._online_error(error, fatal)
		if self.root.winfo_exists():
			self._event_poll_id = self.root.after(40, self._process_online_events)

	def _online_joined(self, code: str, player_index: int, dialog) -> None:
		self.online_room_code = code
		self.online_player_index = player_index
		self.online_button.configure(text="ВЫЙТИ ИЗ ОНЛАЙНА")
		self.message_status.set(f"Комната {code}. Сервер: {self.online_server_label}")
		if dialog.winfo_exists():
			dialog.destroy()

	def _set_online_state(self, state: dict) -> None:
		self.online_state = state
		self._refresh_status()
		self.draw_board()

	def _online_error(self, error: str, fatal: bool = True) -> None:
		self.message_status.set(f"Ошибка онлайн-подключения: {error}")
		if fatal:
			self.online_client = None
			self.online_state = None
			self.online_button.configure(text="ОНЛАЙН")
			self.draw_board()
			messagebox.showerror("Онлайн-подключение", error, parent=self.root)

	def _leave_online(self) -> None:
		if self.online_client is not None:
			self.online_client.close()
		self.online_client = None
		self.online_state = None
		self.online_room_code = ""
		self.online_button.configure(text="ОНЛАЙН")

	def _close_app(self) -> None:
		if self._event_poll_id is not None:
			self.root.after_cancel(self._event_poll_id)
		if self.online_client is not None:
			self.online_client.close()
		if self.local_server is not None:
			self.local_server.stop()
		self.root.destroy()

	def run(self) -> None:
		self.root.mainloop()


if __name__ == "__main__":
	MinesweeperApp().run()
