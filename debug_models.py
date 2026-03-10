from ultralytics import YOLO
import cv2
import os
import numpy as np

path_align = r"E:\programs\visionAlign\model\_openvino_model\VisionAlign_openvino_model"
path_fracture = r"E:\programs\visionAlign\model\_openvino_model\VisionFracture_openvino_model"
img_path = r"e:\programs\visionAlign\data\dataset_collect\images\manual_20260310_094647.jpg"

print("--- TESTING ALIGN MODEL ---")
m_align = YOLO(path_align)
img = cv2.imread(img_path)
if img is None:
    print(f"Error: Could not read image {img_path}")
    exit()

res_align = m_align.predict(img, conf=0.1, verbose=False)
if res_align and len(res_align) > 0:
    boxes = res_align[0].boxes
    print(f"Align found {len(boxes)} boxes.")
    for i, box in enumerate(boxes):
        cls = int(box.cls[0])
        name = res_align[0].names[cls]
        conf = float(box.conf[0])
        print(f"Box {i}: {name} ({conf:.2f})")
        
        # Test Fracture on this ROI
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        roi = img[y1:y2, x1:x2]
        if roi.size > 0:
            print(f"  --- Testing Fracture Model on ROI {i} ---")
            # Force task=segment to be sure
            m_fracture = YOLO(path_fracture, task='segment')
            res_fr = m_fracture.predict(roi, conf=0.1, verbose=False)
            if res_fr and len(res_fr) > 0:
                fr_boxes = res_fr[0].boxes
                print(f"  Fracture found {len(fr_boxes)} objects.")
                if hasattr(res_fr[0], 'masks') and res_fr[0].masks is not None:
                     print(f"  Masks FOUND: {len(res_fr[0].masks)}")
                else:
                     print("  NO MASKS FOUND in fracture results.")
                
                for j, fb in enumerate(fr_boxes):
                    f_cls = int(fb.cls[0])
                    f_name = res_fr[0].names[f_cls]
                    f_conf = float(fb.conf[0])
                    print(f"  Fracture Obj {j}: {f_name} ({f_conf:.2f})")
        else:
            print(f"Box {i} ROI is invalid.")
else:
    print("Align found nothing.")
