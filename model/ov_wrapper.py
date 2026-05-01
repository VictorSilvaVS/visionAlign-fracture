
import numpy as np
import cv2
import yaml
import os
from openvino.runtime import Core


# ---------------------------------------------------------------------------
# Objetos de resultado que imitam a interface ultralytics
# ---------------------------------------------------------------------------

class _Tensor:
    """Tensor simples com .cpu().numpy() e .int() / .tolist()."""
    def __init__(self, data: np.ndarray):
        self._data = np.asarray(data)

    def cpu(self):
        return self

    def numpy(self):
        return self._data

    def int(self):
        return _Tensor(self._data.astype(np.int32))

    def tolist(self):
        return self._data.tolist()

    def __len__(self):
        return len(self._data)

    def __getitem__(self, idx):
        return _Tensor(self._data[idx])

    def __iter__(self):
        for v in self._data:
            yield v


class _Boxes:
    def __init__(self, xyxy, cls, conf, ids=None):
        self.xyxy = _Tensor(xyxy)
        self.cls  = _Tensor(cls)
        self.conf = _Tensor(conf)
        self.id   = _Tensor(ids) if ids is not None else None

    def __len__(self):
        return len(self.xyxy)

    def __getitem__(self, idx):
        ids = self.id._data[idx] if self.id is not None else None
        return _Boxes(
            self.xyxy._data[idx],
            self.cls._data[idx],
            self.conf._data[idx],
            ids,
        )


class _Masks:
    def __init__(self, xy_list):
        # xy_list: lista de arrays (N_pts, 2) em coordenadas de pixel
        self.xy = xy_list

    def __len__(self):
        return len(self.xy)


class _Results:
    def __init__(self, boxes: _Boxes, masks: _Masks = None):
        self.boxes = boxes
        self.masks = masks

    def __len__(self):
        return len(self.boxes) if self.boxes else 0

    def __getitem__(self, idx):
        return _Results(self.boxes[idx], None)


# ---------------------------------------------------------------------------
# ByteTrack mínimo (IoU-based)
# ---------------------------------------------------------------------------

