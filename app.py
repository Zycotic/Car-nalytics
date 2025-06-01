from flask import Flask, jsonify, request, render_template, flash, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
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

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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

# Simple user class
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    users = load_users()
    for user in users:
        if str(user['id']) == str(user_id):
            return User(str(user['id']), user['username'], user['email'])
    return None

# Registration route with enhanced security and notifications
@app.route('/register', methods=['GET', 'POST'])
# @limiter.limit("5 per minute") # Removed rate limit
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate input
        username_valid, username_msg = validate_username(username)
        if not username_valid:
            flash(username_msg, 'error')
            return redirect(url_for('register'))
            
        email_valid, email_msg = validate_email(email)
        if not email_valid:
            flash(email_msg, 'error')
            return redirect(url_for('register'))
            
        password_valid, password_msg = validate_password(password)
        if not password_valid:
            flash(password_msg, 'error')
            return redirect(url_for('register'))
        
        # Check password confirmation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        users = load_users()
        
        # Check if username or email already exists
        for user in users:
            if user['username'] == username:
                flash('Username already exists', 'error')
                return redirect(url_for('register'))
            if user['email'] == email:
                flash('Email already exists', 'error')
                return redirect(url_for('register'))
        
        # Create new user with additional security measures
        new_user = {
            'id': len(users) + 1,
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'failed_login_attempts': 0,
            'is_active': True,
            'verification_token': secrets.token_urlsafe(32)
        }
        users.append(new_user)
        save_users(users)
        
        # Add notification for new registration
        notification = add_notification(f"New user registered: {username}", "success")
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Login route with enhanced security
@app.route('/login', methods=['GET', 'POST'])
# @limiter.limit("5 per minute") # Removed rate limit
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')
        users = load_users()
        user_found = None
        for user in users:
            if user['username'] == username_or_email or user['email'] == username_or_email:
                user_found = user
                break

        if user_found and check_password_hash(user_found['password'], password):
            # Check for account lockout
            attempts = load_registration_attempts()
            user_attempts = attempts.get(str(user_found['id']), {'failed_attempts': 0, 'locked_until': None})
            if user_attempts['locked_until'] and datetime.fromisoformat(user_attempts['locked_until']) > datetime.now():
                flash(f'Account locked. Try again after {datetime.fromisoformat(user_attempts["locked_until"]).strftime("%H:%M:%S")}', 'danger')
                return redirect(url_for('login'))

            user_obj = User(str(user_found['id']), user_found['username'], user_found['email'])
            login_user(user_obj)

            # Reset failed attempts on successful login
            if str(user_found['id']) in attempts:
                attempts[str(user_found['id'])] = {'failed_attempts': 0, 'locked_until': None}
                save_registration_attempts(attempts)

            # Update last login time
            user_found['last_login'] = datetime.now().isoformat()
            save_users(users)

            flash('Login successful!', 'success')  # Flash success message
            return redirect(url_for('index'))
        else:
            # Increment failed attempts
            user_id = None
            users = load_users()
            for user in users:
                if user['username'] == username_or_email or user['email'] == username_or_email:
                    user_id = str(user['id'])
                    break

            if user_id:
                attempts = load_registration_attempts()
                user_attempts = attempts.get(user_id, {'failed_attempts': 0, 'locked_until': None})
                user_attempts['failed_attempts'] += 1

                # Check for lockout threshold
                if user_attempts['failed_attempts'] >= 5: # Lock after 5 failed attempts
                    lockout_end_time = datetime.now() + timedelta(minutes=1) # Lock for 1 minute
                    user_attempts['locked_until'] = lockout_end_time.isoformat()
                    flash(f'Too many failed login attempts. Account locked. Try again after {lockout_end_time.strftime("%H:%M:%S")}', 'danger')
                else:
                    flash('Invalid username/email or password.', 'danger') # Flash danger message
                attempts[user_id] = user_attempts
                save_registration_attempts(attempts)
            else:
                 flash('Invalid username/email or password.', 'danger') # Flash danger message

            return redirect(url_for('login'))

    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'warning') # Flash warning message
    return redirect(url_for('login'))

