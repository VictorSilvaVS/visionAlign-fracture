import cv2
import numpy as np
import os
import sys

# Adiciona o diretório atual ao path para importar os módulos locais
sys.path.append(os.getcwd())

from model.detection_drawer import DetectionDrawer

def test_heatmap():
    # Cria uma imagem preta de teste
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    # Adiciona um pouco de ruído ou fundo
    cv2.rectangle(frame, (0, 0), (640, 640), (50, 50, 50), -1)
    
    # Mock de resultados (imita a estrutura do OVModel/_Results)
    class MockTensor:
        def __init__(self, data): self._data = np.array(data)
        def cpu(self): return self
        def numpy(self): return self._data
        def int(self): return MockTensor(self._data.astype(int))
        def tolist(self): return self._data.tolist()

    class MockBoxes:
        def __init__(self):
            self.xyxy = MockTensor([[200, 200, 400, 400]])
            self.cls = MockTensor([0])
            self.conf = MockTensor([0.95])
            self.id = MockTensor([123])
        def __len__(self):
            return len(self.xyxy._data)

    class MockMasks:
        def __init__(self):
            # Octógono simples como máscara
            self.xy = [np.array([[250, 200], [350, 200], [400, 250], [400, 350], [350, 400], [250, 400], [200, 350], [200, 250]], dtype=np.int32)]

    class MockResults:
        def __init__(self):
            self.boxes = MockBoxes()
            self.masks = MockMasks()

    names_map = {0: 'fracture'}
    colors = {'fracture': (0, 0, 255)}
    
    drawer = DetectionDrawer(colors)
    drawer.show_heatmap = True
    
    # Executa o desenho
    results = MockResults()
    output = drawer.draw_detections(frame.copy(), results, names_map)
    
    # Salva o resultado para inspeção manual se necessário
    test_dir = 'artifacts/tests'
    os.makedirs(test_dir, exist_ok=True)
    cv2.imwrite(os.path.join(test_dir, 'test_heatmap_output.png'), output)
    print(f"Teste concluído. Imagem salva em {os.path.join(test_dir, 'test_heatmap_output.png')}")

if __name__ == "__main__":
    test_heatmap()
