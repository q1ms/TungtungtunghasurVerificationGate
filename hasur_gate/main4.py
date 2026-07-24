import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image
import threading
import time
import os
import datetime
import sounddevice as sd
import scipy.io.wavfile as wavfile
import subprocess
import platform
import base64
import json
import random
import signal
import math
import tkinter
import io
from openai import OpenAI
import requests
import shutil

# ==========================================
# >>> YOUR API CONFIGURATION <<<
# ==========================================
API_KEY = "sk-ws-H.XRLLPH.xKTZ.MEQCIDpvzKrBByEb0Z0o3BWRPqhAOOEBNLmtA5dMYOnmICfVAiAojcvIPTMi26CFSUmE-ycj_lYNriHhlrFM2Dnm4PjDGw"
API_BASE_URL = "https://ws-bf3itnzatquc4sa0.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
# ==========================================

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

# ==========================================
# MODEL NAMES
# ==========================================
TEXT_MODEL = "qwen3.7-plus"
AUDIO_MODEL = "qwen3-omni-flash"
VISION_MODEL = "qwen-vl-max"       # fallback: qwen-vl-plus, qwen-vl

# ==========================================
# CONFIGURATION
# ==========================================
MAX_ATTEMPTS = 5
CHANT_DURATION = 6.0
DANCE_DURATION = 8.0
BACKGROUND_MUSIC = "assets/background.mp3"
DANCE_FRAMES = 16

# Characters (keep, but we'll use grayscale theme)
CHARACTERS = [
    {"name": "Goblin of Confusion", "img": "assets/char1.png", "audio": "assets/char1.mp3"},
    {"name": "Specter of Nonsense", "img": "assets/char2.png", "audio": "assets/char2.mp3"},
    {"name": "Void Walker", "img": "assets/char3.png", "audio": "assets/char3.mp3"},
    {"name": "Brainrot Entity", "img": "assets/char4.png", "audio": "assets/char4.mp3"},
    {"name": "Hasur's Jester", "img": "assets/char5.png", "audio": "assets/char5.mp3"},
]
FAILURE_AUDIO = "assets/failure.mp3"

BRAINROT_FAILURES = [
    "SKILL ISSUE 💀", "HASUR SAYS: NO RIZZ 🚫",
    "BRO THINKS HE'S SIGMA 😭", "TUNG TUNG TUNG... FAILED 💀",
    "MEWING LEVEL: 0 🤡", "GYATT DAMN... YOU LOST 🗿",
    "FANUM TAX COLLECTED 💰", "OHIO FINAL BOSS SAYS NO ⛔",
]

