# Maintenance and Troubleshooting

This guide helps resolve the most common day-to-day issues on the production line, focusing on physical and operational causes.

---

## 🛠️ "What to do if..." (Problems and Solutions)

### 1. The image is blurry or "cloudy"
*   **Probable Cause:** Accumulation of oil, dust, or lubricant on the camera lens.
*   **Action:** Carefully clean the lens with a microfiber cloth and **isopropyl alcohol**. Never use rough cloths or water.

### 2. The system is not detecting anything (Black Screen)
*   **Probable Cause:** Network cable (Ethernet) or power cable is loose.
*   **Action:** Check the physical connections at the back of the camera and on the industrial switch. Ensure the link LED is flashing.

### 3. False Negatives (AI missed an obvious fracture)
*   **Probable Cause:** External lighting interference (sunlight reflection or nearby welding light).
*   **Action:** Ensure the camera's protective shield is correctly positioned to block external light. Clean the VisionSystem's lighting LEDs.

### 4. Image lag or "freezing"
*   **Probable Cause:** Overheating of the Edge Computing box.
*   **Action:** Check if the server's fans are obstructed by dirt. Perform a cleaning with compressed air if necessary.

---

## 📅 Preventive Maintenance Plan

| Activity | Frequency | Tool |
| :--- | :--- | :--- |
| Lens Cleaning | Daily (shift start) | Isopropyl Alcohol |
| Cable Check | Weekly | Visual Inspection |
| Filter/Fan Cleaning | Monthly | Compressed Air |
| Log Backup | Quarterly | Automatic via Dashboard |

> **Pro Tip:** 90% of "bad AI" errors are actually caused by an oil-dirty lens. Keep the machine's vision clean!
