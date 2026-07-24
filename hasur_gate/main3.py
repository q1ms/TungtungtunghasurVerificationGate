import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
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

from openai import OpenAI

# ==========================================
# >>> INSERT YOUR API KEY HERE <<<
# ==========================================
API_KEY = "sk-ws-H.XLLHHD.GQU5.MEQCIGlOQ1CMu9XEN5jFyF2Eyz8V7x7TwZT5PEylyDN99-K0AiB2INQsbiAmPVwxuFH6JCsukduWf9YiWcHxnO-BU4hc1w"
API_BASE_URL = "https://ws-qzavoknndotjynro.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1" 
# ==========================================

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

MAX_ATTEMPTS = 3
BASE_DURATION = 6.7

CHARACTERS = [
    {"name": "Goblin of Confusion", "img": "assets/char1.png", "audio": "assets/char1.mp3"},
    {"name": "Specter of Nonsense", "img": "assets/char2.png", "audio": "assets/char2.mp3"},
    {"name": "Void Walker", "img": "assets/char3.png", "audio": "assets/char3.mp3"},
    {"name": "Brainrot Entity", "img": "assets/char4.png", "audio": "assets/char4.mp3"},
    {"name": "Hasur's Jester", "img": "assets/char5.png", "audio": "assets/char5.mp3"},
]
FAILURE_AUDIO = "assets/failure.mp3"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HasurGateApp(ctk.CTk):
    def __init__(self):
        print("🟢 1. Starting __init__", flush=True)
        super().__init__()
        print("🟢 2. super().__init__() done", flush=True)
        
        self.title("Tung Tung Tung Hasur Verification Gate")
        self.geometry("1200x800")
        self.attributes('-fullscreen', True)
        self.bind("<Escape>", lambda e: self.destroy())
        print("🟢 3. Window setup done", flush=True)
        
        self.attempt = 1
        self.question = ""
        self.challenge = {}
        self.is_recording = False
        self.cap = None
        self.video_writer = None
        self.audio_data = []
        
        self.current_video_filename = ""
        self.current_audio_filename = ""
        self.current_final_filename = ""
        
        # 🔧 NEW: Track the active audio process so we can stop it
        self.current_audio_process = None
        
        self.setup_ui()
        print("🟢 4. setup_ui() done", flush=True)
        
        self.update_camera_loop()
        print("🟢 5. update_camera_loop() started. Entering mainloop...", flush=True)

    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.header = ctk.CTkLabel(self.main_frame, text="🔮 TUNG TUNG TUNG HASUR 🔮", 
                                   font=ctk.CTkFont(size=40, weight="bold"), text_color="#e94560")
        self.header.pack(pady=20)
        
        self.question_frame = ctk.CTkFrame(self.main_frame, fg_color="#1a1a2e", border_width=2, border_color="#e94560", corner_radius=20)
        self.question_frame.pack(pady=50, padx=100, fill="x")
        
        ctk.CTkLabel(self.question_frame, text="Ask a Question, Prepare for the Ritual", font=ctk.CTkFont(size=24)).pack(pady=20)
        
        self.question_entry = ctk.CTkEntry(self.question_frame, placeholder_text="Is this the right choice?", 
                                           width=600, height=50, font=ctk.CTkFont(size=20))
        self.question_entry.pack(pady=20)
        
        self.start_btn = ctk.CTkButton(self.question_frame, text="BEGIN RITUAL", 
                                       command=self.start_ritual, height=60, width=300, 
                                       font=ctk.CTkFont(size=20, weight="bold"), fg_color="#e94560", hover_color="#c73e54")
        self.start_btn.pack(pady=20)
        
        self.attempt_label = ctk.CTkLabel(self.question_frame, text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}", font=ctk.CTkFont(size=18), text_color="#888")
        self.attempt_label.pack(pady=10)
        
        self.ritual_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.ritual_frame.pack_forget()
        
        self.challenge_label = ctk.CTkLabel(self.ritual_frame, text="", font=ctk.CTkFont(size=28, weight="bold"), text_color="#ffd700", wraplength=1000)
        self.challenge_label.pack(pady=20)
        
        self.camera_label = ctk.CTkLabel(self.ritual_frame, text="", width=640, height=480, fg_color="black", corner_radius=10)
        self.camera_label.pack(pady=20)
        
        self.countdown_label = ctk.CTkLabel(self.ritual_frame, text="0.0s", font=ctk.CTkFont(size=80, weight="bold"), text_color="#e94560")
        self.countdown_label.pack(pady=20)
        
        self.failure_overlay = ctk.CTkFrame(self, fg_color="#e94560", corner_radius=0)
        self.failure_overlay.pack_forget()
        self.failure_label = ctk.CTkLabel(self.failure_overlay, text="RITUAL FAILED", font=ctk.CTkFont(size=60, weight="bold"), text_color="white")
        self.failure_label.place(relx=0.5, rely=0.4, anchor="center")
        self.failure_reason_label = ctk.CTkLabel(self.failure_overlay, text="", font=ctk.CTkFont(size=24), text_color="white")
        self.failure_reason_label.place(relx=0.5, rely=0.55, anchor="center")
        
        self.answer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.answer_frame.pack_forget()
        
        self.char_image_label = ctk.CTkLabel(self.answer_frame, text="", width=300, height=500)
        self.char_image_label.pack(side="left", padx=50)
        
        self.dialogue_box = ctk.CTkFrame(self.answer_frame, fg_color="white", corner_radius=15, border_width=3, border_color="#e94560")
        self.dialogue_box.pack(side="left", fill="both", expand=True, padx=50, pady=50)
        
        self.char_name_label = ctk.CTkLabel(self.dialogue_box, text="", font=ctk.CTkFont(size=20, weight="bold"), text_color="#e94560")
        self.char_name_label.pack(pady=(20, 10))
        
        self.answer_text_label = ctk.CTkLabel(self.dialogue_box, text="", font=ctk.CTkFont(size=22), text_color="black", wraplength=600, justify="left")
        self.answer_text_label.pack(pady=20, padx=20)
        
        self.restart_btn = ctk.CTkButton(self.answer_frame, text="SUFFER AGAIN", command=self.restart_app, 
                                         fg_color="#333", hover_color="#555", height=50, width=200)
        self.restart_btn.pack(pady=50)

    def update_camera_loop(self):
        if self.cap is None:
            print("🟢 6. Initializing camera (cv2.VideoCapture)...", flush=True)
            try:
                self.cap = cv2.VideoCapture(0)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                print("🟢 7. Camera object created.", flush=True)
                
                if not self.cap.isOpened():
                    print("🔴 WARNING: Camera could not be opened! Check Mac Camera Permissions.", flush=True)
            except Exception as e:
                print(f"🔴 CAMERA CRASH: {e}", flush=True)
                self.cap = None
            
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                
                if self.is_recording and self.video_writer is not None:
                    self.video_writer.write(frame)
                
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                
                self.camera_label.configure(image=imgtk)
                self.camera_label.image = imgtk
                
        self.after(30, self.update_camera_loop)
        
    def start_ritual(self):
        self.question = self.question_entry.get()
        if not self.question:
            return
            
        self.start_btn.configure(state="disabled", text="SUMMONING HASUR GUARDIAN...")
        threading.Thread(target=self.generate_challenge_thread, daemon=True).start()

    def generate_challenge_thread(self):
        try:
            escalation = 2 ** ((self.attempt - 1) // 3)
            prompt = f"""Generate a ritual challenge for attempt {self.attempt}. Escalate difficulty by {escalation}x. 
            Return ONLY valid JSON: {{"spins": number, "claps": number, "chantBPM": number (135-145), "chantText": string (must include TUNG TUNG TUNG HASUR), "finalMove": string (dab, 67 move, woah, Brazillian Dance)}}"""
            
            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            self.challenge = json.loads(response.choices[0].message.content)
            self.after(0, self.show_ritual_screen)
        except Exception as e:
            print(f"API Error: {e}")
            self.after(0, lambda: self.start_btn.configure(state="normal", text="RETRY"))

    def show_ritual_screen(self):
        self.question_frame.pack_forget()
        self.ritual_frame.pack(fill="both", expand=True)
        
        text = f"⚡ HASUR DECREE ⚡\n{self.challenge.get('spins', 0)}x SPINS | {self.challenge.get('claps', 0)}x CLAPS | {self.challenge.get('chantBPM', 140)} BPM\nCHANT: '{self.challenge.get('chantText', 'TUNG TUNG TUNG HASUR')}'\nFINISH WITH: {self.challenge.get('finalMove', 'DAB').upper()}!"
        self.challenge_label.configure(text=text)
        
        self.after(1000, self.start_recording)

    def start_recording(self):
        self.is_recording = True
        duration = BASE_DURATION * self.attempt
        
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
            
            self.countdown_label.configure(text="ANALYZING...")
            threading.Thread(target=self.run_analysis_thread, daemon=True).start()
            return
            
        self.countdown_label.configure(text=f"{time_left:.1f}s")
        self.after(100, lambda: self.update_countdown(time_left - 0.1, stream))

    def merge_audio_video(self, video_file, audio_file, output_file):
        try:
            cmd = [
                "ffmpeg", "-y", "-i", video_file, "-i", audio_file,
                "-c:v", "libx264", "-c:a", "aac", "-strict", "experimental", "-shortest", output_file
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Successfully merged recording to: {output_file}")
            return True
        except FileNotFoundError:
            print("⚠️ FFmpeg not found. Please install FFmpeg to merge audio and video. Continuing with video-only analysis.")
            return False
        except Exception as e:
            print(f"FFmpeg merge failed: {e}")
            return False

    def get_frames_from_video(self, video_path, num_frames=6):
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

    def run_analysis_thread(self):
        try:
            merged_success = self.merge_audio_video(self.current_video_filename, self.current_audio_filename, self.current_final_filename)
            file_to_analyze = self.current_final_filename if (merged_success and os.path.exists(self.current_final_filename)) else self.current_video_filename
            
            frames_b64 = self.get_frames_from_video(file_to_analyze, num_frames=6)
            
            if not frames_b64:
                raise Exception("Could not extract frames from video.")
            
            prompt = f"""Analyze these sequential frames from a video recording. 
            The user was challenged to perform:
            - {self.challenge.get('spins', 0)} spins
            - {self.challenge.get('claps', 0)} claps
            - Finish with the move: '{self.challenge.get('finalMove', 'dab')}'
            
            Evaluate if the person in the video attempted and completed these actions. Be lenient but check for clear physical attempts.
            Return ONLY valid JSON: {{"passed": boolean, "reason": string, "detected_spins": number, "detected_claps": number, "detected_final_move": string}}"""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                    ] + [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}} for img in frames_b64]
                }
            ]
            
            response = client.chat.completions.create(
                model="qwen-vl-max",
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            passed = result.get("passed", False)
            reason = result.get("reason", "Analysis incomplete.")
            
            self.after(0, lambda: self.handle_result(passed, reason))
            
        except Exception as e:
            print(f"Analysis Error: {e}")
            self.after(0, lambda: self.handle_result(False, f"Vision analysis failed: {str(e)}. The Hasur is blindfolded."))

    # 🔧 NEW: Method to forcefully stop any playing audio
    def stop_audio(self):
        if self.current_audio_process is not None:
            try:
                self.current_audio_process.terminate()
                self.current_audio_process.wait(timeout=0.5)
            except Exception:
                try:
                    self.current_audio_process.kill()
                except Exception:
                    pass
            self.current_audio_process = None

    def play_audio(self, file_path):
        # Stop any currently playing audio first to prevent overlapping
        self.stop_audio()
        
        if not os.path.exists(file_path):
            print(f"Audio file not found: {file_path}")
            return
        
        system = platform.system()
        try:
            if system == "Darwin":  # macOS
                self.current_audio_process = subprocess.Popen(["afplay", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif system == "Windows":
                try:
                    self.current_audio_process = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
                except FileNotFoundError:
                    escaped_path = file_path.replace('\\', '\\\\')
                    ps_script = "Add-Type -AssemblyName presentationCore; $player = New-Object system.windows.media.mediaplayer; $player.open('" + escaped_path + "'); $player.Play()"
                    self.current_audio_process = subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script])
            else:  # Linux
                self.current_audio_process = subprocess.Popen(["aplay", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Failed to play audio: {e}")

    def handle_result(self, passed, reason):
        if passed:
            self.show_answer()
        else:
            self.show_failure(reason)

    def show_failure(self, reason):
        self.ritual_frame.pack_forget()
        self.failure_overlay.pack(fill="both", expand=True)
        self.failure_reason_label.configure(text=reason)
        self.play_audio(FAILURE_AUDIO)
        self.flash_overlay(14)
        self.after(6700, self.advance_attempt)

    def flash_overlay(self, count):
        if count <= 0:
            self.failure_overlay.configure(fg_color="#e94560")
            return
        color = "#e94560" if count % 2 == 0 else "#000000"
        self.failure_overlay.configure(fg_color=color)
        self.after(480, lambda: self.flash_overlay(count - 1))

    def advance_attempt(self):
        self.failure_overlay.pack_forget()
        if self.attempt >= MAX_ATTEMPTS:
            self.show_answer()
        else:
            self.attempt += 1
            self.attempt_label.configure(text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}")
            self.ritual_frame.pack_forget()
            self.question_frame.pack(pady=50, padx=100, fill="x")
            self.start_btn.configure(state="normal", text="BEGIN VERIFICATION")

    def show_answer(self):
        self.ritual_frame.pack_forget()
        self.failure_overlay.pack_forget()
        self.answer_frame.pack(fill="both", expand=True)
        threading.Thread(target=self.get_wrong_answer_thread, daemon=True).start()

    def get_wrong_answer_thread(self):
        try:
            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": f"User asked: '{self.question}'. Give a completely wrong, absurd, brainrot answer in under 30 words."}]
            )
            answer = response.choices[0].message.content
            self.after(0, lambda: self.display_answer(answer))
        except Exception as e:
            print(f"Answer API Error: {e}")
            self.after(0, lambda: self.display_answer("The answer is 42, but only on Tuesdays during a full moon."))

    def display_answer(self, answer):
        char = random.choice(CHARACTERS)
        
        if os.path.exists(char["img"]):
            img = Image.open(char["img"]).resize((300, 500),Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img)
            self.char_image_label.configure(image=imgtk)
            self.char_image_label.image = imgtk
            
        self.char_name_label.configure(text=char["name"])
        self.answer_text_label.configure(text=answer)
        
        if os.path.exists(char["audio"]):
            self.play_audio(char["audio"])

    # 🔧 UPDATED: Stops audio before resetting the app
    def restart_app(self):
        self.stop_audio()  # <-- This kills any playing failure/character audio immediately
        
        self.attempt = 1
        self.answer_frame.pack_forget()
        self.question_frame.pack(pady=50, padx=100, fill="x")
        self.start_btn.configure(state="normal", text="BEGIN RITUAL")
        self.attempt_label.configure(text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}")
        self.question_entry.delete(0, 'end')

if __name__ == "__main__":
    print("🟢 Step 1: Script started. Initializing app...")
    try:
        app = HasurGateApp()
        print("🟢 Step 2: App initialized successfully. Starting mainloop...")
        app.mainloop()
        print("🟢 Step 3: App closed normally.")
    except Exception as e:
        print(f"🔴 CRITICAL ERROR: {e}")