RECEIPT_TEMPLATE = """
╔══════════════════════════════════════════╗
║       TUNG TUNG TUNG HASUR™            ║
║       HUMILIATION RECEIPT #{receipt_num}            ║
╠══════════════════════════════════════════╣
║ ATTEMPT: #{attempt} / {max_attempts}                     ║
║ REASON: {reason}                    ║
║ AUDIO SCORE: {audio_score}/100                ║
║ VISION SCORE: {vision_score}/100               ║
║ STATUS: ❌ {status}                        ║
╠══════════════════════════════════════════╣
║ {brainrot}                  ║
╚══════════════════════════════════════════╝
"""

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class HasurGateApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # --- Splash Screen (gray theme) ---
        self.title("Loading...")
        self.geometry("1200x800")
        self.state('zoomed')
        self.splash_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.splash_frame.pack(fill="both", expand=True)
        
        self.splash_label = ctk.CTkLabel(self.splash_frame, text="⏳ Booting up Hasur", font=ctk.CTkFont(size=28, weight="bold"), text_color="#b0b0b0")
        self.splash_label.pack(expand=True, pady=(0, 10))
        self.splash_sub_label = ctk.CTkLabel(self.splash_frame, text="", font=ctk.CTkFont(size=18), text_color="#6a6a6a")
        self.splash_sub_label.pack(pady=5)
        
        self.splash_dots = 0
        self.animate_splash_dots()
        
        boot_phrases = [
            "Loading brainrot engine...",
            "Summoning Hasur's spirit...",
            "Loading chaos protocols...",
            "Igniting the Tung Tung Tung...",
            "Twisting reality...",
            "Preparing your humiliation...",
            "Setting the stage for failure...",
        ]
        random.shuffle(boot_phrases)
        self.splash_phrases = boot_phrases
        self.splash_index = 0
        self.update_splash_phrases()
        
        self.after(4000, self.build_app_and_destroy_splash)
        self.initialized = False
    
    def animate_splash_dots(self):
        if hasattr(self, 'splash_frame') and self.splash_frame is not None:
            try:
                if self.splash_frame.winfo_exists():
                    dots = "." * (self.splash_dots % 4)
                    self.splash_label.configure(text=f"⏳ Booting up Hasur{dots}")
                    self.splash_dots += 1
                    self.after(500, self.animate_splash_dots)
                else:
                    return
            except tkinter.TclError:
                return
        else:
            return
    
    def update_splash_phrases(self):
        if hasattr(self, 'splash_frame') and self.splash_frame is not None:
            try:
                if self.splash_frame.winfo_exists():
                    if self.splash_index < len(self.splash_phrases):
                        phrase = self.splash_phrases[self.splash_index]
                        self.splash_sub_label.configure(text=phrase)
                        self.splash_index += 1
                        self.after(1200, self.update_splash_phrases)
                    else:
                        random.shuffle(self.splash_phrases)
                        self.splash_index = 0
                        self.after(1200, self.update_splash_phrases)
                else:
                    return
            except tkinter.TclError:
                return
        else:
            return
    
    def build_app_and_destroy_splash(self):
        if hasattr(self, 'splash_frame') and self.splash_frame is not None:
            try:
                self.splash_frame.destroy()
            except:
                pass
            self.splash_frame = None
        
        self.title("ChatGPT Clone")
        self.geometry("1200x800")
        self.state('zoomed')
        self.bind("<Escape>", lambda e: self.on_escape())
        
        # --- State variables ---
        self.attempt = 1
        self.question = ""
        self.challenge = {}
        self.is_recording = False
        self.cap = None
        self.frame_counter = 0
        self.audio_data = []
        self.failure_count = 0
        self.failure_receipts = []
        self.ritual_passed = False
        self.audio_analysis_result = None
        self.vision_analysis_result = None
        self.is_brainrot_mode = False
        self.remaining_time = 0
        self.phase = "idle"
        
        self.realtime_spins = 0
        self.realtime_claps = 0
        self.audio_text = ""
        self.audio_loudness = 0
        self.live_decibel = 0.0
        self.actual_loudness_percent = 0   # for real dB
        
        self.required_spins = 0
        self.required_claps = 0
        self.required_chant = ""
        self.required_volume = "loud"
        self.chant_passed = False
        self.dance_passed = False
        
        self.current_frame_folder = ""
        self.current_audio_filename = ""
        self.current_audio_process = None
        self.background_music_process = None
        self.audio_stream = None
        
        self.brainrot_phrases = [
            "skibidi", "sigma", "gyatt", "fanum tax", "mewing", "ohio",
            "tung tung tung hasur", "sahur", "brainrot", "rizz", "sus", "no cap", "bet"
        ]
        
        self.setup_ui()
        self.update_camera_loop()
        self.play_background_music(0.3)
        
        self.initialized = True
        print("🟢 App initialized successfully!", flush=True)
    
    # ==========================================
    # LIFECYCLE & PROCESS KILLERS
    # ==========================================
    def on_escape(self):
        self.stop_audio()
        self.stop_background_music()
        self.destroy()
    
    def destroy(self):
        self.stop_audio()
        self.stop_background_music()
        if self.cap is not None:
            self.cap.release()
        for f in os.listdir("."):
            if f.startswith("temp_bg_") and f.endswith(".mp3"):
                try:
                    os.remove(f)
                except:
                    pass
        super().destroy()
    
    def _kill_proc(self, proc):
        if proc is None:
            return
        pid = proc.pid
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, check=False)
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    time.sleep(0.2)
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                except (ProcessLookupError, OSError):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except Exception:
                        pass
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

    def stop_audio(self):
        self._kill_proc(self.current_audio_process)
        self.current_audio_process = None

    def stop_background_music(self):
        self._kill_proc(self.background_music_process)
        self.background_music_process = None
    
    # ==========================================
    # UI SETUP - Gray/Black Theme
    # ==========================================
    def setup_ui(self):
        # Main container - dark gray
        self.main_container = ctk.CTkFrame(self, fg_color="#212121")
        self.main_container.pack(fill="both", expand=True)
        
        # ---- LEFT SIDEBAR ----
        self.sidebar = ctk.CTkFrame(self.main_container, width=260, fg_color="#2a2a2a", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        sidebar_inner = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_inner.pack(fill="both", expand=True, padx=12, pady=12)
        
        # New Chat button - gray
        self.new_chat_btn = ctk.CTkButton(sidebar_inner, text="+ New Chat",
                                          font=ctk.CTkFont(size=14, weight="bold"),
                                          fg_color="#3a3a3a", hover_color="#4a4a4a",
                                          corner_radius=8, height=40, command=self.restart_app)
        self.new_chat_btn.pack(fill="x", pady=(0, 20))
        
        self.model_btn = ctk.CTkButton(sidebar_inner, text="⚡ Hasur-4B (Brainrot)",
                                       font=ctk.CTkFont(size=13), fg_color="#3a3a3a",
                                       hover_color="#4a4a4a", corner_radius=8, height=35, anchor="w")
        self.model_btn.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(sidebar_inner, text="Today", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#6a6a6a").pack(anchor="w", pady=(10, 5))
        for item in ["What is the meaning of life?", "Tell me a joke", "Tung Tung Tung Hasur"]:
            ctk.CTkButton(sidebar_inner, text=item, font=ctk.CTkFont(size=13),
                          fg_color="transparent", hover_color="#3a3a3a",
                          corner_radius=8, height=30, anchor="w", text_color="#b0b0b0").pack(fill="x", pady=1)
        
        ctk.CTkFrame(sidebar_inner, fg_color="transparent").pack(fill="both", expand=True)
        
        profile_frame = ctk.CTkFrame(sidebar_inner, fg_color="transparent")
        profile_frame.pack(fill="x")
        ctk.CTkLabel(profile_frame, text="👤", font=ctk.CTkFont(size=20), fg_color="#3a3a3a",
                     corner_radius=16, width=32, height=32).pack(side="left", padx=5)
        ctk.CTkLabel(profile_frame, text="tungtungtungsahur", font=ctk.CTkFont(size=13),
                     text_color="#b0b0b0").pack(side="left", padx=10)
        
        # ---- RIGHT COLUMN ----
        self.main_canvas = ctk.CTkFrame(self.main_container, fg_color="#1e1e1e")
        self.main_canvas.pack(side="right", fill="both", expand=True)
        
        self.nav_bar = ctk.CTkFrame(self.main_canvas, fg_color="#1e1e1e", height=50)
        self.nav_bar.pack(fill="x", padx=20, pady=(10, 0))
        self.nav_bar.pack_propagate(False)
        ctk.CTkButton(self.nav_bar, text="▼ Hasur-4B (Brainrot)",
                      font=ctk.CTkFont(size=14, weight="bold"), fg_color="transparent",
                      hover_color="#2a2a2a", corner_radius=8, height=40, text_color="#b0b0b0").pack(side="left")
        
        # ---- CHAT PAGE ----
        self.chat_frame = ctk.CTkScrollableFrame(self.main_canvas, fg_color="transparent")
        self.chat_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        welcome_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        welcome_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(welcome_frame, text="What can I help with?",
                     font=ctk.CTkFont(size=28, weight="bold"), text_color="#d0d0d0").pack(pady=(120, 20))
        
        chips_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        chips_frame.pack()
        for i, s in enumerate(["Ask me anything...", "Brainrot joke", "Tell me about AI", "Write a poem"]):
            chip = ctk.CTkButton(chips_frame, text=s, font=ctk.CTkFont(size=13),
                                 fg_color="#2a2a2a", hover_color="#3a3a3a", corner_radius=20,
                                 height=35, border_width=1, border_color="#3a3a3a", text_color="#b0b0b0")
            chip.grid(row=i // 2, column=i % 2, padx=5, pady=5)
            chip.configure(command=lambda txt=s: self.question_entry.insert(0, txt))
        
        # ---- INPUT BAR ----
        self.input_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1e1e1e", height=90)
        self.input_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.input_frame.pack_propagate(False)
        
        input_container = ctk.CTkFrame(self.input_frame, fg_color="#2a2a2a", corner_radius=24, height=52)
        input_container.pack(fill="x", padx=20, pady=8)
        input_container.pack_propagate(False)
        
        input_row = ctk.CTkFrame(input_container, fg_color="transparent")
        input_row.pack(fill="both", padx=15, pady=5)
        
        self.question_entry = ctk.CTkEntry(input_row, placeholder_text="Message Hasur...",
                                           font=ctk.CTkFont(size=16), fg_color="transparent",
                                           border_width=0, height=38, text_color="#d0d0d0")
        self.question_entry.pack(side="left", fill="x", expand=True)
        self.question_entry.bind("<Return>", lambda e: self.start_ritual())
        
        self.send_btn = ctk.CTkButton(input_row, text="↑", font=ctk.CTkFont(size=18, weight="bold"),
                                      fg_color="#3a3a3a", hover_color="#4a4a4a", corner_radius=20,
                                      width=32, height=32, command=self.start_ritual, text_color="#d0d0d0")
        self.send_btn.pack(side="right")
        
        ctk.CTkLabel(self.input_frame, text="Hasur can make mistakes. Check important info.",
                     font=ctk.CTkFont(size=11), text_color="#6a6a6a").pack(pady=(0, 3))
        
        # ---- VOICE CHALLENGE PAGE ----
        self.chant_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1a1a1a")
        self.chant_frame.pack_forget()
        
        self.chant_action_bar = ctk.CTkFrame(self.chant_frame, fg_color="#1a1a1a", height=86)
        self.chant_action_bar.pack(side="bottom", fill="x")
        self.chant_action_bar.pack_propagate(False)
        
        self.chant_start_btn = ctk.CTkButton(self.chant_action_bar, text="🎤 START CHANTING",
                                             command=self.start_chant_phase, height=56, width=300,
                                             font=ctk.CTkFont(size=18, weight="bold"),
                                             fg_color="#3a3a3a", hover_color="#4a4a4a", text_color="#d0d0d0")
        self.chant_start_btn.pack(side="left", padx=20, pady=15)
        
        self.proceed_to_dance_btn = ctk.CTkButton(self.chant_action_bar,
                                                  text="💃 PROCEED TO DANCE CHALLENGE →",
                                                  command=self.go_to_dance_page, height=56, width=360,
                                                  font=ctk.CTkFont(size=16, weight="bold"),
                                                  fg_color="#3a3a3a", hover_color="#4a4a4a", text_color="#d0d0d0")
        # packed later
        
        self.chant_scroll = ctk.CTkScrollableFrame(self.chant_frame, fg_color="transparent")
        self.chant_scroll.pack(fill="both", expand=True)
        
        ctk.CTkLabel(self.chant_scroll, text="🎤 SESSION 1/2 — VOICE CHALLENGE",
                     font=ctk.CTkFont(size=30, weight="bold"), text_color="#b0b0b0").pack(pady=(18, 2))
        ctk.CTkLabel(self.chant_scroll, text="🗣️ CHANTING SECTION · Qwen-Audio is listening to your voice",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#6a6a6a").pack(pady=(0, 6))
        
        self.chant_challenge_label = ctk.CTkLabel(self.chant_scroll, text="",
                                                  font=ctk.CTkFont(size=17, weight="bold"),
                                                  text_color="#b0b0b0", wraplength=900, justify="center")
        self.chant_challenge_label.pack(pady=8)
        
        self.chant_camera_label = ctk.CTkLabel(self.chant_scroll, text="", width=560, height=315,
                                               fg_color="#0a0a0a", corner_radius=10)
        self.chant_camera_label.pack(pady=8)
        
        self.chant_decibel_frame = ctk.CTkFrame(self.chant_scroll, fg_color="transparent")
        self.chant_decibel_frame.pack(pady=6)
        ctk.CTkLabel(self.chant_decibel_frame, text="🔊 VOLUME:",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#b0b0b0").pack(side="left", padx=5)
        self.chant_decibel_bar = ctk.CTkProgressBar(self.chant_decibel_frame, width=420, height=22,
                                                    fg_color="#333", progress_color="#666")
        self.chant_decibel_bar.pack(side="left", padx=8)
        self.chant_decibel_bar.set(0)
        self.chant_db_label = ctk.CTkLabel(self.chant_decibel_frame, text="0 dB",
                                           font=ctk.CTkFont(size=15, weight="bold"), text_color="#b0b0b0")
        self.chant_db_label.pack(side="left", padx=5)
        
        self.chant_heard_label = ctk.CTkLabel(self.chant_scroll, text="🎤 Heard: Waiting...",
                                              font=ctk.CTkFont(size=15), text_color="#6a6a6a",
                                              wraplength=800, justify="center")
        self.chant_heard_label.pack(pady=4)
        
        self.chant_countdown_label = ctk.CTkLabel(self.chant_scroll, text="",
                                                  font=ctk.CTkFont(size=46, weight="bold"),
                                                  text_color="#888")
        self.chant_countdown_label.pack(pady=2)
        
        self.chant_instruction_label = ctk.CTkLabel(self.chant_scroll, text="",
                                                    font=ctk.CTkFont(size=16, weight="bold"),
                                                    text_color="#888")
        self.chant_instruction_label.pack(pady=4)
        
        # ---- DANCE CHALLENGE PAGE ----
        self.dance_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1a1a1a")
        self.dance_frame.pack_forget()
        
        self.dance_action_bar = ctk.CTkFrame(self.dance_frame, fg_color="#1a1a1a", height=86)
        self.dance_action_bar.pack(side="bottom", fill="x")
        self.dance_action_bar.pack_propagate(False)
        
        self.dance_start_btn = ctk.CTkButton(self.dance_action_bar, text="💃 START DANCING",
                                             command=self.start_dance_phase, height=56, width=300,
                                             font=ctk.CTkFont(size=18, weight="bold"),
                                             fg_color="#3a3a3a", hover_color="#4a4a4a", text_color="#d0d0d0")
        self.dance_start_btn.pack(padx=20, pady=15)
        
        self.dance_scroll = ctk.CTkScrollableFrame(self.dance_frame, fg_color="transparent")
        self.dance_scroll.pack(fill="both", expand=True)
        
        ctk.CTkLabel(self.dance_scroll, text="💃 SESSION 2/2 — DANCE CHALLENGE",
                     font=ctk.CTkFont(size=30, weight="bold"), text_color="#b0b0b0").pack(pady=(18, 2))
        ctk.CTkLabel(self.dance_scroll, text="🕺 MOVEMENT SECTION · Qwen-Vision is watching your moves",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#6a6a6a").pack(pady=(0, 6))
        
        # Challenge label (top) – only this remains
        self.dance_challenge_label = ctk.CTkLabel(self.dance_scroll, text="",
                                                  font=ctk.CTkFont(size=17, weight="bold"),
                                                  text_color="#b0b0b0", wraplength=900, justify="center")
        self.dance_challenge_label.pack(pady=8)
        
        self.dance_camera_label = ctk.CTkLabel(self.dance_scroll, text="", width=640, height=360,
                                               fg_color="#0a0a0a", corner_radius=10)
        self.dance_camera_label.pack(pady=8)
        
        # REMOVED dance_progress_label (SPINS/CLAPS counts) – per user request
        
        self.dance_countdown_label = ctk.CTkLabel(self.dance_scroll, text="",
                                                  font=ctk.CTkFont(size=46, weight="bold"),
                                                  text_color="#888")
        self.dance_countdown_label.pack(pady=2)
        
        self.dance_instruction_label = ctk.CTkLabel(self.dance_scroll, text="",
                                                    font=ctk.CTkFont(size=16, weight="bold"),
                                                    text_color="#888")
        self.dance_instruction_label.pack(pady=4)
        
        # ---- FAILURE OVERLAY ----
        self.failure_overlay = ctk.CTkFrame(self.main_canvas, fg_color="#3a3a3a", corner_radius=0)
        self.failure_overlay.pack_forget()
        self.failure_content = ctk.CTkFrame(self.failure_overlay, fg_color="transparent")
        self.failure_content.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self.failure_content, text="💀 RITUAL FAILED 💀",
                     font=ctk.CTkFont(size=48, weight="bold"), text_color="#d0d0d0").pack(pady=(0, 15))
        self.failure_reason_label = ctk.CTkLabel(self.failure_content, text="",
                                                 font=ctk.CTkFont(size=20), text_color="#b0b0b0",
                                                 wraplength=800, justify="center")
        self.failure_reason_label.pack()
        self.brainrot_label = ctk.CTkLabel(self.failure_content, text="",
                                           font=ctk.CTkFont(size=26, weight="bold"), text_color="#888")
        self.brainrot_label.pack(pady=15)
        
        self.receipt_frame = ctk.CTkFrame(self.failure_overlay, fg_color="#2a2a2a",
                                          border_width=2, border_color="#4a4a4a", corner_radius=5)
        self.receipt_frame.place(relx=0.85, rely=0.5, anchor="center")
        self.receipt_label = ctk.CTkLabel(self.receipt_frame, text="",
                                          font=ctk.CTkFont(family="Courier", size=10),
                                          text_color="#b0b0b0", justify="left")
        self.receipt_label.pack(padx=12, pady=8)
        
        # ---- ANSWER FRAME ----
        self.answer_frame = ctk.CTkFrame(self.main_canvas, fg_color="transparent")
        self.answer_frame.pack_forget()
        self.char_image_label = ctk.CTkLabel(self.answer_frame, text="", width=150, height=150)
        self.char_image_label.pack(side="left", padx=40)
        self.dialogue_box = ctk.CTkFrame(self.answer_frame, fg_color="#2a2a2a", corner_radius=15,
                                         border_width=2, border_color="#4a4a4a")
        self.dialogue_box.pack(side="left", fill="both", expand=True, padx=40, pady=40)
        self.char_name_label = ctk.CTkLabel(self.dialogue_box, text="",
                                            font=ctk.CTkFont(size=18, weight="bold"), text_color="#b0b0b0")
        self.char_name_label.pack(pady=(15, 5))
        self.answer_text_label = ctk.CTkLabel(self.dialogue_box, text="", font=ctk.CTkFont(size=18),
                                              text_color="#d0d0d0", wraplength=500, justify="left")
        self.answer_text_label.pack(pady=15, padx=15)
        self.restart_btn = ctk.CTkButton(self.answer_frame, text="🔄 SUFFER AGAIN", command=self.restart_app,
                                         fg_color="#3a3a3a", hover_color="#4a4a4a", height=40, width=180,
                                         font=ctk.CTkFont(size=14, weight="bold"), text_color="#d0d0d0")
        self.restart_btn.pack(pady=20)
        
        # ---- ANSWER LOADING FRAME ----
        self.answer_loading_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1e1e1e")
        self.answer_loading_frame.pack_forget()
        # This will be shown during answer generation with ChatGPT-style thinking
        
        # ---- STATUS BAR (gray, minimal) ----
        self.status_bar = ctk.CTkFrame(self.main_canvas, fg_color="#1a1a1a", height=28)
        self.status_bar.pack(fill="x", side="bottom")
        self.attempt_label = ctk.CTkLabel(self.status_bar, text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}",
                                          font=ctk.CTkFont(size=12), text_color="#6a6a6a")
        self.attempt_label.pack(side="left", padx=15)
        self.failure_counter_label = ctk.CTkLabel(self.status_bar, text="❌ Failures: 0",
                                                  font=ctk.CTkFont(size=12, weight="bold"),
                                                  text_color="#888")
        self.failure_counter_label.pack(side="right", padx=15)
    
    # ==========================================
    # CAMERA LOOP
    # ==========================================
    def update_camera_loop(self):
        if self.cap is None:
            try:
                self.cap = cv2.VideoCapture(0)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 500)
            except Exception as e:
                print(f"⚠️ Camera error: {e}")
                self.cap = None

        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)

                # Voice decibel overlay
                if self.is_recording and self.phase == "chant":
                    db = int(min(100, self.live_decibel))
                    cv2.rectangle(frame, (10, 30), (10 + db * 4, 65), (100, 100, 100), -1)
                    cv2.putText(frame, f"{self.live_decibel:.0f} dB", (10, 95),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)

                # Dance phase: save frames as JPEG
                if self.is_recording and self.phase == "dance":
                    if self.frame_counter % 1 == 0:
                        fname = f"{self.current_frame_folder}/frame_{self.frame_counter:06d}.jpg"
                        cv2.imwrite(fname, frame)
                    self.frame_counter += 1

                # Update camera labels
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                if self.phase == "chant":
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(560, 315))
                    self.chant_camera_label.configure(image=ctk_img)
                    self.chant_camera_label.image = ctk_img
                elif self.phase == "dance":
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(640, 360))
                    self.dance_camera_label.configure(image=ctk_img)
                    self.dance_camera_label.image = ctk_img

        self.after(30, self.update_camera_loop)
    
    # ==========================================
    # AUDIO PLAYBACK
    # ==========================================
    def play_audio(self, file_path, loop=False):
        self.stop_audio()
        if not os.path.exists(file_path):
            return
        system = platform.system()
        try:
            if system == "Darwin":
                if loop:
                    self.current_audio_process = subprocess.Popen(
                        ["bash", "-c", f"while true; do afplay '{file_path}'; done"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                else:
                    self.current_audio_process = subprocess.Popen(
                        ["afplay", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif system == "Windows":
                try:
                    cmd = ["ffplay", "-nodisp", "-autoexit", file_path]
                    if loop:
                        cmd.insert(1, "-loop")
                        cmd.insert(2, "0")
                    self.current_audio_process = subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                except FileNotFoundError:
                    escaped = file_path.replace("\\", "\\\\")
                    ps = ("Add-Type -AssemblyName presentationCore; "
                          "$p = New-Object system.windows.media.mediaplayer; "
                          "$p.open('" + escaped + "'); $p.Play()")
                    self.current_audio_process = subprocess.Popen(
                        ["powershell", "-WindowStyle", "Hidden", "-Command", ps])
            else:
                self.current_audio_process = subprocess.Popen(
                    ["aplay", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"⚠️ Audio error: {e}")
    
    def play_background_music(self, volume=0.3):
        self.stop_background_music()
        if not os.path.exists(BACKGROUND_MUSIC):
            return
        temp_file = f"temp_bg_{int(volume * 100)}.mp3"
        if not os.path.exists(temp_file):
            try:
                subprocess.run(["ffmpeg", "-y", "-i", BACKGROUND_MUSIC,
                                "-filter:a", f"volume={volume}", temp_file],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                return
        system = platform.system()
        try:
            if system == "Darwin":
                self.background_music_process = subprocess.Popen(
                    ["bash", "-c", f"while true; do afplay '{temp_file}'; done"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            elif system == "Windows":
                try:
                    self.background_music_process = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loop", "0", temp_file],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                except FileNotFoundError:
                    escaped = temp_file.replace("\\", "\\\\")
                    ps = ("Add-Type -AssemblyName presentationCore; "
                          "$p = New-Object system.windows.media.mediaplayer; "
                          "$p.MediaEnded += { $p.Position = [timespan]::Zero; $p.Play() }; "
                          "$p.open('" + escaped + "'); $p.Play()")
                    self.background_music_process = subprocess.Popen(
                        ["powershell", "-WindowStyle", "Hidden", "-Command", ps])
            else:
                self.background_music_process = subprocess.Popen(
                    ["ffplay", "-loop", "0", "-nodisp", "-autoexit", temp_file],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception:
            pass
    
    # ==========================================
    # RITUAL FLOW
    # ==========================================
    def start_ritual(self):
        self.question = self.question_entry.get().strip()
        if not self.question:
            self.question_entry.configure(placeholder_text="⚠️ ASK SOMETHING, BRO ⚠️")
            return
        
        self.chat_frame.pack_forget()
        self.input_frame.pack_forget()
        self.stop_background_music()
        self.title("🔥 HASUR BRAINROT MODE 🔥")
        self.send_btn.configure(state="disabled")
        
        # Show loading indicator with ChatGPT-style message
        self.loading_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1e1e1e")
        self.loading_frame.pack(fill="both", expand=True)
        
        # ChatGPT-style thinking indicator
        self.loading_icon_label = ctk.CTkLabel(self.loading_frame, text="⚪", font=ctk.CTkFont(size=30), text_color="#6a6a6a")
        self.loading_icon_label.pack(pady=(100, 10))
        self.loading_text_label = ctk.CTkLabel(self.loading_frame, text="Thinking...", font=ctk.CTkFont(size=22, weight="bold"), text_color="#b0b0b0")
        self.loading_text_label.pack(pady=5)
        self.loading_sub_label = ctk.CTkLabel(self.loading_frame, text="", font=ctk.CTkFont(size=16), text_color="#6a6a6a")
        self.loading_sub_label.pack(pady=5)
        # Three-dot animation will be started
        self.loading_dots = 0
        self.animate_loading_dots()
        # Rotating phrases
        self.loading_phrases = [
            "Refining your challenge...",
            "Hasur is pondering...",
            "Generating chaos...",
            "Twisting the question...",
            "Preparing the ritual..."
        ]
        random.shuffle(self.loading_phrases)
        self.loading_phrase_index = 0
        self.update_loading_phrases()
        
        threading.Thread(target=self.generate_challenge_thread, daemon=True).start()
    
    def animate_loading_dots(self):
        if hasattr(self, 'loading_frame') and self.loading_frame is not None:
            try:
                if self.loading_frame.winfo_exists():
                    dots = "." * (self.loading_dots % 4)
                    self.loading_text_label.configure(text=f"Thinking{dots}")
                    self.loading_dots += 1
                    self.after(500, self.animate_loading_dots)
                else:
                    return
            except tkinter.TclError:
                return
        else:
            return
    
    def update_loading_phrases(self):
        if hasattr(self, 'loading_frame') and self.loading_frame is not None:
            try:
                if self.loading_frame.winfo_exists():
                    if self.loading_phrase_index < len(self.loading_phrases):
                        phrase = self.loading_phrases[self.loading_phrase_index]
                        self.loading_sub_label.configure(text=phrase)
                        self.loading_phrase_index += 1
                        self.after(1200, self.update_loading_phrases)
                    else:
                        random.shuffle(self.loading_phrases)
                        self.loading_phrase_index = 0
                        self.after(1200, self.update_loading_phrases)
                else:
                    return
            except tkinter.TclError:
                return
        else:
            return
    
    def generate_challenge_thread(self):
        try:
            escalation = 2 ** ((self.attempt - 1) // 1)
            
            voice_prompt = f"""
            Generate a random VOICE/CHANTING CHALLENGE for attempt {self.attempt}.
            Return ONLY valid JSON:
            {{"chantText": string (must include "TUNG TUNG TUNG HASUR" plus random extra words),
            "chantBPM": number (135-145),
            "requiredVolume": string (whisper/normal/loud/scream),
            "hypeLevel": number (1-10)}}
            """
            voice_response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": voice_prompt}],
                response_format={"type": "json_object"}, temperature=0.95)
            vc = json.loads(voice_response.choices[0].message.content)
            
            final_moves = ["dab", "67 move", "woah", "Brazillian Dance", "floss", "griddy"]
            action_prompt = f"""
            Generate a random MOVEMENT/DANCE CHALLENGE for attempt {self.attempt}.
            Escalate difficulty by {escalation}x.
            Return ONLY valid JSON:
            {{"spins": number (2-8), "claps": number (2-8),
            "finalMove": string (one of: "{', '.join(final_moves)}")}}
            """
            action_response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": action_prompt}],
                response_format={"type": "json_object"}, temperature=0.95)
            ac = json.loads(action_response.choices[0].message.content)
            
            self.challenge = {
                "chantText": vc.get("chantText", "TUNG TUNG TUNG HASUR"),
                "chantBPM": vc.get("chantBPM", 140),
                "requiredVolume": vc.get("requiredVolume", "loud"),
                "hypeLevel": vc.get("hypeLevel", 7),
                "spins": int(ac.get("spins", 2)) * escalation,
                "claps": int(ac.get("claps", 2)) * escalation,
                "finalMove": ac.get("finalMove", "dab"),
            }
            self.required_spins = int(self.challenge["spins"])
            self.required_claps = int(self.challenge["claps"])
            self.required_chant = self.challenge["chantText"]
            self.required_volume = self.challenge["requiredVolume"]
            self.after(0, self.go_to_chant_page)
        except Exception as e:
            print(f"⚠️ Challenge API error: {e}")
            self.simulate_challenge()
        finally:
            # Hide loading frame
            if hasattr(self, 'loading_frame') and self.loading_frame is not None:
                try:
                    self.loading_frame.destroy()
                except:
                    pass
                self.loading_frame = None
    
    def simulate_challenge(self):
        import random
        final_moves = ["dab", "67 move", "woah", "Brazillian Dance", "floss", "griddy"]
        self.challenge = {
            "chantText": "TUNG TUNG TUNG HASUR",
            "chantBPM": random.choice([138, 140, 142]),
            "requiredVolume": random.choice(["whisper", "normal", "loud", "scream"]),
            "hypeLevel": random.randint(7, 10),
            "spins": random.choice([2, 4, 6]),
            "claps": random.choice([2, 4, 6]),
            "finalMove": random.choice(final_moves)
        }
        self.required_spins = int(self.challenge["spins"])
        self.required_claps = int(self.challenge["claps"])
        self.required_chant = self.challenge["chantText"]
        self.required_volume = self.challenge["requiredVolume"]
        self.after(0, self.go_to_chant_page)
        if hasattr(self, 'loading_frame') and self.loading_frame is not None:
            try:
                self.loading_frame.destroy()
            except:
                pass
            self.loading_frame = None
    
    # ==========================================================
    # PAGE NAVIGATION
    # ==========================================================
    def go_to_chant_page(self):
        self.phase = "chant"
        self.chant_passed = False
        self.dance_passed = False
        self.realtime_spins = 0
        self.realtime_claps = 0
        self.audio_text = ""
        self.live_decibel = 0
        self.stop_background_music()
        
        self.chat_frame.pack_forget()
        self.input_frame.pack_forget()
        self.dance_frame.pack_forget()
        self.failure_overlay.pack_forget()
        self.answer_frame.pack_forget()
        self.answer_loading_frame.pack_forget()
        self.chant_frame.pack(fill="both", expand=True)
        
        self.chant_challenge_label.configure(
            text=f"🗣️ Chant: \"{self.required_chant}\"\n"
                 f"Required Volume: {self.required_volume.upper()} | "
                 f"BPM: {self.challenge.get('chantBPM', 140)} | "
                 f"Hype: {self.challenge.get('hypeLevel', 7)}/10")
        self.chant_heard_label.configure(text="🎤 Heard: Waiting for you to chant...")
        self.chant_decibel_bar.set(0)
        self.chant_db_label.configure(text="0 dB")
        self.chant_countdown_label.configure(text="")
        self.chant_instruction_label.configure(
            text="👇 Press START CHANTING below — the mic only listens after you press it!",
            text_color="#b0b0b0")
        self.chant_start_btn.configure(state="normal", text="🎤 START CHANTING")
        self.proceed_to_dance_btn.pack_forget()
    
    def go_to_dance_page(self):
        self.phase = "dance"
        self.stop_background_music()
        self.chant_frame.pack_forget()
        self.dance_frame.pack(fill="both", expand=True)
        
        self.dance_challenge_label.configure(
            text=f"🔄 {self.required_spins}x SPINS | 👏 {self.required_claps}x CLAPS\n"
                 f"🕺 Finish with: {self.challenge.get('finalMove', 'DAB').upper()}!")
        self.dance_countdown_label.configure(text="")
        self.dance_instruction_label.configure(
            text="👇 Press START DANCING below — Qwen-Vision only watches after you press it!",
            text_color="#b0b0b0")
        self.dance_start_btn.configure(state="normal", text="💃 START DANCING")
    
    # ==========================================================
    # SESSION 1: CHANTING (Qwen-Audio)
    # ==========================================================
    def start_chant_phase(self):
        self.chant_start_btn.configure(state="disabled", text="🎤 CHANTING...")
        self.chant_instruction_label.configure(text="🎤 CHANT NOW! Speak loudly!", text_color="#888")
        self.chant_heard_label.configure(text="🎤 Heard: Listening...")
        threading.Thread(target=self.run_chant_recording, daemon=True).start()
    
    def run_chant_recording(self):
        duration = CHANT_DURATION
        samplerate = 44100
        self.audio_data = []
        folder = self.get_session_folder()
        chant_wav = f"{folder}/chant_audio.wav"
        self.current_audio_filename = chant_wav
        
        def audio_cb(indata, frames, time_info, status):
            self.audio_data.append(indata.copy())
            rms = np.sqrt(np.mean(indata ** 2))
            db = min(100, rms * 3000)
            self.live_decibel = db
            self.after(0, lambda v=db: self.update_chant_decibel(v))
        
        stream = sd.InputStream(samplerate=samplerate, channels=1, callback=audio_cb)
        stream.start()
        self.after(0, lambda: self.chant_countdown(duration, stream, chant_wav))
    
    def update_chant_decibel(self, db):
        self.chant_decibel_bar.set(min(1.0, db / 100))
        self.chant_db_label.configure(text=f"{db:.0f} dB")
    
    def chant_countdown(self, time_left, stream, chant_wav):
        if time_left <= 0:
            stream.stop()
            stream.close()
            if self.audio_data:
                audio_array = np.concatenate(self.audio_data, axis=0)
                wavfile.write(chant_wav, 44100, audio_array)
            self.chant_countdown_label.configure(text="🔍")
            self.chant_instruction_label.configure(
                text="⏳ Qwen-Audio is analyzing your chant...", text_color="#888")
            threading.Thread(target=self.analyze_chant_thread, args=(chant_wav,), daemon=True).start()
            return
        self.chant_countdown_label.configure(text=f"🎤 {time_left:.1f}s")
        self.after(100, lambda: self.chant_countdown(time_left - 0.1, stream, chant_wav))
    
    def analyze_chant_thread(self, chant_wav):
        try:
            if not os.path.exists(chant_wav):
                raise Exception("Audio not found.")
            
            sr, audio_array = wavfile.read(chant_wav)
            audio_array = np.asarray(audio_array)
            if audio_array.ndim > 1:
                audio_array = audio_array.mean(axis=1)
            
            # Compute actual loudness (dB) from the recorded audio
            rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
            # Map rms to 0-100 dB scale (calibrated empirically)
            if rms > 0:
                # audio array is int16, max rms ~32767, map to 0-100
                db_val = min(100, int((rms / 32767) * 3000))
            else:
                db_val = 0
            self.actual_loudness_percent = db_val
            # Update the UI with the real dB
            self.after(0, lambda: self.chant_decibel_bar.set(min(1.0, db_val / 100)))
            self.after(0, lambda: self.chant_db_label.configure(text=f"{db_val} dB"))
            
            # Resample to 16kHz for Qwen-Audio API
            if audio_array.dtype in (np.float32, np.float64):
                audio_int16 = (np.clip(audio_array, -1.0, 1.0) * 32767).astype(np.int16)
            else:
                audio_int16 = audio_array.astype(np.int16)
            
            try:
                from scipy.signal import resample_poly
                from math import gcd
                g = gcd(int(sr), 16000)
                audio_16k = resample_poly(audio_int16.astype(np.float64),
                                          16000 // g, int(sr) // g).astype(np.int16)
                target_sr = 16000
            except Exception:
                audio_16k = audio_int16
                target_sr = int(sr)
            
            buf = io.BytesIO()
            wavfile.write(buf, target_sr, audio_16k)
            audio_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            
            url = "https://ws-bf3itnzatquc4sa0.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "qwen3-omni-flash",
                "input": {
                    "messages": [
                        {"role": "system", "content": "You are a transcription assistant. Always transcribe in English."},
                        {"role": "user", "content": [
                            {"audio": f"data:audio/wav;base64,{audio_b64}"},
                            {"text": "Transcribe exactly what the person said in English."}
                        ]}
                    ]
                }
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                content = data["output"]["choices"][0]["message"]["content"]
                transcription = ""
                for item in content:
                    if "text" in item:
                        transcription = item["text"]
                        break
                
                detected_text = transcription.lower()
                required_phrase = self.required_chant.lower()
                phrase_detected = required_phrase in detected_text or detected_text in required_phrase
                if not phrase_detected:
                    alt_phrase = required_phrase.replace("hasur", "sahur")
                    phrase_detected = alt_phrase in detected_text or detected_text in alt_phrase
                
                brainrot_detected = any(phrase in detected_text for phrase in self.brainrot_phrases)
                passed = phrase_detected or brainrot_detected
                
                result = {
                    "transcription": transcription,
                    "detected_volume": self.required_volume,
                    "phrase_correct": phrase_detected,
                    "brainrot_detected": brainrot_detected,
                    "volume_sufficient": True,
                    "passed": passed,
                    "reason": "Phrase detected" if phrase_detected else "Brainrot detected" if brainrot_detected else "Nothing detected",
                    "loudness_percent": db_val  # use real measured dB
                }
            else:
                print(f"⚠️ API error: {response.text}")
                raise Exception("API returned non-200")
            
            self.audio_analysis_result = result
            self.chant_passed = bool(result.get("passed", False))
            self.audio_text = result.get("transcription", "")
            self.after(0, lambda: self.show_chant_result(result))
            
        except Exception as e:
            print(f"⚠️ Chant error: {e}")
            db_val = self.actual_loudness_percent or 0
            fallback = {
                "passed": True,
                "reason": "Qwen-Audio fallback (demo mode)",
                "transcription": self.required_chant,
                "detected_phrase": self.required_chant,
                "detected_volume": self.required_volume,
                "phrase_correct": True,
                "brainrot_detected": True,
                "volume_sufficient": True,
                "loudness_percent": db_val
            }
            self.audio_analysis_result = fallback
            self.chant_passed = True
            self.audio_text = fallback["transcription"]
            self.after(0, lambda: self.show_chant_result(fallback))
    
    def show_chant_result(self, result):
        self.chant_countdown_label.configure(text="")
        transcription = result.get("transcription") or "(nothing detected)"
        volume = result.get("detected_volume", "???")
        loudness = result.get("loudness_percent", 0)
        passed = result.get("passed", False)
        icon = "✅" if passed else "❌"
        brainrot_detected = result.get("brainrot_detected", False)
        extra = " 🧠 Brainrot detected!" if brainrot_detected else ""
        
        self.chant_heard_label.configure(
            text=(f"📝 Qwen-Audio transcribed:\n\"{transcription}\"\n\n"
                  f"🔊 Volume: {str(volume).upper()} ({loudness} dB) {icon}{extra}"),
            text_color="#b0b0b0" if passed else "#888",
            wraplength=800, justify="center")
        # Update the bar and label already set during analysis
        # (they were updated earlier)
        
        if passed:
            self.chant_instruction_label.configure(
                text="✅ VOICE CHALLENGE PASSED! Proceed to the Dance Challenge below.",
                text_color="#888")
            self.chant_start_btn.configure(text="🎤 CHANT ✅")
        else:
            self.chant_instruction_label.configure(
                text=f"❌ VOICE CHALLENGE FAILED: {result.get('reason', 'Unknown')}. Proceed anyway.",
                text_color="#888")
            self.chant_start_btn.configure(text="🎤 CHANT ❌")
        
        self.proceed_to_dance_btn.pack(side="left", padx=10, pady=15)
    
    # ==========================================================
    # SESSION 2: DANCING (Qwen-Vision) - IMAGE-BASED
    # ==========================================================
    def start_dance_phase(self):
        self.dance_start_btn.configure(state="disabled", text="💃 DANCING...")
        self.dance_instruction_label.configure(
            text="💃 DANCE NOW! Spin! Clap! Hit the move!", text_color="#888")
        threading.Thread(target=self.run_dance_recording, daemon=True).start()
    
    def run_dance_recording(self):
        duration = DANCE_DURATION
        folder = self.get_session_folder()
        frame_folder = f"{folder}/frames"
        os.makedirs(frame_folder, exist_ok=True)
        self.current_frame_folder = frame_folder
        self.frame_counter = 0
        self.is_recording = True
        
        samplerate = 44100
        self.audio_data = []
        
        def audio_cb(indata, frames, time_info, status):
            self.audio_data.append(indata.copy())
        
        stream = sd.InputStream(samplerate=samplerate, channels=1, callback=audio_cb)
        stream.start()
        self.after(0, lambda: self.dance_countdown(duration, stream, frame_folder))
    
    def dance_countdown(self, time_left, stream, frame_folder):
        if time_left <= 0:
            self.is_recording = False
            stream.stop()
            stream.close()
            if self.audio_data:
                audio_array = np.concatenate(self.audio_data, axis=0)
                audio_file = f"{os.path.dirname(frame_folder)}/dance_audio.wav"
                wavfile.write(audio_file, 44100, audio_array)
                self.current_audio_filename = audio_file
            
            print(f"📸 Saved {self.frame_counter} frames in {frame_folder}")
            self.dance_countdown_label.configure(text="🔍")
            self.dance_instruction_label.configure(
                text="⏳ Qwen-Vision is counting your moves...", text_color="#888")
            threading.Thread(target=self.analyze_dance_thread, args=(frame_folder,), daemon=True).start()
            return
        self.dance_countdown_label.configure(text=f"💃 {time_left:.1f}s")
        self.after(100, lambda: self.dance_countdown(time_left - 0.1, stream, frame_folder))
    
    def get_frames_from_images(self, folder, num_frames=DANCE_FRAMES):
        images = sorted([f for f in os.listdir(folder) if f.endswith('.jpg')])
        total = len(images)
        if total == 0:
            return []
        indices = [int(i * total / num_frames) for i in range(num_frames)]
        encoded = []
        for idx in indices:
            if idx >= total:
                break
            img_path = os.path.join(folder, images[idx])
            frame = cv2.imread(img_path)
            if frame is not None:
                frame = cv2.resize(frame, (384, 384))
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                encoded.append(base64.b64encode(buffer).decode('utf-8'))
        return encoded
    
    def analyze_dance_thread(self, frame_folder):
        try:
            frames_b64 = self.get_frames_from_images(frame_folder, num_frames=DANCE_FRAMES)
            if not frames_b64:
                raise Exception("No frames extracted from images.")
            
            required_spins = self.required_spins
            required_claps = self.required_claps
            final_move = self.challenge.get('finalMove', 'dab')
            
            prompt = f"""
            You are a motion‑analysis expert. You are given {len(frames_b64)} sequential frames from a video.
            
            The person was asked to:
            - Spin **exactly {required_spins} times** – a full 360° rotation of the body.
            - Clap **exactly {required_claps} times** – both hands touching (palms together).
            - Finish with a **'{final_move}'** pose.
            
            **How to count claps (touches):**
            - A clap is when both hands touch each other (no gap).
            - Look for frames where hands are in contact.
            - Count each separate touching event (touch, separate, touch again = 2).
            
            **How to count spins:**
            - A spin is a full rotation. Track shoulders and head orientation.
            - Count only complete 360° rotations.
            
            **Instructions:**
            - Scan frames in order.
            - If no motion, return 0 for both.
            - Provide the counts and brief reasoning.
            
            Return ONLY valid JSON:
            {{
                "detected_spins": integer,
                "detected_claps": integer,
                "detected_final_move": string,
                "confidence": "high" | "medium" | "low",
                "reasoning": "brief explanation"
            }}
            """
            
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            for img in frames_b64:
                messages[0]["content"].append({"type": "image_url", "image_url": f"data:image/jpeg;base64,{img}"})
            
            vision_models = ["qwen-vl-max", "qwen-vl-plus", "qwen-vl"]
            result = None
            for model in vision_models:
                try:
                    print(f"📡 Trying model: {model}...")
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.0,
                        max_tokens=200,
                        timeout=30
                    )
                    result = json.loads(response.choices[0].message.content)
                    print(f"✅ Success with {model}: {result}")
                    break
                except Exception as e:
                    print(f"⚠️ Model {model} failed: {e}")
                    continue
            
            if result is None:
                # Fallback motion detection
                print("🔄 Falling back to local motion detection.")
                images = sorted([f for f in os.listdir(frame_folder) if f.endswith('.jpg')])
                frames = [cv2.imread(os.path.join(frame_folder, img)) for img in images if cv2.imread(os.path.join(frame_folder, img)) is not None]
                if len(frames) < 2:
                    raise Exception("Not enough frames for motion detection.")
                prev = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
                motion_sum = 0
                for i in range(1, len(frames)):
                    curr = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
                    diff = cv2.absdiff(prev, curr)
                    non_zero = np.count_nonzero(diff > 30)
                    if non_zero > 10000:
                        motion_sum += 1
                    prev = curr
                if motion_sum > 5:
                    detected_spins = min(required_spins, 2)
                    detected_claps = min(required_claps, 2)
                    result = {
                        "detected_spins": detected_spins,
                        "detected_claps": detected_claps,
                        "detected_final_move": "dab",
                        "confidence": "low",
                        "reasoning": "Fallback motion detection"
                    }
                else:
                    result = {
                        "detected_spins": 0,
                        "detected_claps": 0,
                        "detected_final_move": "none",
                        "confidence": "low",
                        "reasoning": "No motion detected"
                    }
                self.vision_analysis_result = result
                detected_spins = result.get("detected_spins", 0)
                detected_claps = result.get("detected_claps", 0)
                self.realtime_spins = detected_spins
                self.realtime_claps = detected_claps
                self.dance_passed = (detected_spins >= self.required_spins and detected_claps >= self.required_claps)
                self.after(0, lambda: self.show_dance_result(result))
                shutil.rmtree(frame_folder)
                return
            
            self.vision_analysis_result = result
            detected_spins = result.get("detected_spins", 0)
            detected_claps = result.get("detected_claps", 0)
            self.realtime_spins = detected_spins
            self.realtime_claps = detected_claps
            self.dance_passed = (detected_spins >= self.required_spins and detected_claps >= self.required_claps)
            self.after(0, lambda: self.show_dance_result(result))
            
        except Exception as e:
            print(f"⚠️ Dance error: {e}")
            fallback = {
                "passed": False,
                "reason": f"Error: {e}",
                "detected_spins": 0,
                "detected_claps": 0,
                "detected_final_move": "none",
                "final_move_correct": False,
                "confidence": "low",
                "reasoning": str(e)
            }
            self.vision_analysis_result = fallback
            self.dance_passed = False
            self.after(0, lambda: self.show_dance_result(fallback))
        finally:
            try:
                shutil.rmtree(frame_folder)
            except:
                pass
    
    def show_dance_result(self, result):
        self.dance_countdown_label.configure(text="")
        det_s = result.get("detected_spins", 0)
        det_c = result.get("detected_claps", 0)
        det_move = result.get("detected_final_move", "?")
        passed = self.dance_passed
        # We removed the progress label, so just show a message.
        # We'll update the instruction label with the result.
        status_text = f"SPINS: {det_s}/{self.required_spins}  |  CLAPS: {det_c}/{self.required_claps}  |  MOVE: {det_move}"
        if passed:
            self.dance_instruction_label.configure(
                text=f"✅ DANCE CHALLENGE PASSED!\n{status_text}", text_color="#888")
            self.dance_start_btn.configure(text="💃 DANCE ✅")
        else:
            self.dance_instruction_label.configure(
                text=f"❌ DANCE CHALLENGE FAILED: {result.get('reason', 'Unknown')}\n{status_text}",
                text_color="#888")
            self.dance_start_btn.configure(text="💃 DANCE ❌")
        self.after(2000, self.evaluate_final_result)
    
    # ==========================================================
    # FINAL EVALUATION
    # ==========================================================
    def evaluate_final_result(self):
        audio_result = self.audio_analysis_result or {}
        vision_result = self.vision_analysis_result or {}
        audio_score = min(100, audio_result.get("loudness_percent", 50))
        vision_score = 100 if self.dance_passed else int(
            min(1.0, self.realtime_spins / max(1, self.required_spins)) * 100)
        
        if self.chant_passed and self.dance_passed:
            self.ritual_passed = True
            self.show_answer()
        else:
            self.ritual_passed = False
            reasons = []
            if not self.chant_passed:
                reasons.append(f"🎤 {audio_result.get('reason', 'Chant failed')}")
            if not self.dance_passed:
                if self.realtime_spins < self.required_spins:
                    reasons.append(f"💃 {self.realtime_spins}/{self.required_spins} spins")
                if self.realtime_claps < self.required_claps:
                    reasons.append(f"💃 {self.realtime_claps}/{self.required_claps} claps")
                if not vision_result.get("final_move_correct", False):
                    reasons.append(f"💃 Wrong move (need {self.challenge.get('finalMove', 'dab')})")
            reason = " | ".join(reasons) if reasons else "Both challenges failed"
            self.failure_count += 1
            self.failure_counter_label.configure(text=f"❌ Failures: {self.failure_count}")
            self.print_thermal_receipt(self.attempt, reason, audio_score, vision_score, "FAILED")
            self.show_failure(reason)
    
    # ==========================================================
    # HELPERS
    # ==========================================================
    def get_session_folder(self):
        today = datetime.datetime.now()
        folder = f"recordings/{today.strftime('%Y-%m-%d')}_{today.strftime('%A')}/attempt{self.attempt}"
        os.makedirs(folder, exist_ok=True)
        return folder
    
    def print_thermal_receipt(self, attempt, reason, audio_score, vision_score, status):
        brainrot = random.choice(BRAINROT_FAILURES)
        receipt = RECEIPT_TEMPLATE.format(
            receipt_num=len(self.failure_receipts) + 1,
            attempt=attempt, max_attempts=MAX_ATTEMPTS,
            reason=reason[:40], audio_score=audio_score,
            vision_score=vision_score, status=status, brainrot=brainrot)
        self.failure_receipts.append(receipt)
        self.receipt_label.configure(text=receipt)
        self.receipt_frame.place(relx=0.85, rely=0.5, anchor="center")
        self.after(6000, lambda: self.receipt_frame.place_forget())
    
    def show_failure(self, reason):
        self.stop_background_music()
        self.dance_frame.pack_forget()
        self.chant_frame.pack_forget()
        self.failure_overlay.pack(fill="both", expand=True)
        self.failure_reason_label.configure(text=reason)
        self.brainrot_label.configure(text=f"💀 {random.choice(BRAINROT_FAILURES)} 💀")
        self.play_audio(FAILURE_AUDIO)
        self.flash_overlay(16)
        self.after(6000, self.advance_attempt)
    
    def flash_overlay(self, count):
        if count <= 0:
            self.failure_overlay.configure(fg_color="#3a3a3a")
            return
        self.failure_overlay.configure(fg_color="#3a3a3a" if count % 2 == 0 else "#1a1a1a")
        self.after(300, lambda: self.flash_overlay(count - 1))
    
    def advance_attempt(self):
        self.failure_overlay.pack_forget()
        if self.attempt >= MAX_ATTEMPTS:
            self.show_answer()
        else:
            self.attempt += 1
            self.attempt_label.configure(text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}")
            self.chat_frame.pack(fill="both", expand=True, padx=20, pady=10)
            self.input_frame.pack(fill="x", padx=20, pady=(0, 10))
            self.send_btn.configure(state="normal")
            self.play_background_music(0.3)
    
    # ==========================================================
    # ANSWER WITH LOADING ANIMATION (ChatGPT-style thinking)
    # ==========================================================
    def show_answer(self):
        self.chant_frame.pack_forget()
        self.dance_frame.pack_forget()
        self.failure_overlay.pack_forget()
        self.answer_frame.pack_forget()
        self.answer_loading_frame.pack(fill="both", expand=True)
        self.answer_loading_frame.lift()
        
        # ChatGPT-style thinking indicator
        self.answer_loading_icon = ctk.CTkLabel(self.answer_loading_frame, text="⚪", font=ctk.CTkFont(size=30), text_color="#6a6a6a")
        self.answer_loading_icon.pack(pady=(100, 10))
        self.answer_loading_text = ctk.CTkLabel(self.answer_loading_frame, text="Generating answer", font=ctk.CTkFont(size=22, weight="bold"), text_color="#b0b0b0")
        self.answer_loading_text.pack(pady=5)
        self.answer_loading_sub = ctk.CTkLabel(self.answer_loading_frame, text="Refining the brainrot...", font=ctk.CTkFont(size=16), text_color="#6a6a6a")
        self.answer_loading_sub.pack(pady=5)
        # Animate dots
        self.answer_dots = 0
        self.animate_answer_dots()
        # Rotating sub-phrases
        self.answer_phrases = [
            "Refining the brainrot...",
            "Hasur is cooking...",
            "Twisting the truth...",
            "Generating chaos...",
            "Preparing your nonsense..."
        ]
        random.shuffle(self.answer_phrases)
        self.answer_phrase_idx = 0
        self.update_answer_phrases()
        
        self.stop_background_music()
        threading.Thread(target=self.get_wrong_answer_thread, daemon=True).start()
    
    def animate_answer_dots(self):
        if not self.answer_loading_frame.winfo_ismapped():
            return
        dots = "." * (self.answer_dots % 4)
        self.answer_loading_text.configure(text=f"Generating answer{dots}")
        self.answer_dots += 1
        self.after(500, self.animate_answer_dots)
    
    def update_answer_phrases(self):
        if not self.answer_loading_frame.winfo_ismapped():
            return
        if self.answer_phrase_idx < len(self.answer_phrases):
            phrase = self.answer_phrases[self.answer_phrase_idx]
            self.answer_loading_sub.configure(text=phrase)
            self.answer_phrase_idx += 1
            self.after(1200, self.update_answer_phrases)
        else:
            random.shuffle(self.answer_phrases)
            self.answer_phrase_idx = 0
            self.after(1200, self.update_answer_phrases)
    
    def get_wrong_answer_thread(self):
        try:
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": (
                    f"User asked: '{self.question}'. "
                    f"Give a completely wrong, absurd, brainrot answer in under 30 words.")}],
                temperature=1.2)
            answer = response.choices[0].message.content
            self.after(0, lambda: self.display_answer(answer))
        except Exception as e:
            print(f"⚠️ Answer error: {e}")
            self.after(0, lambda: self.display_answer(
                "🫠 The answer is 42, but only on Tuesdays in Ohio."))
    
    def display_answer(self, answer):
        self.answer_loading_frame.pack_forget()
        self.answer_frame.pack(fill="both", expand=True)
        
        char = random.choice(CHARACTERS)
        if os.path.exists(char["img"]):
            img = Image.open(char["img"]).resize((150, 150))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 150))
            self.char_image_label.configure(image=ctk_img)
            self.char_image_label.image = ctk_img
        self.char_name_label.configure(text=char["name"])
        self.answer_text_label.configure(text=answer)
        if os.path.exists(char["audio"]):
            self.play_audio(char["audio"], loop=True)
    
    def restart_app(self):
        self.stop_audio()
        self.stop_background_music()
        self.attempt = 1
        self.failure_count = 0
        self.failure_receipts = []
        self.ritual_passed = False
        self.chant_passed = False
        self.dance_passed = False
        self.phase = "idle"
        self.answer_frame.pack_forget()
        self.answer_loading_frame.pack_forget()
        self.failure_overlay.pack_forget()
        self.chant_frame.pack_forget()
        self.dance_frame.pack_forget()
        self.chat_frame.pack(fill="both", expand=True, padx=20, pady=10)
        self.input_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.send_btn.configure(state="normal")
        self.attempt_label.configure(text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}")
        self.failure_counter_label.configure(text="❌ Failures: 0")
        self.question_entry.delete(0, 'end')
        self.receipt_label.configure(text="")
        self.receipt_frame.place_forget()
        self.title("ChatGPT Clone")
        self.play_background_music(0.3)


if __name__ == "__main__":
    print("=" * 60)
    print("🔮 TUNG TUNG TUNG HASUR VERIFICATION GATE 🔮")
    print("=" * 60)
    try:
        app = HasurGateApp()
        app.mainloop()
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
