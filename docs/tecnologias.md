# Tecnologias Utilizadas

Este documento lista todas as ferramentas e bibliotecas que fazem o VisionAlign-Fracture funcionar. O sistema foi construído para ser rápido e rodar em computadores comuns de fábrica.

---

## 1. Linguagem Base

*   **Python (3.11):** É a base de todo o sistema. Escolhido por ser compatível com as melhores ferramentas de inteligência artificial do mercado.

---

## 2. Inteligência Artificial e Visão

*   **Intel OpenVINO:** É o "motor" que faz a inteligência artificial rodar rápido em processadores Intel, sem precisar de placas de vídeo caras.
*   **OpenCV:** Biblioteca usada para manipular as imagens da câmera, fazer recortes e desenhar as marcações na tela.
*   **NumPy:** Usado para fazer cálculos matemáticos rápidos com as imagens.

---

## 3. Interface e Controle

*   **PyQt5:** Usado para criar o programa que o operador usa no computador da fábrica.
*   **Flask:** Transforma o sistema em um servidor que pode ser acessado pelo navegador.
*   **FastAPI:** Uma tecnologia moderna usada no backend para garantir que a comunicação de dados seja instantânea.
*   **Uvicorn:** O servidor que faz o FastAPI rodar com alta performance.

---

## 4. Segurança e Dados

*   **Cryptography (Fernet):** Protege todas as informações enviadas pela rede, garantindo que ninguém de fora consiga ver os dados da fábrica.
*   **SQLite:** Um banco de dados simples que guarda o histórico de produção e os usuários do sistema.
*   **Flask-Login:** Gerencia quem pode entrar e o que cada usuário pode fazer no sistema.
*   **Python-Jose e Passlib:** Ferramentas usadas para criar senhas seguras e logins protegidos.

---

## 5. Ferramentas de Apoio

*   **FFmpeg:** Programa especialista em vídeo usado para receber as imagens da câmera industrial em alta resolução (4K) sem atrasos.
*   **OpenPyXL:** Usado para criar relatórios em Excel que podem ser baixados pelo gestor.
*   **Requests:** Permite que o programa do operador converse com o servidor de inteligência artificial.

---

## Lista Completa de Bibliotecas (Resumo Técnico)

Para desenvolvedores ou equipe de TI, estas são as bibliotecas instaladas:

*   fastapi
*   uvicorn
*   python-multipart
*   pydantic
*   pydantic-settings
*   python-jose[cryptography]
*   passlib[bcrypt]
*   cryptography
*   aiofiles
*   requests
*   opencv-python-headless
*   numpy
*   flask
*   flask-login
*   openvino
*   pyqt5
*   openpyxl

---

Última atualização: Maio de 2026
