# Perguntas Frequentes (FAQ's)

Esta seção explica, de forma simples e direta, como a inteligência do VisionSystem ajuda a sua fábrica a produzir com mais qualidade e menos desperdício.

---

### Como os dois sistemas trabalham juntos?
Imagine uma equipe de inspeção onde cada um tem uma especialidade:
*   **VisionAlign (O Olheiro):** Localiza rapidamente a lata na esteira, ignorando vibrações ou desalinhamentos.
*   **VisionFracture (O Inspetor):** Recebe a área isolada pelo olheiro e foca exclusivamente em encontrar microfissuras e ler o código da máquina.

### Como o sistema consegue ler o BM ID em condições industriais?
O VisionSystem resolve o desafio de ler códigos em metal (mesmo com reflexo e óleo) em dois passos:
*   **Foco de Precisão:** O sistema isola apenas a área do código (ROI), criando uma imagem "limpa" para análise.
*   **Visão Geométrica:** A IA reconstrói os relevos da gravação, permitindo a leitura mesmo que o código esteja fraco ou com excesso de lubrificante.

### Como a IA consegue diferenciar letras parecidas (como "I" e "i")?
Diferente de um scanner comum, a IA analisa a anatomia da letra:
*   **Topologia:** Identifica o ponto no "i" minúsculo e a estrutura reta do "I" maiúsculo.
*   **Geometria:** Avalia a proporção de altura e largura de cada caractere.
*   **Contexto:** Entende o padrão de gravação da sua fábrica para evitar confusões estatísticas.

### 90% de precisão é bom? Por que o sistema demora a atualizar?
Na indústria, **90% de superioridade** é um nível de excelência altíssimo:
*   **Segurança Máxima:** O sistema só troca o "cérebro" se o novo modelo provar ser significativamente mais confiável que o atual.
*   **Validação Rigorosa:** Testamos o novo modelo contra centenas de fotos reais (30% do banco de dados) antes de qualquer mudança.
*   **Backup Garantido:** O modelo anterior nunca é apagado; ele fica guardado como uma reserva de segurança para reversão instantânea.

### Como o sistema fica mais inteligente sozinho?
O sistema funciona como um funcionário que se especializa a cada dia:
*   **Captura de Incerteza:** Toda vez que a IA encontra algo novo ou duvidoso, ela salva essa imagem.
*   **Auto-Ajuste:** O motor OTX estuda essas novas imagens e ajusta o modelo automaticamente.
*   **Evolução Sem Programador:** A IA aprende novas variações de defeitos sem que você precise contratar suporte técnico para isso.

### O óleo ou a sujeira na lata atrapalham o sistema?
Não, pois treinamos a inteligência para ser "imune" ao ruído visual:
*   **Visão Seletiva:** A IA ignora manchas, reflexos e borrões.
*   **Foco Estrutural:** O sistema foca apenas na deformação real do metal ou no formato físico do caractere gravado.

### O sistema é seguro? Quem pode acessar meus dados?
A segurança é tratada com padrão industrial:
*   **Edge Computing:** Todo o processamento é local. As fotos não saem da sua fábrica.
*   **Privacidade Total:** Sem conexão obrigatória com a nuvem ou internet.
*   **Controle de Acesso:** O dashboard é restrito à sua rede industrial interna.

### As bibliotecas utilizadas são pagas?
Não há custos de licença para o motor de inteligência:
*   **Tecnologia Intel:** Utilizamos OpenVINO e OTX, que são ferramentas gratuitas e de código aberto.
*   **Sem Mensalidades:** Você não paga taxas pelo uso da inteligência artificial.
*   **Sistema Auditável:** As bibliotecas são seguras, transparentes e não transmitem dados para terceiros.
