from flask import Flask, jsonify, request, render_template, flash, redirect, url_for
from flask_cors import CORS
import werkzeug.utils
import os
import cv2 as cv
from configs import *
from tools import *
from model_env.model import *
from model_env.logo_model import *
from rembg import remove
from PIL import Image
import json
from werkzeug.security import generate_password_hash, check_password_hash
import re
from datetime import datetime, timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
import pandas as pd
import glob
from flask_mail import Mail, Message
import uuid
import logging
import shutil

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
mail = Mail(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# User data storage in Excel
USERS_EXCEL = 'users.xlsx'
REGISTRATION_ATTEMPTS_FILE = 'registration_attempts.json'
NOTIFICATIONS_FILE = 'notifications.json'

def load_users():
    users = []
    # Try loading from Excel first
    if os.path.exists(USERS_EXCEL):
        try:
            users = pd.read_excel(USERS_EXCEL).to_dict('records')
        except Exception as e:
            print(f"Error loading users from Excel: {str(e)}")
    
    # If Excel loading fails or file doesn't exist, try JSON
    if not users and os.path.exists('users.json'):
        try:
            with open('users.json', 'r') as f:
                json_users = json.load(f)
                for user_id, user_data in json_users.items():
                    user_data['id'] = int(user_id)
                    users.append(user_data)
        except Exception as e:
            print(f"Error loading users from JSON: {str(e)}")
    
    return users

def save_users(users):
    try:
        # Save to Excel
        df = pd.DataFrame(users)
        df.to_excel(USERS_EXCEL, index=False)
        
        # Also save a clean JSON backup
        formatted_users = {}
        for user in users:
            user_id = str(user['id'])
            formatted_users[user_id] = {
                'username': user['username'],
                'email': user['email'],
                'password': user['password'],
                'created_at': user['created_at'],
                'last_login': user['last_login'],
                'failed_login_attempts': user['failed_login_attempts'],
                'is_active': user['is_active'],
                'verification_token': user['verification_token']
            }
        
        with open('users.json', 'w') as f:
            json.dump(formatted_users, f, indent=4)
    except Exception as e:
        print(f"Error saving users: {str(e)}")

def load_registration_attempts():
    if os.path.exists(REGISTRATION_ATTEMPTS_FILE):
        with open(REGISTRATION_ATTEMPTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_registration_attempts(attempts):
    with open(REGISTRATION_ATTEMPTS_FILE, 'w') as f:
        json.dump(attempts, f)

def load_notifications():
    if os.path.exists(NOTIFICATIONS_FILE):
        with open(NOTIFICATIONS_FILE, 'r') as f:
            return json.load(f)
    return {"notifications": []}

def save_notifications(notifications):
    with open(NOTIFICATIONS_FILE, 'w') as f:
        json.dump(notifications, f)

def add_notification(message, notification_type="info"):
    notifications = load_notifications()
    notification = {
        "id": len(notifications["notifications"]) + 1,
        "message": message,
        "type": notification_type,
        "timestamp": datetime.now().isoformat(),
        "read": False
    }
    notifications["notifications"].append(notification)
    save_notifications(notifications)
    return notification

def validate_password(password):
    """
    Password must contain:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"

def validate_username(username):
    """
    Username must:
    - Be 3-20 characters long
    - Contain only letters, numbers, and underscores
    - Start with a letter
    """
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{2,19}$", username):
        return False, "Username must be 3-20 characters long, start with a letter, and contain only letters, numbers, and underscores"
    return True, "Username is valid"

def validate_email(email):
    """
    Basic email validation
    """
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return False, "Invalid email format"
    return True, "Email is valid"

@app.route('/', methods=['GET', 'POST'])
def index():
    # No user ID, just use a shared upload directory
    user_upload_dir = os.path.join('static', 'uploads')
    if not os.path.exists(user_upload_dir):
        return render_template('Home.html', files=[], date=[], brands=[])
    uploaded_dirs = [d for d in os.listdir(user_upload_dir) if os.path.isdir(os.path.join(user_upload_dir, d))]
    uploaded_dirs.sort(reverse=True)
    files_to_display = []
    brands = []
    for upload_dir in uploaded_dirs:
        original_img_path = os.path.join(user_upload_dir, upload_dir, 'original.jpg')
        if os.path.exists(original_img_path):
            files_to_display.append(original_img_path.replace('static/', ''))
            if upload_dir not in brands:
                brands.append(upload_dir)
    dates_to_display = sorted(list(set(map(lambda x: x.split('_')[0], uploaded_dirs))), reverse=True)
    print("Files to display:", files_to_display)
    print("Dates to display:", dates_to_display)
    return render_template('Home.html', files=files_to_display, date=dates_to_display, brands=brands)

@app.route('/apply_livery', methods=['POST'])
def apply_livery():
    # Assuming the car image and livery image filenames are passed in the form
    car_image_filename = request.form.get('car_image_filename')
    livery_image_filename = request.form.get('livery_image_filename')

    car_image_path = os.path.join(app.config['UPLOAD_FOLDER'], car_image_filename)
    livery_image_path = os.path.join(app.config['UPLOAD_FOLDER'], livery_image_filename)

    # Error handling for missing files
    if not os.path.exists(car_image_path):
        flash(f"Car image not found: {car_image_path}", "error")
        return redirect(request.referrer or url_for('index'))
    if not os.path.exists(livery_image_path):
        flash(f"Livery image not found: {livery_image_path}", "error")
        return redirect(request.referrer or url_for('index'))

    # Open the car image and livery image
    car_image = Image.open(car_image_path).convert("RGBA")
    livery_image = Image.open(livery_image_path).convert("RGBA")

    # Apply the livery (this is a simple example, you might need more complex logic)
    car_image.paste(livery_image, (0, 0), livery_image)

    # Save the modified image
    modified_image_path = os.path.join(app.config['UPLOAD_FOLDER'], car_image_filename.split('/')[0], 'modified_car_image.png')
    car_image.save(modified_image_path)

    return redirect(url_for('car', filename=car_image_filename.split('/')[0]))

@app.route('/test', methods=['GET', 'POST'])
def test():
    return jsonify({"message": 2})

@app.route('/upload', methods=['GET', 'POST'])
def uploadfile():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect('/upload')
        files = request.files.getlist('file')
        if not files or all(f.filename == '' for f in files):
            flash('No image selected for uploading')
            return redirect('/upload')
        processed = []
        for file in files:
            if file and allowed_file(file.filename):
                try:
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    base_dir = os.path.join(app.config['UPLOAD_FOLDER'], timestamp)
                    os.makedirs(base_dir, exist_ok=True)
                    os.makedirs(os.path.join(base_dir, 'brand'), exist_ok=True)
                    original_filename = werkzeug.utils.secure_filename(file.filename)
                    original_path = os.path.join(base_dir, original_filename)
                    file.save(original_path)
                    try:
                        nobg_path = os.path.join(base_dir, 'nobg.png')
                        remove_car_background(original_path, nobg_path)
                        img = cv.imread(original_path)
                        if img is None:
                            flash(f'Error: Could not read the uploaded image file {original_filename}.', 'error')
                            continue
                        xy, _ = usemodel(img.copy(), os.path.join(base_dir, 'brand'))
                        visualize_model(img, timestamp, model_finetune)
                        processed.append({'timestamp': timestamp, 'logo': xy['name'], 'filename': original_filename})
                    except Exception as e:
                        flash(f'Error processing image {original_filename}: {str(e)}', 'error')
                        continue
                except Exception as e:
                    flash(f'Error saving file {file.filename}: {str(e)}', 'error')
                    continue
            else:
                flash(f'Allowed image types are - png, jpg, jpeg, gif', 'warning')
        if processed:
            # Redirect to the result/details page for the first processed image
            return redirect(url_for('car', filename=processed[0]['timestamp']))
        else:
            return redirect('/upload')
    return render_template('upload.html')

@app.route('/display/<filename>/<file>')
def display_image(filename, file):
    path = os.path.join('uploads', filename.split('.')[0], file)
    return redirect(url_for('static', filename=path), code=301)

@app.route('/<filename>', methods=['GET', 'POST'])
def car(filename):
    # filename here is the timestamp directory name
    
    # Construct the path to the specific upload directory for this user and timestamp
    upload_dir_path = os.path.join('static', 'uploads', filename)
    
    # Check if the directory exists
    if not os.path.exists(upload_dir_path):
        flash('Upload not found.', 'error')
        return redirect(url_for('index')) # Redirect to history page if not found
        
    try:
        # Construct the path to the brand image within this specific upload directory
        brand_logo_path = glob.glob(os.path.join(upload_dir_path, 'brand', '*.jpg'))
        data = {
            'logo': brand_logo_path[0].replace('static/', '') if brand_logo_path else None
        }
    except Exception as e:
        print(f"Error loading brand logo: {str(e)}")
        data = {'logo': None}
        
    # Get all .png files within this specific upload directory
    files = glob.glob(os.path.join(upload_dir_path, '*.png'))
    files = [f.replace('static/', '') for f in files] # Store paths relative to static
    
    print("Files for car page:", files)
    print("Data for car page:", data)
    
    # Pass the timestamp as filename and the collected files and data to the template
    return render_template('Car.html', filename=filename, files=files, data=data)

@app.route('/clear')
def clear():
    return jsonify({'status': 'remove all file success.', 'filenames': clear_file()}), 201

def remove_car_background(input_path, output_path):
    """Remove background from car image and save result."""
    with open(input_path, "rb") as inp_file:
        input_data = inp_file.read()
        output_data = remove(input_data)
        with open(output_path, "wb") as out_file:
            out_file.write(output_data)
            
         

# Add notification routes
@app.route('/notifications')
def get_notifications():
    notifications = load_notifications()
    return jsonify(notifications)

@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    notifications = load_notifications()
    for notification in notifications["notifications"]:
        if notification["id"] == notification_id:
            notification["read"] = True
            break
    save_notifications(notifications)
    return jsonify({"status": "success"})

@app.route('/notifications/clear', methods=['POST'])
def clear_notifications():
    notifications = load_notifications()
    notifications["notifications"] = []
    save_notifications(notifications)
    return jsonify({"status": "success"})

@app.route('/delete_upload/<timestamp>', methods=['POST'])
def delete_upload(timestamp):
    base_dir = os.path.join(app.config['UPLOAD_FOLDER'], timestamp)
    try:
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/results')
def results():
    user_upload_dir = os.path.join('static', 'uploads')
    if not os.path.exists(user_upload_dir):
        return render_template('Home.html', files=[], date=[], brands=[])
    uploaded_dirs = [d for d in os.listdir(user_upload_dir) if os.path.isdir(os.path.join(user_upload_dir, d))]
    uploaded_dirs.sort(reverse=True)
    files_to_display = []
    brands = []
    for upload_dir in uploaded_dirs:
        original_img_path = os.path.join(user_upload_dir, upload_dir, 'original.jpg')
        if os.path.exists(original_img_path):
            files_to_display.append(original_img_path.replace('static/', ''))
            if upload_dir not in brands:
                brands.append(upload_dir)
    dates_to_display = sorted(list(set(map(lambda x: x.split('_')[0], uploaded_dirs))), reverse=True)
    return render_template('Home.html', files=files_to_display, date=dates_to_display, brands=brands)

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=3001)
