from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


BG = "#111916"
TEXT = "#edf1e8"
MUTED = "#a4b0a5"
ACCENT = "#bedb76"


class SaperInstaller:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Установка Сапёра / Arena")
        self.root.geometry("620x490")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.release_url = tk.StringVar()
        self.install_dir = tk.StringVar(
            value=str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "SaperArena")
        )
        self.create_shortcut = tk.BooleanVar(value=True)
        self.launch_after_install = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Вставьте ссылку на GitHub Releases.")
        self._configure_style()
        self._build_ui()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(12, 9), background="#314239", foreground=TEXT, borderwidth=0)
        style.map("TButton", background=[("active", "#40584a")])
        style.configure("Install.TButton", background=ACCENT, foreground="#172016")
        style.map("Install.TButton", background=[("active", "#cce88a")])
        style.configure("TEntry", fieldbackground="#26332d", foreground=TEXT, insertcolor=TEXT, padding=8)
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#26332d", bordercolor="#26332d")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=26)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="САПЁР  /  ARENA", font=("Segoe UI Semibold", 22)).pack(anchor="w")
        ttk.Label(outer, text="Установка игры", font=("Segoe UI", 12), foreground=ACCENT).pack(anchor="w", pady=(2, 20))
        ttk.Label(outer, text="ССЫЛКА НА РЕЛИЗ GITHUB", style="Muted.TLabel", font=("Segoe UI Semibold", 8)).pack(anchor="w")
        self.url_entry = ttk.Entry(outer, textvariable=self.release_url)
        self.url_entry.pack(fill="x", pady=(6, 5), ipady=3)
        self.url_entry.insert(0, "https://github.com/владелец/репозиторий/releases/latest")
        self.url_entry.bind("<FocusIn>", self._clear_placeholder)
        ttk.Label(outer, text="Ссылка на страницу релиза или прямой .exe/.zip из GitHub Releases.", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Крупные файлы скачиваются напрямую; ограничение 20 МБ не применяется.", style="Muted.TLabel").pack(anchor="w", pady=(3, 17))
        ttk.Label(outer, text="ПАПКА УСТАНОВКИ", style="Muted.TLabel", font=("Segoe UI Semibold", 8)).pack(anchor="w")
        folder_row = ttk.Frame(outer)
        folder_row.pack(fill="x", pady=(6, 16))
        ttk.Entry(folder_row, textvariable=self.install_dir).pack(side="left", fill="x", expand=True, ipady=3)
        ttk.Button(folder_row, text="Обзор", command=self._browse_folder).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(outer, text="Создать ярлык на рабочем столе", variable=self.create_shortcut).pack(anchor="w", pady=3)
        ttk.Checkbutton(outer, text="Запустить игру после установки", variable=self.launch_after_install).pack(anchor="w", pady=3)
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100, style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(17, 7))
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=560).pack(anchor="w")
        self.install_button = ttk.Button(outer, text="СКАЧАТЬ И УСТАНОВИТЬ", style="Install.TButton", command=self._begin_install)
        self.install_button.pack(fill="x", pady=(17, 0))

    def _clear_placeholder(self, _event=None) -> None:
        if "владелец/репозиторий" in self.release_url.get():
            self.release_url.set("")

    def _browse_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.install_dir.get(), parent=self.root)
        if selected:
            self.install_dir.set(selected)

    def _begin_install(self) -> None:
        url = self.release_url.get().strip()
        destination = Path(self.install_dir.get().strip())
        if not url or "владелец/репозиторий" in url:
            messagebox.showerror("Нужна ссылка", "Вставьте ссылку на страницу GitHub Releases.", parent=self.root)
            return
        if not destination:
            messagebox.showerror("Нужна папка", "Выберите папку для установки.", parent=self.root)
            return
        self.install_button.configure(state="disabled")
        self.progress.configure(value=0)
        self.status.set("Подключение к GitHub...")
        threading.Thread(target=self._install_worker, args=(url, destination), daemon=True).start()

    def _install_worker(self, url: str, destination: Path) -> None:
        try:
            download_url, asset_name = self._resolve_asset(url)
            destination.mkdir(parents=True, exist_ok=True)
            extension = Path(asset_name).suffix.lower()
            if extension not in {".exe", ".zip"}:
                raise ValueError("В релизе должен быть .exe или .zip файл.")
            self._set_status(f"Скачивание {asset_name}...")
            temporary_file = self._download(download_url, destination, asset_name)
            if extension == ".zip":
                executable = self._extract_game(temporary_file, destination)
                temporary_file.unlink(missing_ok=True)
            else:
                executable = destination / "Saper.exe"
                os.replace(temporary_file, executable)
            shortcut_note = ""
            if self.create_shortcut.get():
                try:
                    self._create_desktop_shortcut(executable)
                except (OSError, subprocess.SubprocessError):
                    shortcut_note = " Ярлык создать не удалось."
            if self.launch_after_install.get():
                subprocess.Popen([str(executable)], cwd=str(executable.parent))
            self.root.after(0, self._finish_install, f"Игра установлена: {executable}{shortcut_note}")
        except Exception as error:
            self.root.after(0, self._finish_install, f"Ошибка установки: {error}", True)

    def _resolve_asset(self, url: str) -> tuple[str, str]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "github.com":
            raise ValueError("Используйте HTTPS-ссылку с github.com.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 5 and parts[2:4] == ["releases", "download"]:
            return url, urllib.parse.unquote(parts[-1])
        if len(parts) < 2:
            raise ValueError("Ссылка должна вести на репозиторий GitHub или его релиз.")
        owner, repository = parts[0], parts[1]
        if len(parts) >= 5 and parts[2:4] == ["releases", "tag"]:
            tag = urllib.parse.quote(urllib.parse.unquote(parts[4]), safe="")
            endpoint = f"https://api.github.com/repos/{owner}/{repository}/releases/tags/{tag}"
        else:
            endpoint = f"https://api.github.com/repos/{owner}/{repository}/releases/latest"
        request = urllib.request.Request(endpoint, headers={"Accept": "application/vnd.github+json", "User-Agent": "SaperArenaInstaller"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                release = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise ValueError("В репозитории нет опубликованного релиза.") from error
            raise ValueError(f"GitHub вернул HTTP {error.code}.") from error
        assets = [asset for asset in release.get("assets", []) if Path(asset.get("name", "")).suffix.lower() in {".exe", ".zip"}]
        if not assets:
            raise ValueError("В релизе не найден .exe или .zip файл. Загрузите игру в Assets релиза.")
        assets.sort(key=lambda asset: (Path(asset["name"]).suffix.lower() != ".exe", "saper" not in asset["name"].lower(), asset["name"].lower()))
        asset = assets[0]
        return asset["browser_download_url"], asset["name"]

    def _download(self, url: str, destination: Path, asset_name: str) -> Path:
        request = urllib.request.Request(url, headers={"User-Agent": "SaperArenaInstaller"})
        descriptor, temporary_name = tempfile.mkstemp(prefix="saper-download-", suffix=Path(asset_name).suffix, dir=destination)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temporary_path.open("wb") as output:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.root.after(0, self.progress.configure, {"value": downloaded * 100 / total})
                    size = downloaded / 1024 / 1024
                    total_text = f" из {total / 1024 / 1024:.1f} МБ" if total else ""
                    self._set_status(f"Скачано {size:.1f} МБ{total_text}")
            if temporary_path.stat().st_size == 0:
                raise ValueError("GitHub вернул пустой файл.")
            return temporary_path
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def _extract_game(self, archive_path: Path, destination: Path) -> Path:
        with zipfile.ZipFile(archive_path) as archive:
            root = destination.resolve()
            for member in archive.infolist():
                target = (destination / member.filename).resolve()
                if os.path.commonpath((str(root), str(target))) != str(root):
                    raise ValueError("Архив содержит недопустимый путь.")
            archive.extractall(destination)
        executables = list(destination.rglob("*.exe"))
        if not executables:
            raise ValueError("В ZIP-архиве не найден .exe файл игры.")
        return next((path for path in executables if path.name.lower() == "saper.exe"), executables[0])

    def _create_desktop_shortcut(self, executable: Path) -> None:
        desktop = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
        shortcut = desktop / "Сапёр Arena.lnk"
        quote_ps = lambda value: str(value).replace("'", "''")
        script = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$link = $shell.CreateShortcut('{quote_ps(shortcut)}'); "
            f"$link.TargetPath = '{quote_ps(executable)}'; "
            f"$link.WorkingDirectory = '{quote_ps(executable.parent)}'; $link.Save()"
        )
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded], check=True, capture_output=True)

    def _set_status(self, text: str) -> None:
        self.root.after(0, self.status.set, text)

    def _finish_install(self, text: str, is_error: bool = False) -> None:
        self.install_button.configure(state="normal")
        self.status.set(text)
        self.progress.configure(value=0 if is_error else 100)
        if is_error:
            messagebox.showerror("Установка не завершена", text.removeprefix("Ошибка установки: "), parent=self.root)
        else:
            messagebox.showinfo("Готово", text, parent=self.root)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    SaperInstaller().run()