from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget,
                             QGroupBox, QFormLayout, QComboBox, QSpinBox,
                             QDoubleSpinBox, QCheckBox, QLabel, QLineEdit,
                             QDialogButtonBox)

class SettingsDialogDetailed(QDialog):
    """Diálogo detalhado para visualização e edição das configurações."""

    def __init__(self, settings_data, parent=None):
        super().__init__(parent)
        self.settings_data = settings_data # Armazena os dados iniciais
        self.setWindowTitle("Configurações do Sistema")
        self.setMinimumWidth(500)

        # Layout principal
        layout = QVBoxLayout(self)

        # Abas
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # --- Aba Básica ---
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_layout.setSpacing(15) # <<< Adicionar espaçamento vertical
        tab_widget.addTab(basic_tab, "Configurações Básicas")

        # Vídeo
        video_group = QGroupBox("Configurações de Vídeo")
        video_layout = QFormLayout(video_group)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(self.settings_data.get('VIDEO_PARAMS', {}).get('resolutions', {}).keys())
        self.resolution_combo.setCurrentText(self.settings_data.get('VIDEO_PARAMS', {}).get('default_resolution', ''))
        self.fps_combo = QComboBox()
        self.fps_combo.addItems([str(fps) for fps in self.settings_data.get('VIDEO_PARAMS', {}).get('fps_options', [])])
        self.fps_combo.setCurrentText(str(self.settings_data.get('VIDEO_PARAMS', {}).get('default_fps', 30)))
        video_layout.addRow("Resolução:", self.resolution_combo)
        video_layout.addRow("FPS:", self.fps_combo)
        basic_layout.addWidget(video_group)

        # IA Básica
        ai_group = QGroupBox("Configurações de IA")
        ai_layout = QFormLayout(ai_group)
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.01, 1.0)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('conf_default', 0.5))
        self.iou_spin = QDoubleSpinBox()
        self.iou_spin.setRange(0.01, 1.0)
        self.iou_spin.setSingleStep(0.05)
        self.iou_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('iou_default', 0.5))
        ai_layout.addRow("Confidence:", self.conf_spin)
        ai_layout.addRow("IOU:", self.iou_spin)
        basic_layout.addWidget(ai_group)
        basic_layout.addStretch(1) # <<< Empurrar conteúdo para cima

        # --- Aba Avançada ---
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        tab_widget.addTab(advanced_tab, "Configurações Avançadas")
        advanced_layout.setSpacing(15) # <<< Adicionar espaçamento vertical

        # IA Avançada
        advanced_ai_group = QGroupBox("Configurações Avançadas de IA")
        advanced_form = QFormLayout(advanced_ai_group)
        self.frame_skip_spin = QSpinBox()
        self.frame_skip_spin.setRange(1, 3) # <<< Limite máximo alterado para 3
        self.frame_skip_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('frame_skip', 1))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 32)
        self.batch_size_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('batch_size', 1))
        self.det_threshold_spin = QSpinBox() # Limite de detecções para sirene
        self.det_threshold_spin.setRange(1, 10)
        self.det_threshold_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('detection_threshold', 3))
        self.nms_spin = QDoubleSpinBox()
        self.nms_spin.setRange(0.1, 1.0)
        self.nms_spin.setSingleStep(0.05)
        self.nms_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('nms_threshold', 0.5))
        self.max_det_spin = QSpinBox()
        self.max_det_spin.setRange(100, 1000)
        self.max_det_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('max_det', 300))
        self.agnostic_check = QCheckBox()
        self.agnostic_check.setChecked(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('agnostic_nms', False))
        advanced_form.addRow("Frame Skip (1/N):", self.frame_skip_spin)
        advanced_form.addRow("Batch Size:", self.batch_size_spin)
        advanced_form.addRow("Limite Detecções (Sirene):", self.det_threshold_spin) # Nome corrigido
        advanced_form.addRow("NMS Threshold:", self.nms_spin)
        advanced_form.addRow("Max Detections:", self.max_det_spin)
        advanced_form.addRow("NMS Agnóstico:", self.agnostic_check)
        advanced_layout.addWidget(advanced_ai_group)

        # Fonte de Vídeo
        source_group = QGroupBox("Fonte de Vídeo")
        source_layout = QFormLayout(source_group) # Usar QFormLayout para consistência
        self.source_combo = QComboBox()
        self.source_combo.addItems(["video", "camera", "stream"])
        self.source_combo.setCurrentText(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {}).get('type', 'camera'))
        self.camera_spin = QSpinBox()
        self.camera_spin.setRange(0, 10)
        self.camera_spin.setValue(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {}).get('camera_id', 0))
        self.stream_input = QLineEdit()
        self.stream_input.setText(self.settings_data.get('AI_PARAMS', {}).get('advanced', {}).get('video_source', {}).get('stream_url', ''))
        source_layout.addRow("Tipo de Fonte:", self.source_combo)
        source_layout.addRow("ID da Câmera:", self.camera_spin)
        source_layout.addRow("URL do Stream:", self.stream_input)
        advanced_layout.addWidget(source_group)
        advanced_layout.addStretch(1) # <<< Empurrar conteúdo para cima

        # Botões Save/Cancel
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept) # Conecta ao accept padrão
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_settings_data(self):
        """Coleta os dados dos widgets e retorna um dicionário."""
        return {
            'VIDEO_PARAMS': {
                'default_resolution': self.resolution_combo.currentText(),
                'default_fps': int(self.fps_combo.currentText())
                # Preserva outras chaves de VIDEO_PARAMS se existirem nos dados originais
                **{k: v for k, v in self.settings_data.get('VIDEO_PARAMS', {}).items() if k not in ['default_resolution', 'default_fps']}
            },
            'AI_PARAMS': {
                'conf_default': self.conf_spin.value(),
                'iou_default': self.iou_spin.value(),
                'advanced': {
                    'frame_skip': self.frame_skip_spin.value(),
                    'batch_size': self.batch_size_spin.value(),
                    'detection_threshold': self.det_threshold_spin.value(),
                    'nms_threshold': self.nms_spin.value(),
                    'max_det': self.max_det_spin.value(),
                    'agnostic_nms': self.agnostic_check.isChecked(),
                    'video_source': {
                        'type': self.source_combo.currentText(),
                        'camera_id': self.camera_spin.value(),
                        'stream_url': self.stream_input.text()
                    }
                }
                # Preserva outras chaves de AI_PARAMS se existirem nos dados originais
                **{k: v for k, v in self.settings_data.get('AI_PARAMS', {}).items() if k not in ['conf_default', 'iou_default', 'advanced']}
            }
            # Preserva outras seções de alto nível (COLORS, UI_PARAMS, etc.)
            **{k: v for k, v in self.settings_data.items() if k not in ['VIDEO_PARAMS', 'AI_PARAMS']}
        }