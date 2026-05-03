# API Reference and Security

This document describes how data is protected and how different computers communicate with each other.

---

## 1. Data Security (Encryption)

*   **Protected Data:** All sensitive information (statistics, settings, and images) is locked before being sent over the network.
*   **Method:** AES-128-CBC.
*   **Key:** Automatically generated upon the first server run.
*   **Process:** The server locks the data, and only computers with the same key can open and read the information.

---

## 2. Communication Points (Endpoints)

### Statistics and Status
*   **URL:** `/api/stats`
*   **Use:** The system requests production counts and AI status.

### Video Control
*   **URL:** `/api/change_source`
*   **Use:** Allows changing the camera or video being analyzed.

### Real-Time Logs
*   **URL:** `/console_stream`
*   **Use:** Shows live system messages in the browser without needing to refresh the page.

### Settings Update
*   **URL:** `/api/settings`
*   **Use:** Sends new sensitivity adjustments to the AI without needing to restart the system.

---

## 3. User Access

The system controls who can access each area:
*   **Login:** Requires username and password.
*   **Administrator:** Only users with admin permission can change critical AI settings.

---

Last updated: May 2026
