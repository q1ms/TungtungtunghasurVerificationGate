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
import tempfile
from openai import OpenAI

# ==========================================
# >>> INSERT YOUR API KEY HERE <<<
# ==========================================
API_KEY = "sk-ws-H.XLLHHD.GQU5.MEQCIGlOQ1CMu9XEN5jFyF2Eyz8V7x7TwZT5PEylyDN99-K0AiB2INQsbiAmPVwxuFH6JCsukduWf9YiWcHxnO-BU4hc1w"
API_BASE_URL = "https://ws-qzavoknndotjynro.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
# ==========================================

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

# ==========================================
# CONFIGURATION
# ==========================================
MAX_ATTEMPTS = 5
BASE_DURATION = 5.0
BACKGROUND_MUSIC = "assets/background.mp3"

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
        print("🟢 Starting Hasur Gate App...", flush=True)
        super().__init__()
        
        self.title("🔮 Tung Tung Tung Hasur Verification Gate 🔮")
        self.geometry("1400x900")
        self.attributes('-fullscreen', True)
        self.bind("<Escape>", lambda e: self.on_escape())
        
        # State variables
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
        
        # File paths
        self.current_video_filename = ""
        self.current_audio_filename = ""
        self.current_final_filename = ""
        self.current_audio_process = None
        self.background_music_process = None
        
        # Real-time counters (without MediaPipe)
        self.realtime_spins = 0
        self.realtime_claps = 0
        self.est_bpm = 0
        
        # Build UI
        self.setup_ui()
        self.update_camera_loop()
        self.play_background_music(1.0)
        print("🟢 App initialized successfully!", flush=True)
    
    # ==========================================
    # WINDOW LIFECYCLE (FIXED AUDIO STOP)
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
        # Clean up temp background music files
        for f in os.listdir("."):
            if f.startswith("temp_bg_") and f.endswith(".mp3"):
                try:
                    os.remove(f)
                except:
                    pass
        super().destroy()
    
    # ==========================================
    # AUDIO STOP FUNCTIONS (FORCEFUL KILL)
    # ==========================================
    def stop_background_music(self):
        if self.background_music_process is not None:
            pid = self.background_music_process.pid
            try:
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, check=False
                    )
                else:
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                        time.sleep(0.2)
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    except (ProcessLookupError, OSError):
                        os.kill(pid, signal.SIGKILL)
            except Exception:
                try:
                    self.background_music_process.terminate()
                except:
                    pass
            self.background_music_process = None
            print("🔇 Background music stopped.")
    
    def stop_audio(self):
        if self.current_audio_process is not None:
            pid = self.current_audio_process.pid
            try:
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, check=False
                    )
                else:
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                        time.sleep(0.2)
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    except (ProcessLookupError, OSError):
                        os.kill(pid, signal.SIGKILL)
            except Exception:
                try:
                    self.current_audio_process.terminate()
                except:
                    pass
            self.current_audio_process = None
            print("🔇 Audio stopped.")
    
    # ==========================================
    # UI SETUP
    # ==========================================
    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.header = ctk.CTkLabel(
            self.main_frame, 
            text="🔮 TUNG TUNG TUNG HASUR VERIFICATION GATE 🔮",
            font=ctk.CTkFont(size=42, weight="bold"),
            text_color="#e94560"
        )
        self.header.pack(pady=15)
        
        self.subtitle = ctk.CTkLabel(
            self.main_frame,
            text="The AI that makes you dance like a fool before giving you the wrong answer.",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffd700"
        )
        self.subtitle.pack(pady=(0, 20))
        
        # Failure Counter
        self.failure_counter_frame = ctk.CTkFrame(self.main_frame, fg_color="#1a1a2e", corner_radius=15)
        self.failure_counter_frame.pack(anchor="ne", pady=5, padx=5)
        self.failure_counter_label = ctk.CTkLabel(
            self.failure_counter_frame,
            text="❌ FAILURES: 0",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#e94560"
        )
        self.failure_counter_label.pack(padx=15, pady=8)
        
        # Question Frame
        self.question_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="#1a1a2e",
            border_width=2,
            border_color="#e94560",
            corner_radius=20
        )
        self.question_frame.pack(pady=40, padx=150, fill="x")
        
        ctk.CTkLabel(
            self.question_frame,
            text="Ask a Question, Prepare for the Ritual",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#ffffff"
        ).pack(pady=(20, 10))
        
        self.question_entry = ctk.CTkEntry(
            self.question_frame,
            placeholder_text="Ask anything... but you'll regret it...",
            width=600,
            height=50,
            font=ctk.CTkFont(size=20)
        )
        self.question_entry.pack(pady=15)
        self.question_entry.bind("<Return>", lambda e: self.start_ritual())
        
        self.start_btn = ctk.CTkButton(
            self.question_frame,
            text="🔥 BEGIN RITUAL 🔥",
            command=self.start_ritual,
            height=60,
            width=350,
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color="#e94560",
            hover_color="#c73e54"
        )
        self.start_btn.pack(pady=20)
        
        self.attempt_label = ctk.CTkLabel(
            self.question_frame,
            text=f"⚔️ Attempt {self.attempt} of {MAX_ATTEMPTS} ⚔️",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#ffd700"
        )
        self.attempt_label.pack(pady=10)
        
        # Ritual Frame
        self.ritual_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.ritual_frame.pack_forget()
        
        self.challenge_label = ctk.CTkLabel(
            self.ritual_frame,
            text="",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#ffd700",
            wraplength=1000
        )
        self.challenge_label.pack(pady=15)
        
        self.camera_label = ctk.CTkLabel(
            self.ritual_frame,
            text="",
            width=640,
            height=480,
            fg_color="black",
            corner_radius=10
        )
        self.camera_label.pack(pady=15)
        
        self.countdown_label = ctk.CTkLabel(
            self.ritual_frame,
            text="⏳ 0.0s",
            font=ctk.CTkFont(size=80, weight="bold"),
            text_color="#e94560"
        )
        self.countdown_label.pack(pady=15)
        
        self.instruction_label = ctk.CTkLabel(
            self.ritual_frame,
            text="",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00ff00"
        )
        self.instruction_label.pack(pady=10)
        
        # Real-time Feedback Label (without MediaPipe)
        self.realtime_feedback_label = ctk.CTkLabel(
            self.ritual_frame,
            text="🔄 SPINS: 0 | 👏 CLAPS: 0 | 🎤 BPM: --",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#00ffff"
        )
        self.realtime_feedback_label.pack(pady=10)
        
        # Failure Overlay
        self.failure_overlay = ctk.CTkFrame(self, fg_color="#e94560", corner_radius=0)
        self.failure_overlay.pack_forget()
        
        self.failure_content_frame = ctk.CTkFrame(self.failure_overlay, fg_color="transparent")
        self.failure_content_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        self.failure_title = ctk.CTkLabel(
            self.failure_content_frame,
            text="💀 RITUAL FAILED 💀",
            font=ctk.CTkFont(size=60, weight="bold"),
            text_color="white"
        )
        self.failure_title.pack(pady=(0, 20))
        
        self.failure_reason_label = ctk.CTkLabel(
            self.failure_content_frame,
            text="",
            font=ctk.CTkFont(size=28),
            text_color="white",
            wraplength=1000,
            justify="center"
        )
        self.failure_reason_label.pack()
        
        self.brainrot_label = ctk.CTkLabel(
            self.failure_content_frame,
            text="",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="#ffd700"
        )
        self.brainrot_label.pack(pady=20)
        
        # Thermal Receipt
        self.receipt_frame = ctk.CTkFrame(
            self.failure_overlay,
            fg_color="#f5f5dc",
            border_width=3,
            border_color="#333",
            corner_radius=5
        )
        self.receipt_frame.place(relx=0.85, rely=0.5, anchor="center")
        self.receipt_label = ctk.CTkLabel(
            self.receipt_frame,
            text="",
            font=ctk.CTkFont(family="Courier", size=12),
            text_color="#333",
            justify="left"
        )
        self.receipt_label.pack(padx=15, pady=10)
        
        # Answer Frame
        self.answer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.answer_frame.pack_forget()
        
        self.char_image_label = ctk.CTkLabel(
            self.answer_frame,
            text="",
            width=250,
            height=250
        )
        self.char_image_label.pack(side="left", padx=50)
        
        self.dialogue_box = ctk.CTkFrame(
            self.answer_frame,
            fg_color="white",
            corner_radius=15,
            border_width=3,
            border_color="#e94560"
        )
        self.dialogue_box.pack(side="left", fill="both", expand=True, padx=50, pady=50)
        
        self.char_name_label = ctk.CTkLabel(
            self.dialogue_box,
            text="",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#e94560"
        )
        self.char_name_label.pack(pady=(20, 10))
        
        self.answer_text_label = ctk.CTkLabel(
            self.dialogue_box,
            text="",
            font=ctk.CTkFont(size=22),
            text_color="black",
            wraplength=700,
            justify="left"
        )
        self.answer_text_label.pack(pady=20, padx=20)
        
        self.restart_btn = ctk.CTkButton(
            self.answer_frame,
            text="🔄 SUFFER AGAIN 🔄",
            command=self.restart_app,
            fg_color="#333",
            hover_color="#555",
            height=50,
            width=200,
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.restart_btn.pack(pady=30)
    
    # ==========================================
    # CAMERA LOOP (WITH SIMPLE COUNTERS)
    # ==========================================
    def update_camera_loop(self):
        if self.cap is None:
            try:
                self.cap = cv2.VideoCapture(0)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                if not self.cap.isOpened():
                    print("⚠️ Camera not available")
            except Exception as e:
                print(f"⚠️ Camera error: {e}")
                self.cap = None
        
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                
                # Simple overlay counters (no MediaPipe)
                if self.is_recording:
                    # Simulate spin/clap detection with simple motion
                    # This is just a visual effect - actual detection happens in Qwen-VL later
                    cv2.putText(frame, f"SPINS: {self.realtime_spins}  CLAPS: {self.realtime_claps}", 
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    cv2.putText(frame, f"BPM TARGET: 135", 
                                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                
                # Write to video file if recording
                if self.is_recording and self.video_writer is not None:
                    self.video_writer.write(frame)
                
                # Convert and display
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(640, 480))
                self.camera_label.configure(image=ctk_img)
                self.camera_label.image = ctk_img
        
        self.after(30, self.update_camera_loop)
    
    # ==========================================
    # AUDIO PLAYBACK (USES FIXED STOP)
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
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                else:
                    self.current_audio_process = subprocess.Popen(
                        ["afplay", file_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
            elif system == "Windows":
                try:
                    cmd = ["ffplay", "-nodisp", "-autoexit", file_path]
                    if loop:
                        cmd.insert(1, "-loop")
                        cmd.insert(2, "0")
                    self.current_audio_process = subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except FileNotFoundError:
                    escaped_path = file_path.replace('\\', '\\\\')
                    if loop:
                        ps_script = (
                            "Add-Type -AssemblyName presentationCore; "
                            "$player = New-Object system.windows.media.mediaplayer; "
                            "$player.MediaEnded += { $player.Position = [timespan]::Zero; $player.Play() }; "
                            "$player.open('" + escaped_path + "'); $player.Play()"
                        )
                    else:
                        ps_script = (
                            "Add-Type -AssemblyName presentationCore; "
                            "$player = New-Object system.windows.media.mediaplayer; "
                            "$player.open('" + escaped_path + "'); $player.Play()"
                        )
                    self.current_audio_process = subprocess.Popen(
                        ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script]
                    )
            else:
                if loop:
                    self.current_audio_process = subprocess.Popen(
                        ["ffplay", "-loop", "0", "-nodisp", "-autoexit", file_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                else:
                    self.current_audio_process = subprocess.Popen(
                        ["aplay", file_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
        except Exception as e:
            print(f"⚠️ Audio play error: {e}")
    
    def play_background_music(self, volume=1.0):
        self.stop_background_music()
        if not os.path.exists(BACKGROUND_MUSIC):
            return
        temp_file = f"temp_bg_{int(volume*100)}.mp3"
        if not os.path.exists(temp_file):
            try:
                cmd = ["ffmpeg", "-y", "-i", BACKGROUND_MUSIC, "-filter:a", f"volume={volume}", temp_file]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                return
        system = platform.system()
        try:
            if system == "Darwin":
                self.background_music_process = subprocess.Popen(
                    ["bash", "-c", f"while true; do afplay '{temp_file}'; done"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            elif system == "Windows":
                try:
                    self.background_music_process = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loop", "0", temp_file],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except FileNotFoundError:
                    escaped_path = temp_file.replace('\\', '\\\\')
                    ps_script = (
                        "Add-Type -AssemblyName presentationCore; "
                        "$player = New-Object system.windows.media.mediaplayer; "
                        "$player.MediaEnded += { $player.Position = [timespan]::Zero; $player.Play() }; "
                        "$player.open('" + escaped_path + "'); $player.Play()"
                    )
                    self.background_music_process = subprocess.Popen(
                        ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script]
                    )
            else:
                self.background_music_process = subprocess.Popen(
                    ["ffplay", "-loop", "0", "-nodisp", "-autoexit", temp_file],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
        except Exception:
            pass
    
    # ==========================================
    # RITUAL FLOW
    # ==========================================
    def start_ritual(self):
        self.question = self.question_entry.get()
        if not self.question:
            self.question_entry.configure(placeholder_text="⚠️ ASK SOMETHING, BRO ⚠️")
            return
        self.start_btn.configure(state="disabled", text="🔄 SUMMONING HASUR GUARDIAN...")
        threading.Thread(target=self.generate_challenge_thread, daemon=True).start()
    
    def generate_challenge_thread(self):
        try:
            escalation = 2 ** ((self.attempt - 1) // 1)
            final_moves = ["dab", "67 move", "woah", "Brazillian Dance", "floss", "orange justice"]
            prompt = f"""
            Generate a ritual challenge for attempt {self.attempt}.
            Escalate difficulty by {escalation}x.
            The user must do physical actions.
            Return ONLY valid JSON:
            {{
                "spins": number (2-8),
                "claps": number (2-8),
                "chantBPM": number (135-145),
                "chantText": string (must include "TUNG TUNG TUNG HASUR"),
                "finalMove": string ("{random.choice(final_moves)}")
            }}
            """
            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.9
            )
            self.challenge = json.loads(response.choices[0].message.content)
            self.challenge["spins"] = self.challenge.get("spins", 2) * escalation
            self.challenge["claps"] = self.challenge.get("claps", 2) * escalation
            self.after(0, self.show_ritual_screen)
        except Exception as e:
            print(f"⚠️ Challenge API error: {e}")
            self.after(0, lambda: self.start_btn.configure(state="normal", text="🔄 RETRY"))
    
    def show_ritual_screen(self):
        self.question_frame.pack_forget()
        self.ritual_frame.pack(fill="both", expand=True)
        escalation = 2 ** ((self.attempt - 1) // 1)
        warning = "🔥" * min(self.attempt, 5)
        text = (
            f"⚔️ HASUR DECREE ⚔️\n"
            f"{warning} ATTEMPT {self.attempt} {warning}\n"
            f"{self.challenge.get('spins', 2)}x SPINS | "
            f"{self.challenge.get('claps', 2)}x CLAPS | "
            f"{self.challenge.get('chantBPM', 140)} BPM\n"
            f"CHANT: '{self.challenge.get('chantText', 'TUNG TUNG TUNG HASUR')}'\n"
            f"FINISH WITH: {self.challenge.get('finalMove', 'DAB').upper()}!"
        )
        self.challenge_label.configure(text=text)
        self.play_background_music(0.7)
        self.after(1000, self.start_recording)
    
    def start_recording(self):
        # Reset counters
        self.realtime_spins = 0
        self.realtime_claps = 0
        self.est_bpm = 0
        self.realtime_feedback_label.configure(
            text="🔄 SPINS: 0 | 👏 CLAPS: 0 | 🎤 BPM: --"
        )
        
        self.is_recording = True
        duration = BASE_DURATION * (self.attempt ** 0.5)
        duration = min(duration, 15.0)
        self.instruction_label.configure(text="🎤 CHANT NOW! SPIN! CLAP! DAB! 🎤")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        today = datetime.datetime.now()
        day_name = today.strftime("%A")
        date_str = today.strftime("%Y-%m-%d")
        session_folder = f"recordings/{date_str}_{day_name}/attempt{self.attempt}"
        os.makedirs(session_folder, exist_ok=True)
        self.current_video_filename = f"{session_folder}/raw.mp4"
        self.current_audio_filename = f"{session_folder}/audio.wav"
        self.current_final_filename = f"{session_folder}/final.mp4"
        self.video_writer = cv2.VideoWriter(self.current_video_filename, fourcc, 30.0, (640, 480))
        samplerate = 44100
        self.audio_data = []
        def audio_callback(indata, frames, time, status):
            self.audio_data.append(indata.copy())
        stream = sd.InputStream(samplerate=samplerate, channels=1, callback=audio_callback)
        stream.start()
        self.countdown = duration
        self.update_countdown(duration, stream)
    
    def update_countdown(self, time_left, stream):
        if time_left <= 0:
            self.is_recording = False
            stream.stop()
            stream.close()
            if self.video_writer:
                self.video_writer.release()
            audio_array = np.concatenate(self.audio_data, axis=0)
            wavfile.write(self.current_audio_filename, 44100, audio_array)
            self.instruction_label.configure(text="⏳ ANALYZING YOUR FAILURE...")
            self.countdown_label.configure(text="🔍")
            threading.Thread(target=self.run_analysis_thread, daemon=True).start()
            return
        self.countdown_label.configure(text=f"⏳ {time_left:.1f}s")
        self.after(100, lambda: self.update_countdown(time_left - 0.1, stream))
    
    def merge_audio_video(self, video_file, audio_file, output_file):
        try:
            cmd = [
                "ffmpeg", "-y", "-i", video_file, "-i", audio_file,
                "-c:v", "libx264", "-c:a", "aac",
                "-strict", "experimental", "-shortest", output_file
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
    
    def analyze_chant_audio(self, audio_path):
        try:
            with open(audio_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode("utf-8")
            prompt = """
            Analyze this audio recording of a user chanting.
            Determine:
            1. Did they say 'Tung Tung Tung Hasur' clearly? (yes/no)
            2. What is the BPM (beats per minute) of their chant? (should be 135-145)
            3. Rate their 'hype level' from 1-10.
            4. Did they pronounce 'Hasur' correctly? (yes/no)
            Return ONLY valid JSON:
            {"correct_phrase": bool, "bpm": int, "hype": int, "pronunciation": bool, "passed": bool}
            Pass condition: correct_phrase=True AND 135 <= bpm <= 145 AND pronunciation=True
            """
            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "audio_url", "audio_url": {"url": f"data:audio/wav;base64,{audio_base64}"}}
                    ]
                }]
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f"⚠️ Audio analysis error: {e}")
            return {"correct_phrase": False, "bpm": 0, "hype": 0, "pronunciation": False, "passed": False}
    
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
    
    def analyze_vision_frames(self, frames_b64):
        if not frames_b64:
            return {"passed": False, "reason": "No frames extracted", "detected_spins": 0, "detected_claps": 0}
        try:
            prompt = f"""
            Analyze these sequential frames from a video recording.
            The user was challenged to perform:
            - {self.challenge.get('spins', 2)} spins
            - {self.challenge.get('claps', 2)} claps
            - Finish with the move: '{self.challenge.get('finalMove', 'dab')}'
            Evaluate if the person attempted and completed these actions.
            Be STRICT. If they didn't complete all actions, they FAIL.
            Return ONLY valid JSON:
            {{
                "passed": boolean,
                "reason": string,
                "detected_spins": number,
                "detected_claps": number,
                "detected_final_move": string,
                "spin_accuracy": "perfect" | "partial" | "none",
                "clap_accuracy": "perfect" | "partial" | "none"
            }}
            """
            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ] + [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                    for img in frames_b64
                ]}
            ]
            response = client.chat.completions.create(
                model="qwen-vl-max",
                messages=messages,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"⚠️ Vision analysis error: {e}")
            return {"passed": False, "reason": f"Vision error: {str(e)}"}
    
    def run_analysis_thread(self):
        try:
            merged_success = self.merge_audio_video(
                self.current_video_filename,
                self.current_audio_filename,
                self.current_final_filename
            )
            file_to_analyze = (
                self.current_final_filename
                if (merged_success and os.path.exists(self.current_final_filename))
                else self.current_video_filename
            )
            audio_result = self.analyze_chant_audio(self.current_audio_filename)
            self.audio_analysis_result = audio_result
            frames_b64 = self.get_frames_from_video(file_to_analyze, num_frames=8)
            vision_result = self.analyze_vision_frames(frames_b64)
            self.vision_analysis_result = vision_result
            
            audio_passed = audio_result.get("passed", False)
            vision_passed = vision_result.get("passed", False)
            audio_score = min(100, max(0, audio_result.get("hype", 0) * 10 + 30))
            vision_score = 100 if vision_passed else 0
            if vision_result.get("detected_spins", 0) > 0:
                spin_ratio = min(1.0, vision_result.get("detected_spins", 0) / self.challenge.get("spins", 2))
                vision_score = int(spin_ratio * 100)
            
            if audio_passed and vision_passed:
                passed = True
                reason = "✅ Ritual complete! The Hasur is pleased."
                status = "PASSED"
                self.ritual_passed = True
            else:
                passed = False
                reasons = []
                if not audio_passed:
                    if not audio_result.get("correct_phrase", False):
                        reasons.append("❌ Didn't chant 'Tung Tung Tung Hasur'")
                    elif audio_result.get("bpm", 0) < 135 or audio_result.get("bpm", 0) > 145:
                        reasons.append(f"❌ BPM {audio_result.get('bpm', 0)} (need 135-145)")
                    elif not audio_result.get("pronunciation", False):
                        reasons.append("❌ Bad pronunciation of 'Hasur'")
                    else:
                        reasons.append("❌ Audio verification failed")
                if not vision_passed:
                    if vision_result.get("detected_spins", 0) < self.challenge.get("spins", 2):
                        reasons.append(f"❌ Only {vision_result.get('detected_spins', 0)}/{self.challenge.get('spins', 2)} spins")
                    if vision_result.get("detected_claps", 0) < self.challenge.get("claps", 2):
                        reasons.append(f"❌ Only {vision_result.get('detected_claps', 0)}/{self.challenge.get('claps', 2)} claps")
                    if vision_result.get("detected_final_move", "") != self.challenge.get("finalMove", "dab"):
                        reasons.append(f"❌ Wrong final move (need {self.challenge.get('finalMove', 'dab')})")
                    if not reasons:
                        reasons.append("❌ Vision verification failed")
                reason = " | ".join(reasons)
                status = "FAILED"
                self.ritual_passed = False
            
            if not passed:
                self.failure_count += 1
                self.failure_counter_label.configure(text=f"❌ FAILURES: {self.failure_count}")
            
            self.print_thermal_receipt(self.attempt, reason, audio_score, vision_score, status)
            self.after(0, lambda: self.handle_result(passed, reason))
        except Exception as e:
            print(f"⚠️ Analysis pipeline error: {e}")
            self.after(0, lambda: self.handle_result(False, f"💀 Analysis failed: {str(e)}"))
    
    def print_thermal_receipt(self, attempt, reason, audio_score, vision_score, status):
        brainrot = random.choice(BRAINROT_FAILURES)
        receipt_num = len(self.failure_receipts) + 1
        receipt = RECEIPT_TEMPLATE.format(
            receipt_num=receipt_num,
            attempt=attempt,
            max_attempts=MAX_ATTEMPTS,
            reason=reason[:40],
            audio_score=audio_score,
            vision_score=vision_score,
            status=status,
            brainrot=brainrot
        )
        self.failure_receipts.append(receipt)
        self.receipt_label.configure(text=receipt)
        self.receipt_frame.place(relx=0.85, rely=0.5, anchor="center")
        self.after(6000, lambda: self.receipt_frame.place_forget())
    
    def handle_result(self, passed, reason):
        if passed:
            self.show_answer()
        else:
            self.show_failure(reason)
    
    def show_failure(self, reason):
        self.stop_background_music()
        self.ritual_frame.pack_forget()
        self.failure_overlay.pack(fill="both", expand=True)
        self.failure_reason_label.configure(text=reason)
        brainrot = random.choice(BRAINROT_FAILURES)
        self.brainrot_label.configure(text=f"💀 {brainrot} 💀")
        self.play_audio(FAILURE_AUDIO)
        self.flash_overlay(16)
        self.after(6000, self.advance_attempt)
    
    def flash_overlay(self, count):
        if count <= 0:
            self.failure_overlay.configure(fg_color="#e94560")
            return
        color = "#e94560" if count % 2 == 0 else "#000000"
        self.failure_overlay.configure(fg_color=color)
        self.after(300, lambda: self.flash_overlay(count - 1))
    
    def advance_attempt(self):
        self.failure_overlay.pack_forget()
        if self.attempt >= MAX_ATTEMPTS:
            self.show_answer()
        else:
            self.attempt += 1
            self.attempt_label.configure(text=f"⚔️ Attempt {self.attempt} of {MAX_ATTEMPTS} ⚔️")
            self.ritual_frame.pack_forget()
            self.question_frame.pack(pady=40, padx=150, fill="x")
            self.start_btn.configure(state="normal", text="🔥 BEGIN RITUAL 🔥")
            self.play_background_music(1.0)
    
    def show_answer(self):
        self.ritual_frame.pack_forget()
        self.failure_overlay.pack_forget()
        self.answer_frame.pack(fill="both", expand=True)
        self.play_background_music(0.3)
        threading.Thread(target=self.get_wrong_answer_thread, daemon=True).start()
    
    def get_wrong_answer_thread(self):
        try:
            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[{
                    "role": "user",
                    "content": (
                        f"User asked: '{self.question}'. "
                        f"Give a completely wrong, absurd, brainrot answer in under 30 words. "
                        f"Be funny and chaotic."
                    )
                }],
                temperature=1.2
            )
            answer = response.choices[0].message.content
            self.after(0, lambda: self.display_answer(answer))
        except Exception as e:
            print(f"⚠️ Answer API error: {e}")
            self.after(0, lambda: self.display_answer(
                "🫠 The answer is 42, but only on Tuesdays during a full moon in Ohio."
            ))
    
    def display_answer(self, answer):
        char = random.choice(CHARACTERS)
        if os.path.exists(char["img"]):
            img = Image.open(char["img"]).resize((250, 250))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(250, 250))
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
        self.audio_analysis_result = None
        self.vision_analysis_result = None
        self.answer_frame.pack_forget()
        self.failure_overlay.pack_forget()
        self.ritual_frame.pack_forget()
        self.question_frame.pack(pady=40, padx=150, fill="x")
        self.start_btn.configure(state="normal", text="🔥 BEGIN RITUAL 🔥")
        self.attempt_label.configure(text=f"⚔️ Attempt {self.attempt} of {MAX_ATTEMPTS} ⚔️")
        self.failure_counter_label.configure(text="❌ FAILURES: 0")
        self.question_entry.delete(0, 'end')
        self.receipt_label.configure(text="")
        self.receipt_frame.place_forget()
        self.play_background_music(1.0)


if __name__ == "__main__":
    print("="*60)
    print("🔮 TUNG TUNG TUNG HASUR VERIFICATION GATE 🔮")
    print("="*60)
    print("Starting application...")
    try:
        app = HasurGateApp()
        app.mainloop()
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()