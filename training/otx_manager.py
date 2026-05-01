import os
import subprocess
import logging
import json
from pathlib import Path

class OTXManager:
    """
    Gerenciador para OpenVINO Training Extensions (OTX).
    Permite treinar, otimizar e exportar modelos de forma automatizada.
    """
    
    def __init__(self, settings_manager, logger=None):
        self.settings_manager = settings_manager
        self.settings = settings_manager.get_all()
        self.logger = logger or logging.getLogger("VisionAlign.OTX")
        self.project_root = Path(__file__).parent.parent
        
    def _run_command(self, cmd):
        """Executa um comando shell e loga a saída."""
        self.logger.info(f"Executando comando OTX: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project_root
            )
            
            for line in process.stdout:
                self.logger.info(line.strip())
                
            process.wait()
            if process.returncode != 0:
                self.logger.error(f"Comando falhou com código {process.returncode}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Erro ao executar comando: {e}")
            return False

    def train(self, model_type, data_yaml, config_path=None, output_dir="outputs"):
        """
        Inicia o treinamento usando OTX.
        model_type: 'detection', 'segmentation', etc.
        data_yaml: Caminho para o arquivo de dados (estilo YOLO/OTX).
        """
        # Exemplo: otx train --data data.yaml --model detection --output outputs
        cmd = ["otx", "train", "--data", str(data_yaml)]
        
        if config_path:
            cmd.extend(["--config", str(config_path)])
            
        cmd.extend(["--output", str(output_dir)])
        
        return self._run_command(cmd)

    def optimize(self, model_path, output_dir="optimized"):
        """
        Otimiza um modelo treinado para OpenVINO IR.
        """
        # Exemplo: otx optimize --model model.pth --output optimized
        cmd = ["otx", "optimize", "--model", str(model_path), "--output", str(output_dir)]
        return self._run_command(cmd)

    def export(self, model_path, output_dir="exported", format="openvino"):
        """
Próximos passos sugeridos:

Testar o servidor: Podemos rodar o comando uvicorn backend.app.main:app --reload para verificar se tudo sobe corretamente.
Migrar Configurações: Implementar a lógica de leitura/escrita do settings.json via API no roteador de settings.
Atualizar o Cliente PyQt5: Ajustar o main_window.py para usar os novos endpoints /api/v1/... e autenticação via Token.
Deseja que eu ajude a rodar o servidor para teste ou prefere continuar a migração dos outros módulos?  """
        # Exemplo: otx export --model model.pth --output exported --format openvino
        cmd = ["otx", "export", "--model", str(model_path), "--output", str(output_dir), "--format", format]
        return self._run_command(cmd)

    def auto_fine_tune(self, new_data_path, base_model_path=None):
        """
        Realiza um ajuste fino automático com novos dados coletados.
        """
        self.logger.info("Iniciando Fine-Tuning Automático via OTX...")
        
        output_dir = self.project_root / "training" / "fine_tune_results"
        os.makedirs(output_dir, exist_ok=True)
        
        success = self.train("detection", new_data_path, output_dir=output_dir)
        if success:
            best_model = output_dir / "best.pth"
            return self.export(best_model, output_dir=self.project_root / "model" / "_openvino_model" / "UpdatedModel")
            
        return False
