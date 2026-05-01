# VisionSystem: Ecossistema de Inspeção Inteligente

O **VisionSystem** é uma solução integrada de monitoramento industrial que combina o poder de múltiplos modelos de inteligência artificial para garantir a máxima qualidade e rastreabilidade no chão de fábrica.

## Arquitetura Colaborativa

O diferencial do VisionSystem reside na sinergia entre seus módulos principais:

1.  **VisionAlign:** Responsável pela detecção global e posicionamento. Ele fornece o contexto espacial e isola a Região de Interesse (ROI).
2.  **VisionFracture:** Atua dentro da ROI fornecida pelo VisionAlign, realizando inspeção de integridade (fraturas) e identificação de BodyMaker (BM ID).

```mermaid
graph LR
    A[Câmera Industrial] --> B[VisionSystem]
    subgraph Módulos
    B --> C[VisionAlign]
    C -->|ROI Handoff| D[VisionFracture]
    end
    D --> E[Rastreabilidade e Alertas]
```

---

## Capacidades do Ecossistema

- **Autonomia Total:** O sistema gerencia seu próprio ciclo de aprendizado através do OTX (OpenVINO Training Extensions).
- **Rastreabilidade BM ID:** Identificação automática da máquina de origem (*BodyMaker Identification*).
- **Inspeção de Alta Cadência:** Processamento otimizado com Intel OpenVINO para linhas de produção de alta velocidade.
- **Validação Rigorosa:** Novos modelos são testados contra 30% dos dados reais antes de entrarem em produção.
