# Technologies Used

This document lists all the tools and libraries that power VisionAlign-Fracture. The system was built to be fast and run on standard factory computers.

---

## 1. Base Language

*   **Python (3.11):** The foundation of the entire system. Chosen for its compatibility with the best AI tools on the market.

---

## 2. Artificial Intelligence and Vision

*   **Intel OpenVINO:** The "engine" that makes AI run fast on Intel processors without needing expensive graphics cards.
*   **OpenCV:** Library used to handle camera images, perform crops, and draw markings on the screen.
*   **NumPy:** Used for fast mathematical calculations with images.

---

## 3. Interface and Control

*   **PyQt5:** Used to create the desktop program used by operators on the factory floor.
*   **Flask:** Turns the system into a server that can be accessed via a web browser.
*   **FastAPI:** A modern technology used in the backend to ensure data communication is instantaneous.
*   **Uvicorn:** The server that runs FastAPI with high performance.

---

## 4. Security and Data

*   **Cryptography (Fernet):** Protects all information sent over the network, ensuring that no outsiders can see factory data.
*   **SQLite:** A simple database that stores production history and system users.
*   **Flask-Login:** Manages who can log in and what each user is allowed to do.
*   **Python-Jose and Passlib:** Tools used to create secure passwords and protected logins.

---

## 5. Support Tools

*   **FFmpeg:** A specialized video program used to receive high-resolution (4K) industrial camera images without lag.
*   **OpenPyXL:** Used to create Excel reports that can be downloaded by managers.
*   **Requests:** Allows the operator program to communicate with the AI server.

---

## Full Library List (Technical Summary)

For developers or IT staff, these are the installed libraries:

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

Last updated: May 2026
