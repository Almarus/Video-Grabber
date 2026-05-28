import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu
import threading
import os
import time
import requests
from datetime import datetime, timedelta
from PIL import Image
import io
import yt_dlp
import random
import re
from pathlib import Path
import traceback
import sys
import gc
import platform
import json
import webbrowser
import ctypes
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import zipfile
import shutil
import signal

try:
    import browser_cookie3
    BROWSER_COOKIES_AVAILABLE = True
except ImportError:
    BROWSER_COOKIES_AVAILABLE = False

YTDLP_GITHUB_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
YTDLP_EXE_NAME = "yt-dlp.exe"
FFMPEG_BASE_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_ZIP_NAME = "ffmpeg-release-essentials.zip"

class YtDlpUpdater:
    @staticmethod
    def get_local_version(ytdlp_path):
        if not ytdlp_path or not ytdlp_path.exists():
            return None
        try:
            result = subprocess.run([str(ytdlp_path), "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None

    @staticmethod
    def get_latest_version():
        try:
            resp = requests.get(YTDLP_GITHUB_API, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("tag_name", "").lstrip("v")
        except:
            pass
        return None

    @staticmethod
    def download_latest(target_dir, progress_callback=None):
        try:
            release_info = requests.get(YTDLP_GITHUB_API, timeout=10).json()
            for asset in release_info.get("assets", []):
                if asset["name"] == YTDLP_EXE_NAME:
                    exe_url = asset["browser_download_url"]
                    resp = requests.get(exe_url, stream=True, timeout=30)
                    if resp.status_code == 200:
                        total = int(resp.headers.get('content-length', 0))
                        down = 0
                        exe_path = target_dir / YTDLP_EXE_NAME
                        with open(exe_path, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                                down += len(chunk)
                                if progress_callback and total:
                                    progress_callback(down / total)
                        return exe_path
        except:
            pass
        return None

    @staticmethod
    def update(ffmpeg_dir, progress_callback=None):
        if not ffmpeg_dir.exists():
            ffmpeg_dir.mkdir(parents=True)
        local_path = ffmpeg_dir / YTDLP_EXE_NAME
        local_ver = YtDlpUpdater.get_local_version(local_path)
        latest_ver = YtDlpUpdater.get_latest_version()
        if latest_ver and (not local_ver or local_ver != latest_ver):
            print(f"Обновление yt-dlp: {local_ver} -> {latest_ver}")
            new_path = YtDlpUpdater.download_latest(ffmpeg_dir, progress_callback)
            if new_path:
                print("yt-dlp успешно обновлён.")
                return new_path
        return local_path if local_path.exists() else None

class FFmpegUpdater:
    @staticmethod
    def get_local_version(ffmpeg_path):
        if not ffmpeg_path or not ffmpeg_path.exists():
            return None
        try:
            result = subprocess.run([str(ffmpeg_path), "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                first_line = result.stdout.splitlines()[0]
                match = re.search(r"version\s+([\d\.]+)", first_line)
                if match:
                    return match.group(1)
        except:
            pass
        return None

    @staticmethod
    def get_latest_version():
        version_url = "https://www.gyan.dev/ffmpeg/builds/release-version"
        try:
            resp = requests.get(version_url, timeout=10)
            if resp.status_code == 200:
                return resp.text.strip()
        except:
            pass
        return None

    @staticmethod
    def download_latest(target_dir, progress_callback=None):
        zip_path = target_dir / FFMPEG_ZIP_NAME
        try:
            with requests.get(FFMPEG_BASE_URL, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                down = 0
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        down += len(chunk)
                        if progress_callback and total:
                            progress_callback(down / total)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)
            zip_path.unlink()
            for item in target_dir.iterdir():
                if item.is_dir() and item.name.startswith("ffmpeg"):
                    bin_dir = item / "bin"
                    if bin_dir.exists():
                        for exe in bin_dir.glob("*.exe"):
                            shutil.copy(exe, target_dir / exe.name)
                    shutil.rmtree(item)
            return target_dir / "ffmpeg.exe"
        except:
            if zip_path.exists():
                zip_path.unlink()
            return None

    @staticmethod
    def update(ffmpeg_dir, progress_callback=None):
        if not ffmpeg_dir.exists():
            ffmpeg_dir.mkdir(parents=True)
        local_path = ffmpeg_dir / "ffmpeg.exe"
        local_ver = FFmpegUpdater.get_local_version(local_path)
        latest_ver = FFmpegUpdater.get_latest_version()
        if latest_ver and (not local_ver or local_ver != latest_ver):
            print(f"Обновление FFmpeg: {local_ver} -> {latest_ver}")
            new_path = FFmpegUpdater.download_latest(ffmpeg_dir, progress_callback)
            if new_path:
                print("FFmpeg успешно обновлён.")
                return new_path
        return local_path if local_path.exists() else None

class UpdaterProgressWindow:
    def __init__(self, parent, ffmpeg_dir, on_complete=None):
        self.window = ctk.CTkToplevel(parent)
        self.window.title("Обновление компонентов")
        self.window.geometry("450x250")
        self.window.resizable(False, False)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.on_complete = on_complete
        self.ffmpeg_dir = ffmpeg_dir
        self.cancelled = False

        ctk.CTkLabel(self.window, text="Загрузка компонентов...", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15,5))

        self.yt_label = ctk.CTkLabel(self.window, text="yt-dlp: ожидание", anchor="w")
        self.yt_label.pack(fill="x", padx=20, pady=(10,0))
        self.yt_progress = ctk.CTkProgressBar(self.window, width=400, height=8, progress_color="#2563EB")
        self.yt_progress.pack(padx=20, pady=(5,10))
        self.yt_progress.set(0)

        self.ff_label = ctk.CTkLabel(self.window, text="FFmpeg: ожидание", anchor="w")
        self.ff_label.pack(fill="x", padx=20, pady=(0,0))
        self.ff_progress = ctk.CTkProgressBar(self.window, width=400, height=8, progress_color="#2563EB")
        self.ff_progress.pack(padx=20, pady=(5,10))
        self.ff_progress.set(0)

        self.status_label = ctk.CTkLabel(self.window, text="", font=ctk.CTkFont(size=11), text_color="#64748B")
        self.status_label.pack(pady=(5,10))

        self.start_update()

    def on_cancel(self):
        self.cancelled = True
        self.window.destroy()

    def update_yt_progress(self, value):
        self.yt_progress.set(value)
        self.yt_label.configure(text=f"yt-dlp: загрузка ({int(value*100)}%)")

    def update_ff_progress(self, value):
        self.ff_progress.set(value)
        self.ff_label.configure(text=f"FFmpeg: загрузка ({int(value*100)}%)")

    def start_update(self):
        def task():
            try:
                self.status_label.configure(text="Проверка yt-dlp...")
                yt_result = YtDlpUpdater.update(self.ffmpeg_dir, self.update_yt_progress)
                if yt_result:
                    self.yt_label.configure(text="yt-dlp: успешно")
                    self.yt_progress.set(1)
                else:
                    self.yt_label.configure(text="yt-dlp: уже актуален")
                    self.yt_progress.set(1)

                if self.cancelled: return

                self.status_label.configure(text="Проверка FFmpeg...")
                ff_result = FFmpegUpdater.update(self.ffmpeg_dir, self.update_ff_progress)
                if ff_result:
                    self.ff_label.configure(text="FFmpeg: успешно")
                    self.ff_progress.set(1)
                else:
                    self.ff_label.configure(text="FFmpeg: уже актуален")
                    self.ff_progress.set(1)

                if self.cancelled: return

                self.status_label.configure(text="Готово!")
                self.window.after(1000, self.window.destroy)
                if self.on_complete:
                    self.on_complete()
            except Exception as e:
                self.status_label.configure(text=f"Ошибка: {str(e)[:50]}")
                self.window.after(3000, self.window.destroy)

        threading.Thread(target=task, daemon=True).start()

if platform.system() != "Windows":
    ctk.CTk().withdraw()
    messagebox.showerror("Ошибка", "Программа работает только на Windows!")
    sys.exit(1)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

ICON_FILE = "icon.ico"
CONFIG_FILE = Path.home() / ".videograbber_config.json"

def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent

    ffmpeg_exe = base / "ffmpeg" / "ffmpeg.exe"
    if ffmpeg_exe.exists():
        return str(ffmpeg_exe)

    ffmpeg_exe = base / "ffmpeg.exe"
    if ffmpeg_exe.exists():
        return str(ffmpeg_exe)

    found = shutil.which("ffmpeg")
    if found:
        return found

    return None

def refresh_ffmpeg_state():
    global FFMPEG_PATH, FFMPEG_AVAILABLE
    FFMPEG_PATH = get_ffmpeg_path()
    FFMPEG_AVAILABLE = FFMPEG_PATH is not None and os.path.exists(FFMPEG_PATH)

FFMPEG_PATH = get_ffmpeg_path()
FFMPEG_AVAILABLE = FFMPEG_PATH is not None and os.path.exists(FFMPEG_PATH)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
]

POPULAR_SITES = {
    "🎬 YouTube": "https://youtube.com/",
    "🎥 VK Видео": "https://vk.com/video",
    "📺 Rutube": "https://rutube.ru/",
    "📰 Дзен": "https://dzen.ru/",
    "🐻 Bilibili": "https://www.bilibili.com/",
    "🎵 SoundCloud": "https://soundcloud.com/",
    "📹 Vimeo": "https://vimeo.com/",
    "🎮 Twitch": "https://www.twitch.tv/",
    "🐦 Twitter/X": "https://twitter.com/",
    "🎵 TikTok": "https://www.tiktok.com/",
    "🎬 Facebook": "https://www.facebook.com/watch/",
    "🎮 Coub": "https://coub.com/",
}

def get_icon_path():
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    icon = base / ICON_FILE
    return icon if icon.exists() else None

def set_window_icon(window):
    icon_path = get_icon_path()
    if not icon_path or not icon_path.exists():
        return False
    try:
        if platform.system() == "Windows":
            hicon = ctypes.windll.user32.LoadImageW(0, str(icon_path), 1, 0, 0, 0x00000010 | 0x00002000)
            if hicon:
                ctypes.windll.user32.SendMessageW(window.winfo_id(), 0x0080, 0, hicon)
                ctypes.windll.user32.SendMessageW(window.winfo_id(), 0x0080, 1, hicon)
                return True
        window.iconbitmap(str(icon_path))
        return True
    except:
        return False

def safe_filename(title, max_length=200):
    for ch in '<>:"/\\|?*':
        title = title.replace(ch, '_')
    title = ''.join(c for c in title if ord(c) >= 32 or c == ' ')
    if len(title) > max_length:
        title = title[:max_length-3] + "..."
    return title.strip() or "video"

def format_size(bytes_value):
    if not bytes_value:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} TB"

def format_speed(bytes_per_second):
    if not bytes_per_second:
        return "0 B/s"
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.1f} {unit}"
        bytes_per_second /= 1024
    return f"{bytes_per_second:.1f} TB/s"

def extract_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain.replace('www.', '')
    except:
        return ""

class SupportedSitesWindow:
    def __init__(self, parent):
        self.window = ctk.CTkToplevel(parent)
        self.window.title("Поддерживаемые сайты")
        self.window.geometry("600x500")
        self.window.resizable(False, False)
        self.window.grab_set()
        self.window.configure(fg_color="#FFFFFF")
        set_window_icon(self.window)
        self.center_window()
        self.setup_ui()
    
    def center_window(self):
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 600) // 2
        y = (self.window.winfo_screenheight() - 500) // 2
        self.window.geometry(f"600x500+{x}+{y}")
    
    def setup_ui(self):
        main = ctk.CTkFrame(self.window, fg_color="#FFFFFF", corner_radius=0)
        main.pack(fill="both", expand=True)
        header = ctk.CTkFrame(main, fg_color="#FFFFFF", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="🌐", font=ctk.CTkFont(size=28), text_color="#2563EB").pack(side="left", padx=(20,10), pady=15)
        ctk.CTkLabel(header, text="Поддерживаемые сайты", font=ctk.CTkFont(size=18, weight="bold"), text_color="#0F172A").pack(side="left", pady=15)
        ctk.CTkLabel(header, text="1800+ сайтов", font=ctk.CTkFont(size=11, weight="bold"), text_color="#2563EB", fg_color="#EFF6FF", corner_radius=6, padx=8, pady=2).pack(side="left", padx=10, pady=18)
        content = ctk.CTkFrame(main, fg_color="#FFFFFF")
        content.pack(fill="both", expand=True, padx=25, pady=(10,20))
        text_area = ctk.CTkScrollableFrame(content, fg_color="#F8FAFC", corner_radius=12, border_width=1, border_color="#E2E8F0")
        text_area.pack(fill="both", expand=True, pady=(0,15))
        ctk.CTkLabel(text_area, text="Программа поддерживает загрузку видео с более чем 1800 сайтов.\nВот самые популярные из них:", font=ctk.CTkFont(size=12), text_color="#475569", wraplength=550).pack(pady=(10,15), padx=15)
        ctk.CTkFrame(text_area, fg_color="#E2E8F0", height=1).pack(fill="x", padx=15, pady=5)
        sites = ctk.CTkFrame(text_area, fg_color="transparent")
        sites.pack(fill="both", expand=True, padx=15, pady=10)
        items = list(POPULAR_SITES.items())
        mid = (len(items)+1)//2
        left = ctk.CTkFrame(sites, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0,10))
        right = ctk.CTkFrame(sites, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(10,0))
        for name, url in items[:mid]:
            btn = ctk.CTkButton(left, text=name, font=ctk.CTkFont(size=12), fg_color="transparent", text_color="#3B82F6", hover_color="#EFF6FF", anchor="w", height=30, command=lambda u=url: webbrowser.open(u))
            btn.pack(fill="x", pady=2)
        for name, url in items[mid:]:
            btn = ctk.CTkButton(right, text=name, font=ctk.CTkFont(size=12), fg_color="transparent", text_color="#3B82F6", hover_color="#EFF6FF", anchor="w", height=30, command=lambda u=url: webbrowser.open(u))
            btn.pack(fill="x", pady=2)
        ctk.CTkButton(content, text="Закрыть", font=ctk.CTkFont(size=13, weight="bold"), fg_color="#2563EB", hover_color="#1D4ED8", height=38, corner_radius=8, command=self.window.destroy).pack(pady=10)

