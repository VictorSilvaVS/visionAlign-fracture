import cv2
import os
import numpy as np
import sys

# Adiciona o root ao path para importar OVModel
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from model.ov_wrapper import OVModel

# Paths relativos ao root do projeto
path_align = os.path.join(project_root, "model", "_openvino_model", "VisionAlign_openvino_model")
path_fracture = os.path.join(project_root, "model", "_openvino_model", "VisionFracture_openvino_model")
# Tenta encontrar uma imagem de teste válida no dataset
dataset_dir = os.path.join(project_root, "data", "dataset_collect", "images")
img_path = None
if os.path.exists(dataset_dir):
    images = [f for f in os.listdir(dataset_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if images:
        img_path = os.path.join(dataset_dir, images[0])

if not img_path:
    print("Error: No test image found in data/dataset_collect/images")
    exit()

print(f"--- TESTING ALIGN MODEL WITH {img_path} ---")
m_align = OVModel(path_align)
img = cv2.imread(img_path)
if img is None:
    print(f"Error: Could not read image {img_path}")
    exit()

res_align = m_align.predict(img, conf=0.1, verbose=False)
if res_align and len(res_align) > 0:
    boxes = res_align[0].boxes
    print(f"Align found {len(boxes)} boxes.")
    for i in range(len(boxes)):
        box = boxes[i]
        cls = int(box.cls.numpy()[0])
        name = m_align.names[cls]
        conf = float(box.conf.numpy()[0])
        print(f"Box {i}: {name} ({conf:.2f})")
        
        # Test Fracture on this ROI
        x1, y1, x2, y2 = map(int, box.xyxy.numpy()[0])
        roi = img[y1:y2, x1:x2]
        if roi.size > 0:
            print(f"  --- Testing Fracture Model on ROI {i} ---")
            m_fracture = OVModel(path_fracture, task='segment')
            res_fr = m_fracture.predict(roi, conf=0.1, verbose=False)
            if res_fr and len(res_fr) > 0:
                fr_boxes = res_fr[0].boxes
                print(f"  Fracture found {len(fr_boxes)} objects.")
                if res_fr[0].masks is not None:
                     print(f"  Masks FOUND: {len(res_fr[0].masks)}")
                else:
                     print("  NO MASKS FOUND in fracture results.")
                
                for j in range(len(fr_boxes)):
                    fb = fr_boxes[j]
                    f_cls = int(fb.cls.numpy()[0])
                    f_name = m_fracture.names[f_cls]
                    f_conf = float(fb.conf.numpy()[0])
                    print(f"  Fracture Obj {j}: {f_name} ({f_conf:.2f})")
        else:
            print(f"Box {i} ROI is invalid.")
else:
    print("Align found nothing.")
