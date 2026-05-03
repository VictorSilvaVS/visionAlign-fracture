import threading
from pylogix import PLC
from time import sleep
import logging

class CLPCommunication:
    def __init__(self, ip, slot=0):
        self.logger = logging.getLogger('VisionAlign.CLP')
        self.plc = PLC()
        self.plc.IPAddress = ip
        self.plc.ProcessorSlot = slot
        self.connected = False
        
        # Heartbeat settings
        self.heartbeat_active = False
        self.heartbeat_thread = None
        self.heartbeat_tag = None
        self.heartbeat_interval = 1.0  # segundos
        self.heartbeat_value = False
        
    def connect(self):
        try:
            # Tenta ler uma tag básica para validar conexão
            ret = self.plc.Read('Program:MainProgram.Running')
            if ret.Status == 'Success':
                self.connected = True
                self.logger.info(f"Conectado ao CLP {self.plc.IPAddress} com sucesso")
                return True
            self.logger.error(f"Falha ao conectar ao CLP: {ret.Status}")
            return False
        except Exception as e:
            self.logger.error(f"Erro de conexão: {str(e)}")
            return False
    
    def write_detection(self, tag, value):
        """Escreve resultado da detecção no CLP"""
        if not self.connected:
            return False
        try:
            ret = self.plc.Write(tag, value)
            if ret.Status == 'Success':
                return True
            self.logger.error(f"Erro ao escrever no CLP: {ret.Status}")
            return False
        except Exception as e:
            self.logger.error(f"Erro ao escrever no CLP: {str(e)}")
            return False
    
    def read_trigger(self, tag):
        """Lê sinal de trigger do CLP"""
        if not self.connected:
            return None
        try:
            ret = self.plc.Read(tag)
            if ret.Status == 'Success':
                return ret.Value
            self.logger.error(f"Erro ao ler do CLP: {ret.Status}")
            return None
        except Exception as e:
            self.logger.error(f"Erro ao ler do CLP: {str(e)}")
            return None

    def start_heartbeat(self, tag=None, interval=None):
        """Inicia a thread de heartbeat"""
        if tag: self.heartbeat_tag = tag
        if interval: self.heartbeat_interval = interval
        
        if self.heartbeat_active:
            self.logger.warning("Heartbeat já está ativo.")
            return

        self.heartbeat_active = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        self.logger.info(f"Monitor de Heartbeat iniciado na tag: {self.heartbeat_tag}")

    def stop_heartbeat(self):
        """Para a thread de heartbeat"""
        self.heartbeat_active = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=2.0)
            self.logger.info("Monitor de Heartbeat parado.")

    def _heartbeat_loop(self):
        """Loop de fundo para alternar o bit de heartbeat no CLP"""
        while self.heartbeat_active:
            if self.connected:
                # Inverte o valor do bit (toggle)
                self.heartbeat_value = not self.heartbeat_value
                success = self.write_detection(self.heartbeat_tag, self.heartbeat_value)
                
                if not success:
                    self.logger.warning("Falha ao enviar Heartbeat. Tentando reconectar...")
                    self.connected = False # Força tentativa de reconexão na próxima escrita
            else:
                # Tenta reconectar se a conexão caiu
                self.connect()
            
            sleep(self.heartbeat_interval)
            
    def close(self):
        self.stop_heartbeat()
        if self.connected:
            self.plc.Close()

def test_clp():
    """Função de teste básico com Heartbeat"""
    logging.basicConfig(level=logging.INFO)
    clp = CLPCommunication(ip='192.168.1.100')
    
    if clp.connect():
        try:
            # Inicia heartbeat em background
            clp.start_heartbeat(interval=0.5)
            
            print("Heartbeat ativo. Pressione Ctrl+C para parar...")
            for _ in range(10):
                sleep(1)
                trigger = clp.read_trigger('Program:MainProgram.TriggerSensor')
                print(f"Lendo sensor: {trigger}")
                
        except KeyboardInterrupt:
            pass
        finally:
            clp.close()
    else:
        print("Não foi possível conectar para o teste.")

if __name__ == "__main__":
    test_clp()
