# Como Foi Feito

Este documento conta a história do desenvolvimento do VisionAlign-Fracture e as decisões tomadas para chegar ao sistema atual.

---

## 1. O Início e os Desafios

O projeto começou com a necessidade de inspecionar latas em alta velocidade. No início, usamos ferramentas comuns de mercado (como Ultralytics YOLO). 

**O Problema:** Essas ferramentas eram pesadas e exigiam computadores muito caros com placas de vídeo potentes. Na fábrica, precisávamos de algo que rodasse em computadores simples.

---

## 2. A Mudança para Tecnologia Intel

Decidimos mudar para o OpenVINO da Intel. Essa escolha permitiu que o sistema rodasse até 5 vezes mais rápido usando apenas o processador comum do computador.

**Resultado:** Economia de hardware e maior estabilidade para rodar 24 horas por dia.

---

## 3. Divisão de Trabalho (Funil de Inspeção)

Criamos uma estratégia de "equipe digital" para que o sistema não ficasse lento:

*   **Identificador:** Localiza a lata na esteira.
*   **Inspetor:** Foca apenas na lata localizada para procurar falhas.

Isso é como ter uma pessoa para separar as latas e outra apenas para olhar os detalhes de cada uma.

---

## 4. Resolvendo o Atraso do Vídeo

Câmeras industriais 4K enviam muitos dados. Se usássemos o método comum de leitura de vídeo, o sistema começaria a mostrar imagens com atraso. Usamos o programa FFmpeg para garantir que o sistema sempre veja o "agora", descartando imagens velhas automaticamente.

---

## 5. Segurança Industrial

Para proteger os dados da fábrica, todas as informações que passam pela rede são trancadas com uma chave digital (criptografia). Somente o computador autorizado pode ler essas informações.

---

Última atualização: Maio de 2026
