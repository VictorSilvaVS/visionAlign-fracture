# Arquitetura do Sistema de IA

A inteligência do VisionAlign baseia-se em uma arquitetura de múltiplos estágios para garantir estabilidade e precisão em ambientes fabris.

## Integração OpenVINO
O núcleo do processamento utiliza o **OpenVINO IR (Intermediate Representation)** para otimizar modelos YOLO para processadores e aceleradores Intel.
- **Quantização INT8:** Otimização que reduz o uso de memória e aumenta a velocidade de processamento com impacto mínimo na precisão.
- **Inferência Assíncrona:** Gerenciamento eficiente de frames que permite alta cadência de inspeção sem latência na interface de usuário.

## Detecção de Incertezas
O sistema utiliza uma lógica de estimativa de incerteza para identificar novos padrões de erro:
- **Faixa de Ambiguidade:** Identifica detecções com confiança entre 30% e 60%.
- **Coleta Automática:** Imagens ambíguas são isoladas para posterior validação humana.
- **Aprendizado Ativo:** O feedback humano sobre essas imagens alimenta o próximo ciclo de treinamento, expandindo a base de conhecimento da IA.

## Evolução de Desempenho
O sistema apresenta um ganho de precisão logarítmico conforme o volume de dados específicos da planta aumenta, estabilizando-se em níveis de alta confiabilidade operacional.

```mermaid
xychart-beta
    title "Evolução de Acurácia vs. Iterações de Modelo"
    x-axis ["V1.0 (Base)", "V1.2 (1 Sem.)", "V1.5 (1 Mês)", "V2.0 (Otim.)", "V2.1 (Atual)"]
    y-axis "Acurácia Média (%)" 70 --> 100
    bar [72, 85, 91, 96, 98]
    line [72, 85, 91, 96, 98]
```