# Protect routes that require authentication
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # Get current user ID
    user_id = str(current_user.id)
    
    # Define the user's upload directory
    user_upload_dir = os.path.join('static', 'uploads', f'user_{user_id}')
    
    # Check if the user's directory exists, if not, return empty lists
    if not os.path.exists(user_upload_dir):
        return render_template('Home.html', files=[], date=[])
    
    # List directories (representing uploads) within the user's upload directory
    # Filter out any files directly in the user_upload_dir if necessary
    uploaded_dirs = [d for d in os.listdir(user_upload_dir) if os.path.isdir(os.path.join(user_upload_dir, d))]
    
    # Sort the directories by date (timestamp) in descending order
    uploaded_dirs.sort(reverse=True)
    
    # For displaying purposes, you might want to show a representative file from each upload
    # For now, let's just pass the directory names and handle file listing in the template or another route
    
    # The 'files' variable in Home.html seems to expect a list of file paths.
    # Let's adapt this to pass the directory names (timestamps) instead, and update Home.html accordingly.
    # Or, we can get a representative file path (e.g., original.jpg or nobg.png) from each directory.
    
    # Let's get the path to the original image in each uploaded directory for display
    files_to_display = []
    for upload_dir in uploaded_dirs:
        original_img_path = os.path.join(user_upload_dir, upload_dir, 'original.jpg')
        if os.path.exists(original_img_path):
            files_to_display.append(original_img_path.replace('static/', '')) # Store path relative to static
            
    # The date variable seems to be a list of date strings. We can extract dates from the directory names.
    dates_to_display = sorted(list(set(map(lambda x: x.split('_')[0], uploaded_dirs))), reverse=True)
    
    print("Files to display:", files_to_display)
    print("Dates to display:", dates_to_display)
    
    return render_template('Home.html', files=files_to_display, date=dates_to_display)

@app.route('/apply_livery', methods=['POST'])
@login_required
def apply_livery():
    # Assuming the car image and livery image filenames are passed in the form
    car_image_filename = request.form.get('car_image_filename')
    livery_image_filename = request.form.get('livery_image_filename')

    car_image_path = os.path.join(app.config['UPLOAD_FOLDER'], car_image_filename)
    livery_image_path = os.path.join(app.config['UPLOAD_FOLDER'], livery_image_filename)

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
@login_required
def uploadfile():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect('/upload')
        file = request.files['file']
        if file.filename == '':
            flash('No image selected for uploading')
            return redirect('/upload')
        if file and allowed_file(file.filename):
            try:
                # Get current user ID
                user_id = str(current_user.id)
                
                # Generate timestamp-based directory name
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                
                # Create user-specific base directory
                user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'user_{user_id}')
                
                # Create the timestamp directory within the user's directory
                base_dir = os.path.join(user_upload_dir, timestamp)
                
                # Create necessary directories, including the 'brand' subdirectory
                os.makedirs(base_dir, exist_ok=True)
                os.makedirs(os.path.join(base_dir, 'brand'), exist_ok=True)

                # Generate secure filename for the original file
                original_filename = werkzeug.utils.secure_filename(file.filename)
                original_path = os.path.join(base_dir, original_filename)
                
                # Save original file
                file.save(original_path)
                
                # Process image
                try:
                    # Remove background
                    nobg_path = os.path.join(base_dir, 'nobg.png')
                    remove_car_background(original_path, nobg_path)
                    
                    # Read image for model processing
                    img = cv.imread(original_path)
                    if img is None:
                        flash('Error: Could not read the uploaded image file.', 'error')
                        return redirect('/upload')
                        
                    # Run model predictions
                    xy, _ = usemodel(img.copy(), os.path.join(base_dir, 'brand'))
                    visualize_model(img, timestamp, model_finetune) # visualize_model uses timestamp for directory name
                     
                    # Pass the timestamp (which is now the directory name within the user's folder) to the template
                    return render_template('upload.html', filename=timestamp, logo=xy['name'])
                     
                except Exception as e:
                    flash(f'Error processing image: {str(e)}', 'error')
                    # Clean up partially created directory if processing failed
                    # import shutil # Need to add import for shutil
                    # if os.path.exists(base_dir): shutil.rmtree(base_dir)
                    return redirect('/upload')
                     
            except Exception as e:
                flash(f'Error saving file: {str(e)}', 'error')
                return redirect('/upload')
        else:
            flash('Allowed image types are - png, jpg, jpeg, gif', 'warning')
            return redirect('/upload') # Should redirect to upload page after failed upload
    return render_template('upload.html')


@app.route('/display/<filename>/<file>')
@login_required
def display_image(filename, file):
    path = os.path.join('uploads', filename.split('.')[0], file)
    return redirect(url_for('static', filename=path), code=301)


@app.route('/<filename>', methods=['GET', 'POST'])
@login_required
def car(filename):
    # filename here is the timestamp directory name
    
    # Get current user ID
    user_id = str(current_user.id)
    
    # Construct the path to the specific upload directory for this user and timestamp
    upload_dir_path = os.path.join('static', 'uploads', f'user_{user_id}', filename)
    
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
@login_required
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
@login_required
def get_notifications():
    notifications = load_notifications()
    return jsonify(notifications)

@app.route('/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notifications = load_notifications()
    for notification in notifications["notifications"]:
        if notification["id"] == notification_id:
            notification["read"] = True
            break
    save_notifications(notifications)
    return jsonify({"status": "success"})

@app.route('/notifications/clear', methods=['POST'])
@login_required
def clear_notifications():
    notifications = load_notifications()
    notifications["notifications"] = []
    save_notifications(notifications)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=3001)
