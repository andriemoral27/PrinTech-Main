import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import socketio
import subprocess
import time
import os
import sys
from firebase_config import db

import threading

print("[DEBUG] frame1.py started at", time.time())

# SocketIO Configuration
SOCKETIO_SERVER = "https://paperazzi.onrender.com"
socketio_client = socketio.Client(logger=True, engineio_logger=True)

# Global variables
global logo_photo
job_labels = {}

# Function to close the application
def close_application(event=None):
    if root is not None:
        root.quit()

# Function to transition to Wi-Fi screen
def go_to_wifi():
    main_frame.pack_forget()  # Hide the main frame
    wifi_frame.pack(pady=20)  # Show the Wi-Fi frame

# Function to return to the home screen
def return_home():
    wifi_frame.pack_forget()
    main_frame.pack(pady=20)

def show_transition_screen():
    if root is not None:
        for widget in root.winfo_children():
            widget.pack_forget()
        transition_frame = tk.Frame(root, bg="white")
        transition_frame.pack(fill="both", expand=True)
        loading_label = tk.Label(
            transition_frame,
            text="Preparing your print job...",
            font=("Bebas Neue", 50),
            bg="white",
            fg="black"
        )
        loading_label.pack(expand=True)
        root.attributes('-topmost', True)
        root.update_idletasks()
        root.after(1000, lambda: launch_printingoptions(transition_frame))

def launch_printingoptions(transition_frame):
    try:
        transition_frame.tkraise()  # Ensure the frame is on top
        if not os.path.isfile("printingoptions.py"):
            raise FileNotFoundError("The script 'printingoptions.py' was not found!")
        python_executable = "python" if sys.platform.startswith("win") else "python3"
        print(f"Launching {python_executable} printingoptions.py with args: {file_name}, {file_path}, {total_pages}, {job_id}")
        # Use subprocess.Popen with creationflags to hide the console window on Windows
        if sys.platform.startswith("win"):
            try:
                # Use pythonw (Python without console) on Windows
                process = subprocess.Popen([
                    "pythonw",
                    "printingoptions.py",
                    file_name,
                    file_path,
                    str(total_pages),
                    str(job_id),
                ], creationflags=subprocess.CREATE_NO_WINDOW)
            except AttributeError:
                # Fallback for older Windows versions
                process = subprocess.Popen([
                    "pythonw",
                    "printingoptions.py",
                    file_name,
                    file_path,
                    str(total_pages),
                    str(job_id),
                ], creationflags=0x08000000)  # CREATE_NO_WINDOW constant
        else:
            process = subprocess.Popen([
                python_executable,
                "printingoptions.py",
                file_name,
                file_path,
                str(total_pages),
                str(job_id),
            ])
        if root is not None:
            root.after(5000, lambda: check_process_and_close(process, transition_frame))
    except FileNotFoundError as e:
        print(f"File not found error: {e}")
        messagebox.showerror("Error", f"Could not find required file: {e}")
    except subprocess.SubprocessError as e:
        print(f"Subprocess error: {e}")
        messagebox.showerror("Error", f"Failed to launch printing options: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")

def check_process_and_close(process, transition_frame):
    if process.poll() is None:
        print("printingoptions.py launched successfully. Closing transition screen.")
        if root is not None:
            root.destroy()
    else:
        print("Failed to launch printingoptions.py. Keeping the transition frame visible.")
        if root is not None:
            messagebox.showerror("Error", "Failed to launch printing options. Please try again.")

# SocketIO listeners
@socketio_client.on('connect')
def on_connect():
    print("Successfully connected to the server.")

@socketio_client.on('disconnect')
def on_disconnect():
    print("Disconnected from the server.")

@socketio_client.on('file_uploaded')
def on_file_uploaded(data):
    global file_name, file_path, total_pages, job_id
    file_name = data.get('file_name')
    file_path = data.get('file_path')
    total_pages = data.get('total_pages')
    job_id = data.get('job_id')
    download_url = data.get('download_url')  # For future use if needed
    if not all([file_name, total_pages, job_id]):
        print("Error: Missing file upload data.")
        return
    print(f"File uploaded: {file_name}, Path: {file_path}, Pages: {total_pages}")
    show_transition_screen()  

