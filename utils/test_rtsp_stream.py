import cv2
import subprocess
import time
import os

def start_rtsp_server(video_path, rtsp_url="rtsp://admin:Abc123456@10.81.50.33:554/cam/realmonitor?channel=1&subtype=0"):
    """Inicia servidor RTSP usando ffmpeg"""
    
    ffmpeg_cmd = [
        'ffmpeg',
        '-re',  # Lê em taxa real
        '-i', video_path,  # Arquivo de entrada
        '-c:v', 'libx264',  # Codec de vídeo
        '-preset', 'ultrafast',
        '-tune', 'zerolatency',
        '-f', 'rtsp',  # Formato de saída
        '-rtsp_transport', 'tcp',  # Protocolo de transporte
        rtsp_url  # URL do stream
    ]
    
    return subprocess.Popen(ffmpeg_cmd)

def test_stream():
    # Caminho do vídeo de teste
    video_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                             "testes", "videos", "video1.mp4")
    
    if not os.path.exists(video_path):
        print(f"Vídeo não encontrado: {video_path}")
        return
        
    rtsp_url = "rtsp://admin:Abc123456@10.81.50.33:554/cam/realmonitor?channel=1&subtype=0"
    print(f"Iniciando servidor RTSP em {rtsp_url}")
    
    # Inicia servidor RTSP
    server_process = start_rtsp_server(video_path, rtsp_url)
    time.sleep(2)  # Aguarda servidor iniciar
    
    try:
        # Abre stream para visualização
        cap = cv2.VideoCapture(rtsp_url)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            cv2.imshow('RTSP Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        if 'cap' in locals():
            cap.release()
        cv2.destroyAllWindows()
        server_process.terminate()
        server_process.wait()
        print("Stream finalizado")

if __name__ == "__main__":
    test_stream()
