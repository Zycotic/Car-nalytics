from configs import *
import cv2
import numpy as np
import os
import glob
import shutil


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def resize_img(src, dsize, filename):
    output = cv2.resize(src, dsize)
    (B, G, R) = cv2.split(output)
    zeros = np.zeros(output.shape[:2], dtype="uint8")
    filename = filename.split('/')[-1]
    cv2.imwrite(os.path.join('static', 'uploads', 'R' + filename), cv2.merge([zeros, zeros, R]))
    cv2.imwrite(os.path.join('static', 'uploads', 'G' + filename), cv2.merge([zeros, G, zeros]))
    cv2.imwrite(os.path.join('static', 'uploads', 'B' + filename), cv2.merge([B, zeros, zeros]))
    cv2.imwrite(os.path.join('static', 'uploads', filename), output)


def clear_file():
    files = []
    for i in glob.glob(os.path.join('static', 'uploads', '*')):
        files.append(i)
        try:
            shutil.rmtree(i)
        except:
            os.remove(i)
    return files
