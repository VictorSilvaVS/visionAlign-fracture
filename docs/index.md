# Documentação VisionAlign-Fracture

Bem-vindo à documentação do VisionAlign-Fracture, um sistema de inspeção para linhas de produção industrial.

Este sistema usa inteligência artificial para garantir a qualidade na fabricação de latas. Ele identifica se as latas estão na posição correta e detecta pequenas rachaduras ou falhas que seriam difíceis de ver a olho nu.

![Interface do Sistema](assets/images/dashboard.png)

!!! info "Status do Sistema"
    O VisionAlign-Fracture está operando na versão 2.1 com suporte total a processadores Intel via OpenVINO.

## Guia de Navegação

Recomendamos seguir a ordem abaixo para entender o sistema:

### Primeiros Passos
* [Guia de Instalação](installation.md): Como preparar o computador e os programas necessários.
* [Tecnologias Utilizadas](tecnologias.md): Lista dos programas e bibliotecas que fazem o sistema funcionar.

### Arquitetura e IA
* [Arquitetura do Sistema](architecture.md): Como o sistema processa as imagens em duas etapas.
* [Como Foi Feito](como_foi_feito.md): História e decisões tomadas durante o desenvolvimento.
* [Glossário](glossary.md): Explicação de termos simples para facilitar a comunicação.

### Suporte e Operação
* [Manutenção](maintenance.md): Como cuidar das câmeras e do computador.
* [Perguntas Frequentes](faqs.md): Respostas para as dúvidas mais comuns.

### Integração e Segurança
* [Referência da API](api_reference.md): Informações técnicas sobre como o sistema se comunica e se protege.

---

## Funcionalidades Principais

1. VisionAlign: Localiza e acompanha as latas na esteira.
2. VisionFracture: Analisa cada lata individualmente para encontrar falhas.
3. Cérebro Global: Permite que o sistema aprenda com novos exemplos.
4. Segurança: Protege os dados da fábrica através de criptografia.

---

Última atualização: Maio de 2026