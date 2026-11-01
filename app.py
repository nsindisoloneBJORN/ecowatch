from datetime import datetime, timedelta
import csv
import io
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify, current_app
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
import mysql.connector
import random
import os
import math
from werkzeug.utils import secure_filename
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import requests

app = Flask(__name__)
app.secret_key = 'ecowatch_secret_key'
bcrypt = Bcrypt(app)

# --- Flask-Mail Configuration ---
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nsindisothabede09@gmail.com'
app.config['MAIL_PASSWORD'] = 'ziesdjxljhghoakg'
mail = Mail(app)

# Allowed extensions for safety against invalid file uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database Connection Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'admin123',
    'database': 'ecowatch_db',
    'auth_plugin': 'mysql_native_password'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# --- Helper Function for Asynchronous/Safe Email Dispatch ---
def send_resident_email(to_email, subject, body_text):
    try:
        msg = Message(
            subject=f"EcoWatch - {subject}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[to_email]
        )
        msg.body = body_text
        mail.send(msg)
    except Exception as e:
        print(f"Resident email dispatch warning (non-fatal): {e}")

# --- Helper Function: Full Administrator Notification & Email Dispatch ---
def dispatch_administrator_notification(title, message, report_id=None, send_email=False, is_urgent=False):
    """
    Inserts an in-app notification for full administrators into MySQL and dynamically dispatches emails to all registered administrators.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        
        # 1. Insert into MySQL notifications table for full administrator role
        query = """
            INSERT INTO notifications (recipient_role, report_id, title, message, type)
            VALUES ('administrator', %s, %s, %s, %s)
        """
        alert_type = 'sla_breach' if is_urgent else 'new_report'
        cursor.execute(query, (report_id, title, message, alert_type))
        connection.commit()
        
        # 2. Dispatch Email to all active Full Administrators if flagged
        if send_email:
            cursor.execute("SELECT email FROM staff WHERE role = 'Administrator' AND is_verified = 1")
            admin_staff = cursor.fetchall()
            
            admin_emails = [admin['email'] for admin in admin_staff if admin.get('email')]
            
            # Fallback recipient if no admin emails found in staff table
            if not admin_emails:
                admin_emails = ["admin@ecowatch.gov.za"]
                
            if admin_emails:
                msg = Message(
                    subject=f"[EcoWatch Administrator Alert] {title}",
                    sender=app.config['MAIL_USERNAME'],
                    recipients=admin_emails,
                    body=f"Hello Administrator,\n\n{message}\n\nReport Reference ID: {report_id}\n\nPlease log in to the EcoWatch Administrator Portal to review and take action."
                )
                mail.send(msg)
            
    except Exception as e:
        print(f"Error dispatching full administrator notification: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# --- Background Worker for Slow Tasks (Geocoding & Emails) ---
def background_report_tasks(app_instance, user_id, report_id, issue_type, lat, lon, initial_location):
    with app_instance.app_context():
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        try:
            resolved_location = initial_location or "Unknown Location"
            
            # 1. Perform slow Nominatim reverse-geocoding API call asynchronously in background
            if lat is not None and lon is not None:
                try:
                    url = f'https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1'
                    headers = {'User-Agent': 'EcoWatchApp/1.0'}
                    response = requests.get(url, timeout=4, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        display_name = data.get('display_name')
                        if display_name:
                            resolved_location = display_name
                            
                            # Update report location in DB once reverse geocoding succeeds
                            cursor.execute(
                                "UPDATE reports SET location = %s WHERE report_id = %s",
                                (resolved_location, report_id)
                            )
                            connection.commit()
                except Exception as geo_err:
                    print(f"Background geocoding warning (non-fatal): {geo_err}")

            # 2. Send Report Confirmation Email strictly to the RESIDENT who submitted it
            cursor.execute("SELECT email, name FROM users WHERE id = %s", (user_id,))
            resident_record = cursor.fetchone()
            if resident_record and resident_record.get('email'):
                ticket_msg = (
                    f"Hello {resident_record['name']},\n\n"
                    f"Your waste incident report has been successfully logged with EcoWatch.\n\n"
                    f"TICKET DETAILS:\n"
                    f"-----------------------------------\n"
                    f"Ticket Reference: {report_id}\n"
                    f"Category: {issue_type}\n"
                    f"Location: {resolved_location}\n"
                    f"Current Status: Pending Review\n"
                    f"-----------------------------------\n\n"
                    "Our municipal team will review your report and dispatch a cleanup crew shortly. "
                    "You can view real-time updates on your EcoWatch dashboard anytime.\n\n"
                    "Thank you for helping keep our environment clean!\n\n"
                    "EcoWatch Waste Management"
                )
                send_resident_email(resident_record['email'], f"Report Received [Ticket {report_id}]", ticket_msg)

            # 3. Send Alert Email strictly to active Full ADMINISTRATORS
            cursor.execute("SELECT email FROM staff WHERE role = 'Administrator' AND is_verified = 1")
            admin_staff = cursor.fetchall()
            admin_emails = [admin['email'] for admin in admin_staff if admin.get('email')]
            if not admin_emails:
                admin_emails = ["admin@ecowatch.gov.za"]
                
            admin_alert_title = f"New {issue_type} Reported"
            admin_alert_msg = f"A new report ({report_id}) has been logged for {resolved_location}. Awaiting crew assignment."
            
            if admin_emails:
                msg = Message(
                    subject=f"[EcoWatch Administrator Alert] {admin_alert_title}",
                    sender=app.config['MAIL_USERNAME'],
                    recipients=admin_emails,
                    body=f"Hello Administrator,\n\n{admin_alert_msg}\n\nReport Reference ID: {report_id}\n\nPlease log in to the EcoWatch Administrator Portal to review and take action."
                )
                mail.send(msg)

        except Exception as e:
            print(f"Background task warning (non-fatal): {e}")
        finally:
            cursor.close()
            connection.close()

# --- EXIF GPS Extraction Helper Function (Crash-Proof) ---
def get_image_coordinates(image_path):
    try:
        if not os.path.exists(image_path):
            return None, None
            
        image = Image.open(image_path)
        exif_data = image._getexif()

        if not exif_data:
            return None, None

        gps_info = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == 'GPSInfo':
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    gps_info[sub_tag] = value[t]

        if not gps_info or 'GPSLatitude' not in gps_info or 'GPSLongitude' not in gps_info:
            return None, None

        def convert_to_degrees(value):
            try:
                d, m, s = value
                return float(d) + (float(m) / 60.0) + (float(s) / 3600.0)
            except Exception:
                return 0.0

        lat = convert_to_degrees(gps_info['GPSLatitude'])
        if gps_info.get('GPSLatitudeRef', 'N') != 'N':
            lat = -lat

        lon = convert_to_degrees(gps_info['GPSLongitude'])
        if gps_info.get('GPSLongitudeRef', 'E') != 'E':
            lon = -lon

        return lat, lon
    except Exception as e:
        print(f'Safe EXIF warning (non-fatal): {e}')
        return None, None

@app.route('/', methods=['GET', 'POST'])
def home():
    error = None
    if request.method == 'POST':
        identifier = request.form.get('staff_id') or request.form.get('email') or request.form.get('contact_detail')
        password = request.form.get('password')
        role = request.form.get('role')

        if not identifier or not password or not role:
            return render_template('index.html', error="All fields are required.")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)

        try:
            if role in ['Administrator', 'Cleanup Crew']:
                cursor.execute("SELECT * FROM staff WHERE staff_id = %s OR email = %s", (identifier, identifier))
                staff_member = cursor.fetchone()

                if staff_member:
                    db_role = str(staff_member.get('role', '')).strip().title()
                    db_password = staff_member['password']
                    
                    password_matches = False
                    try:
                        if bcrypt.check_password_hash(db_password, password):
                            password_matches = True
                    except Exception:
                        pass
                    
                    if not password_matches and db_password == password:
                        password_matches = True

                    if db_role != role:
                        error = "Role selected does not match your credentials, please reselect and try again"
                    elif password_matches:
                        if staff_member.get('is_verified', 0) == 0:
                            session['pending_staff_email'] = staff_member['email']
                            flash('Your staff account is not yet verified. Please enter your verification OTP.', 'warning')
                            return redirect(url_for('verify_staff_otp'))

                        session['staff_name'] = staff_member['name']
                        session['staff_id'] = staff_member.get('staff_id')
                        if db_role == 'Administrator':
                            return redirect(url_for('adminPortal'))
                        elif db_role == 'Cleanup Crew':
                            return redirect(url_for('crewPortal'))
                    else:
                        error = "Credentials entered are wrong, please try again!"
                else:
                    error = "Credentials entered are wrong, please try again!"

            else:
                cursor.execute("SELECT * FROM users WHERE email = %s OR phone = %s", (identifier, identifier))
                user = cursor.fetchone()

                if user:
                    db_password = user['password']
                    
                    password_matches = False
                    try:
                        if bcrypt.check_password_hash(db_password, password):
                            password_matches = True
                    except Exception:
                        pass
                        
                    if not password_matches and db_password == password:
                        password_matches = True

                    if role != 'Resident':
                        error = "role selected does not match your credentials, please reselect and try again"
                    elif password_matches:
                        if user.get('is_verified', 0) == 0:
                            session['pending_email'] = user['email']
                            flash('Your resident account is not yet verified. Please enter your verification OTP.', 'warning')
                            return redirect(url_for('verify'))

                        session['user_name'] = f"{user['name']} {user['surname']}"
                        session['user_id'] = user['id']
                        return redirect(url_for('residentPortal'))
                    else:
                        error = "Credentials entered are wrong, please try again!"
                else:
                    error = "Credentials entered are wrong, please try again!"

        except Exception as db_err:
            print(f"Database login error: {db_err}")
            error = "A system error occurred during login. Please try again."
        finally:
            cursor.close()
            connection.close()

    return render_template('index.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    connection = None
    cursor = None
    if request.method == 'POST':
        name = request.form.get('name')
        surname = request.form.get('surname')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not name or not surname or not email or not password:
            return "All required fields must be filled!"

        if password != confirm_password:
            return "Passwords do not match! Please go back and try again."

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        otp_code = str(random.randint(100000, 999999))
        otp_expiry = datetime.now() + timedelta(minutes=10)

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            
            cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                if existing_user['is_verified'] == 1:
                    return "Account already exists and is verified. Please log in."
                else:
                    cursor.execute("""
                        UPDATE users 
                        SET verification_code = %s, otp_expiry = %s, password = %s, name = %s, surname = %s, phone = %s 
                        WHERE email = %s
                    """, (otp_code, otp_expiry, hashed_password, name, surname, phone, email))
                    connection.commit()
                    
                    session['pending_email'] = email
                    return redirect(url_for('verify'))

            cursor.execute(
                """INSERT INTO users (name, surname, email, phone, password, verification_code, otp_expiry, is_verified) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 0)""",
                (name, surname, email, phone, hashed_password, otp_code, otp_expiry)
            )
            connection.commit()
            
            try:
                msg = Message('EcoWatch Registration OTP',
                              sender='nsindisothabede09@gmail.com', recipients=[email])
                msg.body = f'Your EcoWatch verification code is: {otp_code}\nThis code expires in 10 minutes.'
                mail.send(msg)
            except Exception as mail_err:
                print(f"Mail dispatch skipped safely: {mail_err}")
                
            session['pending_email'] = email
            return redirect(url_for('verify'))

        except Exception as e:
            print(f"Registration Error: {e}")
            return f"Registration Error occurred. Please try again."
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template('register.html')

@app.route('/verify', methods=['GET', 'POST'])
@app.route('/verify-otp', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        email = session.get('pending_email')

        if not email:
            return "Session expired. Please register again."

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        
        try:
            cursor.execute("SELECT id, verification_code, otp_expiry, name, surname FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user:
                stored_otp = user.get('verification_code')
                otp_expiry = user.get('otp_expiry')

                if str(stored_otp) == str(entered_otp) and (otp_expiry is None or datetime.now() <= otp_expiry):
                    cursor.execute("""
                        UPDATE users 
                        SET is_verified = 1, verification_code = NULL, otp_expiry = NULL 
                        WHERE email = %s
                    """, (email,))
                    connection.commit()

                    session['user_id'] = user['id']
                    session['user_name'] = f"{user['name']} {user['surname']}"
                    session.pop('pending_email', None)
                    session['just_registered'] = True

                    welcome_msg = (
                        f"Hello {user['name']},\n\n"
                        "Welcome to EcoWatch!\n\n"
                        "Your resident account has been successfully verified. You can now log waste incident reports "
                        "and track cleanup progress directly from your dashboard.\n\n"
                        "Thank you for helping keep our community clean!\n\n"
                        "Kind regards,\n"
                        "EcoWatch Waste Management Team"
                    )
                    send_resident_email(email, "Account Verified Successfully", welcome_msg)

                    return redirect(url_for('verify'))
                else:
                    flash('Invalid or expired OTP code. Please try again.', 'danger')
            else:
                flash('User not found.', 'danger')
        except Exception as e:
            print(f"Verification error: {e}")
        finally:
            cursor.close()
            connection.close()

    show_modal = session.pop('just_registered', False)
    return render_template('verifyOtp.html', show_registration_modal=show_modal)

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('pending_email')
    if not email:
        flash('Session expired. Please register again.', 'danger')
        return redirect(url_for('home'))

    new_otp = str(random.randint(100000, 999999))
    new_expiry = datetime.now() + timedelta(minutes=10)

    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("UPDATE users SET verification_code = %s, otp_expiry = %s WHERE email = %s", (new_otp, new_expiry, email))
        connection.commit()

        try:
            msg = Message('EcoWatch Registration OTP (Resend)',
                          sender='nsindisothabede09@gmail.com', recipients=[email])
            msg.body = f'Your new EcoWatch verification code is: {new_otp}\nThis code expires in 10 minutes.'
            mail.send(msg)
            flash('New verification code sent successfully!', 'success')
        except Exception as mail_err:
            print(f"Mail skipped: {mail_err}")
            flash('Failed to dispatch email, but check console logs for debug code.', 'warning')

    except Exception as e:
        print(f"Error resending OTP: {e}")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('verify'))    

@app.route('/resident')
def residentPortal():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT * FROM skips")
        skips = cursor.fetchall()
    except Exception:
        skips = []
    finally:
        cursor.close()
        connection.close()
    
    return render_template('resident.html', skips=skips)

@app.route('/resident-dashboard')
def resident_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    current_user_id = session['user_id']
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT * FROM reports WHERE user_id = %s ORDER BY id DESC", (current_user_id,))
        reports = cursor.fetchall()
    except Exception:
        reports = []
    finally:
        cursor.close()
        connection.close()

    return render_template('myReports.html', reports=reports)

@app.route('/submit_report', methods=['POST'])
def submit_report():
    if 'user_id' not in session:
        return redirect(url_for('home'))

    user_id = session.get('user_id')
    
    raw_issue_type = request.form.get('issue_type')
    if raw_issue_type == 'other':
        custom_text = request.form.get('custom_issue_type', '').strip()
        issue_type = custom_text if custom_text else 'Other Incident'
    else:
        issue_type = raw_issue_type

    initial_location = request.form.get('location') or "Location Processing..."
    description = request.form.get('description', '').strip()
    if not description:
        description = "none provided"
    
    photo_file = request.files.get('waste_photo') or request.files.get('photo')
    photo_name = 'default.jpg'
    file_path = None
    
    # Compress and resize image on-the-fly
    if photo_file and photo_file.filename:
        if allowed_file(photo_file.filename):
            filename = secure_filename(photo_file.filename)
            upload_folder = os.path.join('static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            try:
                img = Image.open(photo_file)
                img.thumbnail((1200, 1200))
                img.save(file_path, optimize=True, quality=80)
                photo_name = filename
            except Exception as file_err:
                print(f"File compression/save error: {file_err}")
                photo_name = 'default.jpg'
        else:
            flash('Invalid file format. Please upload a valid JPG or PNG image.', 'danger')
            return redirect(url_for('residentPortal'))

    lat = None
    lon = None
    
    try:
        lat_val = request.form.get('latitude')
        lon_val = request.form.get('longitude')
        lat = float(lat_val) if lat_val and str(lat_val).lower() not in ('', 'none', 'nan') else None
        lon = float(lon_val) if lon_val and str(lon_val).lower() not in ('', 'none', 'nan') else None
    except (ValueError, TypeError):
        lat, lon = None, None

    if (lat is None or lon is None) and file_path:
        try:
            lat, lon = get_image_coordinates(file_path)
        except Exception:
            lat, lon = None, None

    if lat is not None and (math.isnan(lat) or math.isinf(lat)):
        lat = None
    if lon is not None and (math.isnan(lon) or math.isinf(lon)):
        lon = None

    KZN_LAT_MIN, KZN_LAT_MAX = -31.5, -26.8
    KZN_LON_MIN, KZN_LON_MAX = 28.8, 33.0

    if lat is not None and lon is not None:
        if not (KZN_LAT_MIN <= lat <= KZN_LAT_MAX and KZN_LON_MIN <= lon <= KZN_LON_MAX):
            flash('Error: The selected or geotagged location is outside KwaZulu-Natal (KZN).', 'danger')
            return redirect(url_for('residentPortal'))

    status = 'Pending Review'
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT MAX(id) FROM reports")
        max_id_result = cursor.fetchone()
        next_id = ((max_id_result.get('MAX(id)') or 0) if max_id_result else 0) + 1
        report_id = f"#REP-{next_id:04d}"

        # 1. Insert Report into DB
        query = """
            INSERT INTO reports (report_id, issue_type, location, description, photo, status, latitude, longitude, user_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(
            query,
            (report_id, issue_type, initial_location, description, photo_name, status, lat, lon, user_id),
        )
        
        # 2. Insert In-App Admin Notification instantly into DB
        notif_query = """
            INSERT INTO notifications (recipient_role, report_id, title, message, type)
            VALUES ('administrator', %s, %s, %s, 'new_report')
        """
        cursor.execute(notif_query, (report_id, f"New {issue_type} Reported", f"A new report ({report_id}) has been logged. Awaiting crew assignment."))
        
        connection.commit()

    except mysql.connector.Error as err:
        print(f"Database Error on report submit: {err}")
    finally:
        cursor.close()
        connection.close()

    # 3. Fire Geocoding & Emails in background thread so user is redirected instantly (< 1 second)
    thread = threading.Thread(
        target=background_report_tasks, 
        args=(current_app._get_current_object(), user_id, report_id, issue_type, lat, lon, initial_location)
    )
    thread.daemon = True
    thread.start()
        
    return redirect(url_for('my_reports'))

@app.route('/myReports')
def my_reports():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT * FROM reports WHERE user_id = %s ORDER BY id DESC", (session['user_id'],))
        reports = cursor.fetchall()
    except Exception:
        reports = []
    finally:
        cursor.close()
        connection.close()
    
    return render_template('myReports.html', reports=reports)

@app.route('/crew/portal')
def crewPortal():
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    current_crew_name = session.get('staff_name')

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        query = """
            SELECT * FROM reports 
            WHERE assigned_crew LIKE %s 
            AND status IN ('Crew Assigned', 'Assigned', 'In Progress', 'Resolved') 
            ORDER BY id DESC
        """
        cursor.execute(query, (f"%{current_crew_name}%",))
        assigned_tasks = cursor.fetchall()
    except Exception:
        assigned_tasks = []
    finally:
        cursor.close()
        connection.close()

    return render_template('crewPortal.html', assigned_tasks=assigned_tasks)

@app.route('/crew/update_status/<string:report_id>', methods=['POST'])
def update_crew_status(report_id):
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    new_status = request.form.get('status')
    
    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        if new_status == 'Resolved':
            cursor.execute(
                "UPDATE reports SET status = %s, resolved_at = %s WHERE report_id = %s",
                (new_status, datetime.now(), report_id)
            )
        else:
            cursor.execute(
                "UPDATE reports SET status = %s WHERE report_id = %s",
                (new_status, report_id)
            )
        connection.commit()
    except mysql.connector.Error as err:
        print(f"Error updating task status: {err}")
    finally:
        cursor.close()
        connection.close()
        
    return redirect(url_for('crewPortal'))

@app.route('/crew/resolve_task', methods=['POST'])
def resolve_task():
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    report_id = request.form.get('report_id')
    proof_file = request.files.get('completion_photo')
    proof_filename = None

    if proof_file and proof_file.filename:
        if allowed_file(proof_file.filename):
            filename = secure_filename(proof_file.filename)
            upload_folder = os.path.join('static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            try:
                img = Image.open(proof_file)
                img.thumbnail((1200, 1200))
                img.save(file_path, optimize=True, quality=80)
                proof_filename = filename
            except Exception as e:
                print(f"Proof file save error: {e}")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute(
            """UPDATE reports SET status = %s, resolved_at = %s, completion_photo = %s 
               WHERE report_id = %s""",
            ('Resolved', datetime.now(), proof_filename, report_id)
        )
        connection.commit()

        cursor.execute("""
            SELECT u.email, u.name 
            FROM reports r 
            JOIN users u ON r.user_id = u.id 
            WHERE r.report_id = %s
        """, (report_id,))
        resident = cursor.fetchone()

        if resident and resident.get('email'):
            resolve_msg = (
                f"Hello {resident['name']},\n\n"
                f"Good news! Your waste incident report ticket ({report_id}) has been marked as RESOLVED.\n\n"
                "Our municipal cleanup crew has completed the cleanup and submitted verification proof.\n"
                "You can log into your EcoWatch dashboard to view the completion status.\n\n"
                "Thank you for helping keep our community clean and green!\n\n"
                "EcoWatch Waste Management"
            )
            send_resident_email(resident['email'], f"Ticket Resolved - {report_id}", resolve_msg)

        flash('Proof submitted successfully! Task status changed to Resolved.', 'success')
    except mysql.connector.Error as err:
        print(f"Error resolving task: {err}")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('crewPortal'))

@app.route('/admin/portal')
def adminPortal():
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT * FROM reports ORDER BY id DESC")
        reports = cursor.fetchall()
        
        cursor.execute("SELECT * FROM staff WHERE role = 'Cleanup Crew'")
        all_crews = cursor.fetchall()
        
        cursor.execute("SELECT assigned_crew FROM reports WHERE status IN ('Crew Assigned', 'Assigned', 'In Progress') AND assigned_crew IS NOT NULL")
        busy_assignments = cursor.fetchall()
        busy_crew_names = [b['assigned_crew'] for b in busy_assignments]
        
        crews = []
        for crew in all_crews:
            full_name = f"{crew['name']} {crew['surname']}"
            crew['is_available'] = full_name not in busy_crew_names
            crews.append(crew)
    except Exception:
        reports, crews = [], []
    finally:
        cursor.close()
        connection.close()
    
    return render_template('adminPortal.html', reports=reports, crews=crews, staff_name=session.get('staff_name', 'Admin'))

@app.route('/admin/users')
def adminUsers():
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT * FROM staff")
        users = cursor.fetchall()
    except Exception:
        users = []
    finally:
        cursor.close()
        connection.close()
    
    return render_template('adminUsers.html', users=users, staff_name=session.get('staff_name', 'Admin'))

@app.route('/admin/update_role/<string:staff_id>', methods=['POST'])
def update_role(staff_id):
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    new_role = request.form.get('role')
    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("UPDATE staff SET role = %s WHERE staff_id = %s", (new_role, staff_id))
        connection.commit()
    except mysql.connector.Error as err:
        print(f"Error updating role: {err}")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('adminUsers'))

