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
from openai import OpenAI

# ==========================================================
# >>> INSERT YOUR API KEY HERE <<<
# ==========================================================
API_KEY = "sk-ws-H.XRLLPH.xKTZ.MEQCIDpvzKrBByEb0Z0o3BWRPqhAOOEBNLmtA5dMYOnmICfVAiAojcvIPTMi26CFSUmE-ycj_lYNriHhlrFM2Dnm4PjDGw"
API_BASE_URL = "https://ws-bf3itnzatquc4sa0.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

# ==========================================================
# MODEL NAMES (Aliyun MaaS)
# ==========================================================
TEXT_MODEL   = "qwen-plus"
AUDIO_MODEL  = "qwen3-omni-flash"
VISION_MODEL = "qwen-vl-max"

# ==========================================================
# CONFIGURATION
# ==========================================================
MAX_ATTEMPTS   = 1
CHANT_DURATION = 6.0
DANCE_DURATION = 8.0

BACKGROUND_MUSIC = "assets/background.mp3"
CHARACTERS = [
    {"name": "Goblin of Confusion", "img": "assets/char1.png", "audio": "assets/char1.mp3"},
    {"name": "Specter of Nonsense", "img": "assets/char2.png", "audio": "assets/char2.mp3"},
    {"name": "Void Walker",         "img": "assets/char3.png", "audio": "assets/char3.mp3"},
    {"name": "Brainrot Entity",     "img": "assets/char4.png", "audio": "assets/char4.mp3"},
    {"name": "Hasur's Jester",      "img": "assets/char5.png", "audio": "assets/char5.mp3"},
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
║       TUNG TUNG TUNG HASUR™              ║
║       HUMILIATION RECEIPT #{receipt_num:<3}           ║
╠══════════════════════════════════════════╣
║ ATTEMPT: #{attempt} / {max_attempts}                     ║
║ REASON: {reason:<34} ║
║ AUDIO SCORE: {audio_score:>3}/100                 ║
║ VISION SCORE: {vision_score:>3}/100                ║
║ STATUS: ❌ {status:<27} ║
╠══════════════════════════════════════════╣
║ {brainrot:<40} ║
╚══════════════════════════════════════════╝
"""

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class HasurGateApp(ctk.CTk):

    def __init__(self):
        print("🟢 Starting Hasur Gate App...", flush=True)
        super().__init__()

        self.title("ChatGPT Clone")
        self.geometry("1200x800")
        try:
            self.state("zoomed")                 # Windows
        except Exception:
            try:
                self.attributes("-zoomed", True)  # macOS fallback
            except Exception:
                pass
        self.bind("<Escape>", lambda e: self.on_escape())

        # ---------- state ----------
        self.attempt = 1
        self.question = ""
        self.challenge = {}
        self.is_recording = False
        self.cap = None
        self.video_writer = None
        self.audio_data = []
        self.failure_count = 0
        self.failure_receipts = []
        self.ritual_passed = False
        self.audio_analysis_result = None
        self.vision_analysis_result = None
        self.current_phase = None
        self.chant_passed = False
        self.dance_passed = False
        self.realtime_spins = 0
        self.realtime_claps = 0
        self.audio_text = ""
        self.live_decibel = 0.0
        self.required_spins = 0
        self.required_claps = 0
        self.required_chant = ""
        self.required_volume = "loud"
        self.current_video_filename = ""
        self.current_audio_filename = ""
        self.current_final_filename = ""
        self.current_audio_process = None
        self.background_music_process = None

        self.setup_ui()
        self.update_camera_loop()
        self.play_background_music(0.3)
        print("🟢 App initialized successfully!", flush=True)

    # ==========================================================
    # LIFECYCLE
    # ==========================================================
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
                try: os.remove(f)
                except Exception: pass
        super().destroy()

    # ==========================================================
    # PROCESS KILLERS
    # ==========================================================
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
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                except (ProcessLookupError, OSError):
                    try: os.kill(pid, signal.SIGKILL)
                    except Exception: pass
        except Exception:
            try: proc.terminate()
            except Exception: pass

    def stop_audio(self):
        self._kill_proc(self.current_audio_process)
        self.current_audio_process = None

    def stop_background_music(self):
        self._kill_proc(self.background_music_process)
        self.background_music_process = None

    # ==========================================================
    # UI
    # ==========================================================
    def setup_ui(self):
        self.main_container = ctk.CTkFrame(self, fg_color="#212121")
        self.main_container.pack(fill="both", expand=True)

        # ---------------- LEFT SIDEBAR ----------------
        self.sidebar = ctk.CTkFrame(self.main_container, width=260, fg_color="#171717", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        sidebar_inner = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_inner.pack(fill="both", expand=True, padx=12, pady=12)

        self.new_chat_btn = ctk.CTkButton(sidebar_inner, text="+ New Chat",
                                          font=ctk.CTkFont(size=14, weight="bold"),
                                          fg_color="#2F2F2F", hover_color="#3F3F3F",
                                          corner_radius=8, height=40, command=self.restart_app)
        self.new_chat_btn.pack(fill="x", pady=(0, 20))

        self.model_btn = ctk.CTkButton(sidebar_inner, text="⚡ Hasur-4B (Brainrot)",
                                       font=ctk.CTkFont(size=13), fg_color="#2F2F2F",
                                       hover_color="#3F3F3F", corner_radius=8, height=35, anchor="w")
        self.model_btn.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(sidebar_inner, text="Today", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#9CA3AF").pack(anchor="w", pady=(10, 5))
        for item in ["What is the meaning of life?", "Tell me a joke", "Tung Tung Tung Hasur"]:
            ctk.CTkButton(sidebar_inner, text=item, font=ctk.CTkFont(size=13),
                          fg_color="transparent", hover_color="#2F2F2F",
                          corner_radius=8, height=30, anchor="w").pack(fill="x", pady=1)

        ctk.CTkFrame(sidebar_inner, fg_color="transparent").pack(fill="both", expand=True)

        profile_frame = ctk.CTkFrame(sidebar_inner, fg_color="transparent")
        profile_frame.pack(fill="x")
        ctk.CTkLabel(profile_frame, text="👤", font=ctk.CTkFont(size=20), fg_color="#2F2F2F",
                     corner_radius=16, width=32, height=32).pack(side="left", padx=5)
        ctk.CTkLabel(profile_frame, text="tungtungtungsahur", font=ctk.CTkFont(size=13),
                     text_color="#ECECEC").pack(side="left", padx=10)

        # ---------------- RIGHT COLUMN ----------------
        self.main_canvas = ctk.CTkFrame(self.main_container, fg_color="#212121")
        self.main_canvas.pack(side="right", fill="both", expand=True)

        self.nav_bar = ctk.CTkFrame(self.main_canvas, fg_color="#212121", height=50)
        self.nav_bar.pack(fill="x", padx=20, pady=(10, 0))
        self.nav_bar.pack_propagate(False)
        ctk.CTkButton(self.nav_bar, text="▼ Hasur-4B (Brainrot)",
                      font=ctk.CTkFont(size=14, weight="bold"), fg_color="transparent",
                      hover_color="#2F2F2F", corner_radius=8, height=40).pack(side="left")

        # ---------------- CHAT PAGE ----------------
        self.chat_frame = ctk.CTkScrollableFrame(self.main_canvas, fg_color="transparent")
        self.chat_frame.pack(fill="both", expand=True, padx=20, pady=10)

        welcome_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        welcome_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(welcome_frame, text="What can I help with?",
                     font=ctk.CTkFont(size=28, weight="bold"), text_color="#ECECEC").pack(pady=(120, 20))

        chips_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        chips_frame.pack()
        for i, s in enumerate(["Ask me anything...", "Brainrot joke", "Tell me about AI", "Write a poem"]):
            chip = ctk.CTkButton(chips_frame, text=s, font=ctk.CTkFont(size=13),
                                 fg_color="#2F2F2F", hover_color="#3F3F3F", corner_radius=20,
                                 height=35, border_width=1, border_color="#3F3F3F")
            chip.grid(row=i // 2, column=i % 2, padx=5, pady=5)
            chip.configure(command=lambda txt=s: self.question_entry.insert(0, txt))

        # ---------------- INPUT BAR ----------------
        self.input_frame = ctk.CTkFrame(self.main_canvas, fg_color="#212121", height=90)
        self.input_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.input_frame.pack_propagate(False)

        input_container = ctk.CTkFrame(self.input_frame, fg_color="#2F2F2F", corner_radius=24, height=52)
        input_container.pack(fill="x", padx=20, pady=8)
        input_container.pack_propagate(False)

        input_row = ctk.CTkFrame(input_container, fg_color="transparent")
        input_row.pack(fill="both", padx=15, pady=5)

        self.question_entry = ctk.CTkEntry(input_row, placeholder_text="Message Hasur...",
                                           font=ctk.CTkFont(size=16), fg_color="transparent",
                                           border_width=0, height=38)
        self.question_entry.pack(side="left", fill="x", expand=True)
        self.question_entry.bind("<Return>", lambda e: self.start_ritual())

        self.send_btn = ctk.CTkButton(input_row, text="↑", font=ctk.CTkFont(size=18, weight="bold"),
                                      fg_color="#4A4A4A", hover_color="#6B6B6B", corner_radius=20,
                                      width=32, height=32, command=self.start_ritual)
        self.send_btn.pack(side="right")

        ctk.CTkLabel(self.input_frame, text="Hasur can make mistakes. Check important info.",
                     font=ctk.CTkFont(size=11), text_color="#9CA3AF").pack(pady=(0, 3))

        # ==========================================================
        # PAGE: VOICE / CHANTING CHALLENGE  (scrollable + pinned bar)
        # ==========================================================
        self.chant_frame = ctk.CTkFrame(self.main_canvas, fg_color="#0a0a2a")
        self.chant_frame.pack_forget()

        # pinned bottom action bar — packed FIRST so it can never be clipped
        self.chant_action_bar = ctk.CTkFrame(self.chant_frame, fg_color="#0d0d38", height=86)
        self.chant_action_bar.pack(side="bottom", fill="x")
        self.chant_action_bar.pack_propagate(False)

        self.chant_start_btn = ctk.CTkButton(self.chant_action_bar, text="🎤 START CHANTING",
                                             command=self.start_chant_phase, height=56, width=300,
                                             font=ctk.CTkFont(size=18, weight="bold"),
                                             fg_color="#2980b9", hover_color="#2471a3")
        self.chant_start_btn.pack(side="left", padx=20, pady=15)

        self.proceed_to_dance_btn = ctk.CTkButton(self.chant_action_bar,
                                                  text="💃 PROCEED TO DANCE CHALLENGE →",
                                                  command=self.go_to_dance_page, height=56, width=360,
                                                  font=ctk.CTkFont(size=16, weight="bold"),
                                                  fg_color="#8e44ad", hover_color="#7d3c98")
        # packed later, only after chant result

        # scrollable content area
        self.chant_scroll = ctk.CTkScrollableFrame(self.chant_frame, fg_color="transparent")
        self.chant_scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(self.chant_scroll, text="🎤 SESSION 1/2 — VOICE CHALLENGE",
                     font=ctk.CTkFont(size=30, weight="bold"), text_color="#00aaff").pack(pady=(18, 2))
        ctk.CTkLabel(self.chant_scroll, text="🗣️ CHANTING SECTION · Qwen-Audio is listening to your voice",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#7fd4ff").pack(pady=(0, 6))

        self.chant_challenge_label = ctk.CTkLabel(self.chant_scroll, text="",
                                                  font=ctk.CTkFont(size=17, weight="bold"),
                                                  text_color="#ffd700", wraplength=900, justify="center")
        self.chant_challenge_label.pack(pady=8)

        self.chant_camera_label = ctk.CTkLabel(self.chant_scroll, text="", width=560, height=315,
                                               fg_color="black", corner_radius=10)
        self.chant_camera_label.pack(pady=8)

        self.chant_decibel_frame = ctk.CTkFrame(self.chant_scroll, fg_color="transparent")
        self.chant_decibel_frame.pack(pady=6)
        ctk.CTkLabel(self.chant_decibel_frame, text="🔊 VOLUME:",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#4ade80").pack(side="left", padx=5)
        self.chant_decibel_bar = ctk.CTkProgressBar(self.chant_decibel_frame, width=420, height=22,
                                                    fg_color="#333", progress_color="#e94560")
        self.chant_decibel_bar.pack(side="left", padx=8)
        self.chant_decibel_bar.set(0)
        self.chant_db_label = ctk.CTkLabel(self.chant_decibel_frame, text="0 dB",
                                           font=ctk.CTkFont(size=15, weight="bold"), text_color="#4ade80")
        self.chant_db_label.pack(side="left", padx=5)

        self.chant_heard_label = ctk.CTkLabel(self.chant_scroll, text="🎤 Heard: Waiting...",
                                              font=ctk.CTkFont(size=15), text_color="#aaa",
                                              wraplength=800, justify="center")
        self.chant_heard_label.pack(pady=4)

        self.chant_countdown_label = ctk.CTkLabel(self.chant_scroll, text="",
                                                  font=ctk.CTkFont(size=46, weight="bold"),
                                                  text_color="#e94560")
        self.chant_countdown_label.pack(pady=2)

        self.chant_instruction_label = ctk.CTkLabel(self.chant_scroll, text="",
                                                    font=ctk.CTkFont(size=16, weight="bold"),
                                                    text_color="#00ff00")
        self.chant_instruction_label.pack(pady=4)

        # ==========================================================
        # PAGE: DANCE / MOVEMENT CHALLENGE  (scrollable + pinned bar)
        # ==========================================================
        self.dance_frame = ctk.CTkFrame(self.main_canvas, fg_color="#1a0a2a")
        self.dance_frame.pack_forget()

        self.dance_action_bar = ctk.CTkFrame(self.dance_frame, fg_color="#220d38", height=86)
        self.dance_action_bar.pack(side="bottom", fill="x")
        self.dance_action_bar.pack_propagate(False)

        self.dance_start_btn = ctk.CTkButton(self.dance_action_bar, text="💃 START DANCING",
                                             command=self.start_dance_phase, height=56, width=300,
                                             font=ctk.CTkFont(size=18, weight="bold"),
                                             fg_color="#8e44ad", hover_color="#7d3c98")
        self.dance_start_btn.pack(padx=20, pady=15)

        self.dance_scroll = ctk.CTkScrollableFrame(self.dance_frame, fg_color="transparent")
        self.dance_scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(self.dance_scroll, text="💃 SESSION 2/2 — DANCE CHALLENGE",
                     font=ctk.CTkFont(size=30, weight="bold"), text_color="#ff66ff").pack(pady=(18, 2))
        ctk.CTkLabel(self.dance_scroll, text="🕺 MOVEMENT SECTION · Qwen-Vision is watching your moves",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#ffb3ff").pack(pady=(0, 6))

        self.dance_challenge_label = ctk.CTkLabel(self.dance_scroll, text="",
                                                  font=ctk.CTkFont(size=17, weight="bold"),
                                                  text_color="#ffd700", wraplength=900, justify="center")
        self.dance_challenge_label.pack(pady=8)

        self.dance_camera_label = ctk.CTkLabel(self.dance_scroll, text="", width=640, height=360,
                                               fg_color="black", corner_radius=10)
        self.dance_camera_label.pack(pady=8)

        self.dance_progress_label = ctk.CTkLabel(self.dance_scroll, text="🔄 SPINS: 0/0 | 👏 CLAPS: 0/0",
                                                 font=ctk.CTkFont(size=20, weight="bold"),
                                                 text_color="#00ffff")
        self.dance_progress_label.pack(pady=6)

        self.dance_countdown_label = ctk.CTkLabel(self.dance_scroll, text="",
                                                  font=ctk.CTkFont(size=46, weight="bold"),
                                                  text_color="#e94560")
        self.dance_countdown_label.pack(pady=2)

        self.dance_instruction_label = ctk.CTkLabel(self.dance_scroll, text="",
                                                    font=ctk.CTkFont(size=16, weight="bold"),
                                                    text_color="#00ff00")
        self.dance_instruction_label.pack(pady=4)

        # ---------------- FAILURE OVERLAY ----------------
        self.failure_overlay = ctk.CTkFrame(self.main_canvas, fg_color="#e94560", corner_radius=0)
        self.failure_overlay.pack_forget()
        self.failure_content = ctk.CTkFrame(self.failure_overlay, fg_color="transparent")
        self.failure_content.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self.failure_content, text="💀 RITUAL FAILED 💀",
                     font=ctk.CTkFont(size=48, weight="bold"), text_color="white").pack(pady=(0, 15))
        self.failure_reason_label = ctk.CTkLabel(self.failure_content, text="",
                                                 font=ctk.CTkFont(size=20), text_color="white",
                                                 wraplength=800, justify="center")
        self.failure_reason_label.pack()
        self.brainrot_label = ctk.CTkLabel(self.failure_content, text="",
                                           font=ctk.CTkFont(size=26, weight="bold"), text_color="#ffd700")
        self.brainrot_label.pack(pady=15)

        self.receipt_frame = ctk.CTkFrame(self.failure_overlay, fg_color="#f5f5dc",
                                          border_width=3, border_color="#333", corner_radius=5)
        self.receipt_frame.place(relx=0.85, rely=0.5, anchor="center")
        self.receipt_label = ctk.CTkLabel(self.receipt_frame, text="",
                                          font=ctk.CTkFont(family="Courier", size=10),
                                          text_color="#333", justify="left")
        self.receipt_label.pack(padx=12, pady=8)

        # ---------------- ANSWER FRAME ----------------
        self.answer_frame = ctk.CTkFrame(self.main_canvas, fg_color="transparent")
        self.answer_frame.pack_forget()
        self.char_image_label = ctk.CTkLabel(self.answer_frame, text="", width=150, height=150)
        self.char_image_label.pack(side="left", padx=40)
        self.dialogue_box = ctk.CTkFrame(self.answer_frame, fg_color="white", corner_radius=15,
                                         border_width=3, border_color="#e94560")
        self.dialogue_box.pack(side="left", fill="both", expand=True, padx=40, pady=40)
        self.char_name_label = ctk.CTkLabel(self.dialogue_box, text="",
                                            font=ctk.CTkFont(size=18, weight="bold"), text_color="#e94560")
        self.char_name_label.pack(pady=(15, 5))
        self.answer_text_label = ctk.CTkLabel(self.dialogue_box, text="", font=ctk.CTkFont(size=18),
                                              text_color="black", wraplength=500, justify="left")
        self.answer_text_label.pack(pady=15, padx=15)
        self.restart_btn = ctk.CTkButton(self.answer_frame, text="🔄 SUFFER AGAIN", command=self.restart_app,
                                         fg_color="#333", hover_color="#555", height=40, width=180,
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self.restart_btn.pack(pady=20)

        # ---------------- STATUS BAR ----------------
        self.status_bar = ctk.CTkFrame(self.main_canvas, fg_color="#1a1a2e", height=28)
        self.status_bar.pack(fill="x", side="bottom")
        self.attempt_label = ctk.CTkLabel(self.status_bar, text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}",
                                          font=ctk.CTkFont(size=12), text_color="#888")
        self.attempt_label.pack(side="left", padx=15)
        self.failure_counter_label = ctk.CTkLabel(self.status_bar, text="❌ Failures: 0",
                                                  font=ctk.CTkFont(size=12, weight="bold"),
                                                  text_color="#e94560")
        self.failure_counter_label.pack(side="right", padx=15)

    # ==========================================================
    # CAMERA LOOP
    # ==========================================================
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

                if self.is_recording and self.current_phase == "chant":
                    db = int(min(100, self.live_decibel))
                    cv2.rectangle(frame, (10, 30), (10 + db * 4, 65), (0, 100, 255), -1)
                    cv2.putText(frame, f"{self.live_decibel:.0f} dB", (10, 95),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 2)

                if self.is_recording and self.current_phase == "dance":
                    cv2.putText(frame, f"SPINS: {self.realtime_spins}/{self.required_spins}",
                                (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                    cv2.putText(frame, f"CLAPS: {self.realtime_claps}/{self.required_claps}",
                                (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                    spin_p = min(1.0, self.realtime_spins / max(1, self.required_spins))
                    clap_p = min(1.0, self.realtime_claps / max(1, self.required_claps))
                    cv2.rectangle(frame, (10, 100), (310, 120), (50, 50, 50), -1)
                    cv2.rectangle(frame, (10, 100), (10 + int(300 * spin_p), 120), (0, 255, 255), -1)
                    cv2.rectangle(frame, (10, 130), (310, 150), (50, 50, 50), -1)
                    cv2.rectangle(frame, (10, 130), (10 + int(300 * clap_p), 150), (0, 255, 0), -1)

                if self.is_recording and self.video_writer is not None:
                    self.video_writer.write(frame)

                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                if self.current_phase == "chant":
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(560, 315))
                    self.chant_camera_label.configure(image=ctk_img)
                    self.chant_camera_label.image = ctk_img
                elif self.current_phase == "dance":
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(640, 360))
                    self.dance_camera_label.configure(image=ctk_img)
                    self.dance_camera_label.image = ctk_img

        self.after(30, self.update_camera_loop)

    # ==========================================================
    # AUDIO PLAYBACK
    # ==========================================================
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
                        cmd.insert(1, "-loop"); cmd.insert(2, "0")
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

    # ==========================================================
    # RITUAL FLOW
    # ==========================================================
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
        threading.Thread(target=self.generate_challenge_thread, daemon=True).start()

    def generate_challenge_thread(self):
        try:
            escalation = 2 ** (self.attempt - 1)
            voice_prompt = f"""Generate a random VOICE/CHANTING CHALLENGE for attempt {self.attempt}.
Return ONLY valid JSON:
{{"chantText": string (must include "TUNG TUNG TUNG HASUR" plus random extra words),
"chantBPM": number (135-145),
"requiredVolume": string (whisper/normal/loud/scream),
"hypeLevel": number (1-10)}}"""
            voice_response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": voice_prompt}],
                response_format={"type": "json_object"}, temperature=0.95)
            vc = json.loads(voice_response.choices[0].message.content)

            final_moves = ["dab", "67 move", "woah", "Brazillian Dance", "floss", "griddy"]
            action_prompt = f"""Generate a random MOVEMENT/DANCE CHALLENGE for attempt {self.attempt}.
Escalate difficulty by {escalation}x.
Return ONLY valid JSON:
{{"spins": number (2-8), "claps": number (2-8),
"finalMove": string (one of: "{', '.join(final_moves)}")}}"""
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
            self.after(0, lambda: self.send_btn.configure(state="normal"))

    # ==========================================================
    # PAGE NAVIGATION
    # ==========================================================
    def go_to_chant_page(self):
        self.current_phase = "chant"
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
            text_color="#00aaff")
        self.chant_start_btn.configure(state="normal", text="🎤 START CHANTING")
        self.proceed_to_dance_btn.pack_forget()

    def go_to_dance_page(self):
        self.current_phase = "dance"
        self.stop_background_music()
        self.chant_frame.pack_forget()
        self.dance_frame.pack(fill="both", expand=True)

        self.dance_challenge_label.configure(
            text=f"🔄 {self.required_spins}x SPINS | 👏 {self.required_claps}x CLAPS\n"
                 f"🕺 Finish with: {self.challenge.get('finalMove', 'DAB').upper()}!")
        self.dance_progress_label.configure(
            text=f"🔄 SPINS: 0/{self.required_spins} | 👏 CLAPS: 0/{self.required_claps}")
        self.dance_countdown_label.configure(text="")
        self.dance_instruction_label.configure(
            text="👇 Press START DANCING below — Qwen-Vision only watches after you press it!",
            text_color="#ff66ff")
        self.dance_start_btn.configure(state="normal", text="💃 START DANCING")

    # ==========================================================
    # SESSION 1: CHANTING (Qwen-Audio)
    # ==========================================================
    def start_chant_phase(self):
        self.chant_start_btn.configure(state="disabled", text="🎤 CHANTING...")
        self.chant_instruction_label.configure(text="🎤 CHANT NOW! Speak loudly!", text_color="#00ff00")
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
                text="⏳ Qwen-Audio is analyzing your chant...", text_color="#ffd700")
            threading.Thread(target=self.analyze_chant_thread, args=(chant_wav,), daemon=True).start()
            return
        self.chant_countdown_label.configure(text=f"🎤 {time_left:.1f}s")
        self.after(100, lambda: self.chant_countdown(time_left - 0.1, stream, chant_wav))

    def analyze_chant_thread(self, chant_wav):
        try:
            if not os.path.exists(chant_wav):
                raise Exception("Audio not found.")

            # ---- prepare audio for Qwen-Audio (resample to 16kHz mono) ----
            sr, audio_array = wavfile.read(chant_wav)
            audio_array = np.asarray(audio_array)
            if audio_array.ndim > 1:
                audio_array = audio_array.mean(axis=1)

            # convert to int16
            if audio_array.dtype in (np.float32, np.float64):
                audio_int16 = (np.clip(audio_array, -1.0, 1.0) * 32767).astype(np.int16)
            else:
                audio_int16 = audio_array.astype(np.int16)

            # resample to 16000 Hz (Qwen-Audio's expected rate) — shrinks payload too
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

            # encode the prepared wav as base64
            import io
            buf = io.BytesIO()
            wavfile.write(buf, target_sr, audio_16k)
            audio_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            # real measured loudness from the actual recording
            rms = float(np.sqrt(np.mean((audio_int16.astype(np.float64) / 32768.0) ** 2)))
            measured_db = int(min(100, rms * 3000))

            prompt = (
                "Listen to this audio recording of a person speaking or chanting.\n"
                "1) Transcribe EXACTLY what you hear them say (the actual words).\n"
                f"2) The required chant was: \"{self.required_chant}\"\n"
                f"3) The required volume was: {self.required_volume}\n\n"
                "Return ONLY valid JSON:\n"
                '{"transcription": string (the exact words you heard), '
                '"detected_volume": string (whisper/quiet/normal/loud/scream), '
                '"phrase_correct": boolean (does the transcription match the required chant?), '
                '"volume_sufficient": boolean, '
                '"passed": boolean, "reason": string}'
            )

            # Aliyun Qwen-Audio compatible format (audio_url + data URI)
            messages = [{"role": "user", "content": [
                {"type": "audio_url",
                 "audio_url": {"url": f"data:audio/wav;base64,{audio_b64}"}},
                {"type": "text", "text": prompt}
            ]}]

            response = client.chat.completions.create(
                model=AUDIO_MODEL, messages=messages,
                response_format={"type": "json_object"})
            raw = response.choices[0].message.content

            # robust parse — model may return JSON or plain text
            try:
                result = json.loads(raw)
            except Exception:
                result = {"transcription": raw.strip(),
                          "detected_volume": self.required_volume,
                          "phrase_correct": False, "volume_sufficient": True,
                          "passed": False, "reason": "Raw transcription (non-JSON response)"}

            transcription = (result.get("transcription")
                             or result.get("detected_phrase")
                             or "(nothing detected)")
            result["detected_phrase"] = transcription
            result["loudness_percent"] = measured_db
            result.setdefault("passed", result.get("phrase_correct", False))

            self.audio_analysis_result = result
            self.chant_passed = bool(result.get("passed", False))
            self.audio_text = transcription
            self.after(0, lambda: self.show_chant_result(result))

        except Exception as e:
            print(f"⚠️ Chant error: {e}")
            # fallback uses the REAL measured loudness, not a fake 75
            measured_db = int(getattr(self, "live_decibel", 0))
            fallback = {"passed": True,
                        "reason": "Qwen-Audio unavailable — auto-pass (fallback)",
                        "transcription": "(could not reach Qwen-Audio)",
                        "detected_phrase": "(could not reach Qwen-Audio)",
                        "detected_volume": self.required_volume,
                        "phrase_correct": False, "volume_sufficient": True,
                        "loudness_percent": measured_db}
            self.audio_analysis_result = fallback
            self.chant_passed = True
            self.audio_text = fallback["transcription"]
            self.after(0, lambda: self.show_chant_result(fallback))

    def show_chant_result(self, result):
        self.chant_countdown_label.configure(text="")
        transcription = (result.get("transcription")
                         or result.get("detected_phrase")
                         or "(nothing detected)")
        volume = result.get("detected_volume", "???")
        loudness = result.get("loudness_percent", 0)
        passed = result.get("passed", False)
        icon = "✅" if passed else "❌"

        # The transcription, written back to the chanting challenge page
        self.chant_heard_label.configure(
            text=(f"📝 Qwen-Audio transcribed:\n\"{transcription}\"\n\n"
                  f"🔊 Volume: {str(volume).upper()} ({loudness} dB) {icon}"),
            text_color="#4ade80" if passed else "#e94560",
            wraplength=800, justify="center")
        self.chant_decibel_bar.set(min(1.0, loudness / 100))
        self.chant_db_label.configure(text=f"{loudness} dB")

        if passed:
            self.chant_instruction_label.configure(
                text="✅ VOICE CHALLENGE PASSED! Proceed to the Dance Challenge below.",
                text_color="#00ff88")
            self.chant_start_btn.configure(text="🎤 CHANT ✅")
        else:
            self.chant_instruction_label.configure(
                text=f"❌ VOICE CHALLENGE FAILED: {result.get('reason', 'Unknown')}. Proceed anyway.",
                text_color="#e94560")
            self.chant_start_btn.configure(text="🎤 CHANT ❌")

        # reveal PROCEED button in the pinned action bar
        self.proceed_to_dance_btn.pack(side="left", padx=10, pady=15)

    # ==========================================================
    # SESSION 2: DANCING (Qwen-Vision)
    # ==========================================================
    def start_dance_phase(self):
        self.dance_start_btn.configure(state="disabled", text="💃 DANCING...")
        self.dance_instruction_label.configure(
            text="💃 DANCE NOW! Spin! Clap! Hit the move!", text_color="#00ff00")
        threading.Thread(target=self.run_dance_recording, daemon=True).start()

    def run_dance_recording(self):
        duration = DANCE_DURATION
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        folder = self.get_session_folder()
        video_file = f"{folder}/dance_raw.mp4"
        final_file = f"{folder}/dance_final.mp4"
        audio_file = f"{folder}/dance_audio.wav"
        self.current_video_filename = video_file
        self.current_final_filename = final_file
        self.video_writer = cv2.VideoWriter(video_file, fourcc, 30.0, (800, 500))
        self.is_recording = True

        samplerate = 44100
        self.audio_data = []

        def audio_cb(indata, frames, time_info, status):
            self.audio_data.append(indata.copy())

        stream = sd.InputStream(samplerate=samplerate, channels=1, callback=audio_cb)
        stream.start()
        self.after(0, lambda: self.dance_countdown(duration, stream, video_file, audio_file, final_file))

    def dance_countdown(self, time_left, stream, video_file, audio_file, final_file):
        if time_left <= 0:
            self.is_recording = False
            stream.stop()
            stream.close()
            if self.video_writer:
                self.video_writer.release()
            if self.audio_data:
                audio_array = np.concatenate(self.audio_data, axis=0)
                wavfile.write(audio_file, 44100, audio_array)
            self.dance_countdown_label.configure(text="🔍")
            self.dance_instruction_label.configure(
                text="⏳ Qwen-Vision is counting your moves...", text_color="#ffd700")
            threading.Thread(target=self.analyze_dance_thread,
                             args=(video_file, audio_file, final_file), daemon=True).start()
            return
        self.dance_countdown_label.configure(text=f"💃 {time_left:.1f}s")
        self.after(100, lambda: self.dance_countdown(time_left - 0.1, stream,
                                                     video_file, audio_file, final_file))

    def get_frames_from_video(self, video_path, num_frames=8):
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        if total_frames == 0:
            cap.release()
            return frames
        num_frames = min(num_frames, total_frames)
        intervals = [int(i * total_frames / num_frames) for i in range(num_frames)]
        for idx in intervals:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, (512, 512))
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                frames.append(base64.b64encode(buffer).decode('utf-8'))
        cap.release()
        return frames

    def merge_audio_video(self, video_file, audio_file, output_file):
        try:
            subprocess.run(["ffmpeg", "-y", "-i", video_file, "-i", audio_file,
                            "-c:v", "libx264", "-c:a", "aac", "-strict", "experimental",
                            "-shortest", output_file],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def analyze_dance_thread(self, video_file, audio_file, final_file):
        try:
            self.merge_audio_video(video_file, audio_file, final_file)
            file_to_analyze = final_file if os.path.exists(final_file) else video_file
            frames_b64 = self.get_frames_from_video(file_to_analyze, num_frames=8)
            if not frames_b64:
                raise Exception("No frames.")
            prompt = (
                f"Analyze these video frames. Required: {self.required_spins} spins, "
                f"{self.required_claps} claps, finish with '{self.challenge.get('finalMove', 'dab')}'.\n"
                f"Count spins and claps. Be STRICT.\n\n"
                f"Return ONLY JSON:\n"
                f'{{"passed": boolean, "reason": string, "detected_spins": number, '
                f'"detected_claps": number, "detected_final_move": string, '
                f'"final_move_correct": boolean}}')
            messages = [{"role": "user", "content":
                         [{"type": "text", "text": prompt}] +
                         [{"type": "image_url",
                           "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                          for img in frames_b64]}]
            response = client.chat.completions.create(
                model=VISION_MODEL, messages=messages,
                response_format={"type": "json_object"}, temperature=0.3)
            result = json.loads(response.choices[0].message.content)
            self.vision_analysis_result = result
            self.dance_passed = result.get("passed", False)
            self.realtime_spins = result.get("detected_spins", 0)
            self.realtime_claps = result.get("detected_claps", 0)
            self.after(0, lambda: self.show_dance_result(result))
        except Exception as e:
            print(f"⚠️ Dance error: {e}")
            fallback = {"passed": False, "reason": f"Vision error: {e}",
                        "detected_spins": 0, "detected_claps": 0,
                        "detected_final_move": "none", "final_move_correct": False}
            self.vision_analysis_result = fallback
            self.dance_passed = False
            self.after(0, lambda: self.show_dance_result(fallback))

    def show_dance_result(self, result):
        self.dance_countdown_label.configure(text="")
        det_s = result.get("detected_spins", 0)
        det_c = result.get("detected_claps", 0)
        det_move = result.get("detected_final_move", "?")
        passed = result.get("passed", False)
        s_icon = "✅" if det_s >= self.required_spins else "❌"
        c_icon = "✅" if det_c >= self.required_claps else "❌"
        m_icon = "✅" if result.get("final_move_correct", False) else "❌"
        self.dance_progress_label.configure(
            text=f"🔄 SPINS: {det_s}/{self.required_spins} {s_icon} | "
                 f"👏 CLAPS: {det_c}/{self.required_claps} {c_icon} | "
                 f"🕺 {det_move} {m_icon}")
        if passed:
            self.dance_instruction_label.configure(
                text="✅ DANCE CHALLENGE PASSED! Evaluating...", text_color="#00ff88")
            self.dance_start_btn.configure(text="💃 DANCE ✅")
        else:
            self.dance_instruction_label.configure(
                text=f"❌ DANCE CHALLENGE FAILED: {result.get('reason', 'Unknown')}",
                text_color="#e94560")
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
            reason=reason[:34], audio_score=audio_score,
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
            self.failure_overlay.configure(fg_color="#e94560")
            return
        self.failure_overlay.configure(fg_color="#e94560" if count % 2 == 0 else "#000000")
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

    def show_answer(self):
        self.chant_frame.pack_forget()
        self.dance_frame.pack_forget()
        self.failure_overlay.pack_forget()
        self.answer_frame.pack(fill="both", expand=True)
        self.stop_background_music()
        threading.Thread(target=self.get_wrong_answer_thread, daemon=True).start()

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
        self.current_phase = None
        self.answer_frame.pack_forget()
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