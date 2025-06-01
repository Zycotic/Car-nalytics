import torch
import numpy as np

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

id2label = {0: '_background_', 1: 'back_bumper', 2: 'back_glass', 3: 'back_left_door', 4: 'back_left_light',
            5: 'back_right_door', 6: 'back_right_light', 7: 'front_bumper', 8: 'front_glass', 9: 'front_left_door',
            10: 'front_left_light', 11: 'front_right_door', 12: 'front_right_light', 13: 'hood', 14: 'left_mirror',
            15: 'right_mirror', 16: 'tailgate', 17: 'trunk', 18: 'wheel'}
label2id = {'_background_': 0, 'back_bumper': 1, 'back_glass': 2, 'back_left_door': 3, 'back_left_light': 4,
            'back_right_door': 5, 'back_right_light': 6, 'front_bumper': 7, 'front_glass': 8, 'front_left_door': 9,
            'front_left_light': 10, 'front_right_door': 11, 'front_right_light': 12, 'hood': 13, 'left_mirror': 14,
            'right_mirror': 15, 'tailgate': 16, 'trunk': 17, 'wheel': 18}
palette = np.array([[0, 0, 0],
                    [225, 76, 225],
                    [127, 255, 191],
                    [255, 193, 21],
                    [203, 203, 203],
                    [102, 178, 255],
                    [255, 196, 228],
                    [103, 202, 223],
                    [255, 71, 71],
                    [161, 255, 164],
                    [21, 253, 29],
                    [251, 255, 176],
                    [254, 148, 12],
                    [150, 0, 250],
                    [196, 0, 13],
                    [48, 166, 159],
                    [102, 51, 0],
                    [245, 255, 240],
                    [171, 199, 56]])
classes = ['_background_', 'back_bumper', 'back_glass', 'back_left_door', 'back_left_light', 'back_right_door',
           'back_right_light', 'front_bumper', 'front_glass', 'front_left_door', 'front_left_light', 'front_right_door',
           'front_right_light', 'hood', 'left_mirror', 'right_mirror', 'tailgate', 'trunk', 'wheel']

if __name__ == '__main__':
    print(DEVICE)