@socketio_client.on('file_status_update')
def on_status_update(data):
    document_name = data.get('document_name')
    status = data.get('status')
    print(f"Received update for {document_name}: {status}")
    if document_name not in job_labels:
        job_labels[document_name] = tk.Label(
            job_frame, 
            text=f"{document_name} - {status.upper()}", 
            font=("Bebas Neue", 16)
        )
        job_labels[document_name].pack(pady=5)
    else:
        job_labels[document_name].config(text=f"{document_name} - {status.upper()}")

# Create the main application window
root = tk.Tk()
root.title("Paperazzi")
root.config(bg="white")
root.attributes('-fullscreen', True)
root.bind("<Escape>", close_application)  

# Main frame (fills the window)
main_frame = tk.Frame(root, bg="white")
main_frame.pack(expand=True, fill="both")

# Center frame (centers its content)
center_frame = tk.Frame(main_frame, bg="white")
center_frame.pack(expand=True)

# Logo display
logo_frame = tk.Frame(center_frame, bg="white")
logo_frame.pack(pady=(50, 10))
try:
    logo_image = Image.open("logo.jpg")
    resample = getattr(Image, 'Resampling', None)
    if resample:
        lanczos = Image.Resampling.LANCZOS
    else:
        lanczos = getattr(Image, 'LANCZOS', 1)
    logo_image = logo_image.resize((900, 265), lanczos)
    logo_photo = ImageTk.PhotoImage(logo_image)
    logo_label = tk.Label(logo_frame, image=logo_photo, bg="white")
    logo_label.pack()
except Exception as e:
    print(f"Error loading logo: {e}")
    logo_label = tk.Label(logo_frame, text="[Logo missing]", bg="white", fg="red", font=("Arial", 24, "bold"))
    logo_label.pack()

# Start printing button
start_button_frame = tk.Frame(center_frame, bg="white")
start_button_frame.pack(pady=40)
def on_hover(event):
    start_button.config(bg="#d12246", fg="white", relief=tk.RAISED)
def on_leave(event):
    start_button.config(bg="#b42e41", fg="white", relief=tk.FLAT)
start_button = tk.Button(
    start_button_frame,
    text="Start Printing",
    font=("Bebas Neue", 50),
    bg="#b42e41",
    fg="white",
    activebackground="#b42e41",
    activeforeground="white",
    relief=tk.FLAT,
    bd=0,
    padx=30,
    pady=20,
    command=go_to_wifi
)
start_button.bind("<Enter>", on_hover)
start_button.bind("<Leave>", on_leave)
start_button.pack(pady=10)

# Wi-Fi frame setup
wifi_frame = tk.Frame(root, bg="white")
wifi_inner_frame = tk.Frame(wifi_frame, bg="white")
wifi_inner_frame.pack(expand=True, fill="both", pady=(50, 0))

wifi_instruction_label = tk.Label(
    wifi_inner_frame, text="Connect to Wi-Fi and scan the QR code:", font=("Bebas Neue", 36), bg="white", fg="black"
)
wifi_instruction_label.pack(pady=10)

# QR code for Wi-Fi printing
try:
    qr_image = Image.open("qr_code.png").resize((520, 520))
    qr_photo = ImageTk.PhotoImage(qr_image)
    qr_label = tk.Label(wifi_inner_frame, image=qr_photo, bg="white")
    qr_label.pack(pady=10)
except Exception as e:
    print(f"Error loading QR code: {e}")

website_link_label = tk.Label(
    wifi_inner_frame, text="or visit https://paperazzi.onrender.com", font=("Bebas Neue", 14), bg="white", fg="blue"
)
website_link_label.pack(pady=5)

# Real-time Status Area
job_frame = tk.Frame(wifi_frame, bg="white")
job_frame.pack(pady=10)

status_label = tk.Label(
    wifi_frame, text="Waiting for files...", font=("Bebas Neue", 20), bg="white"
)
status_label.pack(pady=10)

# Start the SocketIO listener
print("[DEBUG] About to connect to SocketIO at", time.time())
def connect_socketio():
    try:
        socketio_client.connect(SOCKETIO_SERVER, transports=['websocket'], wait_timeout=30)
        print("[DEBUG] Connected to SocketIO at", time.time())
    except Exception as e:
        print(f"Failed to connect to SocketIO server: {e}")

threading.Thread(target=connect_socketio, daemon=True).start()

# Start the GUI application
print("[DEBUG] frame1.py entering mainloop at", time.time())
root.mainloop()
