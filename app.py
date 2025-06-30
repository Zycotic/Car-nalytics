from flask import Flask, jsonify, request, render_template, flash, redirect, url_for, session
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
from gen import generate_image, upload_to_imgbb
from configs import IMGBB_API_KEY

# Firebase integration
try:
    from firebase_config import save_user_to_firebase, get_user_from_firebase, get_all_users_from_firebase, update_user_in_firebase, delete_user_from_firebase
    FIREBASE_AVAILABLE = True
    print("Firebase integration enabled")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    print(f"Firebase integration disabled: {str(e)}")

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
    
    # Try loading from Firebase first if available
    if FIREBASE_AVAILABLE:
        try:
            firebase_users = get_all_users_from_firebase()
            if firebase_users:
                users = firebase_users
                print(f"Loaded {len(users)} users from Firebase")
                return users
        except Exception as e:
            print(f"Error loading users from Firebase: {str(e)}")
    
    # Try loading from Excel
    if os.path.exists(USERS_EXCEL):
        try:
            users = pd.read_excel(USERS_EXCEL).to_dict('records')
            print(f"Loaded {len(users)} users from Excel")
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
            print(f"Loaded {len(users)} users from JSON")
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
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', ''),
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
        
        # Save to Firebase if available
        if FIREBASE_AVAILABLE:
            for user in users:
                save_user_to_firebase(user)
                print(f"User {user['username']} saved to Firebase")
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
    if 'user_id' not in session:
        flash('Please log in to view your uploads.', 'error')
        return redirect(url_for('login'))
    user_id = str(session['user_id'])
    user_upload_dir = os.path.join('static', 'uploads', user_id)
    if not os.path.exists(user_upload_dir):
        return render_template('Home.html', uploads=[], date=[], brands=[])
    uploaded_dirs = [d for d in os.listdir(user_upload_dir) if os.path.isdir(os.path.join(user_upload_dir, d))]
    uploaded_dirs.sort(reverse=True)
    uploads = []
    brands = []
    for upload_dir in uploaded_dirs:
        upload_path = os.path.join(user_upload_dir, upload_dir)
        image_files = [f for f in os.listdir(upload_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        # Fix: Use forward slashes for URLs
        images = [os.path.join('uploads', user_id, upload_dir, img).replace("\\", "/") for img in image_files]
        uploads.append({
            'timestamp': upload_dir,
            'images': images,
            'main_image': image_files[0] if image_files else None
        })
        if upload_dir not in brands:
            brands.append(upload_dir)
    dates_to_display = sorted(list(set(map(lambda x: x.split('_')[0], uploaded_dirs))), reverse=True)
    for upload in uploads:
        print('Upload:', upload['timestamp'])
        for img in upload['images']:
            print('  Image:', img, 'Exists:', os.path.exists(os.path.join('static', img.replace("/", os.sep))))
    return render_template('Home.html', uploads=uploads, date=dates_to_display, brands=brands)

@app.route('/apply_livery', methods=['POST'])
def apply_livery():
    # Assuming the car image and livery image filenames are passed in the form
    car_image_filename = request.form.get('car_image_filename')
    livery_image_filename = request.form.get('livery_image_filename')

    car_image_path = os.path.join(app.config['UPLOAD_FOLDER'], car_image_filename.replace("/", os.sep))
    livery_image_path = os.path.join(app.config['UPLOAD_FOLDER'], livery_image_filename.replace("/", os.sep))

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
    modified_dir = os.path.dirname(car_image_path)
    modified_image_path = os.path.join(modified_dir, 'modified_car_image.png')
    car_image.save(modified_image_path)

    return redirect(url_for('car', filename=car_image_filename.split('/')[0]))

@app.route('/test', methods=['GET', 'POST'])
def test():
    return jsonify({"message": 2})

@app.route('/upload', methods=['GET', 'POST'])
def uploadfile():
    if 'user_id' not in session:
        flash('Please log in to upload images.', 'error')
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect('/upload')
        files = request.files.getlist('file')
        if not files or all(f.filename == '' for f in files):
            flash('No image selected for uploading')
            return redirect('/upload')
        processed = []
        user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(session['user_id']))
        os.makedirs(user_upload_dir, exist_ok=True)
        for file in files:
            if file and allowed_file(file.filename):
                try:
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    base_dir = os.path.join(user_upload_dir, timestamp)
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
                        visualize_model(img, os.path.join(str(session['user_id']), timestamp), model_finetune)
                        processed.append({'timestamp': timestamp, 'logo': xy['name'], 'filename': original_filename})
                    except Exception as e:
                        flash(f'Error processing image {original_filename}: {str(e)}', 'error')
                        continue
                except Exception as e:
                    flash(f'Error saving file: {str(e)}', 'error')
                    continue
        if processed:
            flash('Upload and processing successful!', 'success')
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/display/<filename>/<file>')
def display_image(filename, file):
    # Fix: Use forward slashes for URLs
    path = os.path.join('uploads', filename.split('.')[0], file).replace("\\", "/")
    return redirect(url_for('static', filename=path), code=301)

@app.route('/<filename>', methods=['GET', 'POST'])
def car(filename):
    # filename here is the timestamp directory name
    
    if 'user_id' not in session:
        flash('Please log in to view upload details.', 'error')
        return redirect(url_for('login'))
    
    user_id = str(session['user_id'])
    upload_dir_path = os.path.join('static', 'uploads', user_id, filename)
    if not os.path.exists(upload_dir_path):
        flash('Upload not found.', 'error')
        return redirect(url_for('index'))
    
    # Collect all relevant images
    images = {}
    for key in ['original', 'sementic', 'mask', 'nobg', 'logo']:
        ext = 'png' if key == 'nobg' else 'jpg'
        path = os.path.join(upload_dir_path, f'{key}.{ext}')
        if os.path.exists(path):
            images[key] = os.path.join('uploads', user_id, filename, f'{key}.{ext}').replace("\\", "/")
    # Brand logo (from brand folder)
    brand_logo_path = glob.glob(os.path.join(upload_dir_path, 'brand', '*.jpg'))
    if brand_logo_path:
        images['brand'] = brand_logo_path[0].replace('static/', '').replace("\\", "/")
    # Segmented parts (removed from UI, but still collected if needed)
    part_names = ['back_bumper', 'back_glass', 'back_left_door', 'back_left_light', 'back_right_door', 
                 'back_right_light', 'front_bumper', 'front_glass', 'front_left_door', 'front_left_light', 
                 'front_right_door', 'front_right_light', 'hood', 'left_mirror', 'right_mirror', 
                 'tailgate', 'trunk', 'wheel']
    parts = []
    for part_name in part_names:
        part_path = os.path.join(upload_dir_path, f'{part_name}.png')
        if os.path.exists(part_path):
            parts.append(os.path.join('uploads', user_id, filename, f'{part_name}.png').replace("\\", "/"))
    # Generated image
    gen_path = os.path.join(upload_dir_path, 'generated.jpg')
    if os.path.exists(gen_path):
        images['generated'] = os.path.join('uploads', user_id, filename, 'generated.jpg').replace("\\", "/")
    else:
        output_path = os.path.join(upload_dir_path, 'output.jpg')
        if os.path.exists(output_path):
            images['generated'] = os.path.join('uploads', user_id, filename, 'output.jpg').replace("\\", "/")
    print("Car page images:", images)
    print("Car page parts:", parts)
    return render_template('Car.html', filename=filename, images=images, parts=parts)

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
    if 'user_id' not in session:
        print('[Delete Upload] No user_id in session')
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    user_id = session['user_id']
    base_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id), timestamp)
    print(f'[Delete Upload] User ID: {user_id}, Timestamp: {timestamp}, Path: {base_dir}')
    try:
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
            print(f'[Delete Upload] Successfully deleted {base_dir}')
            return jsonify({'status': 'success'})
        else:
            print(f'[Delete Upload] Not found: {base_dir}')
            return jsonify({'status': 'not found'}), 404
    except Exception as e:
        print(f'[Delete Upload] Error: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/results')
