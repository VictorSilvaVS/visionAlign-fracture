# Referência da API e Segurança

Este documento descreve como os dados são protegidos e como os diferentes computadores conversam entre si.

---

## 1. Segurança dos Dados (Criptografia)

*   **Dados Protegidos:** Todas as informações sensíveis (estatísticas, configurações e imagens) são trancadas antes de serem enviadas pela rede.
*   **Método:** AES-128-CBC.
*   **Chave:** Gerada automaticamente na primeira execução do servidor.
*   **Funcionamento:** O servidor tranca os dados e só o computador que possui a mesma chave consegue abrir e ler as informações.

---

## 2. Pontos de Comunicação (Endpoints)

### Estatísticas e Status
*   **URL:** `/api/stats`
*   **Uso:** O sistema pede as contagens de produção e o status da inteligência artificial.

### Controle de Vídeo
*   **URL:** `/api/change_source`
*   **Uso:** Permite mudar a câmera ou o vídeo que está sendo analisado.

### Logs em Tempo Real
*   **URL:** `/console_stream`
*   **Uso:** Mostra as mensagens do sistema ao vivo no navegador sem precisar atualizar a página.

### Atualização de Configurações
*   **URL:** `/api/settings`
*   **Uso:** Envia novos ajustes de sensibilidade para a inteligência artificial sem precisar reiniciar o sistema.

---

## 3. Acesso de Usuários

O sistema controla quem pode acessar cada área:
*   **Login:** Exige nome de usuário e senha.
*   **Administrador:** Apenas usuários com permissão de administrador podem alterar as configurações críticas da inteligência artificial.

---

Última atualização: Maio de 2026