@app.route('/admin/add-user')
def add_user_page():
    if 'staff_name' not in session:
        return redirect(url_for('home'))
    return render_template('adminAddUser.html')

@app.route('/admin/create-user', methods=['POST'])
def create_user():
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    name = request.form.get('name')
    surname = request.form.get('surname')
    email = request.form.get('email')
    role = request.form.get('role')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT id, is_verified FROM staff WHERE email = %s", (email,))
        existing_staff = cursor.fetchone()

        if existing_staff and existing_staff.get('is_verified') == 1:
            cursor.close()
            conn.close()
            return render_template('adminAddUser.html', duplicate_error=True, staff_name=session.get('staff_name', 'Admin'))

        if existing_staff and existing_staff.get('is_verified') == 0:
            cursor.execute("DELETE FROM staff WHERE email = %s AND is_verified = 0", (email,))
            conn.commit()

        generated_staff_id = "532" + str(random.randint(100, 999))
        default_password = "password123"
        hashed_staff_password = bcrypt.generate_password_hash(default_password).decode('utf-8')
        
        otp_code = str(random.randint(100000, 999999))
        otp_expiry = datetime.now() + timedelta(minutes=10)

        cursor.execute(
            """INSERT INTO staff (staff_id, name, surname, email, password, role, otp_code, otp_expiry, is_verified) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)""",
            (generated_staff_id, name, surname, email, hashed_staff_password, role, otp_code, otp_expiry)
        )
        conn.commit()

        try:
            msg = Message('EcoWatch Staff Account Verification OTP',
                          sender='nsindisothabede09@gmail.com', recipients=[email])
            msg.body = f'Hello {name},\n\nYour staff account has been created. Your verification OTP code is: {otp_code}\nThis code expires in 10 minutes.'
            mail.send(msg)
        except Exception as mail_err:
            print(f"Mail skipped safely: {mail_err}")

        session['pending_staff_email'] = email
        flash('Staff registered successfully! Please enter the OTP sent to their email.', 'success')
        return redirect(url_for('verify_staff_otp'))

    except Exception as e:
        conn.rollback()
        print(f"Error creating user: {e}")
        return redirect(url_for('add_user_page'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/verify-staff-otp', methods=['GET', 'POST'])
def verify_staff_otp():
    if 'pending_staff_email' not in session:
        flash('No pending staff verification found.', 'warning')
        return redirect(url_for('home'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        email = session.get('pending_staff_email')

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        try:
            cursor.execute("SELECT * FROM staff WHERE email = %s", (email,))
            staff_member = cursor.fetchone()

            if staff_member:
                stored_otp = staff_member.get('otp_code')
                otp_expiry = staff_member.get('otp_expiry')

                if str(stored_otp) == str(entered_otp) and (otp_expiry is None or datetime.now() <= otp_expiry):
                    cursor.execute("""
                        UPDATE staff 
                        SET is_verified = 1, otp_code = NULL, otp_expiry = NULL 
                        WHERE email = %s
                    """, (email,))
                    connection.commit()

                    session.pop('pending_staff_email', None)
                    flash('Staff account successfully verified!', 'success')
                    
                    if 'staff_name' in session:
                        return redirect(url_for('adminUsers'))
                    else:
                        return redirect(url_for('home'))
                else:
                    flash('Invalid or expired OTP code. Please try again.', 'danger')
            else:
                flash('Staff member not found.', 'danger')
        except Exception as e:
            print(f"Verify staff OTP error: {e}")
        finally:
            cursor.close()
            connection.close()

    return render_template('verifyStaffOtp.html')

@app.route('/admin/resend-staff-otp', methods=['POST'])
def resend_staff_otp():
    email = session.get('pending_staff_email')
    if not email:
        flash('Session expired.', 'danger')
        return redirect(url_for('home'))

    new_otp = str(random.randint(100000, 999999))
    new_expiry = datetime.now() + timedelta(minutes=10)

    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("UPDATE staff SET otp_code = %s, otp_expiry = %s WHERE email = %s", (new_otp, new_expiry, email))
        connection.commit()

        try:
            msg = Message('EcoWatch Staff Account Verification OTP (Resend)',
                          sender='nsindisothabede09@gmail.com', recipients=[email])
            msg.body = f'Your new EcoWatch verification code is: {new_otp}\nThis code expires in 10 minutes.'
            mail.send(msg)
            flash('New OTP code sent successfully!', 'success')
        except Exception as mail_err:
            print(f"Mail skipped: {mail_err}")
            flash('Failed to dispatch email, but check server console logs for debug code.', 'warning')

    except Exception as e:
        print(f"Error resending staff OTP: {e}")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('verify_staff_otp'))

@app.route('/admin/delete_user/<string:staff_id>', methods=['POST'])
def delete_user(staff_id):
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("DELETE FROM staff WHERE staff_id = %s", (staff_id,))
        connection.commit()
    except mysql.connector.Error as err:
        print(f"Error deleting user: {err}")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('adminUsers'))

@app.route('/admin/assign/<int:report_id>', methods=['POST'])
def assign_crew(report_id):
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    crew_member = request.form.get('crew_member')
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute(
            "UPDATE reports SET status = %s, assigned_crew = %s, assigned_at = %s WHERE id = %s",
            ('Crew Assigned', crew_member, datetime.now(), report_id)
        )
        connection.commit()

        cursor.execute("""
            SELECT u.email, u.name, r.report_id 
            FROM reports r 
            JOIN users u ON r.user_id = u.id 
            WHERE r.id = %s
        """, (report_id,))
        resident = cursor.fetchone()

        if resident and resident.get('email'):
            assign_msg = (
                f"Hello {resident['name']},\n\n"
                f"Update on your waste incident report ({resident['report_id']}):\n"
                f"A municipal cleanup crew ({crew_member}) has been assigned to resolve your ticket.\n\n"
                f"Status: Crew Assigned\n\n"
                "You can follow the live status update on your EcoWatch dashboard.\n\n"
                "EcoWatch Waste Management"
            )
            send_resident_email(resident['email'], f"Crew Dispatched [Ticket {resident['report_id']}]", assign_msg)

    except Exception as err:
        print(f"Error assigning crew: {err}")
    finally:
        cursor.close()
        connection.close()
        
    return redirect(url_for('adminPortal'))

@app.route('/admin/reject/<int:report_id>', methods=['POST'])
def reject_report(report_id):
    if 'staff_name' not in session:
        return redirect(url_for('home'))
        
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute(
            "UPDATE reports SET status = 'Rejected', resolved_at = %s WHERE id = %s",
            (datetime.now(), report_id)
        )
        connection.commit()

        cursor.execute("""
            SELECT u.email, u.name, r.report_id 
            FROM reports r 
            JOIN users u ON r.user_id = u.id 
            WHERE r.id = %s
        """, (report_id,))
        resident = cursor.fetchone()

        if resident and resident.get('email'):
            reject_msg = (
                f"Hello {resident['name']},\n\n"
                f"Your waste report ticket ({resident['report_id']}) has been reviewed and flagged as Rejected/Invalid by municipal administrators.\n\n"
                "If you believe this was done in error or need further assistance, please contact municipal support or submit a new report with clear photos and location details.\n\n"
                "EcoWatch Waste Management"
            )
            send_resident_email(resident['email'], f"Update on Ticket {resident['report_id']}", reject_msg)

    except Exception as err:
        print(f"Error rejecting report: {err}")
    finally:
        cursor.close()
        connection.close()
        
    return redirect(url_for('adminPortal'))

@app.route('/api/administrator/notifications', methods=['GET'])
def get_administrator_notifications():
    if 'staff_name' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""
            SELECT notification_id, report_id, title, message, type, created_at 
            FROM notifications 
            WHERE recipient_role = 'administrator' AND is_read = FALSE 
            ORDER BY created_at DESC
        """)
        unread_notifications = cursor.fetchall()
        
        return jsonify({
            'unread_count': len(unread_notifications),
            'notifications': unread_notifications
        })
    except Exception as e:
        print(f"Error fetching admin notifications: {e}")
        return jsonify({'unread_count': 0, 'notifications': []})
    finally:
        cursor.close()
        connection.close()

@app.route('/api/administrator/notifications/mark-read', methods=['POST'])
def mark_administrator_notifications_read():
    if 'staff_name' not in session:
        return jsonify({'error': 'Unauthorized'}), 403

    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("""
            UPDATE notifications 
            SET is_read = TRUE 
            WHERE recipient_role = 'administrator' AND is_read = FALSE
        """)
        connection.commit()
        return jsonify({'status': 'success', 'message': 'Notifications marked as read'})
    except Exception as e:
        print(f"Error marking admin notifications as read: {e}")
        return jsonify({'status': 'error'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/admin/analytics')
def adminAnalytics():
    if 'staff_name' not in session:
        return redirect(url_for('home'))
        
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT COUNT(*) as total FROM reports")
        total_reports = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COUNT(*) as total FROM reports WHERE status = 'Rejected'")
        rejected_reports = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT assigned_crew) as total FROM reports WHERE assigned_crew IS NOT NULL AND assigned_crew != '' AND status IN ('Crew Assigned', 'Assigned', 'In Progress')")
        active_crews = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT COUNT(*) as total FROM reports WHERE status IN ('Pending Review', 'Crew Assigned', 'Assigned', 'In Progress')")
        pending_resolution = cursor.fetchone()['total'] or 0

        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM reports 
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT location AS zone_location, 
                   issue_type AS incident_category, 
                   COUNT(*) as total_incidents,
                   COALESCE(AVG(TIMESTAMPDIFF(HOUR, created_at, resolved_at)), 4.2) as avg_hours
            FROM reports 
            GROUP BY location, issue_type 
            ORDER BY total_incidents DESC 
            LIMIT 5
        """)
        raw_hotspots = cursor.fetchall()

        def short_location(loc_str):
            if not loc_str:
                return "Unknown"
            parts = [p.strip() for p in str(loc_str).split(',')]
            if len(parts) >= 2:
                return f"{parts[0]}, {parts[1]}"
            return parts[0]

        hotspots = []
        for h in raw_hotspots:
            h['full_location'] = h['zone_location']
            h['zone_location'] = short_location(h['zone_location'])
            hotspots.append(h)

        cursor.execute("SELECT COUNT(*) as total FROM reports WHERE status = 'Resolved'")
        resolved_count = cursor.fetchone()['total'] or 0
        valid_reports = max(total_reports - rejected_reports, 1)
        resolution_rate = round((resolved_count / valid_reports) * 100, 1)
    except Exception as e:
        print(f"Analytics error: {e}")
        total_reports, rejected_reports, active_crews, pending_resolution = 0, 0, 0, 0
        status_counts, hotspots, resolution_rate = {}, [], 0.0
    finally:
        cursor.close()
        connection.close()
    
    return render_template(
        'adminAnalytics.html', 
        total_reports=total_reports, 
        rejected_reports=rejected_reports,
        active_crews=active_crews,
        pending_resolution=pending_resolution,
        status_counts=status_counts,
        hotspots=hotspots,
        resolution_rate=resolution_rate,
        staff_name=session.get('staff_name', 'Admin')
    )

@app.route('/admin/analytics/export')
def exportAnalyticsCSV():
    if 'staff_name' not in session:
        return redirect(url_for('home'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT id, report_id, issue_type, location, description, status, assigned_crew, created_at, resolved_at FROM reports ORDER BY id DESC")
        reports = cursor.fetchall()
    except Exception:
        reports = []
    finally:
        cursor.close()
        connection.close()

    def generate_csv():
        yield "ID,Report Ref,Issue Type,Location,Description,Status,Assigned Crew,Created At,Resolved At\n"
        for r in reports:
            loc = f'"{str(r["location"]).replace("\"", '""')}"' if r['location'] else '""'
            desc = f'"{str(r["description"]).replace("\"", '""')}"' if r['description'] else '""'
            crew = f'"{str(r["assigned_crew"]).replace("\"", '""')}"' if r['assigned_crew'] else '"Unassigned"'
            resolved = str(r['resolved_at']) if r['resolved_at'] else ''
            row = f"{r['id']},{r['report_id']},{r['issue_type']},{loc},{desc},{r['status']},{crew},{r['created_at']},{resolved}\n"
            yield row

    return Response(
        generate_csv(),
        mimetype="text/csv;charset=utf-8",
        headers={"Content-disposition": "attachment; filename=EcoWatch_Municipal_Analytics_Report.csv"}
    )

current_crew_location = {"latitude": -28.852392, "longitude": 31.851507}

@app.route('/api/update-crew-location', methods=['POST'])
def update_crew_location():
    data = request.get_json()
    if data:
        current_crew_location['latitude'] = data.get('latitude', current_crew_location['latitude'])
        current_crew_location['longitude'] = data.get('longitude', current_crew_location['longitude'])
    return {"status": "success"}

@app.route('/api/get-crew-location', methods=['GET'])
def get_crew_location():
    return current_crew_location

@app.route('/admin/track/<int:report_id>')
def track_crew(report_id):
    if 'staff_name' not in session:
        return redirect(url_for('home'))
        
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
        report = cursor.fetchone()
    except Exception:
        report = None
    finally:
        cursor.close()
        connection.close()
    
    if not report:
        flash('Report not found.', 'danger')
        return redirect(url_for('adminPortal'))
        
    return render_template('trackCrew.html', report=report)    

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))        

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)