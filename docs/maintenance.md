# Manutenção e Solução de Problemas

Este guia ajuda a resolver os problemas mais comuns do dia a dia na linha de produção, focando em causas físicas e operacionais.

---

## 🛠️ "O que fazer se..." (Problemas e Soluções)

### 1. A imagem está embaçada ou "nublada"
*   **Causa provável:** Acúmulo de óleo, poeira ou lubrificante na lente da câmera.
*   **Ação:** Limpe a lente cuidadosamente com um pano de microfibra e **álcool isopropílico**. Nunca use panos ásperos ou água.

### 2. O sistema não está detectando nada (Tela Preta)
*   **Causa provável:** Cabo de rede (Ethernet) ou cabo de alimentação solto.
*   **Ação:** Verifique as conexões físicas na parte traseira da câmera e no switch industrial. Certifique-se de que o LED de link está piscando.

### 3. Falsos Negativos (A IA não viu uma fratura óbvia)
*   **Causa provável:** Iluminação externa interferindo (reflexo de sol ou luz de solda próxima).
*   **Ação:** Verifique se o anteparo de proteção da câmera está posicionado corretamente para bloquear luz externa. Limpe os LEDs de iluminação do VisionSystem.

### 4. Lentidão ou "travamento" da imagem
*   **Causa provável:** Superaquecimento do computador de borda (Edge Box).
*   **Ação:** Verifique se as ventoinhas do servidor estão obstruídas por sujeira. Realize uma limpeza com ar comprimido se necessário.

---

## 📅 Plano de Manutenção Preventiva

| Atividade | Frequência | Ferramenta |
| :--- | :--- | :--- |
| Limpeza de Lentes | Diária (início de turno) | Álcool Isopropílico |
| Verificação de Cabos | Semanal | Inspeção Visual |
| Limpeza de Filtros/Fans | Mensal | Ar Comprimido |
| Backup de Logs | Trimestral | Automático via Dashboard |

> **Dica de Ouro:** 90% dos erros de "IA ruim" são, na verdade, causados por uma lente suja de óleo. Mantenha a visão da máquina limpa!
