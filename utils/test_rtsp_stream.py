from ultralytics import YOLO
import os

# Caminhos dos seus pesos (ajuste os nomes se forem diferentes)
model_path = r"e:\programs\visionAlign\model\backup\best.pt"

# Carrega o modelo
model = YOLO(model_path)
export_path = model.export(format='openvino', half=True, task='segment')
print(f"Modelo exportado com sucesso para: {export_path}")
