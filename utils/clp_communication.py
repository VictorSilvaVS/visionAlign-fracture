from pylogix import PLC
from time import sleep
import logging

class CLPCommunication:
    def __init__(self, ip='192.168.1.100', slot=0):
        self.logger = logging.getLogger('VisionAlign.CLP')
        self.plc = PLC()
        self.plc.IPAddress = ip
        self.plc.ProcessorSlot = slot
        self.connected = False
        
    def connect(self):
        try:
            ret = self.plc.Read('Program:MainProgram.Running')
            if ret.Status == 'Success':
                self.connected = True
                self.logger.info("Conectado ao CLP Allen-Bradley com sucesso")
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
            
    def close(self):
        if self.connected:
            self.plc.Close()

def test_clp():
    """Função de teste básico"""
    clp = CLPCommunication(ip='192.168.1.100')
    if clp.connect():
        try:
            # Teste de escrita em tag
            clp.write_detection('Program:MainProgram.DetectionResult', True)
            sleep(1)
            
            # Teste de leitura de tag
            trigger = clp.read_trigger('Program:MainProgram.TriggerSensor')
            print(f"Valor do trigger: {trigger}")
            
        finally:
            clp.close()

if __name__ == "__main__":
    test_clp()
