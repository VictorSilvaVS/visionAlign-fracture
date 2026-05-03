# 🔭 VisionAlign-Fracture

> **Sistema de Visão Computacional Industrial para Inspeção de Latas e Detecção de Fraturas em Tempo Real**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![OpenVINO](https://img.shields.io/badge/Intel-OpenVINO-0071C5?logo=intel)](https://docs.openvino.ai/)
[![Flask](https://img.shields.io/badge/Flask-Web%20Server-black?logo=flask)](https://flask.palletsprojects.com/)
[![PyQt5](https://img.shields.io/badge/PyQt5-Desktop%20Client-green)](https://riverbankcomputing.com/software/pyqt/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?logo=sqlite)](https://sqlite.org/)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura do Sistema](#-arquitetura-do-sistema)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Como Executar](#-como-executar)
- [Módulos Principais](#-módulos-principais)
- [Pipeline de IA](#-pipeline-de-ia)
- [Segurança](#-segurança)
- [Documentação Completa](#-documentação-completa)

---

## 🎯 Visão Geral

O **VisionAlign-Fracture** é um sistema industrial de inspeção visual por visão computacional, desenvolvido para operar em linhas de produção de latas. O sistema realiza duas tarefas em paralelo:

1. **VisionAlign** — Detecta e classifica o estado das latas (Normal, Invertida, Tombada) usando rastreamento por ID de objeto.
2. **VisionFracture** — Analisa com alta precisão regiões de interesse (ROI) extraídas de cada lata rastreada, detectando micro-fraturas usando segmentação de instância.

O sistema opera em modo **cliente-servidor**, onde:
- O **servidor** (`run_client_only.py`) roda os modelos de IA, gerencia o stream de vídeo e expõe uma API Flask com dashboard web.
- O **cliente** (`main.py`) é uma interface desktop PyQt5 que se conecta ao servidor remotamente.

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENTE (PyQt5)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ LoginDialog │  │  MainWindow  │  │  Settings UI  │  │
│  └─────────────┘  └──────┬───────┘  └───────────────┘  │
│                           │  HTTP/API (requests)         │
└───────────────────────────┼─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   SERVIDOR (Flask)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Flask API   │  │  Dashboard   │  │  SSE Stream  │  │
│  │  /api/stats  │  │  Web (HTML)  │  │  /api/logs   │  │
│  └──────┬───────┘  └──────────────┘  └──────────────┘  │
│         │                                               │
│  ┌──────▼──────────────────────────────────────────┐   │
│  │              YOLOModel (Pipeline IA)            │   │
│  │  ┌─────────────┐        ┌──────────────────┐   │   │
│  │  │  OVModel    │        │    OVModel       │   │   │
│  │  │  VisionAlign│        │  VisionFracture  │   │   │
│  │  │  (Detect)   │        │  (Segment)       │   │   │
│  │  └──────┬──────┘        └────────┬─────────┘   │   │
│  │         │  ByteTracker           │ Sistema de   │   │
│  │         │  (IoU-based)           │ Votação     │   │
│  └─────────┼────────────────────────┼─────────────┘   │
│            │                        │                   │
│  ┌─────────▼────────────────────────▼─────────────┐   │
│  │           SQLite Database (data/users.db)       │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tecnologias Utilizadas

### Backend / IA
| Tecnologia | Versão | Uso |
|---|---|---|
| **Python** | 3.10+ | Linguagem principal |
| **Intel OpenVINO** | Runtime | Inferência otimizada para CPU Intel |
| **OpenCV** | 4.x | Captura de vídeo, processamento de imagem |
| **FFmpeg** | Via subprocess | Ingestão de streams RTSP 4K |
| **NumPy** | 1.x | Processamento matricial vetorizado |

### Servidor Web
| Tecnologia | Versão | Uso |
|---|---|---|
| **Flask** | 3.x | Servidor HTTP / REST API |
| **Flask-Login** | 0.6+ | Gerenciamento de sessão web |
| **Werkzeug** | 3.x | Hash de senhas (PBKDF2) |

### Cliente Desktop
| Tecnologia | Versão | Uso |
|---|---|---|
| **PyQt5** | 5.x | Interface gráfica desktop |
| **Requests** | 2.x | Chamadas HTTP ao servidor |

### Banco de Dados & Segurança
| Tecnologia | Versão | Uso |
|---|---|---|
| **SQLite3** | Embutido | Banco de dados local |
| **Cryptography (Fernet)** | 41+ | Criptografia simétrica AES-128 para dados em trânsito |

### Documentação
| Tecnologia | Uso |
|---|---|
| **MkDocs Material** | Documentação HTML estática multilíngue (PT/EN) |

---

## 📁 Estrutura do Projeto

```
visionAlign-fracture/
│
├── main.py                    # Entry point: cliente PyQt5
├── run_client_only.py         # Entry point: servidor completo (Flask + IA)
├── system_watchdog.py         # Watchdog de saúde do sistema
├── create_users.py            # Script CLI para criar usuários
├── debug_models.py            # Ferramenta de debug dos modelos
├── mkdocs.yml                 # Config da documentação MkDocs
│
├── model/                     # Módulo de IA
│   ├── yolo_model.py          # Pipeline principal (YOLOModel)
│   ├── ov_wrapper.py          # Wrapper nativo OpenVINO (OVModel + ByteTracker)
│   ├── detection_drawer.py    # Renderização visual das detecções
│   └── _openvino_model/       # Modelos exportados (.xml, .bin, metadata.yaml)
│
├── utils/                     # Utilitários compartilhados
│   ├── server.py              # Flask app + todas as rotas e API
│   ├── database.py            # ORM SQLite (Database class)
│   ├── security.py            # Criptografia Fernet (SecurityManager)
│   ├── logger_config.py       # Sistema de logging configurável
│   ├── email_utils.py         # Envio de alertas por e-mail
│   ├── timezone_utils.py      # Utilitários de fuso horário (UTC)
│   ├── export_model.py        # Exportação de modelos YOLO → OpenVINO
│   └── clp_communication.py   # Comunicação com CLPs industriais
│
├── interface/                 # Interface desktop (PyQt5)
│   ├── main_window.py         # Janela principal (>3000 linhas)
│   ├── configuracoes/         # Módulo de configurações
│   ├── dialogs/               # Diálogos (Login, etc.)
│   ├── assets/                # Recursos visuais
│   └── flask/                 # Templates e static files do dashboard web
│       ├── templates/         # HTML (Jinja2): index, analytics, retrain...
│       └── static/            # CSS, JS, imagens
│
├── backend/                   # Backend FastAPI (alternativo/futuro)
│   ├── app/
│   │   ├── api/v1/            # Endpoints FastAPI
│   │   ├── services/          # Serviços (model worker, cloud sync)
│   │   ├── core/              # Configurações e core
│   │   └── db/                # Modelos de banco
│   └── requirements.txt
│
├── training/                  # Módulo de treinamento
│   └── otx_manager.py         # Gerenciador de re-treinamento via OpenVINO Training Extensions
│
├── data/                      # Dados persistentes
│   ├── users.db               # Banco SQLite
│   └── dataset_collect/       # Imagens coletadas automaticamente
│
├── config/                    # Configurações de segurança
│   └── server_security.key    # Chave Fernet (gerada automaticamente)
│
├── logs/                      # Logs rotativos
├── docs/                      # Fontes da documentação MkDocs (PT + EN)
└── SECURITY.md                # Política de segurança
```

---

## 🚀 Como Executar

### Pré-requisitos

```bash
# 1. Python 3.10+ (recomendado 3.11)
python --version

# 2. FFmpeg no PATH do sistema
ffmpeg -version

# 3. Instalar dependências
pip install -r backend/requirements.txt
pip install PyQt5 flask flask-login werkzeug openvino opencv-python numpy cryptography openpyxl
```

### Executando o Servidor

```bash
# Inicia o servidor Flask + pipeline de IA
python run_client_only.py
```

O servidor subirá na porta **7586** (padrão). O dashboard web estará em `http://localhost:7586`.

### Executando o Cliente Desktop

```bash
# Em outra máquina (ou na mesma)
python main.py
```

### Criando o Usuário Admin

```bash
python create_users.py
```

---

## 🧩 Módulos Principais

| Módulo | Arquivo | Responsabilidade |
|---|---|---|
| **YOLOModel** | `model/yolo_model.py` | Orquestra o pipeline completo de IA, captura de vídeo, rastreamento e votação |
| **OVModel** | `model/ov_wrapper.py` | Wrapper puro OpenVINO: inferência, pós-processamento end2end, ByteTracker IoU |
| **Flask Server** | `utils/server.py` | ~2700 linhas: API REST, dashboard web, SSE, streaming MJPEG, analytics |
| **Database** | `utils/database.py` | CRUD SQLite: usuários, alertas, logs de detecção, histórico |
| **SecurityManager** | `utils/security.py` | Criptografia Fernet: dados em trânsito entre cliente e servidor |
| **MainWindow** | `interface/main_window.py` | UI PyQt5: controles, gráficos em tempo real, painel de configurações |

---

## 🤖 Pipeline de IA

```
Frame (RTSP/Camera/Video)
        │
        ▼
   Pré-processamento
   (Gamma + CLAHE)
        │
        ▼
  VisionAlign Model
  (OVModel - Detect)
  ┌─── ByteTracker ───┐
  │  Assign Track IDs │
  └───────────────────┘
        │
        ▼ Para cada Track ID
  Extração de ROI seguro
  (640x640 centrado na bbox)
        │
        ▼
  Aplicação da AOI (círculo 51mm)
        │
        ▼
  VisionFracture Model
  (OVModel - Segment)
        │
        ▼
  Sistema de Votação
  (score += gain | score -= loss)
  [threshold = 10 frames]
        │
    Confirmado?
   /           \
  Sim           Não
   │             │
  Alerta        Continua
  (DB + E-mail)  rastreando
```

---

## 🔐 Segurança

- **Criptografia de payload**: Todos os dados sensíveis (stats, settings) trafegam criptografados com **AES-128 via Fernet** entre cliente e servidor.
- **Hash de senhas**: `werkzeug.security.generate_password_hash` com PBKDF2-SHA256.
- **Sessões Flask**: Configuradas com `PERMANENT_SESSION_LIFETIME = 30 minutos`.
- **Controle de acesso**: Decorator `@role_required('admin')` protege rotas administrativas.
- **Chave gerenciada automaticamente**: A chave Fernet é gerada e persistida em `config/server_security.key`.

Veja [SECURITY.md](SECURITY.md) para a política de segurança completa.

---

## 📚 Documentação Completa

A documentação técnica detalhada é gerada pelo **MkDocs Material** em português e inglês:

```bash
pip install mkdocs-material mkdocs-i18n
mkdocs serve
```

Acesse em `http://localhost:8000`

### Documentos disponíveis em `docs/`:

| Documento | Descrição |
|---|---|
| `architecture.md` | Arquitetura técnica detalhada |
| `vision_align.md` | Módulo VisionAlign |
| `vision_fracture.md` | Módulo VisionFracture |
| `otx_training.md` | Re-treinamento com OpenVINO Training Extensions |
| `continuous_improvement.md` | Pipeline de melhoria contínua |
| `global_brain.md` | Conceito de Cérebro Global |
| `maintenance.md` | Guia de manutenção |
| `glossary.md` | Glossário técnico |
| `faqs.md` | Perguntas frequentes |

---

## 👥 Roles de Usuário

| Role | Permissões |
|---|---|
| **Admin** | Acesso total: configurações, analytics, re-treinamento, gestão de usuários |
| **User** | Dashboard básico, visualização de stats |
| **Guest** | Somente leitura de status básico |

---

*Desenvolvido com 🧠 inteligência artificial e ⚙️ engenharia industrial.*