def results():
    if 'user_id' not in session:
        flash('Please log in to view your results.', 'error')
        return redirect(url_for('login'))
    user_id = str(session['user_id'])
    user_upload_dir = os.path.join('static', 'uploads', user_id)
    if not os.path.exists(user_upload_dir):
        return render_template('Results.html', results=[], dates=[], brands=[])
    uploaded_dirs = [d for d in os.listdir(user_upload_dir) if os.path.isdir(os.path.join(user_upload_dir, d))]
    uploaded_dirs.sort(reverse=True)
    results_data = []
    brands = []
    for upload_dir in uploaded_dirs:
        upload_path = os.path.join(user_upload_dir, upload_dir)
        processed_images = {}

        # Helper to build web URL from local path
        def to_url(path):
            # Remove only the first 'static' and any leading slashes
            rel_path = os.path.relpath(path, 'static')
            return rel_path.replace("\\", "/")

        # Original image
        original_path = os.path.join(upload_path, 'original.jpg')
        if os.path.exists(original_path):
            processed_images['original'] = to_url(original_path)

        # Semantic segmentation
        semantic_path = os.path.join(upload_path, 'sementic.jpg')
        if os.path.exists(semantic_path):
            processed_images['semantic'] = to_url(semantic_path)

        # Background removed
        nobg_path = os.path.join(upload_path, 'nobg.png')
        if os.path.exists(nobg_path):
            processed_images['nobg'] = to_url(nobg_path)

        # Segmentation mask
        mask_path = os.path.join(upload_path, 'mask.jpg')
        if os.path.exists(mask_path):
            processed_images['mask'] = to_url(mask_path)

        # Brand logo
        brand_logo_path = os.path.join(upload_path, 'brand')
        if os.path.exists(brand_logo_path):
            brand_files = [f for f in os.listdir(brand_logo_path) if f.endswith('.jpg') or f.endswith('.png')]
            if brand_files:
                processed_images['brand'] = to_url(os.path.join(upload_path, 'brand', brand_files[0]))
                brands.append(brand_files[0].split('.')[0])

        # Individual car parts (segmented parts)
        parts = []
        part_names = [
            'back_bumper', 'back_glass', 'back_left_door', 'back_left_light', 'back_right_door',
            'back_right_light', 'front_bumper', 'front_glass', 'front_left_door', 'front_left_light',
            'front_right_door', 'front_right_light', 'hood', 'left_mirror', 'right_mirror',
            'tailgate', 'trunk', 'wheel'
        ]
        for part_name in part_names:
            part_path = os.path.join(upload_path, f'{part_name}.png')
            if os.path.exists(part_path):
                parts.append(to_url(part_path))

        # Generation result
        gen_path = os.path.join(upload_path, 'generated.jpg')
        if os.path.exists(gen_path):
            processed_images['generated'] = to_url(gen_path)
        else:
            output_path = os.path.join(upload_path, 'output.jpg')
            if os.path.exists(output_path):
                processed_images['generated'] = to_url(output_path)

        if parts:
            processed_images['parts'] = parts

        results_data.append({
            'timestamp': upload_dir,
            'date': upload_dir.split('_')[0],
            'images': processed_images
        })

    dates_to_display = sorted(list(set([r['date'] for r in results_data])), reverse=True)
    brands = sorted(list(set(brands)))

    return render_template('Results.html', results=results_data, dates=dates_to_display, brands=brands)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        users = load_users()
        if any(u['username'] == username for u in users):
            flash('Username already exists', 'error')
            return render_template('register.html')
        if any(u['email'] == email for u in users):
            flash('Email already registered', 'error')
            return render_template('register.html')
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        valid, msg = validate_password(password)
        if not valid:
            flash(msg, 'error')
            return render_template('register.html')
        if not first_name or not last_name:
            flash('First name and last name are required.', 'error')
            return render_template('register.html')
        user_id = max([u['id'] for u in users], default=0) + 1
        new_user = {
            'id': user_id,
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'email': email,
            'password': password,  # Store password in plain text (INSECURE - for testing only)
            'created_at': datetime.now().isoformat(),
            'last_login': '',
            'failed_login_attempts': 0,
            'is_active': True,
            'verification_token': ''
        }
        users.append(new_user)
        save_users(users)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username']
        password = request.form['password']
        users = load_users()
        user = next((u for u in users if u['username'] == username_or_email or u['email'] == username_or_email), None)
        if user and user['password'] == password:  # Compare plain text passwords (INSECURE - for testing only)
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username/email or password', 'error')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/delete_my_data', methods=['POST'])
def delete_my_data():
    if 'user_id' not in session:
        flash('You must be logged in to delete your data.', 'error')
        return redirect(url_for('login'))
    user_id = session['user_id']
    # Delete user uploads
    user_upload_dir = os.path.join('static', 'uploads', str(user_id))
    if os.path.exists(user_upload_dir):
        shutil.rmtree(user_upload_dir)
    # Remove user from users database
    users = load_users()
    users = [u for u in users if u['id'] != user_id]
    save_users(users)
    # Delete from Firebase if available
    if FIREBASE_AVAILABLE:
        delete_user_from_firebase(user_id)
    session.clear()
    flash('Your account and all your data have been deleted.', 'success')
    return redirect(url_for('register'))

