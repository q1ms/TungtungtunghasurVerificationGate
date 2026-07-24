import customtkinter as ctk

print("Testing GUI...")
app = ctk.CTk()
app.geometry("400x300")
app.title("Test Window")
label = ctk.CTkLabel(app, text="If you see this, GUI works!", font=ctk.CTkFont(size=24))
label.pack(pady=100)
app.mainloop()
print("Test finished.")