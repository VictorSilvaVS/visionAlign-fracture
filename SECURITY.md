# VisionAlign — Documentação de Segurança

## Índice
1. [Visão Geral da Arquitetura de Segurança](#1-visão-geral)
2. [Criptografia de Dados em Trânsito](#2-criptografia-em-trânsito)
3. [Criptografia de Dados em Repouso](#3-criptografia-em-repouso)
4. [Autenticação e Autorização](#4-autenticação-e-autorização)
5. [Gerenciamento de Sessões](#5-gerenciamento-de-sessões)
6. [Proteção de Credenciais e Segredos](#6-proteção-de-credenciais)
7. [Segurança do Banco de Dados](#7-segurança-do-banco-de-dados)
8. [Segurança da API Flask](#8-segurança-da-api-flask)
9. [Segurança do Pipeline de IA](#9-segurança-do-pipeline-de-ia)
10. [Logging e Auditoria](#10-logging-e-auditoria)
11. [Vulnerabilidades Conhecidas e Mitigações](#11-vulnerabilidades-e-mitigações)
12. [Checklist de Segurança para Deploy](#12-checklist-de-deploy)

---

## 1. Visão Geral

O VisionAlign é um sistema de visão computacional industrial que opera em rede local (LAN). A arquitetura é cliente-servidor:

```
[Cliente PyQt5] <--HTTPS/Fernet--> [Servidor Flask] <--> [SQLite DB]
                                          |
                                   [Modelos Darknet/OpenVINO]
                                          |
                                   [Stream RTSP/Câmera]
```

### Superfície de Ataque
| Componente | Exposição | Risco |
|---|---|---|
| API Flask (porta 7586) | Rede local | Médio |
| Stream MJPEG `/video_feed` | Rede local | Baixo |
| Banco SQLite `users.db` | Disco local | Médio |
| Arquivo `.env` (SMTP) | Disco local | Alto |
| Chaves Fernet `.key` | Disco local | Crítico |
| Modelos `.weights` / OpenVINO | Disco local | Baixo |

---

## 2. Criptografia em Trânsito

### 2.1 Fernet (AES-128-CBC + HMAC-SHA256)

Toda comunicação sensível entre cliente e servidor usa **Fernet** (`cryptography` lib):

```python
# utils/security.py — SecurityManager
from cryptography.fernet import Fernet

# Geração da chave (feita uma única vez, salva em disco)
key = Fernet.generate_key()  # 32 bytes aleatórios, base64url-encoded

# Criptografia
encrypted = cipher_suite.encrypt(data_bytes)

# Descriptografia (valida HMAC automaticamente — proteção contra tampering)
decrypted = cipher_suite.decrypt(encrypted_bytes)
```

**O que é criptografado:**
- Payload de `/api/stats` (estatísticas de detecção)
- Payload de `/api/settings` GET e POST
- Frames extraídos via `/api/extract_frame`
- Logs exportados via `/api/export_data`
- Comandos de mudança de fonte via `/api/change_source`

**O que NÃO é criptografado (por design):**
- Stream MJPEG `/video_feed` — latência seria inaceitável para vídeo ao vivo
- Endpoints de status básico `/api/basic_stats` — dados não sensíveis

### 2.2 Chaves de Criptografia

Existem **duas chaves distintas** no sistema:

| Arquivo | Uso | Localização |
|---|---|---|
| `security.key` | Chave do servidor (Flask) | Raiz do projeto |
| `config/server_security.key` | Chave do cliente (PyQt5) | `config/` |

> **CRÍTICO:** Ambas as chaves devem ser **idênticas** para que cliente e servidor se comuniquem. São geradas automaticamente na primeira execução se não existirem.

**Permissões recomendadas (Unix):**
```bash
chmod 600 security.key
chmod 600 config/server_security.key
```

**No Windows**, proteger via ACL:
```powershell
icacls security.key /inheritance:r /grant:r "$env:USERNAME:(R,W)"
```

### 2.3 Limitações Atuais

- O Flask roda em **HTTP puro** (não HTTPS). Em ambiente de produção, recomenda-se colocar um **reverse proxy Nginx com TLS** na frente. (vai ser alterado quando entrar em producao)
---

## 3. Criptografia em Repouso

### 3.1 Senhas de Usuários

Senhas são armazenadas com **Werkzeug `generate_password_hash`** (PBKDF2-SHA256 por padrão):

```python
# utils/server.py — registro
hashed_password = generate_password_hash(password)

# utils/database.py — verificação
from werkzeug.security import check_password_hash
check_password_hash(stored_hash, provided_password)
```

> **Atenção:** O método `add_user` em `database.py` ainda usa `hashlib.sha256` diretamente (sem salt). Isso é uma vulnerabilidade — veja seção 11.

### 3.2 Banco de Dados SQLite

O arquivo `data/users.db` **não é criptografado em disco**. Contém:
- Hashes de senha (PBKDF2 ou SHA256 legado)
- Emails dos usuários
- Logs de atividade e alertas

**Mitigação recomendada:** Usar SQLCipher ou criptografar a partição do disco.

### 3.3 Arquivo .env

O `.env` contém credenciais SMTP em **texto plano**. Deve ser protegido por permissões de sistema de arquivos e **nunca commitado no Git** (já está no `.gitignore`).

---

## 4. Autenticação e Autorização

### 4.1 Sistema de Roles

O sistema possui dois níveis de acesso:

| Role | Acesso |
|---|---|
| `admin` | Acesso total: configurações, modelos, usuários, logs |
| `user` | Apenas visualização: stats básicos, stream de vídeo |
| `guest` | Somente leitura no cliente PyQt5 |

### 4.2 Decoradores de Proteção

```python
# utils/server.py
@login_required          # Verifica sessão Flask-Login
@role_required('admin')  # Verifica role específica
def endpoint_protegido():
    ...
```

O decorador `role_required` retorna **HTTP 405** (não 403) para ofuscar a existência do endpoint para usuários não autorizados.

### 4.3 Proteção contra Login Duplicado

O sistema detecta sessões simultâneas do mesmo usuário e exibe um modal de confirmação antes de forçar o logout da sessão anterior. Isso previne compartilhamento de credenciais.

### 4.4 Reset de Senha

- Tokens de reset são gerados com `secrets.token_urlsafe(32)` (256 bits de entropia)
- Expiram em **1 hora**
- São marcados como `used=1` após uso (tokens de uso único)
- O endpoint usa mensagem neutra para evitar **enumeração de usuários**

---

## 5. Gerenciamento de Sessões

### 5.1 Configuração da Sessão Flask

```python
flask_app.secret_key = '<chave_longa_aleatória>'
flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
```

> **Vulnerabilidade:** A `secret_key` está hardcoded no código-fonte. Deve ser movida para variável de ambiente.

### 5.2 Headers de Segurança HTTP

Aplicados via `@flask_app.after_request`:

```python
response.headers['Server'] = 'VisionAlign'          # Ofusca versão do servidor
response.headers['X-Content-Type-Options'] = 'nosniff'  # Previne MIME sniffing
response.headers['X-Frame-Options'] = 'DENY'         # Previne clickjacking
```

**Headers ausentes que deveriam ser adicionados:**
- `Content-Security-Policy`
- `Strict-Transport-Security` (quando HTTPS estiver ativo)
- `X-XSS-Protection`

### 5.3 Sessão Permanente com "Lembrar-me"

Quando o usuário marca "Lembrar-me", a sessão é marcada como `permanent=True` com lifetime de 30 minutos. A sessão é renovada a cada request via `session.modified = True`.

---

## 6. Proteção de Credenciais

### 6.1 Variáveis de Ambiente (.env)

```env
SMTP_SERVER=<ip_servidor_smtp>
SMTP_PORT=25
SMTP_USERNAME=<usuario>@<dominio>
SMTP_PASSWORD=<senha>
SMTP_SENDER=<remetente>@<dominio>
EMAIL_NOTIFICATIONS_ENABLED=true
```

**Regras:**
- Nunca commitar o `.env` (verificar `.gitignore`)
- Nunca logar o conteúdo do `.env`
- Em produção, usar um gerenciador de segredos (AWS Secrets Manager, HashiCorp Vault)

### 6.2 Chaves de API e Tokens

- Tokens de reset de senha: gerados com `secrets.token_urlsafe(32)`
- Chaves Fernet: geradas com `Fernet.generate_key()` (CSPRNG do OS)
- Nenhuma chave deve aparecer em logs

---

## 7. Segurança do Banco de Dados

### 7.1 Prevenção de SQL Injection

Todas as queries usam **parâmetros parametrizados** (`?` placeholders):

```python
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
```

Não há concatenação de strings em queries SQL no código atual.

### 7.2 Sanitização de Inputs de Ordenação

Em `get_alerts_with_filters`, o campo `order_by` é sanitizado:

```python
safe_order_by = "".join(c for c in order_by if c.isalnum() or c == '_')
```

### 7.3 Tabelas e Dados Sensíveis

| Tabela | Dados Sensíveis | Proteção |
|---|---|---|
| `users` | senha (hash), email | Hash PBKDF2 |
| `activity_log` | IP, ações do usuário | Nenhuma adicional |
| `alerts` | IDs de latas, timestamps | Nenhuma adicional |
| `password_resets` | tokens de reset | Expiração + uso único |

### 7.4 Context Manager

O `Database` implementa `__enter__`/`__exit__` para garantir fechamento da conexão:

```python
with Database() as db:
    db.log_alert(...)
# Conexão fechada automaticamente
```

---

## 8. Segurança da API Flask

### 8.1 Endpoints e Proteções

| Endpoint | Método | Auth | Role |
|---|---|---|---|
| `/login` | GET/POST | Não | — |
| `/forgot_password` | GET/POST | Não | — |
| `/reset_password/<token>` | GET/POST | Não | — |
| `/api/login` | POST | Não | — |
| `/api/register` | POST | Não | — |
| `/api/stats` | GET | Sim | admin |
| `/api/settings` | GET/POST | Sim | admin |
| `/api/extract_frame` | POST | Sim | admin |
| `/api/change_source` | POST | Sim | admin |
| `/api/express_retrain` | POST | Sim | admin |
| `/api/basic_stats` | GET | Sim | user/admin |
| `/video_feed` | GET | Não* | — |
| `/api/last_fracture_roi` | GET | Não* | — |

> *`/video_feed` e `/api/last_fracture_roi` não exigem autenticação — considerar adicionar `@login_required`.

### 8.2 Validação de Inputs

- Campos obrigatórios verificados antes de processar
- Senhas com mínimo de 6 caracteres
- Content-Type verificado em endpoints que aceitam dados criptografados
- Paginação com valores padrão seguros

### 8.3 Rate Limiting

**Ausente no código atual.** Recomenda-se adicionar `flask-limiter`:

```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=get_remote_address)

@limiter.limit("5 per minute")
@flask_app.route('/api/login', methods=['POST'])
def api_login():
    ...
```

---

## 9. Segurança do Pipeline de IA

### 9.1 Modelos Darknet/OpenVINO

Os modelos são carregados de caminhos locais fixos. Não há verificação de integridade (hash) dos arquivos de modelo antes do carregamento.

**Recomendação:** Verificar SHA256 dos arquivos `.weights` e `.xml`/`.bin` antes de carregar:

```python
import hashlib

def verify_model_integrity(path, expected_sha256):
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_sha256
```

### 9.2 Injeção via Stream de Vídeo

O sistema processa frames de streams RTSP externos. Um atacante com controle do stream poderia tentar:
- **Adversarial examples**: frames manipulados para enganar o modelo
- **Overflow de buffer**: frames com dimensões inesperadas

**Mitigações implementadas:**
- Validação de dimensões do frame antes do processamento
- Try/except em todo o pipeline de inferência
- Timeout no pipe FFmpeg

### 9.3 Coleta de Dataset

Frames são salvos automaticamente em `data/dataset_collect/images/`. Garantir que:
- O diretório não seja acessível via web
- Imagens não contenham dados pessoais identificáveis

### 9.4 Retreinamento (Express Retrain)

O endpoint `/api/express_retrain` executa treinamento em background com imagens enviadas pelo usuário. Riscos:
- Upload de imagens maliciosas (verificar tipo MIME e tamanho)
- Envenenamento do modelo (data poisoning)
- Consumo excessivo de CPU/RAM

---

## 10. Logging e Auditoria

### 10.1 Eventos Auditados

| Evento | Tabela | Nível |
|---|---|---|
| Login bem-sucedido | `activity_log` | INFO |
| Falha de login | `activity_log` | WARNING |
| Logout | `activity_log` | INFO |
| Logout forçado | `activity_log` | INFO |
| Bloqueio temporário | `activity_log` | INFO |
| Banimento | `activity_log` | INFO |
| Fratura detectada | `alerts` | WARNING |
| Mudança de configurações | Log de arquivo | INFO |

### 10.2 Arquivos de Log

```
logs/
├── client_app_debug.log      # Debug do cliente PyQt5
├── server_app_debug.log      # Debug do servidor Flask
├── server_app_error.log      # Erros do servidor
└── server_app_info.log       # Info do servidor
```

### 10.3 Console SSE

O sistema possui um console web em tempo real (`/console`) que transmite logs via Server-Sent Events. Protegido por `@login_required` e `@role_required('admin')`.

### 10.4 O que NÃO deve ser logado

- Senhas (mesmo em hash)
- Tokens de reset
- Conteúdo do `.env`
- Chaves Fernet
- Dados pessoais completos (apenas IDs/usernames)

---

## 11. Vulnerabilidades e Mitigações

### 11.1 [ALTA] Secret Key Hardcoded

**Problema:** `flask_app.secret_key` está hardcoded no `server.py`.

**Mitigação:**
```python
import os
flask_app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(32)
```

### 11.2 [ALTA] Hash de Senha Legado sem Salt

**Problema:** `database.add_user()` usa `hashlib.sha256` sem salt — vulnerável a rainbow tables.

**Mitigação:** Substituir por `generate_password_hash` do Werkzeug em todos os pontos de criação de usuário.

### 11.3 [MÉDIA] Endpoints de Vídeo sem Autenticação

**Problema:** `/video_feed` e `/api/last_fracture_roi` não exigem login.

**Mitigação:** Adicionar `@login_required` ou autenticação por token de sessão.

### 11.4 [MÉDIA] Caminhos Hardcoded

**Problema:** Caminhos absolutos como `E:\programs\visionAlign\...` estão espalhados pelo código.

**Mitigação:** Usar `os.path` relativo ao `__file__` ou variável de ambiente `VISIONALIGN_ROOT`.

### 11.5 [MÉDIA] Flask sem HTTPS

**Problema:** Comunicação em HTTP puro. O Fernet protege o payload, mas metadados (IPs, timestamps, tamanho dos pacotes) ficam expostos.

**Mitigação:** Configurar Nginx como reverse proxy com certificado TLS (Let's Encrypt ou certificado interno).

### 11.6 [BAIXA] Ausência de Rate Limiting

**Problema:** Endpoints de login sem limite de tentativas — vulnerável a brute force.

**Mitigação:** Implementar `flask-limiter` com bloqueio após N tentativas falhas.

### 11.7 [BAIXA] Credenciais SMTP em Texto Plano

**Problema:** `.env` contém senha SMTP em texto plano.

**Mitigação:** Usar autenticação OAuth2 para SMTP ou armazenar em cofre de segredos.

### 11.8 [INFO] Sem Verificação de Integridade dos Modelos

**Problema:** Arquivos de modelo carregados sem verificação de hash.

**Mitigação:** Manter arquivo `model_checksums.sha256` e verificar antes de carregar.

---

## 12. Checklist de Deploy

### Antes de ir para produção:

- [ ] Mover `flask_app.secret_key` para variável de ambiente
- [ ] Configurar HTTPS via Nginx + TLS
- [ ] Adicionar `@login_required` em `/video_feed` e `/api/last_fracture_roi`
- [ ] Implementar rate limiting no endpoint de login
- [ ] Corrigir `add_user` para usar `generate_password_hash`
- [ ] Proteger `.env` com permissões restritivas (`chmod 600`)
- [ ] Proteger arquivos `.key` com permissões restritivas
- [ ] Remover caminhos hardcoded — usar variáveis de ambiente
- [ ] Adicionar headers CSP e HSTS
- [ ] Configurar rotação de logs (logrotate)
- [ ] Fazer backup criptografado do `users.db`
- [ ] Documentar e armazenar com segurança as chaves Fernet
- [ ] Verificar que `.env` e `*.key` estão no `.gitignore`
- [ ] Revisar permissões da pasta `data/alerts/` (imagens de fraturas)
- [ ] Desabilitar modo debug do Flask (`debug=False` — já configurado)

### Monitoramento contínuo:

- [ ] Alertas para múltiplas falhas de login consecutivas
- [ ] Monitorar tamanho do `users.db` (crescimento anormal = possível ataque)
- [ ] Revisar `activity_log` semanalmente
- [ ] Rotacionar chaves Fernet periodicamente (requer re-criptografia dos dados)

---

*Documento gerado para VisionAlign — Sistema de Inspeção Visual Industrial*
*Última atualização: 2025*
