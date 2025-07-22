import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from PIL import Image, ImageTk  # type: ignore
import fitz  # type: ignore  # PyMuPDF for PDF preview
import sys
import io
from docx import Document # type: ignore
from print_summary import show_print_summary  # type: ignore # Import the function
from print_summary import show_payment_screen
import sqlite3
import logging
from firebase_config import db
import time
import requests

# Store image references globally to prevent garbage collection
image_refs = {}

# Configure logging
logging.basicConfig(filename="app.log", level=logging.ERROR)

def log_error(message):
    logging.error(message)

# Firebase: Fetch latest prices
def fetch_latest_prices():
    prices_ref = db.reference('print_prices')
    prices = prices_ref.order_by_child('updated_at').limit_to_last(1).get()
    latest = None
    if isinstance(prices, dict):
        latest = list(prices.values())[-1]
    elif isinstance(prices, list):
        latest = prices[-1]
    if latest:
        return latest.get('black_price'), latest.get('color_price')
    return None, None

# Firebase: Update job status
def update_job_status(job_id, new_status, details=None):
    job_ref = db.reference(f'print_jobs/{job_id}')
    update_data = {'status': new_status}
    if details:
        update_data['details'] = str(details)
    job_ref.update(update_data)
    return True

# Firebase: Save job details
def save_print_job_details(job_id, file_name, total_pages, pages_to_print, color_mode, total_price):
    details_ref = db.reference(f'print_job_details/{job_id}')
    details_ref.set({
        'file_name': file_name,
        'total_pages': total_pages,
        'pages_to_print': pages_to_print,
        'color_mode': color_mode,
        'total_price': total_price,
        'status': 'processing',
        'created_at': time.time(),
        'updated_at': time.time()
    })


def start_print_job(file_name, pages_range, color_mode, total_pages, job_id):
    try:
        black_price, color_price = fetch_latest_prices()
        if black_price is None or color_price is None:
            messagebox.showerror("Error", "Failed to retrieve printing prices from the database.")
            return
        price_per_page = black_price if color_mode == "bw" else color_price
        if pages_range == "all":
            pages_to_print = int(total_pages)
        else:
            start_page, end_page = map(int, pages_range.split('-'))
            pages_to_print = end_page - start_page + 1
        total_price = pages_to_print * price_per_page
        save_print_job_details(job_id, file_name, total_pages, pages_to_print, color_mode, total_price)
        messagebox.showinfo("Print Job Started", f"Print job for {file_name} has started.\nTotal price: {total_price:.2f} pesos.")
        update_job_status(job_id, "completed")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start print job: {e}")




