import logging
import cv2
import numpy as np
import time
import threading
import os
from threading import Event, RLock
from ultralytics import YOLO
from .detection_drawer import DetectionDrawer
from utils.email_utils import send_fracture_alert_email
from utils.database import Database

# **OTIMIZAÇÃO XEON GOLD**: Config de threads e OpenCV
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|buffer_size;102400|max_delay;0|timeout;5000000'
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"
os.environ["OPENCV_NUM_THREADS"] = "8"
os.environ["NUMEXPR_NUM_THREADS"] = "8"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

class YOLOModel:
    def __init__(self, model_path, settings, shared_frame_container=None, shared_frame_lock=None):
        self.logger = logging.getLogger("VisionAlign.Model")
        
        try:
            path_align = r"E:\programs\visionAlign\model\_openvino_model\VisionAlign_openvino_model"
            path_fracture = r"E:\programs\visionAlign\model\_openvino_model\VisionFracture_openvino_model"
            
            self.model_align = YOLO(path_align, task='detect')
            self.model_fracture = YOLO(path_fracture, task='detect')
            
            self.logger.info("Modelos OpenVINO carregados com sucesso.")
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
        self.clahe_enabled = ai_params.get('advanced', {}).get('clahe_enabled', True)
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        self.device = 'cpu' 
        self.processing = False
        self.processing_event = Event()
        self.track_fracture_status = {}
        self.fracture_roi_buffer = {}
        self.track_last_check = {}
        self.fracture_check_interval = settings.get('AI_PARAMS', {}).get('advanced', {}).get('roi_check_interval', 2.0)
        self.target_fps = settings.get('AI_PARAMS', {}).get('advanced', {}).get('fps_cap', 15.0)
        self.last_roi_frame = None
        self.last_roi_lock = RLock()  # **OTIMIZAÇÃO: RLock para melhor concorrência**
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
        self.counted_track_ids = set()
        self.frame_callback = None
        detection_colors = settings.get('COLORS', {}).get('detection', {}).copy()
        self.drawer = DetectionDrawer(detection_colors)
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
        self.clahe_enabled = advanced_settings.get('clahe_enabled', self.clahe_enabled)
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
        video_config = advanced_settings.get('video_source', {})
        if video_config:
            source_type = video_config.get('type')
            new_url = video_config.get('stream_url')
            res = video_config.get('resolution')
            fps = video_config.get('fps')
            if fps:
                try:
                    self.target_fps = int(fps)
                    self.frame_duration = 1.0 / self.target_fps
                    self.logger.info(f"Target FPS do processamento atualizado para: {self.target_fps}")
                except Exception as e:
                    self.logger.error(f"Erro ao converter FPS: {e}")
            
            # Se a fonte mudou, reiniciamos o processamento
            self.logger.info(f"Reiniciando captura para nova fonte: {new_url if source_type == 'stream' else source_type} ({res}, {fps} FPS)")
            self.stop_processing()
            
            if source_type == 'stream':
                self.load_stream(new_url, resolution=res, fps=fps)
            elif source_type == 'camera':
                self.load_camera(video_config.get('camera_id', 0), resolution=res, fps=fps)
                
            self.start_processing()

    # --- MÉTODOS DE CARREGAMENTO ---

    def load_stream(self, url, resolution=None, fps=None):
        """Carrega stream RTSP usando OpenCV + FFMPEG."""
        self.current_source_type = 'stream'
        self.current_source_param = url
        if self.video_source: self.video_source.release()
        
        self.logger.info(f"Abrindo stream RTSP: {url}")
        self.video_source = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        
        if not self.video_source.isOpened():
            self.logger.error(f"Falha ao abrir stream: {url}")
            return False
        
        self._apply_cam_settings(resolution, fps)
        return True

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
            if not self.video_source or not self.video_source.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.video_source.read()
            if not ret:
                self.logger.warning("Falha na leitura do frame. Tentando reconectar...")
                if self.video_source: self.video_source.release()
                time.sleep(2)
                # Reconectar à fonte atual
                if self.current_source_type == 'stream': self.load_stream(self.current_source_param)
                elif self.current_source_type == 'camera': self.load_camera(self.current_source_param)
                elif self.current_source_type == 'video': self.load_video(self.current_source_param)
                continue

            self.last_frame_clean = frame.copy()
            cycle_start = time.time()

            frame_count += 1
            if self.frame_skip > 0 and frame_count % (self.frame_skip + 1) != 0:
                continue

            # --- PRE-PROCESSAMENTO GLOBAL ---
            frame_processed = self._preprocess_frame(frame)

            # 1. Detecção e Tracking VisionAlign (Full Frame)
            results_align = self.model_align.track(
                frame_processed,
                persist=True,
                conf=self.conf,
                iou=self.iou,
                device=self.device,
                verbose=False,
                tracker="bytetrack.yaml"
            )
            if results_align and len(results_align) > 0:
                r_align = results_align[0]
                
                if r_align.boxes is not None:
                    # Filtro de confiança por classe
                    keep_idx = []
                    for k, (c_idx, conf) in enumerate(zip(r_align.boxes.cls.int().tolist(), r_align.boxes.conf.tolist())):
                        raw_name = self.names_align[c_idx]
                        name = self.class_name_map.get(raw_name, raw_name)
                        if conf >= self.thresholds.get(name, self.conf):
                            keep_idx.append(k)
                    
                    if keep_idx:
                        r_align.boxes = r_align.boxes[keep_idx]
                        boxes_xyxy = r_align.boxes.xyxy.int().cpu().numpy()
                        track_ids = r_align.boxes.id.int().cpu().numpy() if r_align.boxes.id is not None else range(len(boxes_xyxy))
                        now = time.time()

                        for box, tid in zip(boxes_xyxy, track_ids):
                            x1, y1, x2, y2 = box

                            # Só dispara a detecção de fratura no intervalo configurado
                            if tid not in self.track_last_check or (now - self.track_last_check[tid] > self.fracture_check_interval):
                                h_img, w_img = frame.shape[:2]
                                
                                # --- RECORTE QUADRADO (Garante que a IA não distorça a lata) ---
                                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                                side = int(max(x2 - x1, y2 - y1) * 1.30) # 30% de margem
                                
                                rx1, ry1 = max(0, cx - side // 2), max(0, cy - side // 2)
                                rx2, ry2 = min(w_img, cx + side // 2), min(h_img, cy + side // 2)

                                roi = frame[ry1:ry2, rx1:rx2].copy()
                                if roi.size == 0: continue

                                with self.last_roi_lock:
                                    self.last_roi_frame = roi.copy()

                                # 2. Inferência de Fratura no ROI (sem pós-processamento)
                                results_fracture = self.model_fracture.predict(
                                    roi, conf=self.conf, iou=self.iou, device=self.device, verbose=False
                                )

                                has_fracture = False
                                if results_fracture and len(results_fracture) > 0:
                                    r_fr = results_fracture[0]
                                    if r_fr.boxes is not None and len(r_fr.boxes) > 0:
                                        # Verifica se algum objeto detectado no ROI passa no threshold de fratura
                                        for c_idx, f_conf in zip(r_fr.boxes.cls.int().tolist(), r_fr.boxes.conf.tolist()):
                                            f_name = self.class_name_map.get(self.names_fracture[c_idx], "fracture")
                                            if f_conf >= self.thresholds.get(f_name, self.conf):
                                                has_fracture = True
                                                break
                                        
                                        if has_fracture:
                                            # Salva o alerta e ROI se confirmado
                                            self._save_inspection_result(frame, roi, tid, box, is_fracture=True, results_fracture=results_fracture)

                                self.track_fracture_status[tid] = has_fracture
                                self.track_last_check[tid] = now

                            # --- DESENHO DE RESULTADOS NO FRAME PRINCIPAL ---
                            if self.track_fracture_status.get(tid, False):
                                # Alerta de Fratura (Círculo vermelho e texto)
                                cv2.circle(frame, (cx, cy), (x2 - x1) // 2 + 10, (0, 0, 255), 2)
                                cv2.putText(frame, "!!! FRATURA !!!", (x1, y1 - 10), 
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    # Desenha as caixas do VisionAlign
                    self.drawer.draw_detections(frame, r_align, self.names_align, show_track_id=True)
                    self._process_results(r_align, self.names_align, model_type="align")

            # Cálculo de FPS e Callback da Interface
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
            self.video_source.release()
    def _process_results(self, r, names, model_type="align"):
        """Contabiliza detecções DO MODELO DE ALINHAMENTO (requer tracking ID único)."""
        if r.boxes is None or r.boxes.id is None:
            return

        cls_list = r.boxes.cls.int().tolist()
        id_list = r.boxes.id.int().tolist()
        conf_list = r.boxes.conf.tolist()

        for c, tid, conf in zip(cls_list, id_list, conf_list):
            raw_name = names[c]
            name = self.class_name_map.get(raw_name, raw_name)
            if name == 'fracture':
                continue  # Fraturas são contabilizadas por _count_fracture_detections
            if conf >= self.thresholds.get(name, self.conf):
                unique_tid = f"{model_type}_{tid}"
                if unique_tid not in self.counted_track_ids:
                    self.counted_track_ids.add(unique_tid)
                    if name in self.detection_stats:
                        self.detection_stats[name] += 1

    def _count_fracture_detections(self, r_fracture, names):
        """Contabiliza fraturas detectadas pelo VisionFracture (sem tracking ID)."""
        if r_fracture.boxes is None:
            return
        cls_list = r_fracture.boxes.cls.int().tolist()
        conf_list = r_fracture.boxes.conf.tolist()
        for c, conf in zip(cls_list, conf_list):
            raw_name = names[c]
            name = self.class_name_map.get(raw_name, raw_name)
            if conf >= self.thresholds.get(name, self.conf):
                if name in self.detection_stats:
                    self.detection_stats[name] += 1

    def _preprocess_frame(self, frame):
        """Aplica filtros CLAHE e correção de Gamma para melhorar detecção."""
        try:
            if abs(self.gamma - 1.0) > 0.01:
                invGamma = 1.0 / self.gamma
                table = np.array([((i / 255.0) ** invGamma) * 255 
                                 for i in np.arange(0, 256)]).astype("uint8")
                frame = cv2.LUT(frame, table)

            # 2. CLAHE (Equalização de contraste adaptativa)
            if self.clahe_enabled:
                # Converte para LAB (mais eficiente para CLAHE sem distorcer cores)
                lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                cl = self.clahe.apply(l)
                limg = cv2.merge((cl, a, b))
                frame = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
                
            return frame
        except Exception as e:
            self.logger.error(f"Erro no pré-processamento: {e}")
            return frame

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
            if not force: # Apenas atualiza o timer de intervalo se for um save por tempo
                self.last_auto_save = now

    def _save_inspection_result(self, full_frame, roi, tid, box, is_fracture, results_fracture=None):
        if not is_fracture:
            return  # Não salva ROIs sem fratura

        now = time.time()
        cooldown_time = 5
        if now - self.last_event_save_times.get('fracture_alert', 0) < cooldown_time:
            return
        self.last_event_save_times['fracture_alert'] = now

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            alerts_dir = r"E:\programs\visionAlign\data\alerts"
            os.makedirs(alerts_dir, exist_ok=True)
            
            # **NOVO: Salvar ROI COM as marcações APENAS nas fraturas detectadas**
            roi_marked = roi.copy()
            h_roi, w_roi = roi_marked.shape[:2]
            
            # Desenha retângulos APENAS ao redor das fraturas detectadas
            fracture_count = 0
            if results_fracture and len(results_fracture) > 0:
                r_fr = results_fracture[0]
                if r_fr.boxes is not None and len(r_fr.boxes) > 0:
                    boxes_xyxy = r_fr.boxes.xyxy.int().cpu().numpy()
                    for box_fr in boxes_xyxy:
                        x1_fr, y1_fr, x2_fr, y2_fr = box_fr
                        # Desenha retângulo vermelho apenas ao redor da fratura
                        cv2.rectangle(roi_marked, (int(x1_fr), int(y1_fr)), (int(x2_fr), int(y2_fr)), (0, 0, 255), 3)
                        fracture_count += 1
            
            # Desenha texto de alerta com a quantidade de fraturas detectadas
            cv2.putText(roi_marked, f"FRATURA DETECTADA! ({fracture_count}x)", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            # Salva o ROI marcado com o label
            roi_filename = f"ROI_insp_FR_{tid}_{timestamp}.jpg"
            roi_path = os.path.join(alerts_dir, roi_filename)
            cv2.imwrite(roi_path, roi_marked)  # roi_marked contém as marcações de fratura
            
            # Salva o frame completo com circle na área da fratura
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
            
            # --- Lógica de Alerta e Email ---
            # 1. Sempre registrar o alerta no banco de dados
            db = Database()
            alert_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            db.log_alert(
                timestamp=alert_timestamp,
                alert_type="fracture",
                lata_id=str(tid),
                details=f"Fratura detectada - ROI: {roi_filename} (com marcações)"
            )
            
            # 2. Enviar e-mail apenas se o cooldown tiver passado
            if now - self.last_email_alert_time > self.email_alert_cooldown:
                self.last_email_alert_time = now
                recipients = db.get_users_for_email_notification()
                if recipients:
                    self.logger.info(f"Iniciando envio de e-mail de alerta de fratura para {recipients}")
                    subject = f"Fratura ID {tid}"
                    body_text = (f"Detecção realizada pelo VisionFracture.\n"
                                 f"Lata ID: {tid}\nHorário: {time.ctime()}")
                    threading.Thread(
                        target=send_fracture_alert_email,
                        args=(recipients, subject, body_text, full_path, roi_path),
                        daemon=True
                    ).start()
            db.close()

        except Exception as e:
            self.logger.error(f"Erro ao salvar resultado de inspeção: {e}")

    def start_processing(self):
        if not self.processing:
            self.processing = True
            self.processing_event.set()
            self.thread = threading.Thread(target=self._process_loop, daemon=True)
            self.thread.start()
            self.logger.info("Processamento iniciado.")

    def stop_processing(self):
        self.processing = False
        self.processing_event.clear()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        self.logger.info("Processamento parado.")