@app.route('/generate_image', methods=['POST'])
def generate_image_route():
    """
    Expects JSON with keys: 'prompt', 'image_path'.
    Uses the server-side IMGBB_API_KEY from configs.py.
    """
    data = request.json
    prompt = data.get('prompt')
    image_path = data.get('image_path')
    if not prompt or not image_path:
        return jsonify({'error': 'Missing required fields'}), 400
    try:
        image_url = upload_to_imgbb(image_path, IMGBB_API_KEY)
        result = generate_image(prompt, image_url)
        output = result['output'][0] if isinstance(result.get('output'), list) else result.get('output')
        # Redirect to result page with output
        return jsonify({'redirect': url_for('generate_result_page', output=output)})
    except Exception as e:
        # Redirect to result page with error
        return jsonify({'redirect': url_for('generate_result_page', error=str(e))})

@app.route('/generate_result', methods=['GET'])
def generate_result_page():
    output = request.args.get('output')
    error = request.args.get('error')
    return render_template('generate_result.html', output=output, error=error)

@app.route('/upload_temp_image', methods=['POST'])
def upload_temp_image():
    """
    Accepts a file upload and saves it to a temporary location. Returns the server path for backend use.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    filename = werkzeug.utils.secure_filename(file.filename)
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, filename)
    file.save(temp_path)
    return jsonify({'path': temp_path})

@app.route('/upload_and_generate', methods=['POST'])
def upload_and_generate():
    if 'user_id' not in session:
        flash('Please log in to upload images.', 'error')
        return redirect(url_for('login'))
    user_id = str(session['user_id'])
    if 'file' not in request.files or not request.form.get('prompt'):
        flash('Image and prompt are required.', 'error')
        return redirect(url_for('uploadfile'))
    file = request.files['file']
    prompt = request.form['prompt']
    if file.filename == '':
        flash('No image selected for uploading', 'error')
        return redirect(url_for('uploadfile'))
    if not allowed_file(file.filename):
        flash('Invalid file type.', 'error')
        return redirect(url_for('uploadfile'))
    # Save image to user folder
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], user_id, timestamp)
    os.makedirs(user_upload_dir, exist_ok=True)
    os.makedirs(os.path.join(user_upload_dir, 'brand'), exist_ok=True)
    original_filename = werkzeug.utils.secure_filename(file.filename)
    original_path = os.path.join(user_upload_dir, 'original.jpg')
    file.save(original_path)
    logger.info(f"[UPLOAD_AND_GENERATE] Saved original image: {original_path}")
    # Segmentation pipeline
    try:
        nobg_path = os.path.join(user_upload_dir, 'nobg.png')
        remove_car_background(original_path, nobg_path)
        logger.info(f"[UPLOAD_AND_GENERATE] Saved background-removed image: {nobg_path}")
        import cv2 as cv
        img = cv.imread(original_path)
        if img is None:
            logger.error(f"[UPLOAD_AND_GENERATE] cv.imread failed for {original_path}")
            flash('Failed to read uploaded image for segmentation.', 'error')
            return redirect(url_for('uploadfile'))
        xy, _ = usemodel(img.copy(), os.path.join(user_upload_dir, 'brand'))
        logger.info(f"[UPLOAD_AND_GENERATE] usemodel result: {xy}")
        visualize_model(img, os.path.join(user_id, timestamp), model_finetune)
        logger.info(f"[UPLOAD_AND_GENERATE] visualize_model completed.")
    except Exception as e:
        logger.error(f"[UPLOAD_AND_GENERATE] Segmentation pipeline error: {str(e)}")
        flash(f'Segmentation error: {str(e)}', 'error')
        return redirect(url_for('uploadfile'))
    # Generation pipeline
    try:
        from gen import generate_image, upload_to_imgbb
        from configs import IMGBB_API_KEY
        # Upload the original image to ImgBB
        logger.info(f"[UPLOAD_AND_GENERATE] Uploading to ImgBB: {original_path}")
        image_url = upload_to_imgbb(original_path, IMGBB_API_KEY)
        logger.info(f"[UPLOAD_AND_GENERATE] ImgBB URL: {image_url}")
        logger.info(f"[UPLOAD_AND_GENERATE] Prompt: {prompt}")
        # Call the generator
        result = generate_image(prompt, image_url)
        logger.info(f"[UPLOAD_AND_GENERATE] Generator result: {result}")
        output_url = result['output'][0] if isinstance(result.get('output'), list) else result.get('output')
        logger.info(f"[UPLOAD_AND_GENERATE] Output URL: {output_url}")
        # Download the generated image to the upload folder for display
        import requests
        gen_path = os.path.join(user_upload_dir, 'generated.jpg')
        r = requests.get(output_url, stream=True)
        if r.status_code == 200:
            with open(gen_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            logger.info(f"[UPLOAD_AND_GENERATE] Saved generated image: {gen_path}")
        else:
            logger.error(f"[UPLOAD_AND_GENERATE] Failed to download generated image from {output_url}, status {r.status_code}")
            flash('Failed to download generated image.', 'error')
            return redirect(url_for('uploadfile'))
    except Exception as e:
        logger.error(f"[UPLOAD_AND_GENERATE] Generation pipeline error: {str(e)}")
        flash(f'Generation error: {str(e)}', 'error')
        return redirect(url_for('uploadfile'))
    # flash('Upload, segmentation, and generation successful!', 'success')
    return jsonify({'redirect': url_for('generate_result_page', output=output_url)})

@app.route('/profile', methods=['GET'])
def profile():
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'error')
        return redirect(url_for('login'))
    user_id = session['user_id']
    users = load_users()
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('index'))
    # Add default fields if missing
    user.setdefault('preferences', '')
    user.setdefault('liveries', [])
    user.setdefault('images', [])
    return render_template('profile.html', user=user)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        flash('Please log in to update your profile.', 'error')
        return redirect(url_for('login'))
    user_id = session['user_id']
    users = load_users()
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('index'))
    # Update fields
    user['first_name'] = request.form.get('first_name', '')
    user['last_name'] = request.form.get('last_name', '')
    user['phone'] = request.form.get('phone', '')
    user['country'] = request.form.get('country', '')
    user['language'] = request.form.get('language', '')
    # Profile photo upload
    if 'profile_photo' in request.files:
        file = request.files['profile_photo']
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext in ['jpg', 'jpeg', 'png'] and len(file.read()) < 1024*1024:
                file.seek(0)
                filename = f"profile_{user_id}.{ext}"
                path = os.path.join('static', 'uploads', str(user_id), filename)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                file.save(path)
                user['profile_photo'] = f"uploads/{user_id}/{filename}"
            else:
                flash('Profile photo must be .jpg/.png and less than 1MB.', 'error')
                return redirect(url_for('profile'))
    save_users(users)
    flash('Profile updated!', 'success')
    return redirect(url_for('profile'))

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        users = load_users()
        user = next((u for u in users if u['id'] == session['user_id']), None)
    return dict(user=user)

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=3001)