import os

SECRET_KEY = '7e4d6d646e788917047ce3298ab34dcec724772faaa9c7dd'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

PORT = 3000

IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY', '515a3a1290d53e22143875f53eaed406')
