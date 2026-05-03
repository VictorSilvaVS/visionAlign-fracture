# Guia de Instalação

Siga este passo a passo para configurar o VisionAlign-Fracture em seu computador.

---

## 1. Requisitos do Computador

*   Processador: Intel Core i5 ou superior (geração 8 em diante).
*   Memória RAM: 8GB ou mais.
*   Sistema: Windows 10/11 ou Linux.

---

## 2. Programas Necessários

Você precisará instalar os seguintes programas antes de começar:
1.  Python (versão 3.10 ou 3.11).
2.  FFmpeg (adicionado ao PATH do sistema).

---

## 3. Passo a Passo de Instalação

### Preparar a Pasta do Projeto
Certifique-se de que todos os arquivos do sistema estão na pasta desejada e abra o terminal nesta pasta.

### Criar Ambiente Isolado
```bash
python -m venv venv
# No Windows:
venv\Scripts\activate
```

### Instalar Bibliotecas
```bash
pip install -r backend/requirements.txt
pip install PyQt5 flask flask-login werkzeug openvino opencv-python numpy cryptography openpyxl requests fastapi uvicorn
```

---

## 4. Configuração de Segurança

Na primeira vez que você rodar o servidor, ele criará uma chave de segurança em `config/server_security.key`. 
**Atenção:** Se você for usar o programa em outro computador para ver os resultados, você deve copiar este arquivo de chave para a mesma pasta no outro computador.

---

## 5. Como Iniciar

### Iniciar o Servidor (Computador da Câmera)
```bash
python run_client_only.py
```

### Iniciar a Tela do Operador
```bash
python main.py
```

---

Última atualização: Maio de 2026