class LicenseWindow:
    def __init__(self, parent, on_accept):
        self.on_accept = on_accept
        self.window = ctk.CTkToplevel(parent)
        self.window.title("Лицензионное соглашение")
        self.window.geometry("650x550")
        self.window.resizable(False, False)
        self.window.grab_set()
        self.window.configure(fg_color="#FFFFFF")
        set_window_icon(self.window)
        self.center_window()
        self.window.protocol("WM_DELETE_WINDOW", self.on_decline)
        self.setup_ui()
    
    def center_window(self):
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 650) // 2
        y = (self.window.winfo_screenheight() - 550) // 2
        self.window.geometry(f"650x550+{x}+{y}")
    
    def setup_ui(self):
        main = ctk.CTkFrame(self.window, fg_color="#FFFFFF", corner_radius=0)
        main.pack(fill="both", expand=True)
        header = ctk.CTkFrame(main, fg_color="#FFFFFF", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="⚖️", font=ctk.CTkFont(size=28), text_color="#2563EB").pack(side="left", padx=(20,10), pady=15)
        ctk.CTkLabel(header, text="Лицензионное соглашение", font=ctk.CTkFont(size=18, weight="bold"), text_color="#0F172A").pack(side="left", pady=15)
        ctk.CTkLabel(header, text="v3.0", font=ctk.CTkFont(size=11, weight="bold"), text_color="#2563EB", fg_color="#EFF6FF", corner_radius=6, padx=8, pady=2).pack(side="left", padx=10, pady=18)
        content = ctk.CTkFrame(main, fg_color="#FFFFFF")
        content.pack(fill="both", expand=True, padx=25, pady=(10,20))
        text_area = ctk.CTkScrollableFrame(content, fg_color="#F8FAFC", corner_radius=12, border_width=1, border_color="#E2E8F0")
        text_area.pack(fill="both", expand=True, pady=(0,15))
        
        sections = [
            ("📌 1. О ПРОГРАММЕ", 
             "Video Grabber является инструментом для удобного переноса личных данных "
             "с популярных видео-сервисов.\n\nПрограмма предназначена для:\n"
             "• Архивирования вашего личного контента\n"
             "• Создания резервных копий собственных каналов\n"
             "• Просмотра видео в образовательных целях в офлайн-режиме"),
            
            ("⚠️ 2. ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ", 
             "АВТОР ПРОГРАММЫ НЕ НЕСЁТ НИКАКОЙ ОТВЕТСТВЕННОСТИ ЗА:\n\n"
             "• Использование программы в целях, нарушающих законодательство\n"
             "• Скачивание чужих видеороликов без разрешения авторов\n"
             "• Нарушение авторских прав и условий использования сервисов\n"
             "• Любые прямые или косвенные убытки\n\n"
             "Пользователь берёт на себя ПОЛНУЮ ОТВЕТСТВЕННОСТЬ за соблюдение "
             "авторских прав и условий использования сервисов."),
            
            ("🔒 3. ОГРАНИЧЕНИЯ ИСПОЛЬЗОВАНИЯ", 
             "• Программа поставляется в ОЗНАКОМИТЕЛЬНЫХ целях\n"
             "• Запрещено массовое скачивание контента\n"
             "• Запрещено коммерческое использование\n"
             "• Запрещено распространение скачанного контента\n"
             "• Запрещено изменение или декомпиляция программы"),
            
            ("📚 4. ИСПОЛЬЗУЕМЫЕ БИБЛИОТЕКИ", 
             "Программа использует следующие открытые библиотеки:\n\n"
             "• yt-dlp (Лицензия Unlicense)\n"
             "  github.com/yt-dlp/yt-dlp\n\n"
             "• customtkinter (Лицензия MIT)\n"
             "  github.com/TomSchimansky/CustomTkinter\n\n"
             "• pillow (Лицензия HPND)\n"
             "  github.com/python-pillow/Pillow"),
            
            ("🎯 5. НАЗНАЧЕНИЕ ИНСТРУМЕНТА", 
             "Данный инструмент создан ИСКЛЮЧИТЕЛЬНО для:\n\n"
             "✓ Архивирования личного контента\n"
             "✓ Бэкапов собственных каналов и плейлистов\n"
             "✓ Офлайн-доступа к образовательным материалам\n"
             "✓ Технического тестирования возможностей загрузки"),
            
            ("✅ 6. ПОДТВЕРЖДЕНИЕ", 
             "Принимая условия, вы подтверждаете, что:\n\n"
             "✓ Ознакомлены с условиями использования\n"
             "✓ Понимаете возможные риски\n"
             "✓ Будете использовать программу легально\n"
             "✓ Не будете распространять скачанный контент\n"
             "✓ Принимаете полную ответственность на себя")
        ]
        
        for title, text in sections:
            ctk.CTkLabel(text_area, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="#2563EB", anchor="w", justify="left").pack(anchor="w", padx=15, pady=(10,5))
            ctk.CTkLabel(text_area, text=text, font=ctk.CTkFont(size=12), text_color="#334155", anchor="w", wraplength=560, justify="left").pack(anchor="w", padx=15, pady=(0,10))
            ctk.CTkFrame(text_area, fg_color="#E2E8F0", height=1).pack(fill="x", padx=15, pady=(5,0))
        
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")
        ctk.CTkButton(btn_frame, text="✅ Принимаю условия", font=ctk.CTkFont(size=14, weight="bold"), fg_color="#10B981", hover_color="#059669", height=44, corner_radius=10, command=self._do_accept).pack(side="right", padx=(10,0), pady=5)
        ctk.CTkButton(btn_frame, text="❌ Отказываюсь", font=ctk.CTkFont(size=14), fg_color="#EF4444", hover_color="#DC2626", height=44, corner_radius=10, command=self.on_decline).pack(side="right", pady=5)
    
    def _do_accept(self):
        self.on_accept()
        self.window.destroy()
    def on_decline(self):
        self.window.destroy()
        sys.exit(0)

