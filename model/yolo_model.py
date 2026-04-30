import logging
import cv2
import numpy as np
import time
import os
import threading
import subprocess
from threading import Event, RLock
from concurrent.futures import ThreadPoolExecutor
from .ov_wrapper import OVModel
from .detection_drawer import DetectionDrawer
from utils.email_utils import send_fracture_alert_email
from utils.database import Database
# Parametros de ambiente para otimização do OpenCV e OpenVINO no Windows
os.environ['OPENCV_CORE_OPTIMIZATION'] = '1'
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|buffer_size;2048000|fifo_size;100000|max_delay;0|timeout;5000000|reorder_queue_size;0|flags;nobuffer'
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
os.environ["OPENCV_NUM_THREADS"] = "8"
os.environ["NUMEXPR_NUM_THREADS"] = "8"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ['OV_CPU_BACKEND'] = 'ONEDNN'


class YOLOModel:
    def __init__(self, model_path, settings, shared_frame_container=None, shared_frame_lock=None):
        self.logger = logging.getLogger("VisionAlign.Model")
        
        try:
            path_align = r"E:\programs\visionAlign\model\_openvino_model\VisionAlign_openvino_model"
            path_fracture = r"E:\programs\visionAlign\model\_openvino_model\VisionFracture_openvino_model"
            
            # FORÇA task=segment APENAS para o modelo de Fratura (se ele for realmente segmentação)
            # Para o Align, deixamos ele detectar automaticamente (é detecção na maioria das vezes)
            self.model_align = OVModel(path_align)
            self.model_fracture = OVModel(path_fracture, task='segment')
            
            self.logger.info(f"Modelos carregados (Align Task: {self.model_align.task} | Fracture Task: {self.model_fracture.task})")
        except Exception as e:
            self.logger.error(f"Erro crítico no carregamento: {e}")
            raise
        self.settings = settings
        ai_params = settings.get('AI_PARAMS', {})
        self.conf = float(ai_params.get('conf_default', 0.25))
        self.iou = float(ai_params.get('iou_default', 0.45))
        self.thresholds = {
            'lata_normal': float(ai_params.get('thresholds', {}).get('lata_normal', 0.5)),
            'lata_invertida': float(ai_params.get('thresholds', {}).get('lata_invertida', 0.5)),
            'lata_tombada': float(ai_params.get('thresholds', {}).get('lata_tombada', 0.5)),
            'fracture': float(ai_params.get('thresholds', {}).get('fracture', 0.5))
        }
        self.exclusion_zones = ai_params.get('advanced', {}).get('exclusion_zones', [])
        self.gamma = float(ai_params.get('advanced', {}).get('gamma', 0.8))
        self._update_gamma_table() # Precalcula a tabela LUT do Gamma
        self.clahe_enabled = ai_params.get('advanced', {}).get('clahe_enabled', True)
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        self.device = 'cpu' 
        self.processing = False
        self.processing_event = Event()
        self.track_fracture_status = {}
        self.fracture_roi_buffer = {}
        self.track_last_check = {}
        self.fracture_check_interval = settings.get('AI_PARAMS', {}).get('advanced', {}).get('roi_check_interval', 0.2)
        self.roi_fixed_size = settings.get('AI_PARAMS', {}).get('advanced', {}).get('roi_fixed_size', 0)
        self.target_fps = settings.get('AI_PARAMS', {}).get('advanced', {}).get('fps_cap', 15.0)
        self.last_roi_frame = None
        self.last_roi_with_mask = None  # ROI com máscaras desenhadas para visualização ao vivo
        self.last_roi_fracture_info = {}  # Informações sobre fratura detectada
        self.last_roi_lock = RLock()  # RLock para melhor concorrência no ROI
        self.track_lock = RLock()      # RLock para proteger estados de votação
        
        # POLÍTICA DE VOTAÇÃO DINÂMICA (Ganho e Perda de Confiança)
        self.vote_policy = {
            'threshold': 10,     # Meta de score para confirmar fratura
            'gain': 1,          # Ganho por frame positivo
            'loss': 1,          # Perda por frame negativo
            'max_score': 15     # Limite para não acumular infinitamente
        }
        self.frame_duration = 1.0 / self.target_fps
        self.video_source = None
        self.current_source_type = None
        self.current_source_param = None
        self.fps = 0.0
        self.class_name_map = {
            'Normal': 'lata_normal',
            'Inverted': 'lata_invertida',
            'Fallen': 'lata_tombada',
            'fracture': 'fracture'
        }
        self.detection_stats = {'lata_normal': 0, 'lata_invertida': 0, 'lata_tombada': 0, 'fracture': 0}
        self.counted_track_ids = {} # Mudado de set para dict para timestamping
        self.max_cache_size = 10000
        # Pipeline Assíncrono Triple-Tier
        self.io_executor = ThreadPoolExecutor(max_workers=4) # Imagens e DB
        self.email_executor = ThreadPoolExecutor(max_workers=1) # E-mail (isolado pois é lento)
        self.frame_callback = None
        detection_colors = settings.get('COLORS', {}).get('detection', {}).copy()
        self.drawer = DetectionDrawer(detection_colors)
        self.names_align = self.model_align.names
        self.names_fracture = self.model_fracture.names
        self.frame_skip = settings.get('AI_PARAMS', {}).get('advanced', {}).get('frame_skip', 0)
        drawing_params = settings.get('AI_PARAMS', {}).get('advanced', {}).get('drawing', {})
        self.drawer.set_params(drawing_params)
        self.dataset_path = r"E:\programs\visionAlign\data\dataset_collect\images"
        if not os.path.exists(self.dataset_path):
            os.makedirs(self.dataset_path, exist_ok=True)
            
        self.last_auto_save = 0
        self.last_event_count = 0
        self.last_event_save_times = {}
        collection = ai_params.get('dataset_collection', {})
        self.collect_enabled = bool(collection.get('enabled', True))
        self.save_interval = float(collection.get('save_interval', 10.0))
        self.conf_distrust_range = collection.get('distrust_range', [0.3, 0.6])
        self.save_on_event = bool(collection.get('save_on_event', False))
        self.last_frame_clean = None
        self.email_alert_cooldown = 300
        self.last_email_alert_time = 0
        
    def set_callback(self, callback):
        self.frame_callback = callback
    def update_conf(self, new_conf):
        self.conf = float(new_conf)
        self.logger.info(f"Confiança ajustada para: {self.conf}")
    def update_iou(self, new_iou):
        """Chamado pela interface para mudar IOU em tempo real."""
        self.iou = float(new_iou)
        self.logger.info(f"IOU ajustado para: {self.iou}")
    def reload_models(self):
        try:
            self.logger.info("Recarregando modelos YOLO...")
            path_align   = r"E:\programs\visionAlign\model\_openvino_model\VisionAlign_openvino_model"
            path_fracture = r"E:\programs\visionAlign\model\_openvino_model\VisionFracture_openvino_model"

            self.model_align    = OVModel(path_align)
            self.model_fracture = OVModel(path_fracture, task='segment')

            self.names_align    = self.model_align.names
            self.names_fracture = self.model_fracture.names

            self.logger.info(f"Modelos recarregados (Align: {self.model_align.task} | Fracture: {self.model_fracture.task})")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao recarregar modelos: {e}")
            return False

    def update_advanced_settings(self, advanced_settings):
        self.logger.info("Aplicando novas configurações avançadas...")
        self.frame_skip = advanced_settings.get('frame_skip', self.frame_skip)
        if 'thresholds' in advanced_settings:
            for k, v in advanced_settings['thresholds'].items():
                self.thresholds[k] = float(v)
            self.logger.info(f"Limiares individuais atualizados: {self.thresholds}")
        if 'exclusion_zones' in advanced_settings:
            self.exclusion_zones = advanced_settings['exclusion_zones']
            self.logger.info(f"Zonas de exclusão atualizadas: {len(self.exclusion_zones)} zonas.")
        self.gamma = float(advanced_settings.get('gamma', self.gamma))
        self._update_gamma_table()
        self.clahe_enabled = advanced_settings.get('clahe_enabled', self.clahe_enabled)
        self.roi_fixed_size = advanced_settings.get('roi_fixed_size', self.roi_fixed_size)
        self.roi_offset_x = int(advanced_settings.get('roi_offset_x', getattr(self, 'roi_offset_x', 0)))
        self.roi_offset_y = int(advanced_settings.get('roi_offset_y', getattr(self, 'roi_offset_y', 0)))
        self.roi_radius = int(advanced_settings.get('roi_radius', getattr(self, 'roi_radius', 0)))
        self.logger.info(f"Filtros: Gamma={self.gamma}, CLAHE={'Ativo' if self.clahe_enabled else 'Inativo'}")
        if 'dataset_collection' in advanced_settings:
            coll = advanced_settings['dataset_collection']
            self.collect_enabled = bool(coll.get('enabled', self.collect_enabled))
            self.save_interval = float(coll.get('save_interval', self.save_interval))
            self.conf_distrust_range = coll.get('distrust_range', self.conf_distrust_range)
            self.save_on_event = bool(coll.get('save_on_event', self.save_on_event))
            self.logger.info(f"Coleta de Dataset: {'Ativa' if self.collect_enabled else 'Inativa'}, Intervalo={self.save_interval}s")
        if 'drawing' in advanced_settings:
            self.drawer.set_params(advanced_settings['drawing'])
            self.logger.info("Configurações visuais de detecção atualizadas.")
        if 'colors' in advanced_settings:
            self.drawer.colors = {k: tuple(map(int, v)) for k, v in advanced_settings['colors'].items()}
            self.logger.info("Cores de detecção atualizadas em tempo real.")
        video_config = advanced_settings.get('video_source', {})
        if video_config:
            source_type = video_config.get('type')
            new_url = video_config.get('stream_url')
            cam_id = video_config.get('camera_id', 0)
            res = video_config.get('resolution')
            fps = video_config.get('fps')
            
            if fps:
                try:
                    self.target_fps = int(fps)
                    self.frame_duration = 1.0 / self.target_fps
                    self.logger.info(f"Target FPS do processamento atualizado para: {self.target_fps}")
                except Exception as e:
                    self.logger.error(f"Erro ao converter FPS: {e}")
            is_new_source = False
            if source_type == 'stream' and str(new_url) != str(self.current_source_param):
                is_new_source = True
            elif source_type == 'camera' and str(cam_id) != str(self.current_source_param):
                is_new_source = True
            elif source_type != self.current_source_type:
                is_new_source = True
                
            if is_new_source:
                self.logger.info(f"Reiniciando captura para nova fonte: {new_url if source_type == 'stream' else source_type} ({res}, {fps} FPS)")
                self.stop_processing()
                self.reset_state()
                
                if source_type == 'stream':
                    self.load_stream(new_url, resolution=res, fps=fps)
                elif source_type == 'camera':
                    self.load_camera(cam_id, resolution=res, fps=fps)
                    
                self.start_processing()
            else:
                self.logger.debug("Fonte de vídeo inalterada. Pulando reconexão de streaming.")

    def _extract_safe_roi(self, frame, results_align, track_id, padding=0.05):
        """Extrai ROI quadrado perfeitamente centrado baseado ESTRITAMENTE na Bounding Box.
        Garante sincronia total com o que o usuário vê na tela (caixa verde real) e resolve 
        distorções causadas por máscaras de segmentação com anomalias de escala.
        """
        h_img, w_img = frame.shape[:2]
        ROI_SIZE = 640
        
        try:
            if results_align.boxes is None or results_align.boxes.id is None:
                return None
            
            track_ids = results_align.boxes.id.int().cpu().numpy()
            target_idx = None
            for idx, tid in enumerate(track_ids):
                if tid == track_id:
                    target_idx = idx
                    break
            
            if target_idx is None:
                return None
            box_xyxy = results_align.boxes.xyxy[target_idx].cpu().numpy()
            x_min, y_min, x_max, y_max = box_xyxy
            
            width = x_max - x_min
            height = y_max - y_min
            roi_fixed_size = getattr(self, "roi_fixed_size", 0)
            if isinstance(roi_fixed_size, (int, float)) and roi_fixed_size > 50:
                side = int(roi_fixed_size)
            else:
                side = int(max(width, height) + 10) # Fallback de quadrado perfeito dinâmico
            
            center_x = (x_min + x_max) / 2
            center_y = (y_min + y_max) / 2
            
            # Aplica os offsets controlados pelo usuário no painel caso o domo da câmera esteja de lado
            offset_x = getattr(self, "roi_offset_x", 0)
            offset_y = getattr(self, "roi_offset_y", 0)
            
            center_x += offset_x
            center_y += offset_y
            
            rx1 = int(center_x - side / 2)
            ry1 = int(center_y - side / 2)
            rx2 = rx1 + side
            ry2 = ry1 + side

            # --- DESLOCAMENTO DE BORDA SEGURO ---
            if rx1 < 0: rx1 = 0; rx2 = side
            if ry1 < 0: ry1 = 0; ry2 = side
            if rx2 > w_img: rx2 = w_img; rx1 = max(0, w_img - side)
            if ry2 > h_img: ry2 = h_img; ry1 = max(0, h_img - side)

            if rx1 >= rx2 or ry1 >= ry2:
                self.logger.warning(f"ROI coordinates invalid: idx={target_idx}, frame={w_img}x{h_img}, box={box_xyxy}, side={side}, coords=({rx1},{ry1},{rx2},{ry2})")
                return None

            roi = frame[ry1:ry2, rx1:rx2].copy()
            if roi.size == 0:
                self.logger.warning(f"ROI is empty: coords=({rx1},{ry1},{rx2},{ry2})")
                return None
            roi_resized = cv2.resize(roi, (ROI_SIZE, ROI_SIZE), interpolation=cv2.INTER_LINEAR)
            return roi_resized

        except Exception as e:
            self.logger.error(f"Erro CRÍTICO ao extrair ROI seguro: {e}")
            return None


    def _has_valid_fracture(self, results_fracture):
        if not results_fracture or len(results_fracture) == 0:
            return False
        r_fr = results_fracture[0]

        # Prioridade: máscaras de segmentação
        if hasattr(r_fr, 'masks') and r_fr.masks is not None and len(r_fr.masks) > 0:
            return True

        # Fallback: detecção com threshold correto
        if r_fr.boxes is not None and len(r_fr.boxes) > 0:
            fracture_threshold = self.thresholds.get('fracture', self.conf)  # ← threshold específico
            for c_idx, f_conf in zip(r_fr.boxes.cls.int().tolist(), r_fr.boxes.conf.tolist()):
                raw_name = self.names_fracture[c_idx]
                name = self.class_name_map.get(raw_name, 'fracture')
                threshold = self.thresholds.get(name, fracture_threshold)
                if f_conf >= threshold:
                    return True
        return False

    def _get_mask_bounding_rect(self, mask_xy_points):
        """Extrai o bounding rect de uma máscara de segmentação.
        Retorna (x1, y1, x2, y2) do retângulo envolvente completo da máscara.
        """
        if not mask_xy_points or len(mask_xy_points) == 0:
            return None
        try:
            pts = np.array(mask_xy_points, dtype=np.int32)
            x_coords = pts[:, 0]
            y_coords = pts[:, 1]
            x1 = int(np.min(x_coords))
            y1 = int(np.min(y_coords))
            x2 = int(np.max(x_coords))
            y2 = int(np.max(y_coords))
            return (x1, y1, x2, y2)
        except Exception as e:
            self.logger.error(f"Erro ao processar máscara: {e}")
            return None

    def _update_gamma_table(self):
        if abs(self.gamma - 1.0) > 0.01:
            invGamma = 1.0 / self.gamma
            self.gamma_table = np.array([((i / 255.0) ** invGamma) * 255 
                                        for i in np.arange(0, 256)]).astype("uint8")
        else:
            self.gamma_table = None

    # --- MÉTODOS DE CARREGAMENTO ---

    def load_stream(self, url, resolution=None, fps=None):
        """Carrega stream RTSP usando OpenCV + FFMPEG."""
        self.current_source_type = 'stream'
        self.current_source_param = url
        if self.video_source: 
            try:
                self.video_source.kill()
            except:
                pass
            self.video_source = None
        
        self.logger.info(f"Abrindo stream FFmpeg Pipe: {url}")
        
        # FFmpeg Pipe - Stream 4K para VisionAlign (ROI é redimensionado p/ 640x640 para o modelo de fratura)
        w, h = 4096, 2160
        if resolution and 'x' in resolution:
            w, h = map(int, resolution.split('x'))

        import shutil
        ffmpeg_cmd = shutil.which('ffmpeg') or 'ffmpeg.exe'
        
        if not url:
            self.logger.warning("Carregamento do stream cancelado: URL está vazia.")
            return False

        command = [
            ffmpeg_cmd,
            '-rtsp_transport', 'tcp', 
            '-max_delay', '500000',
            '-flags', 'low_delay',
            '-fflags', 'nobuffer',
            '-i', url,
            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{w}x{h}',
            '-an',
            '-sn',
            '-v', 'error',
            '-'
        ]
        
        try:
            self.video_source = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=w*h*3)
            self._stream_w = w
            self._stream_h = h
            self.logger.info("Pipe FFmpeg aberto com sucesso.")
            return True
        except Exception as e:
            self.logger.error(f"Erro gigante ao criar Pipe FFmpeg: {e}")
            return False

    def load_camera(self, index, resolution=None, fps=None):
        """Carrega câmera local usando OpenCV."""
        self.current_source_type = 'camera'
        self.current_source_param = index
        if self.video_source: self.video_source.release()
        
        self.logger.info(f"Abrindo câmera: {index}")
        self.video_source = cv2.VideoCapture(int(index))
        
        if not self.video_source.isOpened():
            self.logger.error(f"Falha ao abrir câmera: {index}")
            return False
        
        self._apply_cam_settings(resolution, fps)
        return True

    def _apply_cam_settings(self, resolution, fps):
        if not self.video_source: return
        
        if resolution and 'x' in resolution:
            try:
                w, h = map(int, resolution.split('x'))
                self.video_source.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                self.video_source.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                self.logger.info(f"Resolução solicitada: {w}x{h}")
            except Exception as e:
                self.logger.error(f"Erro ao definir resolução: {e}")
                
        if fps:
            try:
                self.video_source.set(cv2.CAP_PROP_FPS, int(fps))
                self.logger.info(f"FPS da fonte solicitado: {fps}")
            except Exception as e:
                self.logger.error(f"Erro ao definir FPS: {e}")

    def load_video(self, path):
        self.current_source_type = 'video'
        self.current_source_param = path
        if self.video_source: self.video_source.release()
        self.video_source = cv2.VideoCapture(path)
        return self.video_source.isOpened()

    # --- LOOP DE PROCESSAMENTO ---

    def _process_loop(self):
        frame_count = 0
        while self.processing_event.is_set():
            if not self.video_source:
                time.sleep(0.1)
                continue

            cycle_start = time.time()
            frame = None

            if self.current_source_type == 'stream':
                try:
                    # Robust read: Garante que lemos o frame completo do PIPE
                    required_bytes = self._stream_w * self._stream_h * 3
                    frame_bytes = b''
                    while len(frame_bytes) < required_bytes:
                        chunk = self.video_source.stdout.read(required_bytes - len(frame_bytes))
                        if not chunk: break
                        frame_bytes += chunk
                        
                    if len(frame_bytes) != required_bytes:
                        self.logger.warning("FFmpeg Pipe: Frame incompleto ou fim da stream. Reconectando...")
                        if self.video_source:
                            try: self.video_source.kill()
                            except: pass
                        time.sleep(1)
                        self.load_stream(self.current_source_param)
                        continue
                    # .copy() é essencial aqui pois o buffer do pipe é read-only e o OpenCV precisa escrever no frame
                    frame = np.frombuffer(frame_bytes, np.uint8).reshape((self._stream_h, self._stream_w, 3)).copy()
                except Exception as e:
                    self.logger.error(f"Erro ao ler pipe: {e}")
                    time.sleep(1)
                    continue
            else:
                if not self.video_source.isOpened():
                    time.sleep(0.1)
                    continue
                if not self.video_source.grab():
                    self.logger.warning("Falha no grab do frame. Tentando reconectar...")
                    if self.video_source: self.video_source.release()
                    time.sleep(1)
                    if self.current_source_type == 'camera': self.load_camera(self.current_source_param)
                    elif self.current_source_type == 'video': self.load_video(self.current_source_param)
                    continue
                ret, frame = self.video_source.retrieve()
                if not ret or frame is None:
                    continue

            # MEMORY OPTIMIZATION: Evita cópia de 25MB (4K). Reduz para 1080p ou copia direto.
            try:
                h_c, w_c = frame.shape[:2]
                if w_c > 1920:
                    scale_c = 1920 / w_c
                    self.last_frame_clean = cv2.resize(frame, (1920, int(h_c * scale_c)), interpolation=cv2.INTER_AREA)
                else:
                    self.last_frame_clean = frame.copy()
            except Exception:
                self.last_frame_clean = frame.copy()
            cycle_start = time.time()

            frame_count += 1
            # Otimização: GC Periódico para não travar o loop
            if frame_count % 300 == 0:
                self.io_executor.submit(self._cleanup_memory)

            if self.frame_skip > 0 and frame_count % (self.frame_skip + 1) != 0:
                continue

            # 1. Inferência de Alinhamento (Frame Puro)
            results_align = self.model_align.track(
                frame, persist=True, conf=self.conf, iou=self.iou,
                verbose=False, tracker="bytetrack.yaml"
            )

            if results_align and len(results_align) > 0:
                r_align = results_align[0]
                if r_align.boxes is not None and r_align.boxes.id is not None:
                    # Vetorização: Convertendo tensores para NumPy antes do loop (Otimização Intel)
                    cls_arr = r_align.boxes.cls.int().cpu().numpy()
                    conf_arr = r_align.boxes.conf.cpu().numpy()
                    
                    keep_idx = []
                    for k in range(len(cls_arr)):
                        c_idx = cls_arr[k]
                        conf = conf_arr[k]
                        raw_name = self.names_align[c_idx]
                        name = self.class_name_map.get(raw_name, raw_name)
                        if conf >= self.thresholds.get(name, self.conf):
                            keep_idx.append(k)
                    
                    if keep_idx:
                        # FIX: Filtra o objeto de resultado inteiro para manter boxes, masks e IDs em sincronia
                        r_align = r_align[keep_idx]
                        
                        boxes_xyxy = r_align.boxes.xyxy.int().cpu().numpy()
                        track_ids = r_align.boxes.id.int().cpu().numpy()
                        now = time.time()

                        # --- ATUALIZAÇÃO DO ROI "AO VIVO" (Slot 1) em Tempo Real ---
                        # Seleciona a lata que está mais central na imagem para o preview constante
                        if len(track_ids) > 0:
                            img_center_x = frame.shape[1] // 2
                            best_tid = track_ids[0]
                            min_dist = float('inf')
                            for b, t in zip(boxes_xyxy, track_ids):
                                dist = abs((b[0] + b[2]) / 2 - img_center_x)
                                if dist < min_dist:
                                    min_dist = dist
                                    best_tid = t
                            
                            roi_live_raw = self._extract_safe_roi(frame, r_align, best_tid)
                            if roi_live_raw is not None:
                                # Aplicamos preprocessamento (Gamma/CLAHE) para mostrar exatamente o que a IA vê
                                roi_live_processed = self._preprocess_roi(roi_live_raw.copy())
                                with self.last_roi_lock:
                                    self.last_roi_frame = roi_live_processed

                        # MEMORY OPTIMIZAÇÃO: Gera uma versão pequena do frame (Full Context) apenas UMA VEZ por ciclo
                        # e apenas se houver necessidade de processamento de fratura.
                        cached_frame_small = None
                        
                        for box, tid in zip(boxes_xyxy, track_ids):
                            # ID Tracking / Stats (Assíncrono)
                            self.io_executor.submit(self._process_single_result, int(tid), r_align, box.copy())
                            
                            with self.track_lock:
                                # 1. Inicialização Atômica de Votação
                                if tid not in self.track_fracture_status or isinstance(self.track_fracture_status[tid], bool):
                                    self.track_fracture_status[tid] = {
                                        'score': 0, 'attempts': 0, 'confirmed': False, 'alert_sent': False, 'last_seen': now, 'checking': False
                                    }
                                
                                status = self.track_fracture_status[tid]
                                status['last_seen'] = now

                                # Curto-circuito: Só processa se não foi alertado e não está em análise
                                if not status['alert_sent'] and not status.get('checking', False):
                                    if tid not in self.track_last_check or (now - self.track_last_check[tid] > self.fracture_check_interval):
                                        
                                        # ROI extraído baseado na MÁSCARA de segmentação
                                        roi_raw = self._extract_safe_roi(frame, r_align, tid)
                                        if roi_raw is not None:
                                            # Gera o frame de contexto reduzido uma única vez para economizar RAM (4K -> 1080p ou menos)
                                            if cached_frame_small is None:
                                                h_f, w_f = frame.shape[:2]
                                                if w_f > 1280:
                                                    scale = 1280 / w_f
                                                    new_w, new_h = int(w_f * scale), int(h_f * scale)
                                                    cached_frame_small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                                                else:
                                                    cached_frame_small = frame.copy()
                                            
                                            status['checking'] = True 
                                            self.track_last_check[tid] = now
                                            
                                            self.io_executor.submit(
                                                self._run_async_fracture_logic, 
                                                int(tid), roi_raw.copy(), box.copy(), cached_frame_small
                                            )
                            
                            # Desenho de Alerta Visual no frame principal (que será enviado para o Dashboard)
                            if status.get('confirmed'):
                                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 0, 255), 4)
                                cv2.putText(frame, f"!!! FRATURA CONFIRMADA ({tid}) !!!", (box[0], box[1] - 20), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

                    self.drawer.draw_detections(frame, r_align, self.names_align, show_track_id=True)
            actual_duration = time.time() - cycle_start
            self.fps = 1.0 / max(actual_duration, self.frame_duration)
            if self.frame_callback:
                self.frame_callback({
                    'frame': frame,
                    'stats': {**self.detection_stats, 'fps': round(self.fps, 1), 'processamento': 'OpenVINO CPU'}
                })
            time_to_sleep = self.frame_duration - actual_duration
            time.sleep(max(0.001, time_to_sleep))

        if self.video_source:
            if self.current_source_type == 'stream':
                try:
                    self.video_source.terminate()
                except:
                    pass
            else:
                self.video_source.release()

    def _cleanup_memory(self):
        now = time.time()
        if len(self.counted_track_ids) > self.max_cache_size:
            cutoff = now - 3600
            self.counted_track_ids = {k: v for k, v in self.counted_track_ids.items() if v > cutoff}
            if len(self.counted_track_ids) > self.max_cache_size:
                self.counted_track_ids.clear()
        if len(self.track_fracture_status) > 1000:
            with self.track_lock:
                cutoff = now - 600 # 10 minutos
                keys_to_delete = [
                    k for k, v in self.track_fracture_status.items() 
                    if isinstance(v, dict) and v.get('last_seen', 0) < cutoff
                ]
                for k in keys_to_delete:
                    del self.track_fracture_status[k]

    def _run_async_fracture_logic(self, tid, roi_raw, box, frame):
        """Desacopla a IA de fratura do loop RTSP."""
        try:
            if roi_raw is None or roi_raw.size == 0:
                self.logger.debug(f"ROI inválido para ID {tid}")
                return
            
            with self.last_roi_lock:
                self.last_roi_frame = roi_raw.copy()
            
            roi_processed = self._preprocess_roi(roi_raw)
            if roi_processed is None or roi_processed.size == 0:
                self.logger.debug(f"ROI processado inválido para ID {tid}")
                return

            # --- FOCO NA ÁREA DE INTERESSE (AOI) ---
            h_p, w_p = roi_processed.shape[:2]
            center_roi = (w_p // 2, h_p // 2)
            
            # Utiliza o raio calibrado visualmente pelo painel (suporta override avançado, evita hardcodes antigos)
            aoi_radius_px = getattr(self, 'roi_radius', 244)
            if aoi_radius_px <= 0 or aoi_radius_px >= w_p:
                px_per_mm = (max(h_p, w_p) - 10) / 65.75
                aoi_radius_px = int((51.0 * px_per_mm) / 2) # Fallback

            # Criamos uma máscara preta para o que está fora do círculo calibrado
            aoi_mask = np.zeros((h_p, w_p), dtype=np.uint8)
            cv2.circle(aoi_mask, center_roi, aoi_radius_px, 255, -1)
            roi_processed = cv2.bitwise_and(roi_processed, roi_processed, mask=aoi_mask)

            import gc
            gc.collect()
            results_fracture = self.model_fracture.predict(
                roi_processed, conf=self.conf, iou=self.iou, device=self.device, verbose=False
            )
            is_fracture_now = self._has_valid_fracture(results_fracture)
            
            # Desenha guia da AOI de 51mm no ROI para o Dashboard (azul claro)
            roi_with_mask = roi_raw.copy()
            cv2.circle(roi_with_mask, center_roi, aoi_radius_px, (255, 255, 0), 1, lineType=cv2.LINE_AA)
            cv2.putText(roi_with_mask, "AOI 51mm", (center_roi[0] - aoi_radius_px, center_roi[1] - aoi_radius_px - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
            
            fracture_info = {
                'detected': False,
                'mask_count': 0,
                'total_area_px': 0.0,
                'timestamp': time.time()
            }
            
            if results_fracture and len(results_fracture) > 0:
                r_fr = results_fracture[0]
                if hasattr(r_fr, 'masks') and r_fr.masks is not None and len(r_fr.masks) > 0:
                    try:
                        # Lógica requisitada pelo usuário: Seleciona APENAS a maior máscara de fratura (max 1 identificador)
                        largest_area = -1
                        best_pts = None
                        
                        for mask_idx, mask_xy in enumerate(r_fr.masks.xy):
                            if len(mask_xy) > 2:
                                pts = np.array(mask_xy, dtype=np.int32).reshape((-1, 1, 2))
                                area = cv2.contourArea(pts.astype(np.float32))
                                if area > largest_area:
                                    largest_area = area
                                    best_pts = pts
                                    
                        if best_pts is not None:
                            # --- ESTILO LIMPO E PRECISO (Exato contorno da segmentação vs bloco quadrado horrendo) ---
                            cv2.drawContours(roi_with_mask, [best_pts], -1, (0, 0, 255), 2, lineType=cv2.LINE_AA)
                            
                            # Suave Fill Interno Translúcido no poli do contorno original (só 25%)
                            overlay = roi_with_mask.copy()
                            cv2.fillPoly(overlay, [best_pts], (0, 0, 255))
                            cv2.addWeighted(overlay, 0.25, roi_with_mask, 0.75, 0, roi_with_mask)
                            
                            fracture_info['mask_count'] = 1
                            fracture_info['total_area_px'] = largest_area
                    except Exception as mask_err:
                        self.logger.debug(f"Erro ao desenhar mask para visualização: {mask_err}")
            
            fracture_info['detected'] = is_fracture_now
            with self.last_roi_lock:
                self.last_roi_with_mask = roi_with_mask.copy()
                self.last_roi_fracture_info = fracture_info.copy()
            with self.track_lock:
                if tid not in self.track_fracture_status:
                    return
                status = self.track_fracture_status[tid]
                status['attempts'] += 1
                if is_fracture_now:
                    status['score'] = min(self.vote_policy['max_score'], status['score'] + self.vote_policy['gain'])
                else:
                    status['score'] = max(0, status['score'] - self.vote_policy['loss'])
                if status['score'] >= self.vote_policy['threshold'] and not status['confirmed']:
                    status['confirmed'] = True
                    status['alert_sent'] = True
                    self.logger.warning(f"SISTEMA DE VOTAÇÃO: Fratura CONFIRMADA ID {tid} (Score: {status['score']})")
                    if 'fracture' in self.detection_stats:
                        self.detection_stats['fracture'] += 1
                    h_f, w_f = frame.shape[:2]
                    if w_f > 1920:
                        scale = 1920 / w_f
                        new_w, new_h = int(w_f * scale), int(h_f * scale)
                        frame_small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    else:
                        frame_small = frame.copy()
                    
                    self.io_executor.submit(
                        self._save_inspection_result, 
                        frame_small, roi_processed.copy(), int(tid), box.copy(), True, results_fracture
                    )
        except Exception as e:
            self.logger.error(f"Erro na inferência assíncrona de fratura: {e}")
        finally:
            with self.track_lock:
                if tid in self.track_fracture_status:
                    self.track_fracture_status[tid]['checking'] = False

    def _process_single_result(self, tid, r_align, box):
        """Processa um único tracking ID, atualizando estatísticas se for novo."""
        now = time.time()
        unique_tid = f"align_{tid}"
        if unique_tid not in self.counted_track_ids:
            self.counted_track_ids[unique_tid] = now
            try:
                ids = r_align.boxes.id.int().cpu().numpy().tolist()
                if tid in ids:
                    idx = ids.index(tid)
                    c = int(r_align.boxes.cls[idx])
                    raw_name = self.names_align[c]
                    name = self.class_name_map.get(raw_name, raw_name)
                    if name in self.detection_stats:
                        self.detection_stats[name] += 1
            except Exception:
                pass

    def _process_results(self, r, names, model_type="align"):
        """Legado: Mantido por compatibilidade mas redireciona para a nova lógica se necessário."""
        pass

    def _count_fracture_detections(self, r_fracture, names):
        """Contabiliza fraturas segmentadas pelo VisionFracture (sem tracking ID)."""
        if hasattr(r_fracture, 'masks') and r_fracture.masks is not None and len(r_fracture.masks) > 0:
            if r_fracture.boxes is not None:
                cls_list = r_fracture.boxes.cls.int().tolist()
                conf_list = r_fracture.boxes.conf.tolist()
                for c, conf in zip(cls_list, conf_list):
                    raw_name = names[c]
                    name = self.class_name_map.get(raw_name, raw_name)
                    if conf >= self.thresholds.get(name, self.conf):
                        if name in self.detection_stats:
                            self.detection_stats[name] += 1
        elif r_fracture.boxes is not None:
            cls_list = r_fracture.boxes.cls.int().tolist()
            conf_list = r_fracture.boxes.conf.tolist()
            for c, conf in zip(cls_list, conf_list):
                raw_name = names[c]
                name = self.class_name_map.get(raw_name, raw_name)
                if conf >= self.thresholds.get(name, self.conf):
                    if name in self.detection_stats:
                        self.detection_stats[name] += 1

    def _preprocess_roi(self, img):
        """Aplica filtros apenas no ROI (ex: 640x640) economizando CPU vs full frame 8MP."""
        try:
            if img is None or img.size == 0 or len(img.shape) != 3:
                return img
                
            if self.gamma_table is not None:
                # Garante que a imagem é uint8 para o LUT
                if img.dtype != np.uint8:
                    img = img.astype(np.uint8)
                img = cv2.LUT(img, self.gamma_table)
            if self.clahe_enabled:
                lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                cl = self.clahe.apply(l)
                limg = cv2.merge((cl, a, b))
                img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
                
            return img
        except Exception as e:
            self.logger.error(f"Erro no pré-processamento do ROI: {e}")
            return img

    def save_for_dataset(self, prefix="manual"):
        """Salva o frame atual (limpo) na pasta de dataset."""
        if self.last_frame_clean is None:
            return False, "Nenhum frame disponível."
        
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.jpg"
            save_path = os.path.join(self.dataset_path, filename)
            cv2.imwrite(save_path, self.last_frame_clean)
            self.logger.info(f"Frame salvo para dataset: {save_path}")
            return True, filename
        except Exception as e:
            self.logger.error(f"Erro ao salvar frame: {e}")
            return False, str(e)

    def _maybe_auto_save(self, reason, force=False):
        if not self.collect_enabled and not force:
            return
        now = time.time()
        if force:
            if reason in self.last_event_save_times:
                if now - self.last_event_save_times[reason] < 10:
                    return
            self.last_event_save_times[reason] = now
        if force or (now - self.last_auto_save > self.save_interval):
            self.save_for_dataset(prefix=f"auto_{reason}")
            if not force:
                self.last_auto_save = now

    def _save_inspection_result(self, full_frame, roi, tid, box, is_fracture, results_fracture=None):
        if not is_fracture:
            return
        now = time.time()
        # Cooldown por ID para evitar loop de gravação se o tracking falhar
        per_id_key = f"fracture_alert_{tid}"
        if now - self.last_event_save_times.get(per_id_key, 0) < 30: # 30 segundos de paz para o mesmo ID
            return
        self.last_event_save_times[per_id_key] = now
        self.last_event_save_times['fracture_alert_global'] = now # Apenas para registro interno

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            alerts_dir = r"E:\programs\visionAlign\data\alerts"
            os.makedirs(alerts_dir, exist_ok=True)
            # ROI para inspeção HUMANA (Email/Dashboard) deve conter as marcações (inspeção)
            roi_marked = roi.copy()
            h_roi, w_roi = roi_marked.shape[:2]
            fracture_count = 0
            label_type = "Inspecionada"
            
            if results_fracture and len(results_fracture) > 0:
                r_fr = results_fracture[0]
                if hasattr(r_fr, 'masks') and r_fr.masks is not None and len(r_fr.masks) > 0:
                    try:
                        for mask_idx, mask_xy in enumerate(r_fr.masks.xy):
                            if len(mask_xy) > 2:
                                pts = np.array(mask_xy, dtype=np.int32).reshape((-1, 1, 2))
                                # --- ESTILO INSTANCE SEGMENTATION (alerta salvo) ---
                                # 1. Fill semi-transparente
                                overlay = roi_marked.copy()
                                cv2.fillPoly(overlay, [pts], (60, 20, 220))
                                cv2.addWeighted(overlay, 0.45, roi_marked, 0.55, 0, roi_marked)
                                # Sem linhas externas de contorno ("apenas o interior")
                                fracture_count += 1
                        label_type = "SEGMENTADA"
                    except Exception as mask_err:
                        self.logger.warning(f"Erro ao marcar mask no ROI de alerta: {mask_err}")
                
                # Sem fallback de box: se não há máscara, não desenha retângulo
                if fracture_count == 0:
                    self.logger.debug("Nenhuma máscara de fratura disponível para visualização.")

            # Legenda discreta no canto inferior (sem texto sobre a imagem principal)
            h_roi_m, w_roi_m = roi_marked.shape[:2]
            cv2.putText(roi_marked, "FRATURA DETECTADA", (8, h_roi_m - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 40, 255), 1, cv2.LINE_AA)

            roi_filename = f"ROI_insp_FR_{tid}_{timestamp}.jpg"
            roi_path = os.path.join(alerts_dir, roi_filename)
            cv2.imwrite(roi_path, roi_marked) 
            
            marked_frame = full_frame.copy()
            x1, y1, x2, y2 = box
            center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
            radius = int(max(x2 - x1, y2 - y1) / 2) + 10
            cv2.circle(marked_frame, center, radius, (0, 0, 255), 3)
            cv2.putText(marked_frame, f"FRATURA DETECTADA - ID:{tid}", (x1, max(y1 - 20, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            full_filename = f"Alert_insp_FR_{tid}_{timestamp}.jpg"
            full_path = os.path.join(alerts_dir, full_filename)
            cv2.imwrite(full_path, marked_frame)
            self.logger.info(f"ALERTA DE FRATURA GERADO: {full_path}")
            try:
                with Database() as db:
                    alert_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    db.log_alert(
                        timestamp=alert_timestamp,
                        alert_type="fracture",
                        lata_id=str(tid),
                        details=f"Fratura detectada - ROI: {roi_filename}"
                    )
                    
                    # 2. Enviar e-mail isolado (offloading para email_executor)
                    if now - self.last_email_alert_time > self.email_alert_cooldown:
                        self.last_email_alert_time = now
                        recipients = db.get_users_for_email_notification()
                        if recipients:
                            subject = f"Fratura ID {tid}"
                            body_text = (f"Detecção realizada pelo VisionFracture.\n"
                                         f"Lata ID: {tid}\nHorário: {time.ctime()}")
                            
                            # Disparo isolado: não trava o io_executor nem o loop de frames
                            self.email_executor.submit(
                                send_fracture_alert_email,
                                recipients, subject, body_text, full_path, roi_path
                            )
            except Exception as db_err:
                self.logger.error(f"Erro ao registrar no Banco de Dados: {db_err}")

        except Exception as e:
            self.logger.error(f"Erro ao salvar resultado de inspeção: {e}")

    def reset_state(self):
        """Reseta contadores internos e limpa cache de imagem LIVE para nova fonte."""
        self.logger.info("Resetando estado interno e cache de visualização LIVE...")
        
        # 1. Zerar estatísticas de detecção (Inicia nova contagem para a nova fonte)
        for key in self.detection_stats:
            self.detection_stats[key] = 0
            
        # 2. Limpar cache de IDs e buffers de processamento
        with self.track_lock:
            self.counted_track_ids.clear()
            self.track_fracture_status.clear()
            self.track_last_check.clear()
            self.fracture_roi_buffer.clear()
            
        # 3. Limpar referências para as últimas imagens da câmera anterior (Thread-safe)
        if hasattr(self, 'last_roi_lock'):
            with self.last_roi_lock:
                self.last_roi_frame = None
                self.last_roi_with_mask = None
                self.last_roi_fracture_info = {}
                self.last_full_frame = None
        
        self.logger.info("Estado interno resetado. O Dataset em disco foi preservado.")

    def start_processing(self):
        if not self.processing:
            self.processing = True
            
            # Recriando os executores de threads de forma limpa caso o serviço tenha sido parado (ex: settings reload)
            self.io_executor = ThreadPoolExecutor(max_workers=4)
            self.email_executor = ThreadPoolExecutor(max_workers=1)
            
            self.processing_event.set()
            self.thread = threading.Thread(target=self._process_loop, daemon=True)
            self.thread.start()
            self.logger.info("Processamento iniciado e executores ativados.")

    def stop_processing(self):
        self.processing = False
        self.processing_event.clear()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        self.io_executor.shutdown(wait=False)
        self.email_executor.shutdown(wait=False)
        self.logger.info("Processamento parado e executores de I/O e E-mail encerrados.")