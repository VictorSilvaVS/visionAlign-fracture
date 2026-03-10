import time
import os
import psutil
import subprocess
import logging
from datetime import datetime
PROCESS_NAME = "python"
SCRIPT_TO_RUN = "run_client_only.py"  

MAX_RAM_MB = 16384  
CHECK_INTERVAL_SECONDS = 30
LOG_FILE = "watchdog_monitor.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Watchdog")

def get_process_id():
    """Busca processos em execução rodando o script alvo."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and SCRIPT_TO_RUN in cmdline and proc.info['name'] == PROCESS_NAME + ".exe":
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def start_process():
    """Inicia o processo principal desacoplado e loga a ação."""
    logger.info(f"Iniciando o sistema: {SCRIPT_TO_RUN}...")
    
    
    p = subprocess.Popen([PROCESS_NAME, SCRIPT_TO_RUN], cwd=os.path.dirname(os.path.abspath(__file__)))
    time.sleep(5)  
    return p

def kill_process(proc):
    """Mata de forma hard a árvore do processo no Windows num cenário de emergência."""
    try:
        logger.warning(f"Enviando sinal KILL para PID {proc.pid}")
        
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):  
            child.kill()
        parent.kill()
        proc.wait(timeout=5)
    except Exception as e:
        logger.error(f"Erro ao matar processo: {e}")

def main():
    logger.info(f"=== WATCHDOG INICIADO (Max RAM: {MAX_RAM_MB}MB) ===")
    
    current_proc = get_process_id()
    
    if current_proc is None:
        logger.info("Sistema não está em execução. Iniciando agora.")
        start_process()
    else:
        logger.info(f"Sistema já em execução: PID {current_proc.pid}")

    while True:
        try:
            current_proc = get_process_id()
            
            if current_proc is None:
                logger.error("ALERTA: Processo principal NÃO encontrado. O sistema CRASHOU.")
                logger.info("Reiniciando imediatamente...")
                start_process()
                time.sleep(5)
                continue

            
            mem_info = current_proc.memory_info()
            ram_usage_mb = mem_info.rss / (1024 * 1024)
            cpu_usage = current_proc.cpu_percent(interval=1.0)
            
            
            
            
            if ram_usage_mb > MAX_RAM_MB:
                logger.critical(f"ESTOURO DE MEMÓRIA DETECTADO! Uso Atual: {ram_usage_mb:.2f} MB. Limite: {MAX_RAM_MB} MB.")
                logger.warning("Iniciando reinicialização de segurança (Hard Reset)...")
                kill_process(current_proc)
                time.sleep(3) 
                start_process()

            time.sleep(CHECK_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            logger.info("Watchdog interrompido manualmente.")
            break
        except Exception as e:
            logger.error(f"Erro no loop do Watchdog: {e}")
            time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    print(f"[*] Watchdog Rodando - Limite Mapeado: {MAX_RAM_MB}MB")
    print(f"[*] Monitorando: {SCRIPT_TO_RUN}")
    print(f"[*] Verifique o arquivo {LOG_FILE} para detalhes.")
    main()