from flask import Flask, jsonify, request, render_template, flash, redirect, url_for
from flask_cors import CORS
import werkzeug.utils
import os,datetime
import cv2 as cv
from configs import *
from tools import *
from model_env.model import *
from model_env.logo_model import *
from rembg import remove
from PIL import Image

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/', methods=['GET', 'POST'])
def index():
    files = sorted(os.listdir(os.path.join('static', 'uploads')),reverse=True)
    set_date = list(set(map(lambda x:x.split('_')[0],files)))
    set_date = sorted(set_date,reverse=True)
    print(files)
    print(set_date)
    return render_template('Home.html', files=files, date=set_date)

@app.route('/apply_livery', methods=['POST'])
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
            filename = file.filename.replace(' ', '_')
            print(filename)
            filename = datetime.datetime.now().strftime("%Y-%m-%d_%X._")
            print(datetime.datetime.now().strftime("%Y-%m-%d_%X.3"))
            filename = werkzeug.utils.secure_filename(filename)
            if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0])):
                os.mkdir(os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0]))
                os.mkdir(os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0], 'brand'))

            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0], 'original.jpg'))

            # Remove background from the uploaded image
            input_img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0], 'original.jpg')
            output_img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0], 'nobg.png')
            remove_car_background(input_img_path, output_img_path)
            
            img = cv.imread(os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0], 'original.jpg'))

            xy, _ = usemodel(img.copy(), os.path.join(app.config['UPLOAD_FOLDER'], filename.split('.')[0], 'brand'))
            print(xy)
            visualize_model(img, filename, model_finetune)

            return render_template('upload.html', filename=filename,logo = xy['name'])
        else:
            flash('Allowed image types are - png, jpg, jpeg, gif')
            return redirect('/')
    return render_template('upload.html')


@app.route('/display/<filename>/<file>')
def display_image(filename, file):
    path = os.path.join('uploads', filename.split('.')[0], file)
    return redirect(url_for('static', filename=path), code=301)


@app.route('/<filename>', methods=['GET', 'POST'])
def car(filename):
    try:
        data = {
            'logo':glob.glob(os.path.join('static', 'uploads', filename,'brand', '*.jpg'))[0]
        }
    except: data = dict()
    files = glob.glob(os.path.join('static', 'uploads', filename, '*.png'))
    files = list(map(lambda x: x.replace('static/', ''), files))
    print(files)
    return render_template('Car.html', filename=filename, files=files,data=data)


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
            
         

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=PORT)
