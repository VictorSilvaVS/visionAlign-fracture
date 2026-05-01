# Módulo VisionAlign

O **VisionAlign** é a porta de entrada do pipeline de inteligência do VisionSystem. Sua função principal é a detecção e alinhamento global de objetos na linha de produção.

## Funcionamento Técnico

O modelo VisionAlign é treinado para identificar a estrutura completa da lata e determinar seu centro geométrico e orientação espacial.

### 1. Detecção Global
Utilizando uma rede YOLO otimizada pelo OpenVINO, o sistema varre o frame em busca de padrões cilíndricos ou circulares que caracterizam o produto.

### 2. Handoff de ROI (Region of Interest)
A característica mais crítica do VisionAlign não é apenas detectar a lata, mas isolar a área de interesse para os módulos subsequentes.
- O sistema calcula um retângulo delimitador (*Bounding Box*) em torno da peça.
- Esta área (ROI) é recortada com precisão sub-pixel.
- A imagem isolada é então normalizada e enviada para o **VisionFracture**.

## Vantagens Operacionais
- **Redução de Ruído:** Ao isolar a lata, o sistema ignora elementos de fundo, sombras e interferências externas.
- **Eficiência de Processamento:** O segundo estágio da IA (VisionFracture) processa apenas a ROI, economizando recursos computacionais e aumentando a velocidade global.
- **Robustez de Posicionamento:** O VisionAlign compensa vibrações e desalinhamentos mecânicos da esteira.
