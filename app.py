from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from math import ceil
from datetime import timedelta, datetime
# import mysql.connector  # Commented out for Firebase migration
import os
from flask import make_response

import firebase_admin
from firebase_admin import credentials, db
from werkzeug.utils import secure_filename
# from firebase_admin import storage # Removed as per edit hint

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from flask import send_file
from reportlab.lib.colors import HexColor
import json


# Initialize Flask app and Bcrypt for password hashing
app = Flask(__name__)
bcrypt = Bcrypt(app)


# Secret key for session management
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(days=7)

# --- Firebase Initialization ---
FIREBASE_CRED_PATH = os.path.join(os.path.dirname(__file__), 'firebase_service_account.json')
FIREBASE_DB_URL = 'https://printech-bd2ca-default-rtdb.asia-southeast1.firebasedatabase.app/'

# Support loading service account from environment variable for deployment
if os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'):
    service_account_info = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_JSON'])
    cred = credentials.Certificate(service_account_info)
else:
    cred = credentials.Certificate(FIREBASE_CRED_PATH)

firebase_admin.initialize_app(cred, {
    'databaseURL': FIREBASE_DB_URL
})

# --- Firebase Storage Initialization ---
# (Removed: No Firebase Storage needed for local file saving)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_total_pages(file_path):
    try:
        if file_path.lower().endswith('.pdf'):
            import fitz
            with fitz.open(file_path) as pdf:
                return pdf.page_count
        elif file_path.lower().endswith(('.doc', '.docx')):
            from docx import Document
            doc = Document(file_path)
            total_characters = sum(len(p.text) for p in doc.paragraphs)
            average_chars_per_page = 1500
            return max(1, total_characters // average_chars_per_page)
        return "N/A"
    except Exception as e:
        print(f"Error processing file: {e}")
        return None

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
            if not os.path.exists(uploads_dir):
                os.makedirs(uploads_dir)
            local_path = os.path.join(uploads_dir, filename)
            file.save(local_path)
            file_size = os.path.getsize(local_path)
            total_pages = get_total_pages(local_path)
            if total_pages is None:
                os.remove(local_path)
                flash('Error processing the file.', 'danger')
                return redirect(request.url)
            # Store metadata in Firebase Realtime Database
            jobs_ref = db.reference('print_jobs')
            job_data = {
                'file_name': filename,
                'file_size': file_size,
                'total_pages': total_pages,
                'status': 'pending',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'local_path': local_path,
                'details': [
                    {
                        'file_name': filename,
                        'pages_to_print': total_pages,
                        'color_mode': '',
                        'total_price': 0,
                        'inserted_amount': 0,
                        'status': 'pending',
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'local_path': local_path
                    }
                ]
            }
            new_job = jobs_ref.push(job_data)
            return render_template('uploaded_file.html', filename=filename, file_size=file_size, total_pages=total_pages)
        else:
            flash('Invalid file type. Please upload a .doc, .docx, or .pdf file.', 'danger')
            return redirect(request.url)
    return render_template('index.html')

# --- MySQL connection (commented out) ---
# connection = mysql.connector.connect(
#     host="mydatabase.cziagw6u0a1u.ap-southeast-2.rds.amazonaws.com",
#     user="admin",
#     password="paperazzi",
#     database="paperazzi"
# )

@app.route('/generate_report', methods=['GET'])
def generate_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Firebase query to fetch report data
    report_ref = db.reference('print_jobs')
    report_data = report_ref.order_by_child('created_at').start_at(start_date).end_at(end_date).get()

    # Transform report_data to a list of dictionaries
    report_list = []
    if report_data:
        for job_id, job_details in report_data.items():
            for detail in job_details.get('details', []):
                if detail.get('status') == 'complete':
                    report_list.append({
                        'file_name': detail.get('file_name', ''),
                        'color_mode': detail.get('color_mode', ''),
                        'total_price': float(detail.get('total_price', 0)),
                        'created_at': job_details.get('created_at', '')
                    })

    # Fetch summary metrics from the transformed report_list
    total_jobs = len(report_list)
    total_revenue = sum(item['total_price'] for item in report_list)
    color_revenue = sum(item['total_price'] for item in report_list if item['color_mode'] == 'colored')
    bw_revenue = sum(item['total_price'] for item in report_list if item['color_mode'] == 'bw')

    summary = {
        'total_jobs': total_jobs,
        'total_revenue': total_revenue,
        'color_revenue': color_revenue,
        'bw_revenue': bw_revenue
    }

    #pdf
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        topMargin=20,  # Reduce top margin
        leftMargin=20,
        rightMargin=20,
        bottomMargin=20
    )
    elements = []

    styles = getSampleStyleSheet()
    normal_style = styles['Normal']

    # Header Section with Logo and Title
    logo_path = os.path.join(app.static_folder, "logo.jpg")
    header_table_data = []
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=80, height=80)
        header_table_data.append([
            logo,
            Paragraph(
                "<strong>Paperazzi: Coin Operated Printing Machine Sales Report</strong><br/>Cavite State University - Imus Campus",
                normal_style
            )
        ])

    header_table = Table(header_table_data, colWidths=[100, 400])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))  # Reduce spacer size here


    # Summary Section
    summary_data = [
        ["Summary", ""],
        ["Total Completed Jobs", summary["total_jobs"]],
        ["Total Revenue (PHP)", f"{summary['total_revenue']:.2f}"],
        ["Color Revenue (PHP)", f"{summary['color_revenue']:.2f}"],
        ["Black & White Revenue (PHP)", f"{summary['bw_revenue']:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#ff294f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Detailed Table
    table_data = [["Date", "File Name", "Color Mode", "Total Price (PHP)"]]
    for row in report_list:
        # If created_at is a string, just use it; otherwise, format as needed
        created_at = row["created_at"]
        if isinstance(created_at, datetime):
            created_at_str = created_at.strftime("%Y-%m-%d")
        else:
            created_at_str = str(created_at)[:10]
        table_data.append([
            created_at_str,
            row["file_name"],
            row["color_mode"].capitalize(),
            f"{row['total_price']:.2f}"
        ])

    detail_table = Table(table_data, colWidths=[100, 250, 100, 100])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#ff294f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(detail_table)

    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"Sales_Report_{start_date}_to_{end_date}.pdf")


# Signup Page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # --- MySQL code commented out ---
        # cursor = connection.cursor()
        # try:
        #     cursor.execute("""
        #         INSERT INTO admins (username, email, password_hash) 
        #         VALUES (%s, %s, %s)
        #     """, (username, email, hashed_password))
        #     connection.commit()
        #     flash('Account created successfully. Please log in.', 'success')
        #     return redirect(url_for('login'))
        # except mysql.connector.Error as err:
        #     flash(f'Error: {err}', 'danger')
        # finally:
        #     cursor.close()

        # --- Firebase version ---
        admins_ref = db.reference('admins')
        # Check if email already exists
        existing_admins = admins_ref.order_by_child('email').equal_to(email).get()
        if existing_admins:
            flash('Email already registered.', 'danger')
            return render_template('signup.html')
        new_admin = admins_ref.push({
            'username': username,
            'email': email,
            'password_hash': hashed_password
        })
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # --- MySQL code commented out ---
        # cursor = connection.cursor(dictionary=True)
        # cursor.execute("SELECT * FROM admins WHERE email = %s", (email,))
        # admin = cursor.fetchone()
        # cursor.close()

        # --- Firebase version ---
        admins_ref = db.reference('admins')
        admins = admins_ref.order_by_child('email').equal_to(email).get()
        admin = None
        admin_id = None
        for key, value in admins.items() if admins else []:
            admin = value
            admin_id = key
            break

        if admin and bcrypt.check_password_hash(admin['password_hash'], password):
            session.permanent = True
            session['admin_id'] = admin_id
            session['username'] = admin['username']
            flash(f'Welcome back, {admin["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')


# Logout
@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    if 'admin_id' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    admin_username = session.get('username')
    todays_page = int(request.args.get('todays_page', 1))  # Default to page 1
    jobs_per_page = 10

    # --- MySQL code commented out ---
    # try:
    #     cursor = connection.cursor(dictionary=True)
    #     ... MySQL queries ...
    # except mysql.connector.Error as err:
    #     return f"Error: {err}"

    # --- Firebase version ---
    try:
        # Fetch all print jobs
        jobs_ref = db.reference('print_jobs')
        all_jobs = jobs_ref.get() or {}

        # Total print jobs
        total_jobs = len(all_jobs)

        # Fetch remaining paper and last refilled time
        printer_status_ref = db.reference('printer_status')
        printer_statuses = printer_status_ref.order_by_child('updated_at').get()
        printer_status_list = list(printer_statuses.values()) if printer_statuses else []
        if printer_status_list:
            latest_status = sorted(printer_status_list, key=lambda x: x.get('updated_at', ''), reverse=True)[0]
            remaining_paper = latest_status.get('remaining_paper', 0)
            last_refilled = latest_status.get('updated_at', 'N/A')
            if isinstance(last_refilled, str) and last_refilled != 'N/A':
                try:
                    last_refilled = datetime.strptime(last_refilled, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
                except Exception:
                    pass
        else:
            remaining_paper = 0
            last_refilled = 'N/A'

        # Today's completed jobs and sales
        today_str = datetime.now().strftime('%Y-%m-%d')
        todays_completed_jobs = 0
        todays_total_sales = 0.0
        todays_jobs_count = 0
        todays_jobs = []

        for job_id, job in all_jobs.items():
            created_at = job.get('created_at', '')
            created_date = created_at[:10] if created_at else ''
            if created_date == today_str:
                todays_jobs_count += 1
                for detail in job.get('details', []):
                    if detail.get('status') == 'complete':
                        todays_completed_jobs += 1
                        todays_total_sales += float(detail.get('total_price', 0))
                # For pagination
                for detail in job.get('details', []):
                    job_row = {
                        'job_id': job_id,
                        'file_name': detail.get('file_name', ''),
                        'pages_to_print': detail.get('pages_to_print', 0),
                        'color_mode': detail.get('color_mode', ''),
                        'total_price': detail.get('total_price', 0),
                        'inserted_amount': detail.get('inserted_amount', 0),
                        'status': detail.get('status', ''),
                        'created_at': created_at
                    }
                    todays_jobs.append(job_row)

        # Pagination
        todays_total_pages = (todays_jobs_count + jobs_per_page - 1) // jobs_per_page
        offset = (todays_page - 1) * jobs_per_page
        todays_jobs_paginated = todays_jobs[offset:offset + jobs_per_page]

        # Fetch printing prices
        prices_ref = db.reference('print_prices')
        prices_data = prices_ref.order_by_child('updated_at').get()
        prices_list = list(prices_data.values()) if prices_data else []
        if prices_list:
            latest_price = sorted(prices_list, key=lambda x: x.get('updated_at', ''), reverse=True)[0]
            black_price = latest_price.get('black_price', 3)
            color_price = latest_price.get('color_price', 5)
        else:
            black_price, color_price = 3, 5  # Default prices

        # Render the dashboard template with all data
        return render_template(
            'dashboard.html',
            admin_username=admin_username,
            total_jobs=total_jobs,
            remaining_paper=remaining_paper,
            last_refilled=last_refilled,
            todays_completed_jobs=todays_completed_jobs,
            todays_total_sales=todays_total_sales,
            todays_jobs=todays_jobs_paginated,
            todays_page=todays_page,
            todays_total_pages=todays_total_pages,
            black_price=black_price,
            color_price=color_price
        )
    except Exception as err:
        return f"Error: {err}"

@app.route('/update_prices', methods=['POST'])
def update_prices():
    if 'admin_id' not in session:
        flash('Please log in to update prices.', 'warning')
        return redirect(url_for('login'))

    black_price = request.form.get('black_price', type=float)
    color_price = request.form.get('color_price', type=float)

    # --- MySQL code commented out ---
    # try:
    #     cursor = connection.cursor()
    #     cursor.execute("""
    #         INSERT INTO print_prices (black_price, color_price) 
    #         VALUES (%s, %s)
    #     """, (black_price, color_price))
    #     connection.commit()
    #     flash('Prices updated successfully.', 'success')
    # except mysql.connector.Error as err:
    #     flash(f"Error updating prices: {err}", 'danger')
    # return redirect(url_for('dashboard'))

    # --- Firebase version ---
    try:
        prices_ref = db.reference('print_prices')
        prices_ref.push({
            'black_price': black_price,
            'color_price': color_price,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        flash('Prices updated successfully.', 'success')
    except Exception as err:
        flash(f"Error updating prices: {err}", 'danger')
    return redirect(url_for('dashboard'))

@app.route('/jobs')
def jobs():
    # --- MySQL code commented out ---
    # try:
    #     cursor = connection.cursor(dictionary=True)
    #     ... MySQL queries ...
    # except mysql.connector.Error as err:
    #     return f"Error: {err}"

    # --- Firebase version ---
    try:
        # Get the month filter from query parameters
        selected_month = request.args.get('month')
        filter_month = selected_month if selected_month else None

        # Fetch all print jobs
        jobs_ref = db.reference('print_jobs')
        all_jobs = jobs_ref.get() or {}

        # Prepare job details
        job_details = []
        for job_id, job in all_jobs.items():
            created_at = job.get('created_at', '')
            created_month = created_at[:7] if created_at else ''
            if filter_month and created_month != filter_month:
                continue
            for detail in job.get('details', []):
                job_details.append({
                    'id': detail.get('id', ''),
                    'job_id': job_id,
                    'file_name': detail.get('file_name', ''),
                    'status': detail.get('status', ''),
                    'created_at': created_at,
                    'pages_to_print': detail.get('pages_to_print', 0),
                    'color_mode': detail.get('color_mode', ''),
                    'total_price': float(detail.get('total_price', 0)),
                    'inserted_amount': float(detail.get('inserted_amount', 0)),
                    'total_pages': detail.get('total_pages', 0)
                })

        # Total jobs (regardless of status)
        total_jobs = len(job_details)

        # Total sales (only for completed jobs)
        total_sales = sum(j['total_price'] for j in job_details if j['status'] == 'complete')

        # Completed and cancelled jobs
        completed_jobs = sum(1 for j in job_details if j['status'] == 'complete')
        cancelled_jobs = sum(1 for j in job_details if j['status'] == 'cancelled')

        # Revenue breakdown
        color_revenue = sum(j['total_price'] for j in job_details if j['color_mode'] == 'colored' and j['status'] == 'complete')
        bw_revenue = sum(j['total_price'] for j in job_details if j['color_mode'] == 'bw' and j['status'] == 'complete')

        total_revenue = color_revenue + bw_revenue
        color_percentage = (color_revenue / total_revenue * 100) if total_revenue > 0 else 0
        bw_percentage = (bw_revenue / total_revenue * 100) if total_revenue > 0 else 0

        # Pagination
        rows_per_page = 10
        page = int(request.args.get('page', 1))
        offset = (page - 1) * rows_per_page
        total_records = total_jobs
        total_pages = ceil(total_records / rows_per_page)
        print_jobs = job_details[offset:offset + rows_per_page]

        # Job trends (number of jobs by date)
        job_trends_dict = {}
        for j in job_details:
            job_date = j['created_at'][:10] if j['created_at'] else ''
            if job_date:
                job_trends_dict[job_date] = job_trends_dict.get(job_date, 0) + 1
        job_trend_dates = sorted(job_trends_dict.keys())
        job_trend_counts = [job_trends_dict[date] for date in job_trend_dates]

        # Pagination range logic
        pagination_range = 5
        start_page = max(1, page - pagination_range // 2)
        end_page = min(total_pages, start_page + pagination_range - 1)
        if end_page - start_page < pagination_range:
            start_page = max(1, end_page - pagination_range + 1)

        return render_template(
            'jobs.html',
            total_jobs=total_jobs,
            total_sales=total_sales,
            completed_jobs=completed_jobs,
            cancelled_jobs=cancelled_jobs,
            color_revenue=color_revenue,
            bw_revenue=bw_revenue,
            color_percentage=color_percentage,
            bw_percentage=bw_percentage,
            print_jobs=print_jobs,
            page=page,
            total_pages=total_pages,
            start_page=start_page,
            end_page=end_page,
            selected_month=selected_month,
            job_trend_dates=job_trend_dates,
            job_trend_counts=job_trend_counts
        )

    except Exception as err:
        return f"Error: {err}"




@app.route('/update_remaining_paper', methods=['POST'])
def update_remaining_paper():
    # --- MySQL code commented out ---
    # try:
    #     # Get the new paper count from the form
    #     new_remaining_paper = int(request.form['new_remaining_paper'])
    #     # Update the database
    #     cursor = connection.cursor(dictionary=True)  # Use dictionary cursor
    #     cursor.execute("""
    #         INSERT INTO printer_status (remaining_paper, updated_at) 
    #         VALUES (%s, NOW())
    #     """, (new_remaining_paper,))
    #     connection.commit()
    #     cursor.execute("""
    #         SELECT updated_at 
    #         FROM printer_status 
    #         WHERE refill = TRUE 
    #         ORDER BY updated_at DESC 
    #         LIMIT 1
    #     """)
    #     last_refilled_row = cursor.fetchone()
    #     if last_refilled_row:
    #         last_refilled = last_refilled_row['updated_at'].strftime('%B %d, %Y')
    #     else:
    #         last_refilled = 'N/A'
    #     flash(f"Paper count updated successfully. Last refilled: {last_refilled}", 'success')
    #     return redirect(url_for('dashboard'))
    # except mysql.connector.Error as err:
    #     return f"Error: {err}"

    # --- Firebase version ---
    try:
        new_remaining_paper = int(request.form['new_remaining_paper'])
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        printer_status_ref = db.reference('printer_status')
        printer_status_ref.push({
            'remaining_paper': new_remaining_paper,
            'updated_at': now_str,
            'refill': True
        })

        # Get last refilled time
        statuses = printer_status_ref.order_by_child('updated_at').get()
        last_refilled = 'N/A'
        if statuses:
            refill_statuses = [s for s in statuses.values() if s.get('refill')]
            if refill_statuses:
                last_refilled_time = sorted(refill_statuses, key=lambda x: x.get('updated_at', ''), reverse=True)[0].get('updated_at', '')
                if last_refilled_time:
                    try:
                        last_refilled = datetime.strptime(last_refilled_time, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
                    except Exception:
                        last_refilled = last_refilled_time
        flash(f"Paper count updated successfully. Last refilled: {last_refilled}", 'success')
        return redirect(url_for('dashboard'))
    except Exception as err:
        return f"Error: {err}"


@app.before_request
def require_login():
    allowed_routes = ['login', 'signup', 'logout', 'static']
    if request.endpoint not in allowed_routes and 'admin_id' not in session:
        flash('You must log in to access this page.', 'danger')
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)

# Install the required packages
# pip install flask flask-bcrypt firebase-admin reportlab
