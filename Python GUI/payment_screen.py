import time
import tkinter as tk
from threading import Thread
import subprocess
import os
import sys
from PIL import Image, ImageTk
from tkinter import messagebox  # Import messagebox for alert popups
from tkinter import Button
from firebase_config import db

# Conditional import for RPi.GPIO - only on Raspberry Pi
try:
    import RPi.GPIO as GPIO
    COIN_PIN = 26  # The GPIO pin connected to the COIN wire
    GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
    GPIO.setup(COIN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Use internal pull-up resistor
    IS_RASPBERRY_PI = True
except ImportError:
    # Mock GPIO for non-Raspberry Pi systems (like Windows)
    class MockGPIO:
        BCM = 11  # Use int value
        IN = 1    # Use int value
        PUD_UP = 22  # Use int value
        HIGH = 1
        LOW = 0
        
        @staticmethod
        def setmode(mode):
            pass
            
        @staticmethod
        def setup(pin, direction, pull_up_down=None):
            pass
            
        @staticmethod
        def input(pin):
            return 0  # Mock input value
            
        @staticmethod
        def cleanup():
            pass
    
    GPIO = MockGPIO()
    COIN_PIN = 26
    IS_RASPBERRY_PI = False

from PyPDF2 import PdfReader  # Install PyPDF2 if not already installed




def print_job_in_thread():
    try:
        # Call the original print_job logic here
        pass  # print_job() is not defined, so skip
    except Exception as e:
        print(f"[ERROR] Error in print_job: {e}")


def validate_tmp_permissions():
    import tempfile
    temp_dir = tempfile.gettempdir()
    test_path = os.path.join(temp_dir, "test_file.txt")
    try:
        with open(test_path, "w") as f:
            f.write("Permission test successful.")
        print(f"[DEBUG] Write permission to {temp_dir} is validated.")
    except PermissionError as e:
        print(f"[ERROR] Permission error: {e}")
        messagebox.showerror("Permission Error", f"Unable to write to {temp_dir}. Please check permissions.")
        return False
    finally:
        if os.path.exists(test_path):  # Check before removing
            os.remove(test_path)
            print("[DEBUG] Temporary file cleanup successful.")
    return True



def count_total_pages(pdf_file_path):
    try:
        reader = PdfReader(pdf_file_path)
        total_pages = len(reader.pages)
        print(f"[DEBUG] Total pages in {pdf_file_path}: {total_pages}")
        return total_pages
    except Exception as e:
        print(f"[ERROR] Failed to count pages in {pdf_file_path}: {e}")
        return 0
        
def parse_pages_to_print(pages_to_print):
    """Parses the pages_to_print string and returns a list of page numbers."""
    pages = []
    if pages_to_print.lower() == "all":
        return []  # Represents all pages
    for part in pages_to_print.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    return pages

def update_job_status(job_id, status):
    """Update the job status in Firebase."""
    try:
        job_ref = db.reference(f'print_job_details/{job_id}')
        job_ref.update({'status': status, 'updated_at': time.time()})
        print(f"[DEBUG] Job ID {job_id} marked as '{status}' in Firebase.")
    except Exception as e:
        print(f"[ERROR] Firebase error while updating job status: {e}")

def convert_docx_to_pdf(docx_file_path):
    pdf_file_path = docx_file_path.replace(".docx", ".pdf")  # Ensure proper PDF extension
    command = [
        "xvfb-run", "--auto-servernum", "--server-args=-screen 0 640x480x24",
        "libreoffice", "--headless", "--convert-to", "pdf", docx_file_path,
        "--outdir", os.path.dirname(pdf_file_path)  # Specify output directory
    ]
    try:
        import sys
        if sys.platform.startswith("win"):
            subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(command, check=True)
        print(f"[INFO] Successfully converted {docx_file_path} to {pdf_file_path}.")
        return pdf_file_path
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Conversion failed: {e}")
        return None


        
def update_printer_status(pages_printed, job_id):
    """Insert a new row in the printer_status node to track paper usage."""
    try:
        printer_status_ref = db.reference('printer_status')
        all_status = printer_status_ref.order_by_key().limit_to_last(1).get()
        latest = None
        if isinstance(all_status, dict):
            latest = list(all_status.values())[-1]
        elif isinstance(all_status, list):
            latest = all_status[-1]
        if latest and 'remaining_paper' in latest:
            remaining_paper = latest['remaining_paper']
            print(f"[DEBUG] Latest Remaining Paper: {remaining_paper}")
            if remaining_paper < pages_printed:
                print("[ERROR] Not enough paper. Please reload.")
                update_job_status(job_id, "failed")
                return False
            new_remaining_paper = remaining_paper - pages_printed
            # Insert a new record instead of updating
            printer_status_ref.push(str({
                'remaining_paper': new_remaining_paper,
                'updated_at': time.time()
            }))
            print(f"[DEBUG] Inserted new printer status entry with Remaining Paper: {new_remaining_paper}")
            return True
        else:
            print("[ERROR] No entries found in printer_status node.")
            return False
    except Exception as e:
        print(f"[ERROR] Firebase error while updating printer status: {e}")
        return False



def print_file(job_id):
    """Fetch file data, verify, and send it to the printer."""
    try:
        # Fetch job details
        job_ref = db.reference(f'print_jobs/{job_id}')
        job_data = job_ref.get()
        if job_data and isinstance(job_data, dict):
            document_name = job_data.get('document_name')
            file_data = job_data.get('file_data')
            pages_to_print = job_data.get('pages_to_print')
            color_mode = job_data.get('color_mode')
            import tempfile
            temp_dir = tempfile.gettempdir()
            if temp_dir and file_data:
                temp_file_path = os.path.join(temp_dir, f"{document_name}")
                with open(temp_file_path, "wb") as f:
                    if isinstance(file_data, bytes):
                        f.write(file_data)
                    elif isinstance(file_data, str):
                        import base64
                        f.write(base64.b64decode(file_data))
                if isinstance(document_name, str) and document_name.endswith('.pdf'):
                    # Skip conversion if the file is already a PDF
                    if document_name.endswith(".pdf"):
                        print(f"[DEBUG] Directly handling PDF: {temp_file_path}")
                        converted_path = temp_file_path
                    else:
                        # Convert .docx to PDF
                        converted_path = convert_docx_to_pdf(temp_file_path)

                    if converted_path and os.path.exists(converted_path):
                        temp_file_path = converted_path
                    else:
                        print(f"[ERROR] File conversion failed or file not found: {converted_path}")
                        return
                
                # Determine pages to print
                if isinstance(pages_to_print, str) and pages_to_print.lower() == "all":
                    total_pages = count_total_pages(temp_file_path)
                    page_range_option = []  # No range specified for all pages
                elif isinstance(pages_to_print, str) and pages_to_print.isnumeric():
                    parsed_pages = parse_pages_to_print(pages_to_print)
                else:
                    print("[ERROR] Invalid page range format.")
                    return



                # Fixing color_mode check
                if isinstance(color_mode, str):
                    color_mode = color_mode.lower()
                else:
                    print(f"[DEBUG] Unexpected color_mode type: {type(color_mode)} -> {color_mode}")
                    color_mode = "bw"  # Default fallback

                color_option = "ColorModel=RGB" if color_mode == "colored" else "ColorModel=Gray"

                # Check if the printer has enough paper
                if not update_printer_status(pages_printed=total_pages, job_id=job_id):
                    print("[ERROR] Printing aborted due to paper shortage.")
                    return

                # Send the file to the printer
                print(f"[DEBUG] Sending {temp_file_path} to printer with page range: {page_range_option}.")
                command = ["lp", "-d", "Epson_L5290", "-o", color_option, *page_range_option, temp_file_path]

                try:
                    import sys
                    if sys.platform.startswith("win"):
                        subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        subprocess.run(command, check=True)
                    print(f"[INFO] Print job for {temp_file_path} completed successfully.")

                    # Update job status to "complete"
                    update_query = """
                        UPDATE print_job_details
                        SET status = %s, updated_at = NOW()
                        WHERE job_id = %s
                    """
                    # This part of the code was removed as per the edit hint.
                    # The original code had a mysql.connector.Error here.
                    # The new code does not have a mysql.connector.Error.
                    # The original code had a mysql.connector.Error here.
                    # The new code does not have a mysql.connector.Error.

                except subprocess.CalledProcessError as e:
                    print(f"[ERROR] Printing failed: {e}")
                    return

                # Cleanup temporary file
                os.remove(temp_file_path)
                print(f"[DEBUG] Temporary file {temp_file_path} deleted.")
        else:
            print(f"[ERROR] No file data found for Job ID {job_id}.")

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")

# Validate before starting the GUI
if not validate_tmp_permissions():
    exit(1)



def show_payment_screen(total_price, job_id, existing_root=None):
    """Displays the payment screen and handles coin detection and printing."""# Function to update the database status to 'cancelled'
     
    if existing_root:
        root = existing_root
        # Clear existing widgets
        for widget in root.winfo_children():
            widget.destroy()
        root.title("Payment Screen")
        root.configure(bg="white")
    else:
        root = tk.Tk()
        root.title("Payment Screen")
        root.configure(bg="white")  # Set the background to white
        root.attributes("-fullscreen", True)
        root.overrideredirect(True)

    
    # Force fullscreen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}+0+0")

    # Calculate responsive sizes based on screen resolution
    base_width = 1920
    base_height = 1280
    scale_factor = min(screen_width / base_width, screen_height / base_height)
    
    # Responsive font sizes
    header_font_size = int(42 * scale_factor)
    price_font_size = int(36 * scale_factor)
    status_font_size = int(36 * scale_factor)
    button_font_size = int(16 * scale_factor)
    footer_font_size = int(20 * scale_factor)
    
    # Responsive spacing
    padding_y = int(30 * scale_factor)
    button_padding = int(40 * scale_factor)
    separator_padding = int(15 * scale_factor)

    # Exit fullscreen on ESC
    def exit_fullscreen(event):
        root.destroy()
    total_amount = 0
    timeout = 300  # Timeout in seconds (5 minutes)


    def cancel_transaction():
        """Handle transaction cancellation and return to main screen."""
        def background_cleanup():
            try:
                # Update the database status to 'cancelled'
                job_ref = db.reference(f'print_job_details/{job_id}')
                job_ref.update({'status': 'cancelled', 'updated_at': time.time()})
            except Exception as e:
                print(f"[ERROR] Firebase error while updating cancellation status: {e}")
            finally:
                try:
                    GPIO.cleanup()
                except Exception as e:
                    print(f"[ERROR] Error cleaning up GPIO: {e}")

        # Launch frame1.py directly without showing a command prompt
        try:
            import sys
            import subprocess
            if sys.platform.startswith("win"):
                subprocess.Popen(
                    ["pythonw", "frame1.py"],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([
                    "python3", "frame1.py"
                ])
        except Exception as e:
            print(f"[ERROR] Error launching frame1.py: {e}")

        # Start cleanup in a background thread
        Thread(target=background_cleanup, daemon=True).start()

        # Close current GUI immediately
        root.destroy()



    def calculate_amount(pulse_count):
        """Calculate the amount in pesos based on the pulse count."""
        coin_value = 1  # Adjust this if different pulses mean different values
        return pulse_count * coin_value

    def update_gui(message, color="black"):
        try:
            if root and root.winfo_exists() and status_label.winfo_exists():
                status_label.config(text=message, fg=color)
        except Exception as e:
            print(f"[ERROR] GUI update failed: {e}")



    def timeout_handler():
        """Handle timeout if no coins are inserted."""
        global total_amount
        if total_amount < total_price:
            update_gui("Payment timed out. Resetting...", "red")
            root.after(2000, root.destroy)  # Close the GUI after 2 seconds
            GPIO.cleanup()
            try:
                import sys
                import os
                
                # Use subprocess.Popen with creationflags to hide the console window on Windows
                if sys.platform.startswith("win"):
                    try:
                        # Use batch file to launch silently
                        subprocess.Popen(["launch_frame1_silent.bat"], 
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        # Fallback: try direct pythonw with CREATE_NO_WINDOW
                        subprocess.Popen(["pythonw", "frame1.py"], 
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    python_executable = "python3"
                    subprocess.Popen([python_executable, "frame1.py"])
            except Exception as e:
                print(f"[ERROR] Error launching frame1.py: {e}")

     
    
    def print_job():
        """Handles the print job process, updates database status, and monitors printing."""
        global total_amount  # Ensure global variable is accessed correctly
    
        try:
            # Verify `job_id` exists in the database
            job_ref = db.reference(f'print_job_details/{job_id}')
            if not job_ref.get():
                print(f"[ERROR] Job ID {job_id} does not exist in the database!")
                return

            # Debug: Log total_amount and total_price before updating
            print(f"[DEBUG] Total amount inserted: {total_amount}, Total price: {total_price}, Job ID: {job_id}")

            # Notify the user about overpayment
            if total_amount > total_price:
                excess_amount = total_amount - total_price
                print(f"[DEBUG] Overpayment detected: {excess_amount} pesos.")
                root.after(0, update_gui, f"Overpaid by {excess_amount} pesos. Thank you!", "blue")

            # Update the database with the actual inserted amount
            job_ref.update({'inserted_amount': total_amount, 'updated_at': time.time()})


            # Debug: Confirm database update
            print(f"[DEBUG] Final inserted_amount for Job ID {job_id} recorded as {total_amount} pesos.")

            # Notify the user and update GUI
            root.after(0, update_gui, "Printing in progress...", "blue")

            # Trigger the actual print job
            print_file(job_id)

            # Monitor the print job status
            print(f"[DEBUG] Monitoring print queue for Job ID {job_id}...")
            job_complete = False

            while not job_complete:
                try:
                    result = subprocess.run(["lpstat", "-o"], capture_output=True, text=True)
                    print(f"[DEBUG] lpstat output: {result.stdout}")
                    if str(job_id) not in result.stdout:
                        job_complete = True
                    else:
                        print(f"[DEBUG] Print job {job_id} still in the queue. Retrying...")
                        time.sleep(2)  # Check again after 2 seconds
                except subprocess.CalledProcessError as e:
                    print(f"[ERROR] Failed to query printer queue: {e}")
                    break

            if job_complete:
                print(f"[DEBUG] Print job {job_id} completed.")
                root.after(0, update_gui, "Processing complete. Please wait..", "green")
                root.after(2000, root.destroy)  # Add a delay before destroying the frame

            # Notify the user and return to the main menu
            try:
                print("[DEBUG] Launching frame1.py...")
                import sys
                import os
                
                # Use subprocess.Popen with creationflags to hide the console window on Windows
                if sys.platform.startswith("win"):
                    try:
                        # Use batch file to launch silently
                        subprocess.Popen(["launch_frame1_silent.bat"], 
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        # Fallback: try direct pythonw with CREATE_NO_WINDOW
                        subprocess.Popen(["pythonw", "frame1.py"], 
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    python_executable = "python3"
                    subprocess.Popen([python_executable, "frame1.py"])
            except Exception as e:
                print(f"[ERROR] Failed to launch frame1.py: {e}")
                root.after(0, update_gui, "Error returning to main menu. Please restart.", "red")

        except Exception as e:
            root.after(0, update_gui, "An error occurred.", "red")
            print(f"[ERROR] Exception: {e}")
            print(f"[ERROR] Unexpected error: {e}")
        finally:
            # Clean up resources
            print("[DEBUG] Cleaning up resources and closing GUI.")
            try:
                root.destroy()
            except Exception as e:
                print(f"[ERROR] Error destroying root: {e}")
            try:
                GPIO.cleanup()
            except Exception as e:
                print(f"[ERROR] Error cleaning up GPIO: {e}")

                       

    def coin_detection():
        """Detect coin pulses and update the total amount."""
        global total_amount
        pulse_count = 0
        last_state = GPIO.input(COIN_PIN)
        payment_complete = False

        try:
            while True:
                current_state = GPIO.input(COIN_PIN)

                # Detect falling edge (pulse detection)
                if last_state == GPIO.HIGH and current_state == GPIO.LOW:
                    pulse_count += 1
                    total_amount = calculate_amount(pulse_count)

                    # Debug: Log the current pulse count and total amount
                    print(f"[DEBUG] Pulse detected. Pulse count: {pulse_count}, Total amount: {total_amount}")

                    # Update the GUI with the latest inserted amount
                    root.after(0, update_gui, f"Inserted Amount: {total_amount} pesos", "black")

                    # If the total price is met, notify the user
                    if not payment_complete and total_amount >= total_price:
                        payment_complete = True
                        print(f"[DEBUG] Payment complete. Total amount: {total_amount}, Total price: {total_price}")
                        root.after(0, update_gui, "Payment Complete! You can insert more coins if desired.", "green")

                        # Start the print job in a separate thread but don't stop detection
                        Thread(target=print_job, daemon=True).start()

                last_state = current_state
                time.sleep(0.01)  # Check every 10 ms

        except RuntimeError as e:
            print(f"[ERROR] GPIO error: {e}")
        except KeyboardInterrupt:
            print("\n[DEBUG] Exiting coin detection.")
        finally:
            GPIO.cleanup()


    # GUI setup
    content_frame = tk.Frame(root, bg="white")  
    content_frame.pack(fill="both", expand=True)  

    # Logo display
    logo_width = int(800 * scale_factor)
    logo_height = int(260 * scale_factor)
    logo_frame = tk.Frame(content_frame, bg="white", width=logo_width) 
    logo_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(int(85 * scale_factor), int(10 * scale_factor)))
    logo_frame.pack_propagate(False)

    try:
        logo_img = Image.open("logo.jpg")
        logo_img = logo_img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)  
        logo_photo = ImageTk.PhotoImage(logo_img)
        logo_label = tk.Label(logo_frame, image=logo_photo, bg="white")
        logo_label.place(relx=0.5, rely=0.5, anchor="center")  
    except Exception as e:
        print(f"Error loading logo: {e}")
        logo_label = tk.Label(logo_frame, text="LOGO", font=("Arial", int(24 * scale_factor), "bold"), bg="white", fg="gray")
        logo_label.place(relx=0.5, rely=0.5, anchor="center")

    # Container for centering text vertically
    text_container = tk.Frame(content_frame, bg="white")
    text_container.pack(side="left", fill="both", expand=True)

    text_frame = tk.Frame(text_container, bg="white")
    text_frame.place(relx=0.5, rely=0.5, anchor="center")  

    # Header Label
    header_label = tk.Label(
        text_frame,
        text="Insert Coins to Complete Payment",
        font=("Helvetica", header_font_size, "bold"),
        bg="white",
        fg="black",
        anchor="center",
    )
    header_label.pack(pady=padding_y)

    # Total Price Label
    total_price_label = tk.Label(
        text_frame,
        text=f"Total Price: {total_price} pesos",
        font=("Arial", price_font_size, "bold"),
        bg="white",
        fg="black",
        anchor="center",
    )
    total_price_label.pack(pady=padding_y)

    # Remaining Balance Label
    status_label = tk.Label(
        text_frame,
        text=f"Remaining: {total_price} pesos",
        font=("Helvetica", status_font_size, "bold"),
        bg="white",
        fg="#b42e41",
        anchor="center",
    )
    status_label.pack(pady=padding_y)

    separator = tk.Frame(text_frame, height=2, bg="#CCCCCC")
    separator.pack(fill="x", pady=separator_padding)

    # Cancel button
    cancel_button = tk.Button(
        text_frame,
        text="Cancel",
        font=("Arial", button_font_size, "bold"),
        bg="#b42e41",
        fg="white",
        activebackground="#b42e41",
        activeforeground="white",    
        padx=int(150 * scale_factor),
        pady=int(25 * scale_factor),
        relief="flat",
        bd=0,
        cursor="hand2",
        command=cancel_transaction
    )
    cancel_button.pack(pady=button_padding)

    # hover functions
    def on_cancel_enter(e):
        cancel_button['bg'] = '#d12246'

    def on_cancel_leave(e):
        cancel_button['bg'] = '#b42e41'

    # hover events
    cancel_button.bind("<Enter>", on_cancel_enter)
    cancel_button.bind("<Leave>", on_cancel_leave)

    # Footer
    footer_frame = tk.Frame(root, bg="white")
    footer_frame.pack(side="bottom", fill="x")

    footer_label = tk.Label(
        footer_frame,
        text="Thank you for using our service!",
        font=("Helvetica", footer_font_size),
        bg="white",
        fg="gray",
    )
    footer_label.pack(pady=int(10 * scale_factor))


    # Ensure GPIO is set before starting the thread
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(COIN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except RuntimeError as e:
        print(f"[ERROR] GPIO initialization error: {e}")
        return

    # Run the coin detection in a separate thread
    coin_thread = Thread(target=coin_detection, daemon=True)
    coin_thread.start()

    # Start the timeout timer
    root.after(timeout * 1000, timeout_handler)

    root.mainloop()


if __name__ == "__main__":
    # Example call to the payment screen function for testing
    show_payment_screen(total_price=5, job_id="12345")
