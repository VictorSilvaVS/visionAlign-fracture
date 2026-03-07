import cv2
import numpy as np

class DetectionDrawer:
    def __init__(self, colors):
        self.colors = {k: tuple(map(int, v)) for k, v in colors.items()}
        # Padrões de desenho (podem ser atualizados via set_params)
        self.box_thickness = 2
        self.font_scale = 0.5
        self.font_thickness = 1
        self.show_label = True
        self.show_conf = True
        self.show_bg = True

    def set_params(self, params):
        """Atualiza os parâmetros de desenho."""
        self.box_thickness = int(params.get('box_thickness', self.box_thickness))
        self.font_scale = float(params.get('font_scale', self.font_scale))
        self.font_thickness = int(params.get('font_thickness', self.font_thickness))
        self.show_label = bool(params.get('show_label', self.show_label))
        self.show_conf = bool(params.get('show_conf', self.show_conf))
        self.show_bg = bool(params.get('show_bg', self.show_bg))

    def draw_detections(self, frame, results_obj, names_map, show_track_id=True):
        boxes = results_obj.boxes
        if boxes is None or len(boxes) == 0:
            return frame
        xyxy = boxes.xyxy.int().cpu().numpy()
        cls = boxes.cls.int().cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        if boxes.id is not None:
            ids = boxes.id.int().cpu().numpy()
        else:
            ids = [None] * len(cls)

        for box, c, s, tid in zip(xyxy, cls, conf, ids):
            x1, y1, x2, y2 = box
            cls_name = names_map.get(int(c), "Unknown")
            color = self.colors.get(cls_name, (0, 255, 0))
            
            # Desenha o retângulo
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, self.box_thickness)
            
            if not self.show_label:
                continue

            id_str = f"ID:{tid} " if (show_track_id and tid is not None) else ""
            conf_str = f" {s:.2f}" if self.show_conf else ""
            label_text = f"{id_str}{cls_name}{conf_str}"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            (w, h), bl = cv2.getTextSize(label_text, font, self.font_scale, self.font_thickness)
            t_y = y1 - 5 if y1 - h - 5 > 0 else y1 + h + 5
            
            # Desenha fundo do label
            if self.show_bg:
                cv2.rectangle(frame, (x1, t_y - h - 2), (x1 + w, t_y + bl), color, -1)
            
            # Desenha o texto
            text_color = (255, 255, 255) if self.show_bg else color
            cv2.putText(frame, label_text, (x1, t_y), font, self.font_scale, text_color, self.font_thickness, cv2.LINE_AA)

        return frame