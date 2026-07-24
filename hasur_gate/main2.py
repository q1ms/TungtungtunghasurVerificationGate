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
from openai import OpenAI
import json
import random

# ==========================================
# >>> INSERT YOUR API KEY HERE <<<
# ==========================================
API_KEY = "sk-ws-H.XLLHHD.GQU5.MEQCIGlOQ1CMu9XEN5jFyF2Eyz8V7x7TwZT5PEylyDN99-K0AiB2INQsbiAmPVwxuFH6JCsukduWf9YiWcHxnO-BU4hc1w"
API_BASE_URL = "https://ws-qzavoknndotjynro.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1" 
# ==========================================

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

MAX_ATTEMPTS = 3
BASE_DURATION = 6.7
CHARACTERS = ["assets/char1.png", "assets/char2.png", "assets/char3.png", "assets/char4.png", "assets/char5.png"]
FAILURE_AUDIO = "assets/failure.mp3"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HasurGateApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Tung Tung Tung Hasur Verification Gate")
        self.geometry("1200x800")
        self.attributes('-fullscreen', True)
        self.bind("<Escape>", lambda e: self.destroy())
        
        self.attempt = 1
        self.question = ""
        self.challenge = {}
        self.is_recording = False
        self.cap = None
        self.video_writer = None
        self.audio_data = []
        
        self.setup_ui()
        self.update_camera_loop()

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
        
        self.char_image_label = ctk.CTkLabel(self.answer_frame, text="", width=200, height=200)
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
            self.cap = cv2.VideoCapture(0)
            # 🔧 FIX 1: Force camera to 640x480 to perfectly match VideoWriter
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
        if self.cap.isOpened():
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
        
        # 🔧 FIX 2: Use 'avc1' (H.264) instead of 'mp4v'. 
        # 'mp4v' frequently fails on macOS due to missing FFmpeg encoders in the pip package.
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        
        today = datetime.datetime.now()
        day_name = today.strftime("%A")
        date_str = today.strftime("%Y-%m-%d")
        filename = f"recordings/{day_name}_{date_str}_attempt{self.attempt}.mp4"
        os.makedirs("recordings", exist_ok=True)
        
        # Explicitly set size to 640x480 to match the forced camera resolution
        self.video_writer = cv2.VideoWriter(filename, fourcc, 30.0, (640, 480))
        
        samplerate = 44100
        self.audio_data = []
        def audio_callback(indata, frames, time, status):
            self.audio_data.append(indata.copy())
            
        stream = sd.InputStream(samplerate=samplerate, channels=1, callback=audio_callback)
        stream.start()
        
        self.countdown = duration
        self.update_countdown(duration, stream, filename.replace('.mp4', '.wav'))

    def update_countdown(self, time_left, stream, audio_filename):
        if time_left <= 0:
            self.is_recording = False
            stream.stop()
            stream.close()
            if self.video_writer:
                self.video_writer.release()
            
            audio_array = np.concatenate(self.audio_data, axis=0)
            wavfile.write(audio_filename, 44100, audio_array)
            
            self.analyze_performance(audio_filename)
            return
            
        self.countdown_label.configure(text=f"{time_left:.1f}s")
        self.after(100, lambda: self.update_countdown(time_left - 0.1, stream, audio_filename))

    def analyze_performance(self, audio_filename):
        self.countdown_label.configure(text="ANALYZING...")
        threading.Thread(target=self.run_analysis_thread, args=(audio_filename,), daemon=True).start()

    def run_analysis_thread(self, audio_filename):
        passed = False
        reason = "Your vibe was insufficient. The Hasur is disappointed."
        self.after(0, lambda: self.handle_result(passed, reason))

    def handle_result(self, passed, reason):
        if passed:
            self.show_answer()
        else:
            self.show_failure(reason)

    def show_failure(self, reason):
        self.ritual_frame.pack_forget()
        self.failure_overlay.pack(fill="both", expand=True)
        self.failure_reason_label.configure(text=reason)
        
        if os.path.exists(FAILURE_AUDIO):
            subprocess.Popen(["afplay", FAILURE_AUDIO])
            
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
        except:
            self.after(0, lambda: self.display_answer("The answer is 42, but only on Tuesdays during a full moon."))

    def display_answer(self, answer):
        char_img = random.choice(CHARACTERS)
        if os.path.exists(char_img):
            img = Image.open(char_img).resize((200, 200))
            imgtk = ImageTk.PhotoImage(image=img)
            self.char_image_label.configure(image=imgtk)
            self.char_image_label.image = imgtk
            
        self.char_name_label.configure(text="Brainrot Entity")
        self.answer_text_label.configure(text=answer)

    def restart_app(self):
        self.attempt = 1
        self.answer_frame.pack_forget()
        self.question_frame.pack(pady=50, padx=100, fill="x")
        self.start_btn.configure(state="normal", text="BEGIN RITUAL")
        self.attempt_label.configure(text=f"Attempt {self.attempt} of {MAX_ATTEMPTS}")
        self.question_entry.delete(0, 'end')

if __name__ == "__main__":
    app = HasurGateApp()
    app.mainloop()
