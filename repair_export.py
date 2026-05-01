import os
import sys

# Adiciona o root ao path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from training.otx_manager import OTXManager
from interface.configuracoes.settings import Settings

def main():
    print("--- OpenVINO Model Repair/Export Tool (OTX-based) ---")
    settings_manager = Settings()
    otx = OTXManager(settings_manager)
    
    # Exemplo de uso: Exportar um modelo treinado para OpenVINO
    # OTX pode exportar modelos treinados por ele mesmo (.pth) para OpenVINO (.xml/.bin)
    
    model_dir = os.path.join(project_root, "model", "backup")
    if not os.path.exists(model_dir):
        print(f"Diretório de backup não encontrado: {model_dir}")
        return

    # Procura por modelos .pth (OTX) ou outros formatos suportados
    models = [f for f in os.listdir(model_dir) if f.endswith('.pth')]
    
    if not models:
        print("Nenhum modelo .pth encontrado em model/backup para exportar via OTX.")
        print("Se você ainda tem arquivos .pt (Ultralytics), você deve convertê-los ANTES de remover o Ultralytics,")
        print("ou usar o Model Optimizer (MO) do OpenVINO diretamente.")
        return

    for m in models:
        pt_path = os.path.join(model_dir, m)
        target_name = m.replace('.pth', '_openvino_model')
        target_dir = os.path.join(project_root, "model", "_openvino_model", target_name)
        
        print(f"Exportando {m} para OpenVINO...")
        success = otx.export(pt_path, output_dir=target_dir)
        if success:
            print(f"Sucesso! Modelo exportado em: {target_dir}")
        else:
            print(f"Falha ao exportar {m}")

if __name__ == "__main__":
    main()
