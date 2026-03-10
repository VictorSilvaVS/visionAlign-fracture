from ultralytics import YOLO
import os
import shutil

def export_model(pt_path, target_dir, task):
    if not os.path.exists(pt_path):
        print(f"Error: {pt_path} not found.")
        return
    
    print(f"Exporting {pt_path} ({task})...")
    model = YOLO(pt_path, task=task)
    ov_path = model.export(format='openvino', imgsz=640, half=True)
    
    if os.path.exists(ov_path):
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        shutil.copytree(ov_path, target_dir)
        print(f"Successfully exported to {target_dir}")
    else:
        print(f"Fail to export {pt_path}")

# Fracture Model (segment)
export_model(r"e:\programs\visionAlign\model\backup\best.pt", 
             r"e:\programs\visionAlign\model\_openvino_model\VisionFracture_openvino_model", 
             'segment')

# Align Model (segment - yes, it has masks)
# Wait, I need a PT for align. I saw yolo26n.pt in backup.
export_model(r"e:\programs\visionAlign\model\backup\yolo26n.pt", 
             r"e:\programs\visionAlign\model\_openvino_model\VisionAlign_openvino_model", 
             'segment')
