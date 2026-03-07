from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt

class BasicSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Configurações Básicas")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Configurações de Vídeo
        video_group = QGroupBox("Configurações de Vídeo")
        video_layout = QFormLayout()
        
        # Resolução
        self.resolution_combo = QComboBox()
        resolutions = self.settings['VIDEO_PARAMS']['resolutions'].keys()
        self.resolution_combo.addItems(resolutions)
        self.resolution_combo.setCurrentText(self.settings['VIDEO_PARAMS']['default_resolution'])
        
        # FPS
        self.fps_combo = QComboBox()
        fps_options = [str(fps) for fps in self.settings['VIDEO_PARAMS']['fps_options']]
        self.fps_combo.addItems(fps_options)
        self.fps_combo.setCurrentText(str(self.settings['VIDEO_PARAMS']['default_fps']))
        
        video_layout.addRow("Resolução:", self.resolution_combo)
        video_layout.addRow("FPS:", self.fps_combo)
        video_group.setLayout(video_layout)
        
        # Configurações de IA Básicas
        ai_group = QGroupBox("Configurações de IA")
        ai_layout = QFormLayout()
        
        # Confidence
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.01, 1.0)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setValue(self.settings['AI_PARAMS']['conf_default'])
        
        # IOU
        self.iou_spin = QDoubleSpinBox()
        self.iou_spin.setRange(0.01, 1.0)
        self.iou_spin.setSingleStep(0.05)
        self.iou_spin.setValue(self.settings['AI_PARAMS']['iou_default'])
        
        ai_layout.addRow("Confidence:", self.conf_spin)
        ai_layout.addRow("IOU:", self.iou_spin)
        ai_group.setLayout(ai_layout)
        
        layout.addWidget(video_group)
        layout.addWidget(ai_group)
        
        # Botões
        buttons = QHBoxLayout()
        save_btn = QPushButton("Salvar")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
        
        self.setLayout(layout)

    def save_settings(self):
        basic_settings = {
            'VIDEO_PARAMS': {
                'default_resolution': self.resolution_combo.currentText(),
                'default_fps': int(self.fps_combo.currentText())
            },
            'AI_PARAMS': {
                'conf_default': self.conf_spin.value(),
                'iou_default': self.iou_spin.value()
            }
        }
        
        if self.parent().settings_manager.update_basic_settings(basic_settings):
            self.accept()
        else:
            QMessageBox.warning(self, "Erro", "Erro ao salvar configurações")

class AdvancedSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Configurações Avançadas")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        
        advanced_group = QGroupBox("Configurações Avançadas de IA")
        advanced_layout = QFormLayout()
        
        # Frame Skip
        self.frame_skip_spin = QSpinBox()
        self.frame_skip_spin.setRange(1, 30)
        self.frame_skip_spin.setValue(self.settings['AI_PARAMS']['advanced']['frame_skip'])
        
        # Batch Size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 32)
        self.batch_size_spin.setValue(self.settings['AI_PARAMS']['advanced']['batch_size'])
        
        # Detection Threshold
        self.det_threshold_spin = QSpinBox()
        self.det_threshold_spin.setRange(1, 10)
        self.det_threshold_spin.setValue(self.settings['AI_PARAMS']['advanced']['detection_threshold'])
        
        # NMS Threshold
        self.nms_spin = QDoubleSpinBox()
        self.nms_spin.setRange(0.1, 1.0)
        self.nms_spin.setSingleStep(0.05)
        self.nms_spin.setValue(self.settings['AI_PARAMS']['advanced']['nms_threshold'])
        
        # Max Detections
        self.max_det_spin = QSpinBox()
        self.max_det_spin.setRange(100, 1000)
        self.max_det_spin.setValue(self.settings['AI_PARAMS']['advanced']['max_det'])
        
        # Agnostic NMS
        self.agnostic_check = QCheckBox()
        self.agnostic_check.setChecked(self.settings['AI_PARAMS']['advanced']['agnostic_nms'])
        
        advanced_layout.addRow("Frame Skip (1/N):", self.frame_skip_spin)
        advanced_layout.addRow("Batch Size:", self.batch_size_spin)
        advanced_layout.addRow("Detection Threshold:", self.det_threshold_spin)
        advanced_layout.addRow("NMS Threshold:", self.nms_spin)
        advanced_layout.addRow("Max Detections:", self.max_det_spin)
        advanced_layout.addRow("NMS Agnóstico:", self.agnostic_check)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # Botões
        buttons = QHBoxLayout()
        save_btn = QPushButton("Salvar")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
        
        self.setLayout(layout)

    def save_settings(self):
        advanced_settings = {
            'frame_skip': self.frame_skip_spin.value(),
            'batch_size': self.batch_size_spin.value(),
            'detection_threshold': self.det_threshold_spin.value(),
            'nms_threshold': self.nms_spin.value(),
            'max_det': self.max_det_spin.value(),
            'agnostic_nms': self.agnostic_check.isChecked()
        }
        
        if self.parent().settings_manager.update_advanced_settings(advanced_settings):
            self.accept()
        else:
            QMessageBox.warning(self, "Erro", "Erro ao salvar configurações")