class AboutWindow:
    def __init__(self, parent, video_grabber_instance):
        self.parent = parent
        self.video_grabber = video_grabber_instance
        self.window = ctk.CTkToplevel(parent)
        self.window.title("О программе")
        self.window.geometry("500x650")
        self.window.resizable(False, False)
        self.window.grab_set()
        self.window.configure(fg_color="#FFFFFF")
        set_window_icon(self.window)
        self.center_window()
        self.setup_ui()
    
    def center_window(self):
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 500) // 2
        y = (self.window.winfo_screenheight() - 650) // 2
        self.window.geometry(f"500x650+{x}+{y}")
    
    def setup_ui(self):
        main = ctk.CTkFrame(self.window, fg_color="#FFFFFF", corner_radius=0)
        main.pack(fill="both", expand=True)
        scroll = ctk.CTkScrollableFrame(main, fg_color="#FFFFFF", corner_radius=0)
        scroll.pack(fill="both", expand=True)
        icon_path = get_icon_path()
        if icon_path and icon_path.exists():
            try:
                img = Image.open(icon_path).resize((64,64), Image.Resampling.LANCZOS)
                icon_img = ctk.CTkImage(light_image=img, dark_image=img, size=(64,64))
                logo = ctk.CTkLabel(scroll, image=icon_img, text="")
                logo.image = icon_img
            except:
                logo = ctk.CTkLabel(scroll, text="🎬", font=ctk.CTkFont(size=64), text_color="#2563EB")
        else:
            logo = ctk.CTkLabel(scroll, text="🎬", font=ctk.CTkFont(size=64), text_color="#2563EB")
        logo.pack(pady=(25,10))
        ctk.CTkLabel(scroll, text="Video Grabber", font=ctk.CTkFont(size=28, weight="bold"), text_color="#0F172A").pack()
        ctk.CTkLabel(scroll, text="Версия 3.0", font=ctk.CTkFont(size=13), text_color="#64748B").pack(pady=(5,20))
        ctk.CTkFrame(scroll, fg_color="#E2E8F0", height=1).pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(scroll, text="Инструмент для архивирования личного контента\nсо 1800+ видео-сервисов", font=ctk.CTkFont(size=12), text_color="#475569", justify="center").pack(pady=(15,10))
        
        update_btn = ctk.CTkButton(scroll, text="🔄 Обновить компоненты (yt-dlp и FFmpeg)", font=ctk.CTkFont(size=13, weight="bold"), fg_color="#2563EB", hover_color="#1D4ED8", height=38, corner_radius=8, command=self.run_updater)
        update_btn.pack(pady=10, padx=20)
        
        author = ctk.CTkFrame(scroll, fg_color="#F8FAFC", corner_radius=10)
        author.pack(fill="x", padx=25, pady=10)
        ctk.CTkLabel(author, text="👨‍💻 Автор программы", font=ctk.CTkFont(size=13, weight="bold"), text_color="#0F172A").pack(anchor="w", padx=15, pady=(10,5))
        ctk.CTkLabel(author, text="Павел Прилуцкий", font=ctk.CTkFont(size=12), text_color="#2563EB").pack(anchor="w", padx=15, pady=(0,5))
        ctk.CTkLabel(author, text="📞 Связь", font=ctk.CTkFont(size=13, weight="bold"), text_color="#0F172A").pack(anchor="w", padx=15, pady=(10,5))
        def open_vk(): webbrowser.open("https://vk.com/kerfaers")
        def open_tg(): webbrowser.open("https://t.me/Pavel_Priluckiy")
        vk = ctk.CTkLabel(author, text="VK: https://vk.com/kerfaers", font=ctk.CTkFont(size=11), text_color="#3B82F6", cursor="hand2")
        vk.pack(anchor="w", padx=15, pady=(0,3))
        vk.bind("<Button-1>", lambda e: open_vk())
        tg = ctk.CTkLabel(author, text="Telegram: @Pavel_Priluckiy", font=ctk.CTkFont(size=11), text_color="#3B82F6", cursor="hand2")
        tg.pack(anchor="w", padx=15, pady=(0,10))
        tg.bind("<Button-1>", lambda e: open_tg())
        libs = ctk.CTkFrame(scroll, fg_color="#F8FAFC", corner_radius=10)
        libs.pack(fill="x", padx=25, pady=10)
        ctk.CTkLabel(libs, text="📦 Используемые библиотеки", font=ctk.CTkFont(size=13, weight="bold"), text_color="#0F172A").pack(anchor="w", padx=15, pady=(10,5))
        ctk.CTkLabel(libs, text="• yt-dlp (Unlicense) — 1800+ сайтов", font=ctk.CTkFont(size=11), text_color="#475569").pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(libs, text="• customtkinter (MIT)", font=ctk.CTkFont(size=11), text_color="#475569").pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(libs, text="• pillow (HPND)", font=ctk.CTkFont(size=11), text_color="#475569").pack(anchor="w", padx=15, pady=(2,10))

        disc = ctk.CTkFrame(scroll, fg_color="#FEF2F2", corner_radius=8)
        disc.pack(fill="x", padx=25, pady=(15,20))
        ctk.CTkLabel(disc, text="⚠️ Данный инструмент предназначен для архивирования личного контента.\nПользователь несёт полную ответственность за соблюдение авторских прав.", font=ctk.CTkFont(size=10), text_color="#991B1B", wraplength=430, justify="center").pack(padx=10, pady=10)
    
    def run_updater(self):
        self.window.destroy()
        UpdaterProgressWindow(self.parent, self.video_grabber.ffmpeg_dir, on_complete=self.video_grabber.on_update_complete)
    
    def on_update_complete(self):
        refresh_ffmpeg_state()
        status = "FFmpeg найден — высокое качество доступно." if FFMPEG_AVAILABLE else "FFmpeg не найден. Качество ограничено 360p."
        messagebox.showinfo("Обновление завершено", "Компоненты обновлены.\n\n" + status)

class WidgetStateManager:
    def __init__(self):
        self.state_widgets = {}
        self.current_state = None
    def register_widget(self, state_name, widget, pack_config=None):
        if state_name not in self.state_widgets:
            self.state_widgets[state_name] = []
        self.state_widgets[state_name].append({'widget': widget, 'pack_config': pack_config or {}})
    def switch_state(self, new_state, parent_frame):
        if self.current_state and self.current_state in self.state_widgets:
            for item in self.state_widgets[self.current_state]:
                try:
                    item['widget'].pack_forget()
                except:
                    pass
        if new_state in self.state_widgets:
            for item in self.state_widgets[new_state]:
                try:
                    item['widget'].pack(**item['pack_config'])
                except:
                    pass
        self.current_state = new_state
    def cleanup(self):
        for widgets in self.state_widgets.values():
            for item in widgets:
                try:
                    if hasattr(item['widget'], 'destroy'):
                        item['widget'].destroy()
                except:
                    pass
        self.state_widgets.clear()

