import tkinter as tk
import sys
from PIL import Image, ImageTk
from payment_screen import show_payment_screen  # Import show_payment_screen

def show_print_summary(file_name, pages_range, color_mode, total_price, job_id, root):
    """
    Displays the print summary, including file information, and provides a button to proceed to payment.
    """
    # Clear the root window instead of destroying it
    for widget in root.winfo_children():
        widget.destroy()

    root.title("Printing Summary")
    root.configure(bg="white")

    # Force fullscreen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}+0+0")
    root.attributes("-fullscreen", True)
    root.overrideredirect(True)  # Remove title bar and borders

    # Calculate responsive sizes based on screen resolution
    base_width = 1920
    base_height = 1280
    scale_factor = min(screen_width / base_width, screen_height / base_height)

    # Responsive font sizes
    title_font_size = int(40 * scale_factor)
    content_font_size = int(32 * scale_factor)
    price_font_size = int(36 * scale_factor)
    button_font_size = int(30 * scale_factor)
    footer_font_size = int(20 * scale_factor)
    error_font_size = int(24 * scale_factor)

    # Responsive spacing
    main_padding = int(50 * scale_factor)
    logo_padding = int(50 * scale_factor)
    content_padding = int(50 * scale_factor)
    label_padding = int(30 * scale_factor)
    button_padding = int(40 * scale_factor)
    footer_padding = int(20 * scale_factor)

    # Responsive dimensions - same as payment_screen
    logo_width = int(700 * scale_factor)
    logo_height = int(265 * scale_factor)

    # Exit fullscreen on ESC
    def exit_fullscreen(event):
        root.destroy()
    root.bind("<Escape>", exit_fullscreen)

    # Main container with responsive padding
    main_frame = tk.Frame(root, bg="white")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=main_padding, pady=main_padding)

    # Left side - Logo section (same layout as payment_screen)
    logo_width = int(800 * scale_factor)
    logo_height = int(260 * scale_factor)
    logo_frame = tk.Frame(main_frame, bg="white", width=logo_width)
    logo_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(int(30 * scale_factor), int(10 * scale_factor)))
    logo_frame.pack_propagate(False)
    try:
        # Open and resize the image
        logo_img = Image.open("logo.jpg")
        logo_img = logo_img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_img)

        # Display the image - centered like payment_screen
        logo_label = tk.Label(logo_frame, image=logo_photo, bg="white")
        logo_label.image = logo_photo  # prevent garbage collection
        logo_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    except FileNotFoundError:
        error_label = tk.Label(logo_frame, text="Logo not found!", font=("Arial", error_font_size), bg="white", fg="red")
        error_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    except Exception as e:
        error_label = tk.Label(logo_frame, text=f"Error loading logo: {e}", font=("Arial", error_font_size), bg="white", fg="red")
        error_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # Right side - Content section (same layout as payment_screen)
    content_frame = tk.Frame(main_frame, bg="white")
    content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Container for centering text vertically (same as payment_screen)
    text_container = tk.Frame(content_frame, bg="white")
    text_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Center the content vertically and horizontally
    content_inner_frame = tk.Frame(text_container, bg="white")
    content_inner_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # File information labels with left alignment
    file_name_label = tk.Label(
        content_inner_frame, 
        text=f"File Name: {file_name}", 
        font=("Arial", title_font_size, "bold"), 
        bg="white", 
        fg="#b42e41", 
        anchor="w",
        justify="left"
    )
    file_name_label.pack(pady=(0, label_padding), anchor="w", fill="x")

    pages_label = tk.Label(
        content_inner_frame, 
        text=f"Pages to Print: {pages_range}", 
        font=("Arial", content_font_size), 
        bg="white", 
        fg="black", 
        anchor="w",
        justify="left"
    )
    pages_label.pack(pady=(0, int(20 * scale_factor)), anchor="w", fill="x")

    color_label = tk.Label(
        content_inner_frame, 
        text=f"Color Mode: {color_mode.title()}", 
        font=("Arial", content_font_size), 
        bg="white", 
        fg="black", 
        anchor="w",
        justify="left"
    )
    color_label.pack(pady=(0, int(20 * scale_factor)), anchor="w", fill="x")

    price_label = tk.Label(
        content_inner_frame, 
        text=f"Total Price: {total_price} pesos", 
        font=("Arial", price_font_size, "bold"), 
        bg="white", 
        fg="#b42e41", 
        anchor="w",
        justify="left"
    )
    price_label.pack(pady=(0, label_padding), anchor="w", fill="x")

    # Spacer frame for better visual separation
    spacer_frame = tk.Frame(content_inner_frame, bg="white", height=int(40 * scale_factor))
    spacer_frame.pack(fill="x", pady=int(20 * scale_factor))

    def proceed_to_payment():
        # Clear the current window instead of destroying it
        for widget in root.winfo_children():
            widget.destroy()
        # Call payment screen with the same root window to avoid window closing/reopening
        show_payment_screen(total_price, job_id, root)

    # Payment button with responsive sizing, centered
    payment_button = tk.Button(
        content_inner_frame,
        text="Proceed to Payment",
        font=("Arial", button_font_size, "bold"),
        bg="#b42e41",
        fg="white",
        activebackground="#a12336",  # hover/click background
        activeforeground="white",    # keep text white on click
        padx=int(60 * scale_factor),
        pady=int(20 * scale_factor),
        relief="flat",
        bd=0,
        command=proceed_to_payment
    )
    payment_button.pack(pady=button_padding)

    # Define hover functions
    def on_enter(e):
        payment_button['bg'] = '#d12246'

    def on_leave(e):
        payment_button['bg'] = '#b42e41'

    # Bind hover events
    payment_button.bind("<Enter>", on_enter)
    payment_button.bind("<Leave>", on_leave)

    # Footer with responsive font sizing
    footer_label = tk.Label(
        root,
        text="Click the button to proceed to payment",
        font=("Arial", footer_font_size),
        bg="white",
        fg="gray"
    )
    footer_label.pack(side=tk.BOTTOM, pady=footer_padding)

    root.mainloop()

if __name__ == "__main__":
    # Create the root window
    root = tk.Tk()
    # root.withdraw()  # Do not hide the root window for design

    # Example call to the print summary function
    sample_file_name = "example_document.pdf"
    sample_pages_range = "1-10"
    sample_color_mode = "colored"
    sample_total_price = 20
    sample_job_id = 123

    # Pass the root explicitly
    show_print_summary(
        file_name=sample_file_name,
        pages_range=sample_pages_range,
        color_mode=sample_color_mode,
        total_price=sample_total_price,
        job_id=sample_job_id,
        root=root
    )
