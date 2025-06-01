import os
import torch
import ssl
import cv2
ssl._create_default_https_context = ssl._create_unverified_context
logo_model = torch.hub.load("ultralytics/yolov5", 'custom', path='./model_env/best_yolov5s_size640.pt')

def usemodel(img, savepath='.'):
    img_c = img.copy()
    result = logo_model(img, size=640)
    img = result.render()[0]
    xy = result.pandas().xyxy[0].to_dict(orient="records")[0]
    logo = img_c[ int(xy['ymin']):int(xy['ymax']) ,int(xy['xmin']):int(xy['xmax'])]
    logo = cv2.resize(logo,(240,240))
    print(xy['name'])
    cv2.imwrite(os.path.join(savepath,xy['name'] + '.jpg'), logo)
    cv2.imwrite(os.path.join(savepath[:-6],'logo.jpg'), img)
    print(os.path.join(savepath,xy['name'] + '.jpg'))
    print(os.path.join(savepath[:-6],'logo.jpg'))
    return xy,logo


if __name__ =='__main__':
    a = cv2.imread('car.jpg')
    result, logo = usemodel(a,'.')
    