def start_printing_options(file_name, file_path, total_pages, job_id):
    def start_printing():
        selected_pages = pages_var.get()
        color_option = color_var.get()
        black_price, color_price = fetch_latest_prices()
        if black_price is None or color_price is None:
            messagebox.showerror("Error", "Failed to retrieve printing prices from the database.")
            return
        price_per_page = black_price if color_option == "bw" else color_price
        if selected_pages == "range":
            try:
                start_page = int(start_page_var.get())
                end_page = int(end_page_var.get())
                if start_page < 1 or end_page > int(total_pages) or start_page > end_page:
                    raise ValueError("Invalid page range.")
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid page range: {e}")
                return
            pages_range = f"{start_page}-{end_page}"
            pages_to_print = end_page - start_page + 1
        else:
            pages_range = "all"
            pages_to_print = int(total_pages)
        total_price = pages_to_print * price_per_page
        save_print_job_details(job_id, file_name, total_pages, pages_range, color_option, total_price)
        try:
            show_print_summary(file_name, pages_range, color_option, total_price, job_id, root)
            update_job_status(job_id, "processing")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display print summary: {e}")
        if not update_job_status(job_id, "processing"):
            messagebox.showerror("Error", "Failed to update job status to processing.")



    def increment_start_page():
        try:
            current = int(start_page_var.get())
            end_page = int(end_page_var.get())
            if current < end_page and current < int(total_pages):
                start_page_var.set(str(current + 1))
        except ValueError:
            pass

    def decrement_start_page():
        try:
            current = int(start_page_var.get())
            if current > 1:
                start_page_var.set(str(current - 1))
        except ValueError:
            pass

    def increment_end_page():
        try:
            current = int(end_page_var.get())
            start_page = int(start_page_var.get())
            if current < int(total_pages):
                end_page_var.set(str(current + 1))
        except ValueError:
            pass

    def decrement_end_page():
        try:
            current = int(end_page_var.get())
            start_page = int(start_page_var.get())
            if current > start_page and current > 1:
                end_page_var.set(str(current - 1))
        except ValueError:
            pass

    #full-page file preview
    root = tk.Tk()
    root.title("Printing Options")
    root.configure(bg="white")
    root.attributes("-fullscreen", True)
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}+0+0")
    root.overrideredirect(True)
    def exit_fullscreen(event):
        root.destroy()
    root.bind("<Escape>", exit_fullscreen)

    # Calculate responsive sizes based on screen resolution
    base_width = 1920
    base_height = 1280
    scale_factor = min(screen_width / base_width, screen_height / base_height)

    # Responsive font sizes - bigger for 1920x1280
    base_font = int(24 * scale_factor)  # Increased from 14
    title_font = int(32 * scale_factor)  # Increased from 18
    section_font = int(28 * scale_factor)  # Increased from 15
    button_font = int(30 * scale_factor)  # Increased from 16
    
    # Responsive spacing - bigger for 1920x1280
    bigger_pad = int(80 * scale_factor)  # Increased from 48
    inner_pad = int(30 * scale_factor)  # Increased from 14
    side_pad = int(80 * scale_factor)  # Increased from 48
    between_pad = int(60 * scale_factor)  # Increased from 32
    
    # Responsive dimensions - bigger for 1920x1280
    preview_max_width = int(screen_width * 0.50)
    preview_max_height = int(screen_height * 0.98)
    logo_size = int(300 * scale_factor)  # Increased from 180

    main_frame = tk.Frame(root, bg="white", padx=0, pady=inner_pad)
    main_frame.pack(fill="both", expand=True)
    main_frame.grid_rowconfigure(0, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)

    # Left Frame - File Preview
    left_frame = tk.Frame(main_frame, bg="white", padx=0, pady=0)
    left_frame.grid(row=0, column=0, sticky="nsew", padx=(side_pad, between_pad), pady=0)
    left_frame.grid_rowconfigure(0, weight=1)
    left_frame.grid_columnconfigure(0, weight=1)

    # File Preview Title
    preview_title = tk.Label(left_frame, text="File Preview", font=("Arial", section_font, "bold"), bg="white", fg="#333333")
    preview_title.pack(pady=(0, 4))
    
    preview_container = tk.Frame(left_frame, bg="#f7f7f7", bd=1, relief="solid", highlightbackground="#e0e0e0", highlightthickness=1)
    preview_container.pack(fill="both", expand=True, padx=0, pady=0)
    preview_container.grid_rowconfigure(0, weight=1)
    preview_container.grid_columnconfigure(0, weight=1)

    preview_canvas = tk.Canvas(preview_container, bg="white", highlightthickness=0)
    preview_canvas.grid(row=0, column=0, sticky="nsew")

    def resize_preview(event=None):
        set_preview_page(preview_page["num"])
    preview_canvas.bind("<Configure>", resize_preview)

    # Centered page navigation bar below preview
    page_nav_frame = tk.Frame(left_frame, bg="white", padx=0, pady=0)
    page_nav_frame.pack(pady=(inner_pad, 0))
    page_nav_frame.grid_columnconfigure(0, weight=1)
    page_nav_inner = tk.Frame(page_nav_frame, bg="white")
    page_nav_inner.grid(row=0, column=0)
   
    # Minus Button
    button_width = int(8 * scale_factor)  
    button_height = int(2 * scale_factor)  
    page_nav_minus = tk.Button(
        page_nav_inner,
        text="-",
        font=("Arial", base_font, "bold"),
        width=button_width,
        height=button_height,
        bg="#b42e41",
        fg="white",
        activebackground="#b42e41",
        activeforeground="white",
        bd=0,
        relief="flat",
        padx=int(10 * scale_factor),  
        pady=int(5 * scale_factor)   
    )
    page_nav_minus.grid(row=0, column=0, padx=int(8 * scale_factor))  

    # Label 
    page_nav_label = tk.Label(
        page_nav_inner,
        text="",
        font=("Arial", base_font),
        bg="white",
        padx=int(8 * scale_factor)  
    )
    page_nav_label.grid(row=0, column=1, padx=int(8 * scale_factor))  

    # Plus Button 
    page_nav_plus = tk.Button(
        page_nav_inner,
        text="+",
        font=("Arial", base_font, "bold"),
        width=button_width,
        height=button_height,
        bg="#b42e41",
        fg="white",
        activebackground="#b42e41",
        activeforeground="white",
        bd=0,
        relief="flat",
        padx=int(10 * scale_factor),
        pady=int(5 * scale_factor)   
    )
    page_nav_plus.grid(row=0, column=2, padx=int(8 * scale_factor))  

    #Hover Functions
    def on_minus_enter(e):
        page_nav_minus['bg'] = '#d12246'

    def on_minus_leave(e):
        page_nav_minus['bg'] = '#b42e41'

    def on_plus_enter(e):
        page_nav_plus['bg'] = '#d12246'

    def on_plus_leave(e):
        page_nav_plus['bg'] = '#b42e41'

    #Hover Bindings
    page_nav_minus.bind("<Enter>", on_minus_enter)
    page_nav_minus.bind("<Leave>", on_minus_leave)
    page_nav_plus.bind("<Enter>", on_plus_enter)
    page_nav_plus.bind("<Leave>", on_plus_leave)


    # --- Update load_preview to use dynamic canvas size ---
    def load_preview(page_num=1):
        try:
            job_ref = db.reference(f'print_jobs/{job_id}')
            job_data = job_ref.get()
            preview_canvas.delete("all")
            if not job_data or not isinstance(job_data, dict):
                preview_canvas.create_text(
                    preview_canvas.winfo_width()//2, preview_canvas.winfo_height()//2, text="File not found in database", font=("Arial", 16), fill="black"
                )
                return
            # Fetch file from local_path if present
            file_data = None
            if 'local_path' in job_data:
                try:
                    with open(job_data['local_path'], 'rb') as f:
                        file_data = f.read()
                except Exception as e:
                    preview_canvas.create_text(
                        preview_canvas.winfo_width()//2, preview_canvas.winfo_height()//2, text=f"File not found: {e}", font=("Arial", 16), fill="black"
                    )
                    return
            elif 'file_data' in job_data:
                file_data = job_data['file_data']
            if not file_data:
                preview_canvas.create_text(
                    preview_canvas.winfo_width()//2, preview_canvas.winfo_height()//2, text="File not found in storage", font=("Arial", 16), fill="black"
                )
                return
            canvas_w = preview_canvas.winfo_width()
            canvas_h = preview_canvas.winfo_height()
            if file_name.endswith(('.png', '.jpg', '.jpeg')):
                img = Image.open(io.BytesIO(file_data))
                img.thumbnail((canvas_w, canvas_h))
                img_tk = ImageTk.PhotoImage(img)
                preview_canvas.create_image(canvas_w//2, canvas_h//2, image=img_tk)
                image_refs['preview'] = img_tk  # Prevent garbage collection
                page_nav_label.config(text="Page 1 of 1")
                page_nav_minus.config(state="disabled")
                page_nav_plus.config(state="disabled")
            elif file_name.endswith('.pdf'):
                pdf_document = fitz.open(stream=file_data, filetype="pdf")
                total_pdf_pages = pdf_document.page_count
                page = pdf_document[page_num-1]
                try:
                    pix = page.get_pixmap()  # type: ignore
                except AttributeError:
                    pix = page.getPixmap()  # type: ignore
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                img.thumbnail((canvas_w, canvas_h))
                img_tk = ImageTk.PhotoImage(img)
                preview_canvas.create_image(canvas_w//2, canvas_h//2, image=img_tk)
                image_refs['preview'] = img_tk
                page_nav_label.config(text=f"Page {page_num} of {total_pdf_pages}")
                page_nav_minus.config(state="normal" if page_num > 1 else "disabled")
                page_nav_plus.config(state="normal" if page_num < total_pdf_pages else "disabled")
                pdf_document.close()
            else:
                preview_canvas.create_text(
                    canvas_w//2, canvas_h//2, text="Preview not available", font=("Arial", 16), fill="black"
                )
                page_nav_label.config(text="")
                page_nav_minus.config(state="disabled")
                page_nav_plus.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preview: {e}")

    # --- Page navigation logic ---
    preview_page = {"num": 1, "max": 1}
    def update_preview_page(delta):
        try:
            job_ref = db.reference(f'print_jobs/{job_id}')
            job_data = job_ref.get()
            if not job_data or not isinstance(job_data, dict) or 'file_data' not in job_data:
                return
            file_data = job_data['file_data']
            pdf_document = fitz.open(stream=file_data, filetype="pdf")
            preview_page["max"] = pdf_document.page_count
            pdf_document.close()
        except:
            preview_page["max"] = 1
        new_page = preview_page["num"] + delta
        if 1 <= new_page <= preview_page["max"]:
            preview_page["num"] = new_page
            load_preview(preview_page["num"])
    def set_preview_page(page):
        preview_page["num"] = page
        load_preview(page)
    page_nav_minus.config(command=lambda: update_preview_page(-1))
    page_nav_plus.config(command=lambda: update_preview_page(1))

    # Load the preview (initial)
    set_preview_page(1)

    # Right Frame - Options (bigger titles, smaller choices, minimal containers)
    right_frame = tk.Frame(main_frame, bg="white", padx=2, pady=2)
    right_frame.grid(row=0, column=1, sticky="nsew", padx=(between_pad, side_pad), pady=0)
    right_frame.grid_rowconfigure(10, weight=1)
    right_frame.grid_columnconfigure(0, weight=1)

    # Logo
    try:
        logo_size = min(400, int(screen_width * 0.25))  
        logo_img = Image.open("logo.jpg")
        logo_img.thumbnail((logo_size, logo_size))
        logo_tk = ImageTk.PhotoImage(logo_img)
        logo_label = tk.Label(right_frame, image=logo_tk, bg="white")
        image_refs['logo'] = logo_tk  # Prevent garbage collection
        logo_label.grid(row=0, column=0, pady=(0, int(16 * scale_factor)), sticky="n")  
    except Exception as e:
        tk.Label(right_frame, text="Logo not found", bg="white", font=("Arial", base_font), fg="red").grid(row=0, column=0, pady=(0, int(16 * scale_factor)), sticky="n")

    # File details
    file_details_frame = tk.Frame(right_frame, bg="white", padx=0, pady=0)
    file_details_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, int(16 * scale_factor)))  
    file_details_frame.grid_columnconfigure(1, weight=1)
    file_name_label = tk.Label(file_details_frame, text="File Name:", font=("Arial", section_font, "bold"), bg="white", anchor="w", padx=0)
    file_name_label.grid(row=0, column=0, sticky="w", padx=(0, int(4 * scale_factor)), pady=int(4 * scale_factor))  
    file_name_value = tk.Label(file_details_frame, text=file_name, font=("Arial", section_font), bg="white", anchor="w", padx=0)
    file_name_value.grid(row=0, column=1, sticky="w", pady=int(4 * scale_factor)) 
    total_pages_label = tk.Label(file_details_frame, text="Total Pages:", font=("Arial", section_font, "bold"), bg="white", anchor="w", padx=0)
    total_pages_label.grid(row=1, column=0, sticky="w", padx=(0, int(4 * scale_factor)), pady=int(4 * scale_factor))  
    total_pages_value = tk.Label(file_details_frame, text=total_pages, font=("Arial", section_font), bg="white", anchor="w", padx=0)
    total_pages_value.grid(row=1, column=1, sticky="w", pady=int(4 * scale_factor))  

    # Function to enable/disable page range widgets
    def toggle_page_range_inputs():
        if pages_var.get() == "range":
            start_page_entry.config(state="normal")
            end_page_entry.config(state="normal")
            decrement_start_button.config(state="normal")
            increment_start_button.config(state="normal")
            decrement_end_button.config(state="normal")
            increment_end_button.config(state="normal")
        else:
            start_page_entry.config(state="disabled")
            end_page_entry.config(state="disabled")
            decrement_start_button.config(state="disabled")
            increment_start_button.config(state="disabled")
            decrement_end_button.config(state="disabled")
            increment_end_button.config(state="disabled")

    # Pages to Print Section 
    pages_section = tk.Frame(right_frame, bg="#f9f9f9", padx=int(6 * scale_factor), pady=int(4 * scale_factor), relief="solid", bd=1, highlightbackground="#e0e0e0", highlightthickness=1)
    pages_section.grid(row=2, column=0, sticky="ew", pady=(0, int(8 * scale_factor)), padx=0)  
    pages_section.grid_columnconfigure(0, weight=1)

    pages_label = tk.Label(pages_section, text="Pages to Print", font=("Arial", section_font+8, "bold"), bg="#f9f9f9", anchor="center")  
    pages_label.pack(pady=(0, int(4 * scale_factor)), anchor="center")  

    pages_var = tk.StringVar(value="all")
    color_var = tk.StringVar(value="colored")
    radio_font = ("Arial", max(section_font-2, int(24 * scale_factor))) 
    radio_pad = int(3 * scale_factor)  

    # Radio Buttons
    all_pages_radio = tk.Radiobutton(
        pages_section, text="All Pages", variable=pages_var, value="all", 
        font=radio_font, bg="#fafafa", padx=radio_pad, pady=radio_pad,
        highlightthickness=0, bd=0, indicatoron=True,
        command=toggle_page_range_inputs
    )
    all_pages_radio.pack(anchor="w")

    range_pages_radio = tk.Radiobutton(
        pages_section, text="Page Range", variable=pages_var, value="range", 
        font=radio_font, bg="#fafafa", padx=radio_pad, pady=radio_pad,
        highlightthickness=0, bd=0, indicatoron=True,
        command=toggle_page_range_inputs
    )
    range_pages_radio.pack(anchor="w")

    # Page range grid for plus/minus
    page_range_frame = tk.Frame(pages_section, bg="#fafafa")
    page_range_frame.pack(pady=int(8 * scale_factor), anchor="w")

    # Start Page
    start_page_var = tk.StringVar(value="1")
    start_page_label = tk.Label(page_range_frame, text="Start Page", font=("Arial", base_font), bg="#fafafa", width=12, anchor="e")
    start_page_label.grid(row=0, column=0, sticky="e", padx=(0, int(4 * scale_factor)), pady=int(4 * scale_factor))

    start_page_entry = tk.Entry(page_range_frame, textvariable=start_page_var, font=("Arial", base_font), width=6)
    start_page_entry.grid(row=0, column=1, sticky="w", pady=int(4 * scale_factor), padx=(0, int(4 * scale_factor)))

    # Frame to hold Start Page +/- buttons
    start_btn_frame = tk.Frame(page_range_frame, bg="#fafafa")
    start_btn_frame.grid(row=0, column=2, pady=int(4 * scale_factor), sticky="w")

    range_btn_font = ("Arial", max(base_font-2, int(18 * scale_factor)), "bold")

    decrement_start_button = tk.Button(
        start_btn_frame, text="-", font=range_btn_font, width=5, height=2,
        bg="#b42e41", fg="white", command=decrement_start_page,
        bd=0, relief="flat", padx=0, pady=0,
        activebackground="#b42e41", activeforeground="white"
    )
    decrement_start_button.pack(side="left", padx=(6, int(4 * scale_factor)))

    increment_start_button = tk.Button(
        start_btn_frame, text="+", font=range_btn_font, width=5, height=2,
        bg="#b42e41", fg="white", command=increment_start_page,
        bd=0, relief="flat", padx=0, pady=0,
        activebackground="#b42e41", activeforeground="white"
    )
    increment_start_button.pack(side="left", padx=(int(10 * scale_factor), 0))

    # Hover Functions for Start Page Buttons
    decrement_start_button.bind("<Enter>", lambda e: decrement_start_button.config(bg="#d12246") if decrement_start_button['state'] == "normal" else None)
    decrement_start_button.bind("<Leave>", lambda e: decrement_start_button.config(bg="#b42e41") if decrement_start_button['state'] == "normal" else None)
    increment_start_button.bind("<Enter>", lambda e: increment_start_button.config(bg="#d12246") if increment_start_button['state'] == "normal" else None)
    increment_start_button.bind("<Leave>", lambda e: increment_start_button.config(bg="#b42e41") if increment_start_button['state'] == "normal" else None)

    # End Page Section (Same structure)
    end_page_var = tk.StringVar(value="5")
    end_page_label = tk.Label(page_range_frame, text="End Page", font=("Arial", base_font), bg="#fafafa", width=12, anchor="e")
    end_page_label.grid(row=1, column=0, sticky="e", padx=(0, int(4 * scale_factor)), pady=int(4 * scale_factor))

    end_page_entry = tk.Entry(page_range_frame, textvariable=end_page_var, font=("Arial", base_font), width=6)
    end_page_entry.grid(row=1, column=1, sticky="w", pady=int(4 * scale_factor), padx=(0, int(4 * scale_factor)))

    # Frame to hold End Page +/- buttons
    end_btn_frame = tk.Frame(page_range_frame, bg="#fafafa")
    end_btn_frame.grid(row=1, column=2, pady=int(4 * scale_factor), sticky="w")

    decrement_end_button = tk.Button(
        end_btn_frame, text="-", font=range_btn_font, width=5, height=2,
        bg="#b42e41", fg="white", command=decrement_end_page,
        bd=0, relief="flat", padx=0, pady=0,
        activebackground="#b42e41", activeforeground="white"
    )
    decrement_end_button.pack(side="left", padx=(6, int(4 * scale_factor)))

    increment_end_button = tk.Button(
        end_btn_frame, text="+", font=range_btn_font, width=5, height=2,
        bg="#b42e41", fg="white", command=increment_end_page,
        bd=0, relief="flat", padx=0, pady=0,
        activebackground="#b42e41", activeforeground="white"
    )
    increment_end_button.pack(side="left", padx=(int(10 * scale_factor), 0))

    # Hover Functions for End Page Buttons
    decrement_end_button.bind("<Enter>", lambda e: decrement_end_button.config(bg="#d12246") if decrement_end_button['state'] == "normal" else None)
    decrement_end_button.bind("<Leave>", lambda e: decrement_end_button.config(bg="#b42e41") if decrement_end_button['state'] == "normal" else None)
    increment_end_button.bind("<Enter>", lambda e: increment_end_button.config(bg="#d12246") if increment_end_button['state'] == "normal" else None)
    increment_end_button.bind("<Leave>", lambda e: increment_end_button.config(bg="#b42e41") if increment_end_button['state'] == "normal" else None)

    toggle_page_range_inputs()


    # Color mode
    color_section = tk.Frame(right_frame, bg="#f9f9f9", padx=int(6 * scale_factor), pady=int(4 * scale_factor), relief="solid", bd=1, highlightbackground="#e0e0e0", highlightthickness=1)
    color_section.grid(row=3, column=0, sticky="ew", pady=(0, int(8 * scale_factor)), padx=0) 
    color_section.grid_columnconfigure(0, weight=1)
    color_mode_label = tk.Label(color_section, text="Color Mode", font=("Arial", section_font+8, "bold"), bg="#f9f9f9", anchor="center")  
    color_mode_label.pack(pady=(0, int(4 * scale_factor)), anchor="center")  
    colored_radio = tk.Radiobutton(color_section, text="Colored", variable=color_var, value="colored", 
                                   font=radio_font, bg="#fafafa", padx=radio_pad, pady=radio_pad, highlightthickness=0, bd=0, indicatoron=True)  
    colored_radio.pack(anchor="w")
    black_white_radio = tk.Radiobutton(color_section, text="Black and White", variable=color_var, value="bw", 
                                       font=radio_font, bg="#fafafa", padx=radio_pad, pady=radio_pad, highlightthickness=0, bd=0, indicatoron=True)  
    black_white_radio.pack(anchor="w")

    # Page Size
    page_size_section = tk.Frame(right_frame, bg="#f9f9f9", padx=int(6 * scale_factor), pady=int(4 * scale_factor), relief="solid", bd=1, highlightbackground="#e0e0e0", highlightthickness=1)
    page_size_section.grid(row=4, column=0, sticky="ew", pady=(0, int(8 * scale_factor)), padx=0)  
    page_size_section.grid_columnconfigure(0, weight=1)
    page_size_label = tk.Label(page_size_section, text="Page Size", font=("Arial", section_font+8, "bold"), bg="#f9f9f9", anchor="center") 
    page_size_label.pack(pady=(0, int(4 * scale_factor)), anchor="center")
    page_size_var = tk.StringVar(value="Letter Size")
    letter_radio = tk.Radiobutton(page_size_section, text="Letter Size", variable=page_size_var, value="Letter Size", font=radio_font, bg="#fafafa", padx=radio_pad, pady=radio_pad, highlightthickness=0, bd=0, indicatoron=True)
    letter_radio.pack(anchor="w")
    a4_radio = tk.Radiobutton(page_size_section, text="A4", variable=page_size_var, value="A4", font=radio_font, bg="#fafafa", padx=radio_pad, pady=radio_pad, highlightthickness=0, bd=0, indicatoron=True)
    a4_radio.pack(anchor="w")

    # Action Buttons
    action_buttons_frame = tk.Frame(right_frame, bg="white", padx=0, pady=0)
    action_buttons_frame.grid(row=10, column=0, sticky="e", pady=(int(12 * scale_factor), 0), padx=0) 
    start_button = tk.Button(
        action_buttons_frame,
        text="Start Printing",
        command=start_printing,
        font=("Arial", button_font, "bold"), 
        bg="#b42e41",
        fg="white",
        padx=int(60 * scale_factor),  
        pady=int(30 * scale_factor),  
        bd=0,
        relief="flat",
        width=20,  
        activebackground="#b42e41",
        activeforeground="white"
    )
    start_button.pack(side="right", padx=int(8 * scale_factor), pady=int(8 * scale_factor)) 

    # Hover Function
    start_button.bind("<Enter>", lambda e: start_button.config(bg="#d12246") if start_button['state'] == "normal" else None)
    start_button.bind("<Leave>", lambda e: start_button.config(bg="#b42e41") if start_button['state'] == "normal" else None)

    root.mainloop()



# Entry point for this script
if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python printingoptions.py <file_name> <file_path> <total_pages> <job_id>")
        sys.exit(1)

    file_name = sys.argv[1]
    file_path = sys.argv[2]
    total_pages = sys.argv[3]
    job_id = sys.argv[4]

    start_printing_options(file_name, file_path, total_pages, job_id)
