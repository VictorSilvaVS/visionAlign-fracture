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
        self.show_mask = True  # Ativado por padrão para segmentação

    def set_params(self, params):
        """Atualiza os parâmetros de desenho."""
        self.box_thickness = int(params.get('box_thickness', self.box_thickness))
        self.font_scale = float(params.get('font_scale', self.font_scale))
        self.font_thickness = int(params.get('font_thickness', self.font_thickness))
        self.show_label = bool(params.get('show_label', self.show_label))
        self.show_conf = bool(params.get('show_conf', self.show_conf))
        self.show_bg = bool(params.get('show_bg', self.show_bg))
        self.show_mask = bool(params.get('show_mask', self.show_mask))

    def draw_detections(self, frame, results_obj, names_map, show_track_id=True):
        """Desenha detecções com suporte a masks (segmentação).
        Prioriza masks sobre boxes se disponíveis."""
        # Primeiro, desenha masks se show_mask estiver ativado
        if self.show_mask and getattr(results_obj, 'masks', None) is not None:
            try:
                cls_list = results_obj.boxes.cls.int().cpu().numpy() if results_obj.boxes is not None else []
                for mask_idx, mask_xy in enumerate(results_obj.masks.xy):
                    if len(mask_xy) > 0 and mask_idx < len(cls_list):
                        c = int(cls_list[mask_idx])
                        cls_name = names_map.get(c, "Unknown")
                        color = self.colors.get(cls_name, (0, 255, 0))
                        
                        # Desenha máscara com preenchimento translúcido
                        pts = np.int32([mask_xy])
                        overlay = frame.copy()
                        cv2.fillPoly(overlay, pts, color)
                        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
                        
                        # Desenha contorno da máscara
                        cv2.polylines(frame, pts, isClosed=True, color=color, thickness=self.box_thickness)
                        
                        # Desenha label próximo ao centroide da máscara
                        if self.show_label:
                            centroid = np.mean(mask_xy, axis=0).astype(int)
                            self._draw_label(frame, cls_name, centroid[0], centroid[1], color)
            except Exception as e:
                pass  # Fallback para boxes
        
        # Fallback: desenha boxes se não houver masks
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
            
            # Desenha o retângulo (apenas se não temos masks)
            if not (self.show_mask and getattr(results_obj, 'masks', None) is not None):
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
    
    def _draw_label(self, frame, label_text, x, y, color):
        """Desenha label em posição específica com fundo."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        (w, h), bl = cv2.getTextSize(label_text, font, self.font_scale, self.font_thickness)
        
        # Calcula posição usando o ponto como referência
        text_x = max(0, x - w // 2)
        text_y = max(h + 5, y - 5)
        
        if self.show_bg:
            cv2.rectangle(frame, (text_x - 2, text_y - h - 2), (text_x + w, text_y + bl), color, -1)
        
        text_color = (255, 255, 255) if self.show_bg else color
        cv2.putText(frame, label_text, (text_x, text_y), font, self.font_scale, text_color, self.font_thickness, cv2.LINE_AA)