class _ByteTracker:
    """Tracker IoU simples para substituir bytetrack.yaml da ultralytics."""

    def __init__(self, iou_thresh=0.3, max_age=30):
        self._iou_thresh = iou_thresh
        self._max_age    = max_age
        self._next_id    = 1
        self._tracks     = {}  # id -> {'box': xyxy, 'age': int}

    @staticmethod
    def _iou(a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        return inter / (area_a + area_b - inter)

    def update(self, boxes_xyxy: np.ndarray) -> np.ndarray:
        """Retorna array de track_ids com mesmo comprimento que boxes_xyxy."""
        if len(boxes_xyxy) == 0:
            for tid in list(self._tracks):
                self._tracks[tid]['age'] += 1
                if self._tracks[tid]['age'] > self._max_age:
                    del self._tracks[tid]
            return np.array([], dtype=np.int32)

        track_ids = list(self._tracks.keys())
        assigned  = {}  # det_idx -> track_id
        used_tids = set()

        for det_idx, det_box in enumerate(boxes_xyxy):
            best_iou = self._iou_thresh
            best_tid = None
            for tid in track_ids:
                if tid in used_tids:
                    continue
                iou = self._iou(det_box, self._tracks[tid]['box'])
                if iou > best_iou:
                    best_iou = iou
                    best_tid = tid
            if best_tid is not None:
                assigned[det_idx] = best_tid
                used_tids.add(best_tid)

        result_ids = []
        for det_idx, det_box in enumerate(boxes_xyxy):
            if det_idx in assigned:
                tid = assigned[det_idx]
                self._tracks[tid] = {'box': det_box, 'age': 0}
                result_ids.append(tid)
            else:
                new_id = self._next_id
                self._next_id += 1
                self._tracks[new_id] = {'box': det_box, 'age': 0}
                result_ids.append(new_id)

        # Envelhece tracks não associados
        for tid in track_ids:
            if tid not in used_tids:
                self._tracks[tid]['age'] += 1
                if self._tracks[tid]['age'] > self._max_age:
                    del self._tracks[tid]

        return np.array(result_ids, dtype=np.int32)


# ---------------------------------------------------------------------------
# Pós-processamento end2end (NMS já embutido no modelo)
# ---------------------------------------------------------------------------

def _postprocess_end2end(outputs, img_w, img_h, input_w, input_h, conf_thresh, task):
    """
    Interpreta saída end2end de modelos YOLO exportados para OpenVINO.
    Retorna (boxes_xyxy, cls, conf, masks_xy_list).

    Formato típico end2end ultralytics OpenVINO:
      output0: [1, num_det, 6]  -> [x1,y1,x2,y2, conf, cls]   (detect)
      output0: [1, num_det, 6+mask_dim] + output1: [1, mask_dim, mh, mw]  (segment)
    """
    scale_x = img_w / input_w
    scale_y = img_h / input_h

    # Identifica tensores de saída
    det_out  = None
    proto_out = None

    for name, arr in outputs.items():
        arr = arr.squeeze(0)  # remove batch dim
        if arr.ndim == 2:
            det_out = arr      # (num_det, 6+k)
        elif arr.ndim == 3:
            proto_out = arr    # (mask_dim, mh, mw)

    if det_out is None or len(det_out) == 0:
        return np.empty((0, 4)), np.empty(0), np.empty(0), []

    # Filtra por confiança
    confs = det_out[:, 4].astype(np.float32)
    mask  = confs >= conf_thresh
    det_out = det_out[mask]
    if len(det_out) == 0:
        return np.empty((0, 4)), np.empty(0), np.empty(0), []

    boxes_norm = det_out[:, :4].astype(np.float32)
    confs      = det_out[:, 4].astype(np.float32)
    cls_ids    = det_out[:, 5].astype(np.int32)

    # Desnormaliza coordenadas (end2end já em pixels do input ou normalizadas 0-1)
    # Detecta se está normalizado (valores <= 1.0) ou em pixels do input
    if boxes_norm[:, 2].max() <= 1.5:
        boxes_xyxy = boxes_norm * np.array([input_w, input_h, input_w, input_h])
    else:
        boxes_xyxy = boxes_norm.copy()

    # Escala para o frame original
    boxes_xyxy[:, [0, 2]] *= scale_x
    boxes_xyxy[:, [1, 3]] *= scale_y
    boxes_xyxy = boxes_xyxy.astype(np.float32)

    masks_xy = []
    if task == 'segment' and proto_out is not None and det_out.shape[1] > 6:
        mask_coefs = det_out[:, 6:].astype(np.float32)  # (N, mask_dim)
        mask_dim, mh, mw = proto_out.shape
        proto_flat = proto_out.reshape(mask_dim, -1)     # (mask_dim, mh*mw)

        for i, coef in enumerate(mask_coefs):
            mask_map = (coef @ proto_flat).reshape(mh, mw)
            mask_map = 1 / (1 + np.exp(-mask_map))       # sigmoid

            # Recorta na bbox do input
            x1i = int(np.clip(boxes_xyxy[i, 0] / scale_x, 0, input_w))
            y1i = int(np.clip(boxes_xyxy[i, 1] / scale_y, 0, input_h))
            x2i = int(np.clip(boxes_xyxy[i, 2] / scale_x, 0, input_w))
            y2i = int(np.clip(boxes_xyxy[i, 3] / scale_y, 0, input_h))

            mask_resized = cv2.resize(mask_map, (input_w, input_h), interpolation=cv2.INTER_LINEAR)
            binary = (mask_resized[y1i:y2i, x1i:x2i] > 0.5).astype(np.uint8)

            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                cnt = max(contours, key=cv2.contourArea)
                pts = cnt.reshape(-1, 2).astype(np.float32)
                # Translada de volta para coordenadas do frame original
                pts[:, 0] = pts[:, 0] * scale_x + boxes_xyxy[i, 0] - x1i * scale_x
                pts[:, 1] = pts[:, 1] * scale_y + boxes_xyxy[i, 1] - y1i * scale_y
                masks_xy.append(pts)
            else:
                masks_xy.append(np.empty((0, 2), dtype=np.float32))

    return boxes_xyxy, cls_ids, confs, masks_xy


# ---------------------------------------------------------------------------
# Classe principal OVModel
# ---------------------------------------------------------------------------

class OVModel:
    """
    Substituto drop-in para ultralytics.YOLO com backend OpenVINO puro.
    Suporta .predict() e .track() com saída compatível com DetectionDrawer.
    """

    def __init__(self, model_dir: str, task: str = None):
        xml_path = os.path.join(model_dir, 'best.xml')
        meta_path = os.path.join(model_dir, 'metadata.yaml')

        with open(meta_path, 'r') as f:
            meta = yaml.safe_load(f)

        self.task  = task or meta.get('task', 'detect')
        self.names = {int(k): v for k, v in meta['names'].items()}
        imgsz      = meta.get('imgsz', [640, 640])
        self._input_h, self._input_w = imgsz[0], imgsz[1]

        ie = Core()
        model = ie.read_model(xml_path)
        self._compiled = ie.compile_model(model, 'CPU')
        # Algumas versões/modelos do OpenVINO podem não ter nomes definidos para os tensores de saída.
        # Usamos any_name com um fallback para evitar RuntimeError.
        self._output_names = []
        for i, o in enumerate(self._compiled.outputs):
            try:
                name = o.any_name
            except Exception:
                name = f"output_{i}"
            self._output_names.append(name)

        self._tracker = _ByteTracker()

    def _preprocess(self, frame: np.ndarray):
        img = cv2.resize(frame, (self._input_w, self._input_h), interpolation=cv2.INTER_LINEAR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        return img.transpose(2, 0, 1)[np.newaxis]  # (1, 3, H, W)

    def _infer(self, blob):
        result = self._compiled(blob)
        return {self._output_names[i]: result[o] for i, o in enumerate(self._compiled.outputs)}

    def _build_results(self, frame, outputs, conf, with_tracking=False):
        h, w = frame.shape[:2]
        boxes_xyxy, cls_ids, confs, masks_xy = _postprocess_end2end(
            outputs, w, h, self._input_w, self._input_h, conf, self.task
        )

        ids = None
        if with_tracking and len(boxes_xyxy) > 0:
            ids = self._tracker.update(boxes_xyxy)

        masks_obj = _Masks(masks_xy) if masks_xy else None
        boxes_obj = _Boxes(boxes_xyxy, cls_ids, confs, ids)
        return [_Results(boxes_obj, masks_obj)]

    def predict(self, frame: np.ndarray, conf=0.25, iou=0.45,
                device=None, verbose=False, **kwargs):
        blob    = self._preprocess(frame)
        outputs = self._infer(blob)
        return self._build_results(frame, outputs, conf, with_tracking=False)

    def track(self, frame: np.ndarray, persist=True, conf=0.25, iou=0.45,
              verbose=False, tracker=None, **kwargs):
        blob    = self._preprocess(frame)
        outputs = self._infer(blob)
        return self._build_results(frame, outputs, conf, with_tracking=True)
