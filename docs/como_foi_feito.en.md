# How It Was Made

This document tells the story of the development of VisionAlign-Fracture and the decisions made to reach the current system.

---

## 1. The Beginning and Challenges

The project started with the need to inspect cans at high speed. Initially, we used common market tools (like Ultralytics YOLO).

**The Problem:** These tools were heavy and required very expensive computers with powerful graphics cards. For the factory, we needed something that could run on standard computers.

---

## 2. Switching to Intel Technology

We decided to switch to Intel's OpenVINO. This choice allowed the system to run up to 5 times faster using only the computer's standard processor.

**Result:** Hardware savings and greater stability for 24-hour operation.

---

## 3. Division of Labor (Inspection Funnel)

We created a "digital team" strategy so the system wouldn't slow down:

*   **Identifier:** Locates the can on the conveyor belt.
*   **Inspector:** Focuses only on the located can to look for flaws.

This is like having one person to separate the cans and another just to look at the details of each one.

---

## 4. Solving Video Lag

4K industrial cameras send a lot of data. If we used the standard video reading method, the system would start showing images with a delay. We used the FFmpeg program to ensure the system always sees the "now," automatically discarding old images.

---

## 5. Industrial Security

To protect factory data, all information passing through the network is locked with a digital key (encryption). Only authorized computers can read this information.

---

Last updated: May 2026
