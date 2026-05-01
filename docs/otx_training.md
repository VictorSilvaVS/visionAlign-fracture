# Treinamento e OTX

O **OpenVINO Training Extensions (OTX)** é a ferramenta central para o refinamento de modelos no VisionAlign. Ele permite a atualização de pesos de detecção sem a necessidade de intervenção manual complexa.

## Treinamento Autônomo e Inteligente

O diferencial do VisionAlign é a sua capacidade de **autotreinamento**. Através da integração com o OTX, o sistema não apenas detecta falhas, mas gerencia sua própria evolução técnica:

- **Gatilhos Automáticos:** O sistema monitora a densidade de imagens coletadas no "dataset de incerteza". Ao atingir um limiar crítico, o backend dispara um processo de retreinamento em segundo plano.
- **Intervenção Zero:** Todo o pipeline (preparação de dados, treinamento, otimização OpenVINO e deploy do novo modelo) ocorre sem a necessidade de comandos manuais ou parada de linha.
- **Auto-Validação e Backup:** O sistema isola automaticamente **30% das novas imagens** para validação rigorosa. O novo modelo só é implementado se apresentar uma **superioridade acima de 90%** em métricas-chave ou uma redução significativa no **LOSS** (perda). Caso aprovado, o modelo antigo é movido para um diretório de backup, permitindo reversão instantânea se necessário.

### Benefícios Operacionais
- **Automação:** Redução da necessidade de especialistas em ciência de dados no local.
- **Eficiência:** Otimização para os aceleradores de hardware disponíveis.
- **Customização:** Modelos perfeitamente ajustados para as condições reais da linha de produção.

---

## Comandos Operacionais
O motor backend executa as seguintes operações:
```bash
otx train --model detection --data data.yaml
otx export --model model.pth --format openvino
```
