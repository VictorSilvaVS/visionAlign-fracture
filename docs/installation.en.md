# Installation Guide

Follow these steps to set up VisionAlign-Fracture on your computer.

---

## 1. Computer Requirements

*   Processor: Intel Core i5 or higher (8th generation onwards).
*   RAM: 8GB or more.
*   System: Windows 10/11 or Linux.

---

## 2. Necessary Software

You will need to install the following software before starting:
1.  Python (version 3.10 or 3.11).
2.  FFmpeg (added to the system PATH).

---

## 3. Installation Steps

### Prepare the Project Folder
Ensure all system files are in the desired folder and open the terminal in that folder.

### Create Isolated Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
```

### Install Libraries
```bash
pip install -r backend/requirements.txt
pip install PyQt5 flask flask-login werkzeug openvino opencv-python numpy cryptography openpyxl requests fastapi uvicorn
```

---

## 4. Security Configuration

The first time you run the server, it will create a security key in `config/server_security.key`.
**Important:** If you are going to use the program on another computer to view the results, you must copy this key file to the same folder on the other computer.

---

## 5. How to Start

### Start the Server (Camera Computer)
```bash
python run_client_only.py
```

### Start the Operator Screen
```bash
python main.py
```

---

Last updated: May 2026