class VideoGrabber:
    def __init__(self):
        self.animation_running = True
        self.fade_id = None
        self.current_info_lock = threading.Lock()
        self.download_lock = threading.Lock()
        self.load_settings()

        if getattr(sys, 'frozen', False):
            _base = Path(sys.executable).parent
        else:
            _base = Path(__file__).parent
        self.ffmpeg_dir = _base / "ffmpeg"

        self._temp_root = ctk.CTk()
        self._temp_root.withdraw()

        self.check_components_first_run()

        if not self.is_license_accepted():
            self.root = self._temp_root
            self.show_license_window()
        else:
            self._temp_root.destroy()
            self.init_main_app()
    
    def check_components_first_run(self):
        yt_path = self.ffmpeg_dir / "yt-dlp.exe"
        ff_path = self.ffmpeg_dir / "ffmpeg.exe"
        yt_exists = yt_path.exists()
        ff_exists = ff_path.exists()

        need_update = not yt_exists or not ff_exists

        if yt_exists and not need_update:
            local_ver = YtDlpUpdater.get_local_version(yt_path)
            latest_ver = YtDlpUpdater.get_latest_version()
            if local_ver and latest_ver and local_ver != latest_ver:
                answer = messagebox.askyesno(
                    "Доступно обновление yt-dlp",
                    f"Установлена версия yt-dlp: {local_ver}\n"
                    f"Новая версия: {latest_ver}\n\n"
                    "YouTube постоянно меняет защиту — старые версии могут не скачивать видео выше 360p.\n\n"
                    "Обновить сейчас?"
                )
                if answer:
                    need_update = True

        if need_update:
            answer = messagebox.askyesno(
                "Отсутствуют компоненты" if not yt_exists or not ff_exists else "Обновление компонентов",
                "Для работы программы необходимы yt-dlp и FFmpeg.\n\n"
                "Хотите загрузить/обновить их сейчас?\n(Около 50 МБ)"
            )
            if answer:
                temp_root = ctk.CTk()
                temp_root.withdraw()
                UpdaterProgressWindow(temp_root, self.ffmpeg_dir, on_complete=lambda: temp_root.after(100, temp_root.destroy))
                temp_root.mainloop()
            else:
                messagebox.showwarning(
                    "Компоненты не загружены",
                    "Без актуальной версии yt-dlp YouTube может ограничивать качество до 360p.\n\n"
                    "Вы можете обновить позже через меню 'О программе'."
                )
    
    def on_update_complete(self):
        refresh_ffmpeg_state()
        status = "✅ FFmpeg найден — скачивание в высоком качестве доступно." if FFMPEG_AVAILABLE else "⚠️ FFmpeg не найден. Качество будет ограничено 360p."
        messagebox.showinfo("Обновление завершено", f"Компоненты успешно обновлены.\n\n{status}")
    
    def load_settings(self):
        self.download_path = str(Path.home() / "Downloads")
        self.selected_quality = "Лучшее"
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'download_path' in data and os.path.exists(data['download_path']):
                        self.download_path = data['download_path']
                    if 'quality' in data:
                        self.selected_quality = data['quality']
        except:
            pass
    def save_settings(self):
        try:
            data = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data['download_path'] = self.download_path
            data['quality'] = self.selected_quality
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except:
            pass
    def is_license_accepted(self):
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('license_accepted', False)
        except:
            pass
        return False
    def save_license_accepted(self):
        try:
            data = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data['license_accepted'] = True
            data['version'] = '3.0'
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except:
            pass
    def show_license_window(self):
        def accept():
            self.save_license_accepted()
            self.root.quit()
            self.root.destroy()
            self.init_main_app()
        LicenseWindow(self.root, accept)
        self.root.mainloop()
    
    def init_main_app(self):
        self.root = ctk.CTk()
        self.root.title("Video Grabber")
        self.root.configure(fg_color="#FFFFFF")
        set_window_icon(self.root)
        if platform.system() == "Windows":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VideoGrabber.App")
            except:
                pass
        self.window_width = 480
        self.window_height = 320
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.root.resizable(False, False)
        self.state_manager = WidgetStateManager()
        self.current_info = None
        self.is_downloading = False
        self.should_stop = False
        self.current_ydl = None
        self.total_size = 0
        self.downloaded = 0
        self.start_time = None
        self.playlist_videos = []
        self.skipped_videos = set()
        self.is_playlist = False
        self.selected_video_index = 0
        self.thumbnail_cache = {}
        self._thumbnail_semaphore = threading.Semaphore(5)
        self.video_title = None
        self.video_widgets_data = []
        self.downloaded_videos = 0
        self.total_videos = 0
        self.current_video_title = ""
        self.colors = {
            'primary': '#2563EB', 'primary_hover': '#1D4ED8', 'success': '#10B981',
            'danger': '#EF4444', 'danger_hover': '#DC2626', 'bg': '#FFFFFF',
            'surface': '#F8FAFC', 'border': '#E2E8F0', 'text': '#0F172A',
            'text_secondary': '#64748B', 'text_light': '#94A3B8',
        }
        self.setup_ui()
        self.center_window()
        
        # Исправленный обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.root.attributes('-alpha', 0.0)
        self.fade_in()
        self.setup_context_menu()
        if not FFMPEG_AVAILABLE:
            self.root.after(800, self._warn_no_ffmpeg)
    
    def setup_context_menu(self):
        def show_context_menu(event):
            menu = Menu(self.root, tearoff=False)
            menu.add_command(label="О программе", command=self.show_about)
            menu.add_separator()
            menu.add_command(label="Выход", command=self.on_closing)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        self.root.bind("<Button-3>", show_context_menu)
    
    def open_updater_from_menu(self):
        UpdaterProgressWindow(self.root, self.ffmpeg_dir, on_complete=self.on_update_complete)
    
    def _warn_no_ffmpeg(self):
        answer = messagebox.askyesno(
            "FFmpeg не найден",
            "FFmpeg не обнаружен — без него YouTube отдаёт видео максимум в 360p.\n\n"
            "Хотите скачать FFmpeg и yt-dlp прямо сейчас?\n"
            "(~50 МБ, потребуется один раз)"
        )
        if answer:
            UpdaterProgressWindow(self.root, self.ffmpeg_dir, on_complete=self.on_update_complete)

    def show_about(self):
        AboutWindow(self.root, self)
    
    def fade_in(self):
        try:
            if not self.animation_running:
                return
            alpha = self.root.attributes('-alpha')
            if alpha < 1.0:
                alpha += 0.1
                self.root.attributes('-alpha', min(alpha, 1.0))
                self.fade_id = self.root.after(50, self.fade_in)
            else:
                self.fade_id = None
        except:
            pass
    def center_window(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.window_width) // 2
        y = (self.root.winfo_screenheight() - self.window_height) // 2
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
    def get_random_user_agent(self):
        return random.choice(USER_AGENTS)
    
    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self.root, fg_color=self.colors['bg'], corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color=self.colors['bg'], height=50)
        self.header_frame.pack(fill="x")
        self.header_frame.pack_propagate(False)
        ctk.CTkLabel(self.header_frame, text="🎬", font=ctk.CTkFont(size=24), text_color=self.colors['primary']).pack(side="left", padx=(30,8), pady=10)
        ctk.CTkLabel(self.header_frame, text="Video Grabber", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.colors['text']).pack(side="left", pady=10)
        ctk.CTkLabel(self.header_frame, text="PRO", font=ctk.CTkFont(size=10, weight="bold"), text_color=self.colors['primary'], fg_color="#EFF6FF", corner_radius=4).pack(side="left", padx=8, pady=12)
        about_btn = ctk.CTkButton(self.header_frame, text="ℹ️", font=ctk.CTkFont(size=16), width=30, height=30, corner_radius=15, fg_color="transparent", text_color=self.colors['text_secondary'], hover_color=self.colors['surface'], command=self.show_about)
        about_btn.pack(side="right", padx=(0,20), pady=10)
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color=self.colors['bg'])
        self.content_frame.pack(fill="both", expand=True, padx=25, pady=(0,15))
        self.create_initial_state_widgets()
        self.create_video_state_widgets()
        self.create_playlist_state_widgets()
        self.state_manager.switch_state('initial', self.content_frame)
    
    def create_initial_state_widgets(self):
        state = 'initial'
        instr = ctk.CTkLabel(self.content_frame, text="Вставьте ссылку на видео, плейлист или канал", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.colors['text'])
        self.state_manager.register_widget(state, instr, {'pady': (15,5)})
        inp = ctk.CTkFrame(self.content_frame, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'])
        self.state_manager.register_widget(state, inp, {'fill': 'x', 'padx': 5, 'pady': (0,12)})
        self.url_entry = ctk.CTkEntry(inp, placeholder_text="https://youtube.com/watch?v=... или любой другой сайт", font=ctk.CTkFont(size=13), fg_color=self.colors['surface'], border_width=0, text_color=self.colors['text'], height=42)
        self.url_entry.pack(fill="x", padx=12, pady=3)
        self.bind_paste_events()
        self.analyze_button = ctk.CTkButton(self.content_frame, text="Анализировать", font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.colors['primary'], hover_color=self.colors['primary_hover'], height=40, corner_radius=8, command=self.start_analysis)
        self.state_manager.register_widget(state, self.analyze_button, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        sites_btn = ctk.CTkButton(self.content_frame, text="🌐 Список поддерживаемых сайтов (1800+)", font=ctk.CTkFont(size=12), fg_color="transparent", text_color=self.colors['text_secondary'], hover_color=self.colors['surface'], height=30, corner_radius=6, command=lambda: SupportedSitesWindow(self.root))
        self.state_manager.register_widget(state, sites_btn, {'fill': 'x', 'padx': 5, 'pady': (5,0)})
    
    def bind_paste_events(self):
        from tkinter import Menu
        self.url_entry.bind('<<Paste>>', self.on_paste_event)
        def check_ctrl_v(e):
            if (e.state & 0x4) and e.keycode == 86:
                self.root.after(10, self.paste_from_clipboard)
                return "break"
            return None
        self.root.bind('<Control-Key>', check_ctrl_v)
        self.root.bind('<Control-v>', self.on_ctrl_v)
        self.root.bind('<Control-V>', self.on_ctrl_v)
        def show_ctx(e):
            m = Menu(self.root, tearoff=False)
            m.add_command(label="Вставить", command=self.paste_from_clipboard)
            m.add_separator()
            m.add_command(label="Очистить", command=lambda: self.url_entry.delete(0,'end'))
            try:
                m.tk_popup(e.x_root, e.y_root)
            finally:
                m.grab_release()
        self.url_entry.bind('<Button-3>', show_ctx)
        self.url_entry.bind('<Return>', lambda e: self.start_analysis())
    def on_paste_event(self, e):
        self.root.after(10, self.paste_from_clipboard)
        return "break"
    def on_ctrl_v(self, e):
        self.root.after(10, self.paste_from_clipboard)
        return "break"
    def paste_from_clipboard(self):
        try:
            txt = self.root.clipboard_get()
            if txt:
                txt = txt.strip()
                self.url_entry.delete(0,'end')
                self.url_entry.insert(0, txt)
                self.url_entry.configure(border_color=self.colors['primary'])
                self.root.after(500, lambda: self.url_entry.configure(border_color=self.colors['border']))
                self.root.after(800, self.start_analysis)
        except:
            pass
    
    def create_video_state_widgets(self):
        state = 'video'
        self.video_info_frame = ctk.CTkFrame(self.content_frame, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'])
        self.state_manager.register_widget(state, self.video_info_frame, {'fill': 'x', 'padx': 5, 'pady': (0,10)})
        info_row = ctk.CTkFrame(self.video_info_frame, fg_color="transparent")
        info_row.pack(fill="x", padx=12, pady=12)
        self.preview_frame = ctk.CTkFrame(info_row, width=120, height=75, fg_color="#E2E8F0", corner_radius=6, cursor="hand2")
        self.preview_frame.pack(side="left")
        self.preview_frame.pack_propagate(False)
        self.preview_label = ctk.CTkLabel(self.preview_frame, text="🎬", font=ctk.CTkFont(size=24), text_color=self.colors['text_light'])
        self.preview_label.pack(expand=True)
        self.preview_frame.bind("<Button-1>", self.on_preview_click)
        self.preview_label.bind("<Button-1>", self.on_preview_click)
        text_info = ctk.CTkFrame(info_row, fg_color="transparent")
        text_info.pack(side="left", fill="both", expand=True, padx=(12,0))
        title_row = ctk.CTkFrame(text_info, fg_color="transparent")
        title_row.pack(fill="x", anchor="w", pady=(0,5))
        self.title_label = ctk.CTkLabel(title_row, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.colors['text'], wraplength=140, anchor="w")
        self.title_label.pack(side="left", fill="x", expand=True)
        self.cancel_button = ctk.CTkButton(title_row, text="✖", font=ctk.CTkFont(size=13, weight="bold"), fg_color="transparent", text_color=self.colors['danger'], hover_color=self.colors['danger_hover'], width=24, height=24, corner_radius=12, command=self.cancel_and_return)
        self.cancel_button.pack(side="right", padx=(5,0))
        self.video_meta_frame = ctk.CTkFrame(text_info, fg_color="transparent")
        self.video_meta_frame.pack(fill="x", anchor="w")
        self.video_progress_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.state_manager.register_widget(state, self.video_progress_container, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        self.progress_bar = ctk.CTkProgressBar(self.video_progress_container, height=5, progress_color=self.colors['success'], fg_color=self.colors['border'], corner_radius=3)
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)
        stats = ctk.CTkFrame(self.video_progress_container, fg_color="transparent")
        stats.pack(fill="x", pady=(4,0))
        self.speed_label = ctk.CTkLabel(stats, text="Готов к загрузке", font=ctk.CTkFont(size=11), text_color=self.colors['text_secondary'])
        self.speed_label.pack(side="left")
        self.size_label = ctk.CTkLabel(stats, text="", font=ctk.CTkFont(size=11), text_color=self.colors['text_light'])
        self.size_label.pack(side="right")
        self.download_button = ctk.CTkButton(self.content_frame, text="Скачать видео", font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.colors['primary'], hover_color=self.colors['primary_hover'], height=42, corner_radius=8, command=self.toggle_download)
        self.state_manager.register_widget(state, self.download_button, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        opts = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.state_manager.register_widget(state, opts, {'fill': 'x', 'padx': 5})
        self.quality_menu = ctk.CTkOptionMenu(opts, values=["Лучшее", "1080p", "720p", "480p", "360p", "Аудио"], width=100, height=32, font=ctk.CTkFont(size=11), fg_color=self.colors['surface'], text_color=self.colors['text'], button_color=self.colors['primary'], corner_radius=6)
        self.quality_menu.pack(side="left", padx=(0,5))
        self.quality_menu.set(self.selected_quality)
        self.quality_menu.configure(command=self.on_quality_changed)
        self.open_folder_button = ctk.CTkButton(opts, text="Открыть папку", font=ctk.CTkFont(size=11), fg_color=self.colors['surface'], text_color=self.colors['text'], hover_color=self.colors['border'], height=32, corner_radius=6, command=self.open_download_folder, state="disabled")
        self.open_folder_button.pack(side="left", padx=(0,5))
        self.folder_button = ctk.CTkButton(opts, text="Выбрать папку", font=ctk.CTkFont(size=11), fg_color=self.colors['surface'], text_color=self.colors['text'], hover_color=self.colors['border'], height=32, corner_radius=6, command=self.select_folder)
        self.folder_button.pack(side="left")
    def on_quality_changed(self, choice):
        self.selected_quality = choice
        self.save_settings()
    
    def create_playlist_state_widgets(self):
        state = 'playlist'
        self.playlist_title_frame = ctk.CTkFrame(self.content_frame, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'])
        self.state_manager.register_widget(state, self.playlist_title_frame, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        title_row = ctk.CTkFrame(self.playlist_title_frame, fg_color="transparent")
        title_row.pack(fill="x", padx=12, pady=(10,5))
        self.playlist_title_label = ctk.CTkLabel(title_row, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.colors['text'], wraplength=260, anchor="w")
        self.playlist_title_label.pack(side="left", fill="x", expand=True)
        self.playlist_cancel_button = ctk.CTkButton(title_row, text="✖", font=ctk.CTkFont(size=13, weight="bold"), fg_color="transparent", text_color=self.colors['danger'], hover_color=self.colors['danger_hover'], width=24, height=24, corner_radius=12, command=self.cancel_and_return)
        self.playlist_cancel_button.pack(side="right", padx=(5,0))
        self.playlist_count_label = ctk.CTkLabel(self.playlist_title_frame, text="", font=ctk.CTkFont(size=11), text_color=self.colors['text_secondary'])
        self.playlist_count_label.pack(padx=12, pady=(0,10))
        self.playlist_list_frame = ctk.CTkScrollableFrame(self.content_frame, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'], height=350)
        self.state_manager.register_widget(state, self.playlist_list_frame, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        self.playlist_preview_container = ctk.CTkFrame(self.content_frame, fg_color=self.colors['surface'], corner_radius=10, border_width=1, border_color=self.colors['border'], height=100)
        self.state_manager.register_widget(state, self.playlist_preview_container, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        self.playlist_preview_container.pack_propagate(False)
        self.playlist_download_button = ctk.CTkButton(self.content_frame, text="Скачать плейлист", font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.colors['primary'], hover_color=self.colors['primary_hover'], height=42, corner_radius=8, command=self.toggle_download)
        self.state_manager.register_widget(state, self.playlist_download_button, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        prog_cont = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.state_manager.register_widget(state, prog_cont, {'fill': 'x', 'padx': 5, 'pady': (0,8)})
        self.playlist_progress_bar = ctk.CTkProgressBar(prog_cont, height=5, progress_color=self.colors['success'], fg_color=self.colors['border'], corner_radius=3)
        self.playlist_progress_bar.pack(fill="x")
        self.playlist_progress_bar.set(0)
        self.current_video_label = ctk.CTkLabel(prog_cont, text="", font=ctk.CTkFont(size=11), text_color=self.colors['text_secondary'])
        self.current_video_label.pack(pady=(4,0))
        self.playlist_stats_label = ctk.CTkLabel(prog_cont, text="", font=ctk.CTkFont(size=11), text_color=self.colors['text_secondary'])
        self.playlist_stats_label.pack()
        opts = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.state_manager.register_widget(state, opts, {'fill': 'x', 'padx': 5})
        self.playlist_quality_menu = ctk.CTkOptionMenu(opts, values=["Лучшее", "1080p", "720p", "480p", "360p", "Аудио"], width=100, height=32, font=ctk.CTkFont(size=11), fg_color=self.colors['surface'], text_color=self.colors['text'], button_color=self.colors['primary'], corner_radius=6)
        self.playlist_quality_menu.pack(side="left", padx=(0,5))
        self.playlist_quality_menu.set(self.selected_quality)
        self.playlist_quality_menu.configure(command=self.on_quality_changed)
        self.playlist_open_folder_button = ctk.CTkButton(opts, text="Открыть папку", font=ctk.CTkFont(size=11), fg_color=self.colors['surface'], text_color=self.colors['text'], hover_color=self.colors['border'], height=32, corner_radius=6, command=self.open_download_folder, state="disabled")
        self.playlist_open_folder_button.pack(side="left", padx=(0,5))
        self.playlist_folder_button = ctk.CTkButton(opts, text="Выбрать папку", font=ctk.CTkFont(size=11), fg_color=self.colors['surface'], text_color=self.colors['text'], hover_color=self.colors['border'], height=32, corner_radius=6, command=self.select_folder)
        self.playlist_folder_button.pack(side="left")
    
    def on_preview_click(self, e=None):
        with self.current_info_lock:
            if self.current_info:
                url = self.current_info.get('webpage_url','')
                if url:
                    webbrowser.open(url)
    def on_playlist_preview_click(self, e=None):
        if self.selected_video_index < len(self.playlist_videos):
            url = self.playlist_videos[self.selected_video_index].get('webpage_url') or self.playlist_videos[self.selected_video_index].get('url')
            if url:
                webbrowser.open(url)
    def open_download_folder(self):
        if os.path.exists(self.download_path):
            os.startfile(self.download_path)
    def enable_open_folder_button(self):
        if hasattr(self, 'open_folder_button'):
            self.open_folder_button.configure(state="normal", fg_color=self.colors['success'], text_color="white")
        if hasattr(self, 'playlist_open_folder_button'):
            self.playlist_open_folder_button.configure(state="normal", fg_color=self.colors['success'], text_color="white")
    def select_folder(self):
        path = filedialog.askdirectory(initialdir=self.download_path)
        if path:
            self.download_path = path
            self.save_settings()
    
    def cancel_and_return(self):
        if self.is_downloading:
            with self.download_lock:
                self.should_stop = True
                self.is_downloading = False
            time.sleep(0.5)
        self.current_info = None
        self.playlist_videos = []
        self.skipped_videos.clear()
        self.is_playlist = False
        self.downloaded_videos = 0
        self.total_videos = 0
        if hasattr(self, 'progress_bar'): self.progress_bar.set(0)
        if hasattr(self, 'speed_label'): self.speed_label.configure(text="Готов к загрузке")
        if hasattr(self, 'size_label'): self.size_label.configure(text="")
        if hasattr(self, 'playlist_progress_bar'): self.playlist_progress_bar.set(0)
        if hasattr(self, 'playlist_stats_label'): self.playlist_stats_label.configure(text="")
        if hasattr(self, 'current_video_label'): self.current_video_label.configure(text="")
        self.url_entry.delete(0,'end')
        self.state_manager.switch_state('initial', self.content_frame)
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.url_entry.focus()
    
    def switch_to_video_state(self, info):
        self.is_playlist = False
        with self.current_info_lock:
            self.current_info = info
        title = safe_filename(info.get('title', 'Неизвестное видео'), 30)
        self.title_label.configure(text=title)
        for w in self.video_meta_frame.winfo_children(): w.destroy()
        dur = info.get('duration',0)
        if dur:
            badge = ctk.CTkFrame(self.video_meta_frame, fg_color=self.colors['bg'], corner_radius=4)
            badge.pack(side="left", padx=(0,5))
            ctk.CTkLabel(badge, text=f"⏱ {str(timedelta(seconds=dur))}", font=ctk.CTkFont(size=10), text_color=self.colors['text_secondary']).pack(padx=5, pady=2)
        best_h = 0
        for f in info.get('formats',[]):
            h = f.get('height',0) or 0
            if h>best_h: best_h = h
        if best_h>0:
            badge = ctk.CTkFrame(self.video_meta_frame, fg_color=self.colors['bg'], corner_radius=4)
            badge.pack(side="left")
            ctk.CTkLabel(badge, text=f"📺 {best_h}p", font=ctk.CTkFont(size=10), text_color=self.colors['text_secondary']).pack(padx=5, pady=2)
        self.progress_bar.set(0)
        self.speed_label.configure(text="Готов к загрузке")
        self.size_label.configure(text="")
        self.download_button.configure(text="Скачать видео", fg_color=self.colors['primary'])
        self.open_folder_button.configure(state="disabled")
        self.state_manager.switch_state('video', self.content_frame)
        self.root.geometry(f"{self.window_width}x{440}")
        if info.get('thumbnail'):
            threading.Thread(target=self.load_thumbnail, args=(info['thumbnail'], 'video'), daemon=True).start()
    
    def is_channel_url(self, url):
        patterns = [
            r'youtube\.com/@[\w-]+/?$', r'youtube\.com/channel/[\w-]+/?$', r'youtube\.com/c/[\w-]+/?$', r'youtube\.com/user/[\w-]+/?$',
            r'vk\.com/@[\w-]+/?$', r'vkvideo\.ru/@[\w-]+/?$',
            r'rutube\.ru/channel/[\d]+/?$', r'rutube\.ru/user/[\w-]+/?$',
            r'dzen\.ru/[\w-]+/?$', r'zen\.yandex\.ru/[\w-]+/?$',
            r'bilibili\.com/space/[\d]+', r'twitch\.tv/[\w-]+/?$'
        ]
        return any(re.search(p, url.lower()) for p in patterns)
    
    def switch_to_playlist_state(self, info):
        self.is_playlist = True
        self.skipped_videos.clear()
        self.downloaded_videos = 0
        self.total_videos = len(self.playlist_videos)
        is_channel = self.is_channel_url(self.url_entry.get())
        content_type = "канала" if is_channel else "плейлиста"
        pl_title = safe_filename(info.get('title', content_type), 35)
        self.playlist_title_label.configure(text=f"{'📺' if is_channel else '📋'} {pl_title}")
        self.playlist_count_label.configure(text=f"{self.total_videos} видео")
        if self.total_videos > 1000:
            self.playlist_videos = self.playlist_videos[:1000]
            self.playlist_count_label.configure(text=f"{len(self.playlist_videos)} видео (ограничено)")
            self.total_videos = len(self.playlist_videos)
        for w in self.playlist_list_frame.winfo_children(): w.destroy()
        self.video_widgets_data = []
        for i, vid in enumerate(self.playlist_videos):
            vid_title = safe_filename(vid.get('title', f'Видео {i+1}'), 45)
            item = ctk.CTkFrame(self.playlist_list_frame, fg_color=self.colors['bg'] if i%2==0 else self.colors['surface'], corner_radius=0)
            item.pack(fill="x", pady=2)
            item.bind("<Button-3>", lambda e, idx=i: self.show_playlist_context_menu(e, idx))
            top = ctk.CTkFrame(item, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(4,2))
            ctk.CTkLabel(top, text=f"{i+1}", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors['text_light'], width=30).pack(side="left")
            btn = ctk.CTkButton(top, text=vid_title, font=ctk.CTkFont(size=11), fg_color="transparent", text_color=self.colors['text'], hover_color=self.colors['border'], anchor="w", height=28, corner_radius=4, command=lambda idx=i: self.select_playlist_video(idx))
            btn.pack(side="left", fill="x", expand=True, padx=5)
            btn.bind("<Button-3>", lambda e, idx=i: self.show_playlist_context_menu(e, idx))
            dur = vid.get('duration')
            if dur:
                ctk.CTkLabel(top, text=str(timedelta(seconds=dur)), font=ctk.CTkFont(size=10), text_color=self.colors['text_light'], width=50).pack(side="right")
            prog_frame = ctk.CTkFrame(item, fg_color="transparent")
            prog_frame.pack(fill="x", padx=8, pady=(0,4))
            pbar = ctk.CTkProgressBar(prog_frame, height=3, progress_color=self.colors['primary'], fg_color=self.colors['border'])
            pbar.pack(side="left", fill="x", expand=True, padx=(0,5))
            pbar.set(0)
            plab = ctk.CTkLabel(prog_frame, text="0%", font=ctk.CTkFont(size=9), text_color=self.colors['text_light'], width=35)
            plab.pack(side="right")
            self.video_widgets_data.append({
                'frame': item, 'index': i, 'progress_bar': pbar, 'progress_label': plab, 'title': vid_title
            })
        for w in self.playlist_preview_container.winfo_children(): w.destroy()
        left = ctk.CTkFrame(self.playlist_preview_container, fg_color="transparent")
        left.pack(side="left", fill="y", padx=12, pady=12)
        self.playlist_preview_frame = ctk.CTkFrame(left, width=120, height=68, fg_color="#E2E8F0", corner_radius=6, cursor="hand2")
        self.playlist_preview_frame.pack()
        self.playlist_preview_frame.pack_propagate(False)
        self.playlist_preview_label = ctk.CTkLabel(self.playlist_preview_frame, text="🎬", font=ctk.CTkFont(size=22), text_color=self.colors['text_light'])
        self.playlist_preview_label.pack(expand=True)
        self.playlist_preview_frame.bind("<Button-1>", self.on_playlist_preview_click)
        self.playlist_preview_label.bind("<Button-1>", self.on_playlist_preview_click)
        right = ctk.CTkFrame(self.playlist_preview_container, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(0,12), pady=12)
        self.selected_video_title = ctk.CTkLabel(right, text="Выберите видео", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.colors['text'], wraplength=170, anchor="w")
        self.selected_video_title.pack(anchor="w", pady=(0,3))
        self.selected_video_info = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=10), text_color=self.colors['text_secondary'])
        self.selected_video_info.pack(anchor="w")
        self.progress_bar.set(0)
        self.speed_label.configure(text="Готов к загрузке")
        self.size_label.configure(text="")
        self.playlist_progress_bar.set(0)
        self.playlist_stats_label.configure(text="")
        self.current_video_label.configure(text="")
        self.playlist_open_folder_button.configure(state="disabled")
        active = len(self.playlist_videos)
        self.playlist_download_button.configure(text=f"Скачать {content_type} ({active})", fg_color=self.colors['primary'])
        self.state_manager.switch_state('playlist', self.content_frame)
        self.root.geometry(f"{self.window_width}x{700}")
        if self.playlist_videos:
            self.select_playlist_video(0)
    
    def show_playlist_context_menu(self, event, index):
        menu = Menu(self.root, tearoff=False)
        if index in self.skipped_videos:
            menu.add_command(label="✅ Включить в загрузку", command=lambda: self.toggle_skip_video(index, False))
        else:
            menu.add_command(label="⏭ Пропустить при скачивании", command=lambda: self.toggle_skip_video(index, True))
        menu.add_separator()
        menu.add_command(label="📋 Копировать название", command=lambda: self.copy_video_title(index))
        menu.add_command(label="🔗 Копировать ссылку", command=lambda: self.copy_video_url(index))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    def toggle_skip_video(self, index, skip):
        if skip:
            self.skipped_videos.add(index)
            if index < len(self.video_widgets_data):
                self.video_widgets_data[index]['frame'].configure(fg_color="#FEF2F2")
        else:
            self.skipped_videos.discard(index)
            if index < len(self.video_widgets_data):
                self.video_widgets_data[index]['frame'].configure(fg_color=self.colors['bg'] if index%2==0 else self.colors['surface'])
        total = len(self.playlist_videos)
        active = total - len(self.skipped_videos)
        self.playlist_count_label.configure(text=f"{total} видео (пропущено: {len(self.skipped_videos)})")
        self.playlist_download_button.configure(text=f"Скачать плейлист ({active})")
    def copy_video_title(self, index):
        if index < len(self.playlist_videos):
            title = self.playlist_videos[index].get('title','')
            if title:
                self.root.clipboard_clear()
                self.root.clipboard_append(title)
                self.speed_label.configure(text="Название скопировано!")
                self.root.after(2000, lambda: self.speed_label.configure(text="Готов к загрузке"))
    def copy_video_url(self, index):
        if index < len(self.playlist_videos):
            url = self.playlist_videos[index].get('webpage_url') or self.playlist_videos[index].get('url')
            if url:
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                self.speed_label.configure(text="Ссылка скопирована!")
                self.root.after(2000, lambda: self.speed_label.configure(text="Готов к загрузке"))
    
    def select_playlist_video(self, index):
        if index >= len(self.playlist_videos): return
        self.selected_video_index = index
        video = self.playlist_videos[index]
        title = safe_filename(video.get('title', f'Видео {index+1}'), 35)
        self.selected_video_title.configure(text=title)
        dur = video.get('duration')
        if dur:
            self.selected_video_info.configure(text=f"⏱ {str(timedelta(seconds=dur))}")
        if video.get('thumbnail'):
            threading.Thread(target=self.load_thumbnail, args=(video['thumbnail'], 'playlist'), daemon=True).start()
    
    def load_thumbnail(self, url, target='video'):
        if len(self.thumbnail_cache) > 200:
            for k in list(self.thumbnail_cache.keys())[:50]:
                del self.thumbnail_cache[k]
            gc.collect()
        with self._thumbnail_semaphore:
            try:
                if url in self.thumbnail_cache:
                    self.root.after(0, lambda: self.update_thumbnail_label(self.thumbnail_cache[url], target))
                    return
                resp = requests.get(url, headers={'User-Agent': self.get_random_user_agent()}, timeout=8)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content))
                    size = (120, 75) if target == 'video' else (120, 68)
                    img = img.resize(size, Image.Resampling.LANCZOS)
                    self.thumbnail_cache[url] = img
                    self.root.after(0, lambda i=img: self.update_thumbnail_label(i, target))
            except Exception as e:
                pass
    def update_thumbnail_label(self, img, target):
        try:
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            if target=='video' and hasattr(self,'preview_label'):
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img
            elif target=='playlist' and hasattr(self,'playlist_preview_label'):
                self.playlist_preview_label.configure(image=ctk_img, text="")
                self.playlist_preview_label.image = ctk_img
        except Exception as e:
            pass
    
    def validate_url(self, url):
        if not url: return None
        url_low = url.lower().strip()
        if not url_low.startswith(('http://','https://')): return None
        if self.is_channel_url(url):
            if 'youtube.com' in url_low or 'youtu.be' in url_low: return 'YouTube Channel'
            if 'vk.com' in url_low or 'vkvideo.ru' in url_low: return 'VK Channel'
            if 'rutube.ru' in url_low: return 'Rutube Channel'
            if 'dzen.ru' in url_low or 'zen.yandex.ru' in url_low: return 'Dzen Channel'
            if 'bilibili.com' in url_low: return 'Bilibili Space'
            if 'twitch.tv' in url_low: return 'Twitch Channel'
        if 'playlist' in url_low or 'list=' in url_low:
            if 'youtube.com' in url_low or 'youtu.be' in url_low: return 'YouTube Playlist'
            if 'rutube.ru' in url_low: return 'Rutube Playlist'
            if 'vk.com' in url_low or 'vkvideo.ru' in url_low: return 'VK Playlist'
        domain = extract_domain(url)
        return f'Сайт: {domain}' if domain else 'Видео'
    
    def start_analysis(self):
        url = self.url_entry.get().strip()
        if not url: return
        if not url.startswith(('http://','https://')):
            url = 'https://'+url
            self.url_entry.delete(0,'end')
            self.url_entry.insert(0,url)
        service = self.validate_url(url)
        if not service:
            messagebox.showerror("Ошибка", "Некорректная ссылка")
            return
        self.analyze_button.configure(text="Анализ...", state="disabled")
        threading.Thread(target=self.analyze_video, args=(url, service), daemon=True).start()
    
    def analyze_video(self, url, service):
        try:
            is_pl = 'Playlist' in service or 'Channel' in service or 'Space' in service
            opts = {
                'quiet': True, 'no_warnings': True,
                'extract_flat': 'in_playlist' if is_pl else False,
                'user_agent': self.get_random_user_agent(),
                'socket_timeout': 30, 'ignoreerrors': True,
            }
            if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                opts['extractor_args'] = {
                    'youtube': {
                        'player_client': ['android_vr', 'android', 'web'],
                    }
                }
            elif 'rutube.ru' in url.lower():
                opts['extractor_args'] = {'rutube': {'skip_download': ['false']}}
                opts['referer'] = 'https://rutube.ru/'
            elif 'vk.com' in url.lower() or 'vkvideo.ru' in url.lower():
                opts['extractor_args'] = {'vk': {'skip_download': ['false']}}
                opts['referer'] = 'https://vk.com/'
                if BROWSER_COOKIES_AVAILABLE:
                    try:
                        cj = browser_cookie3.load(domain_name='vk.com')
                        opts['cookiefile'] = cj
                    except: pass
            elif 'dzen.ru' in url.lower() or 'zen.yandex.ru' in url.lower():
                if 'dzen.ru' in url.lower():
                    url = url.replace('dzen.ru', 'zen.yandex.ru')
                opts['extractor_args'] = {'zenyandex': {'skip_download': ['false']}}
                opts['referer'] = 'https://zen.yandex.ru/'
                opts['headers'] = {'User-Agent': self.get_random_user_agent(), 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ValueError("Не удалось получить информацию о видео. Возможно, оно недоступно или геоблокировано.")
                if info.get('_type') == 'playlist' or 'entries' in info:
                    entries = list(info.get('entries', []))
                    all_videos = []
                    for e in entries:
                        if e is None: continue
                        if e.get('_type') == 'playlist' or e.get('ie_key') == 'YoutubePlaylist':
                            try:
                                sub = ydl.extract_info(e.get('url'), download=False)
                                if sub and sub.get('entries'):
                                    for v in sub.get('entries'):
                                        if v:
                                            all_videos.append(v)
                            except: pass
                        else:
                            all_videos.append(e)
                    self.playlist_videos = all_videos if all_videos else entries
                    self.root.after(0, self.switch_to_playlist_state, info)
                else:
                    self.playlist_videos = []
                    with self.current_info_lock:
                        self.current_info = info
                    self.root.after(0, self.switch_to_video_state, info)
            self.root.after(0, lambda: self.analyze_button.configure(text="Анализировать", state="normal"))
        except Exception as e:
            err = str(e)
            if 'Sign in to confirm' in err or 'bot' in err.lower():
                err = "Ошибка аутентификации. Попробуйте позже."
            elif '403' in err:
                err = "Доступ ограничен. Возможно, видео недоступно."
            elif 'Unsupported URL' in err:
                err = f"Сайт не поддерживается.\n{err[:200]}"
            else:
                err = f"Ошибка при анализе:\n{err[:300]}"
            self.root.after(0, lambda: messagebox.showerror("Ошибка", err))
            self.root.after(0, lambda: self.analyze_button.configure(text="Анализировать", state="normal"))
    
    def toggle_download(self):
        if self.is_downloading:
            self.stop_download()
        else:
            self.start_download()
    
    def start_download(self):
        with self.download_lock:
            if self.is_downloading: return
            self.is_downloading = True
            self.should_stop = False
        if self.is_playlist:
            self.playlist_download_button.configure(text="⏹ Остановить", fg_color=self.colors['danger'], hover_color=self.colors['danger_hover'])
            threading.Thread(target=self.download_playlist, daemon=True).start()
        else:
            self.download_button.configure(text="⏹ Остановить", fg_color=self.colors['danger'], hover_color=self.colors['danger_hover'])
            threading.Thread(target=self.download_single_video_wrapper, daemon=True).start()
    
    def download_single_video_wrapper(self):
        url = self.url_entry.get().strip()
        success = self.download_single_video(url, None)
        self.root.after(0, self.reset_ui)
        if success:
            self.root.after(0, self.enable_open_folder_button)
    
    def download_playlist(self):
        tasks = []
        for i, v in enumerate(self.playlist_videos):
            if i in self.skipped_videos: continue
            v_url = v.get('url') or v.get('webpage_url')
            if v_url:
                tasks.append((i, v_url, v.get('title', f'Видео {i+1}')))
        if not tasks:
            self.root.after(0, lambda: messagebox.showwarning("Внимание", "Нет видео для загрузки"))
            self.reset_ui()
            return
        self.total_videos = len(tasks)
        self.downloaded_videos = 0
        failed = 0
        self.playlist_stats_label.configure(text=f"0/{self.total_videos}")
        self.current_video_label.configure(text="Подготовка к загрузке...")
        for d in self.video_widgets_data:
            d['progress_bar'].set(0)
            d['progress_label'].configure(text="0%")
        def download_task(task):
            if self.should_stop:
                return (task[0], False)
            return (task[0], self.download_single_video(task[1], task[0]))
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(download_task, t): t for t in tasks}
            for f in as_completed(futures):
                if self.should_stop:
                    ex.shutdown(wait=False, cancel_futures=True)
                    break
                t = futures[f]
                try:
                    idx, ok = f.result(timeout=60)
                    if ok:
                        self.downloaded_videos += 1
                        self.root.after(0, self.update_video_progress, idx, 1.0, 100)
                    else:
                        failed += 1
                        self.root.after(0, self.update_video_progress, idx, 0, 0)
                except Exception as e:
                    failed += 1
                    print(f"Ошибка {t[2]}: {e}")
                    self.root.after(0, self.update_video_progress, t[0], 0, 0)
                prog = self.downloaded_videos / self.total_videos if self.total_videos>0 else 0
                self.root.after(0, self.update_playlist_progress, prog, self.downloaded_videos, self.total_videos, failed, t[2])
        if not self.should_stop:
            msg = f"Загружено: {self.downloaded_videos} из {self.total_videos}"
            if failed: msg += f"\nОшибок: {failed}"
            if self.skipped_videos: msg += f"\nПропущено: {len(self.skipped_videos)}"
            self.root.after(0, lambda: messagebox.showinfo("Загрузка завершена", msg))
        self.root.after(0, self.reset_ui)
        self.root.after(0, self.enable_open_folder_button)
    
    def update_video_progress(self, idx, prog, percent):
        if idx < len(self.video_widgets_data):
            d = self.video_widgets_data[idx]
            d['progress_bar'].set(prog)
            d['progress_label'].configure(text=f"{percent}%")
    
    def update_playlist_progress(self, prog, downloaded, total, failed, cur_title):
        try:
            self.playlist_progress_bar.set(prog)
            status = f"Загружено: {downloaded}/{total}"
            if failed>0: status += f" | Ошибок: {failed}"
            self.playlist_stats_label.configure(text=status)
            self.current_video_label.configure(text=f"📥 {safe_filename(cur_title,50)}")
        except: pass
    
    def download_single_video(self, url, video_index):
        _state = {'downloaded': 0, 'total_size': 0, 'start_time': time.time()}
        if video_index is None:
            self.start_time = _state['start_time']
        quality = self.selected_quality

        refresh_ffmpeg_state()

        is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()

        if FFMPEG_AVAILABLE:
            fmt_map = {
                "Лучшее": "bestvideo+bestaudio/best",
                "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
                "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
                "Аудио": "bestaudio/best"
            }
        else:
            print("ВНИМАНИЕ: FFmpeg не найден! Качество будет ограничено ~360p.")
            fmt_map = {
                "Лучшее": "best[ext=mp4]/best",
                "1080p": "best[height<=1080][ext=mp4]/best[ext=mp4]/best",
                "720p": "best[height<=720][ext=mp4]/best[ext=mp4]/best",
                "480p": "best[height<=480][ext=mp4]/best[ext=mp4]/best",
                "360p": "best[height<=360][ext=mp4]/best",
                "Аудио": "bestaudio/best"
            }

        format_str = fmt_map.get(quality, fmt_map["Лучшее"])

        ext_args = {}
        if is_youtube:
            ext_args['youtube'] = {
                'player_client': ['android_vr', 'android', 'web'],
            }

        opts = {
            'format': format_str,
            'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
            'progress_hooks': [lambda d, _s=_state: self.progress_hook(d, video_index, _s)],
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'user_agent': self.get_random_user_agent(),
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'concurrent_fragment_downloads': 5,
            'buffersize': 1024*1024*16,
            'http_chunk_size': 1024*1024*10,
            'extractor_args': ext_args,
        }

        if FFMPEG_AVAILABLE:
            opts['merge_output_format'] = 'mp4'
            opts['ffmpeg_location'] = FFMPEG_PATH
        else:
            print("ВНИМАНИЕ: FFmpeg не найден — качество ограничено ~360p.")

        if quality == "Аудио" and FFMPEG_AVAILABLE:
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}]

        if 'rutube.ru' in url.lower():
            opts['referer'] = 'https://rutube.ru/'
        elif 'vk.com' in url.lower() or 'vkvideo.ru' in url.lower():
            opts['referer'] = 'https://vk.com/'
            if BROWSER_COOKIES_AVAILABLE:
                try:
                    cj = browser_cookie3.load(domain_name='vk.com')
                    opts['cookiefile'] = cj
                except:
                    pass
        elif 'dzen.ru' in url.lower() or 'zen.yandex.ru' in url.lower():
            opts['referer'] = 'https://zen.yandex.ru/'

        if is_youtube:
            try:
                info_opts = {k: v for k, v in opts.items() if k not in ('progress_hooks',)}
                info_opts['quiet'] = True
                info_opts['no_warnings'] = True
                with yt_dlp.YoutubeDL(info_opts) as ydl_info:
                    info = ydl_info.extract_info(url, download=False)
                    if info:
                        fmts = info.get('formats', [])
                        best_height = max((f.get('height') or 0 for f in fmts), default=0)
            except Exception as e:
                pass

        strategies = []

        if is_youtube and FFMPEG_AVAILABLE:
            s1 = dict(opts)
            s1['extractor_args'] = {'youtube': {'player_client': ['android_vr', 'android']}}
            strategies.append(('android_vr', s1))

            s2 = dict(opts)
            s2['extractor_args'] = {'youtube': {'player_client': ['android']}}
            strategies.append(('android', s2))

            s3 = dict(opts)
            s3.pop('extractor_args', None)
            strategies.append(('авто-клиент', s3))

            s4 = dict(opts)
            s4.pop('extractor_args', None)
            h = quality.replace('p', '') if quality.endswith('p') else '1080'
            s4['format'] = f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best'
            s4['extractor_args'] = {'youtube': {'player_client': ['android_vr', 'android']}}
            strategies.append(('mp4+m4a', s4))
        else:
            strategies.append(('основная', opts))

        last_error = None
        for i, (name, strategy_opts) in enumerate(strategies):
            if self.should_stop:
                return False
            try:
                print(f"Попытка {i+1}/{len(strategies)} [{name}]...")
                self.current_ydl = yt_dlp.YoutubeDL(strategy_opts)
                self.current_ydl.download([url])
                print(f"Успешно скачано [{name}]")
                return True
            except Exception as e:
                last_error = e
                if self.should_stop:
                    return False
                print(f"[{name}] не сработало: {e}")

        print(f"Все стратегии исчерпаны. Последняя ошибка: {last_error}")
        return False
    
    def progress_hook(self, d, video_index, _state=None):
        if self.should_stop:
            if self.current_ydl:
                try:
                    self.current_ydl.params['quiet'] = True
                except:
                    pass
            return
        if _state is None:
            _state = {'downloaded': 0, 'total_size': 0, 'start_time': self.start_time}
        if d['status'] == 'downloading':
            try:
                total_size = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                _state['total_size'] = total_size
                _state['downloaded'] = downloaded
                if video_index is None:
                    self.total_size = total_size
                    self.downloaded = downloaded
                if total_size > 0:
                    prog = min(downloaded / total_size, 1.0)
                    elapsed = max(time.time() - _state['start_time'], 0.001)
                    speed = downloaded / elapsed
                    percent = int(prog * 100)
                    speed_str = format_speed(speed)
                    eta = str(timedelta(seconds=int((total_size - downloaded) / speed))) if speed > 0 else "--:--"
                    if self.is_playlist and video_index is not None:
                        self.root.after(0, self.update_video_progress, video_index, prog, percent)
                        if hasattr(self, 'current_video_label'):
                            title_str = safe_filename(d.get('filename', 'видео'), 50)
                            self.root.after(0, lambda t=title_str, p=percent, s=speed_str: self.current_video_label.configure(
                                text=f"📥 {t} [{p}%] {s}"
                            ))
                    else:
                        self.root.after(0, self.update_progress, prog, f"{speed_str} • {eta}", format_size(downloaded), format_size(total_size))
            except:
                pass
        elif d['status'] == 'finished' and not self.is_playlist:
            self.root.after(0, lambda: self.speed_label.configure(text="Загрузка завершена!"))
    
    def update_progress(self, prog, speed_eta, downloaded, total):
        try:
            self.progress_bar.set(prog)
            self.speed_label.configure(text=speed_eta)
            self.size_label.configure(text=f"{downloaded}/{total}")
        except: pass
    
    def stop_download(self):
        with self.download_lock:
            self.should_stop = True
            self.is_downloading = False
        if self.current_ydl:
            try:
                self.current_ydl.params['quiet'] = True
            except: pass
        self.speed_label.configure(text="Загрузка остановлена")
        self.reset_ui()
    
    def reset_ui(self):
        with self.download_lock:
            self.is_downloading = False
            self.should_stop = False
        if hasattr(self, 'download_button'):
            try:
                self.download_button.configure(text="Скачать видео", fg_color=self.colors['primary'], hover_color=self.colors['primary_hover'])
            except Exception:
                pass
        if hasattr(self, 'playlist_download_button'):
            try:
                active = len(self.playlist_videos) - len(self.skipped_videos)
                is_ch = self.is_channel_url(self.url_entry.get()) if hasattr(self, 'url_entry') else False
                txt = "канала" if is_ch else "плейлиста"
                self.playlist_download_button.configure(text=f"Скачать {txt} ({active})", fg_color=self.colors['primary'], hover_color=self.colors['primary_hover'])
            except Exception:
                pass
        self.progress_bar.set(0)
        self.speed_label.configure(text="Готов к загрузке")
        self.size_label.configure(text="")
        if hasattr(self, 'playlist_progress_bar'):
            self.playlist_progress_bar.set(0)
            self.playlist_stats_label.configure(text="")
            self.current_video_label.configure(text="")
    
    # ИСПРАВЛЕННЫЙ МЕТОД on_closing - корректное завершение программы
    def on_closing(self):
        """Корректное завершение программы"""
        self.animation_running = False
        
        # Отменяем анимацию если она запущена
        if self.fade_id:
            try:
                self.root.after_cancel(self.fade_id)
            except:
                pass
        
        # Если идет загрузка - спрашиваем подтверждение
        if self.is_downloading:
            if messagebox.askyesno("Подтверждение", "Загрузка не завершена. Выйти?"):
                self.should_stop = True
                self.is_downloading = False
                # Даем время на остановку загрузки
                time.sleep(0.5)
                self._destroy_app()
            # Если пользователь отказался - ничего не делаем
        else:
            self._destroy_app()
    
    def _destroy_app(self):
        """Полное уничтожение приложения"""
        try:
            # Очищаем кэш
            self.thumbnail_cache.clear()
            self.skipped_videos.clear()
            self.playlist_videos.clear()
            self.video_widgets_data.clear()
            
            # Очищаем менеджер состояний
            if hasattr(self, 'state_manager'):
                self.state_manager.cleanup()
            
            # Принудительная сборка мусора
            gc.collect()
            
            # Закрываем окно и завершаем приложение
            self.root.quit()
            self.root.destroy()
            
        except Exception as e:
            print(f"Ошибка при закрытии: {e}")
        
        # Полный выход из программы
        sys.exit(0)
    
    def run(self):
        self.root.mainloop()

def main():
    try:
        app = VideoGrabber()
        app.run()
    except Exception as e:
        print(f"Ошибка: {e}")
        traceback.print_exc()
        input("Нажмите Enter для выхода...")
    finally:
        # Гарантированный выход при любом исходе
        sys.exit(0)

if __name__ == "__main__":
    main()