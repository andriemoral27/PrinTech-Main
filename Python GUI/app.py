from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import os
import fitz  # PyMuPDF for PDF processing
from docx import Document  # For handling Word documents
import subprocess
import qrcode
import base64
from firebase_config import db

# Flask application setup
app = Flask(__name__)
socketio = SocketIO(app)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'doc', 'docx', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_total_pages(file_path):
    try:
        if file_path.lower().endswith('.pdf'):
            with fitz.open(file_path) as pdf:
                return pdf.page_count
        elif file_path.lower().endswith(('.doc', '.docx')):
            doc = Document(file_path)
            total_characters = sum(len(p.text) for p in doc.paragraphs)
            average_chars_per_page = 1500
            return max(1, total_characters // average_chars_per_page)
        return "N/A"
    except Exception as e:
        print(f"Error processing file: {e}")
        return None

# Ensure 'uploads' directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']
    
    if file and allowed_file(file.filename):
        filename = file.filename
        file_path = os.path.join('uploads', filename)
        file.save(file_path)

        file_size = os.path.getsize(file_path)
        total_pages = get_total_pages(file_path)

        if total_pages is None:
            os.remove(file_path)
            return "Error processing the file.", 500

        try:
            # Insert file info into Firebase with status 'pending'
            ref = db.reference('print_jobs')
            with open(file_path, 'rb') as f:
                file_data = base64.b64encode(f.read()).decode('utf-8')
            new_job = ref.push({
                'document_name': filename,
                'document_size': file_size,
                'file_data': file_data,
                'status': 'pending',
                'total_pages': total_pages
            })
            job_id = new_job.key

            # Notify the kiosk in real-time about the status
            socketio.emit('file_uploaded', {
                'file_name': filename,
                'file_path': file_path,
                'total_pages': total_pages,
                'job_id': job_id
            })

            return render_template('uploaded_file.html', filename=filename, file_size=file_size, total_pages=total_pages)
        except Exception as e:
            print(f"Error: {e}")
            socketio.emit('file_status_update', {'document_name': filename, 'status': 'failed'})
            return f"Error processing file: {e}", 500
        finally:
            os.remove(file_path)

    return "Invalid file type. Please upload a .doc, .docx, or .pdf file."

@app.route('/generate_wifi_qr')
def generate_wifi_qr():
    ssid = "YourSSID"
    password = "YourPassword"

    wifi_config = f"WIFI:S:{ssid};T:WPA;P:{password};;"
    qr = qrcode.QRCode()
    qr.add_data(wifi_config)
    qr.make(fit=True)

    img = qr.make_image(fill="black", back_color="white")
    qr_code_path = os.path.join('static', 'wifi_qr_code.png')
    img.save(qr_code_path)
    
    return render_template('wifi_qr.html', qr_code_path=qr_code_path)

@app.teardown_appcontext
def close_db_connection(exception):
    pass  # No persistent connection to close with Firebase

@socketio.on('update_status')
def update_status(data):
    document_name = data['document_name']
    status = data['status']

    # Find the job by document_name and update status
    jobs_ref = db.reference('print_jobs')
    jobs = jobs_ref.order_by_child('document_name').equal_to(document_name).get()
    if jobs:
        for job_id, job in jobs.items():
            jobs_ref.child(job_id).update({'status': status})
            socketio.emit('status_update', {'document_name': document_name, 'status': status})
            break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
