# System Architecture

This document explains how the system works internally and how it is organized to ensure that no defect goes unnoticed.

---

## 1. System Organization (The 4 Layers)

Think of the system as a 4-story building, where each floor has a specific function:

```mermaid
graph TD
    subgraph Layer_4 [4. Presentation and Visualization]
        direction LR
        A1[Operator Program] --- A2[Web Dashboard]
    end

    subgraph Layer_3 [3. Application and Security]
        direction LR
        B1[Data Communication] --- B2[Security Manager] --- B3[Database]
    end

    subgraph Layer_2 [2. Artificial Intelligence]
        direction LR
        C1[OpenVINO Engine] --- C2[Location Model] --- C3[Detail Model]
    end

    subgraph Layer_1 [1. Infrastructure and Base]
        direction LR
        D1[Video Reading] --- D2[Logging System] --- D3[Task Management]
    end

    Layer_1 --> Layer_2
    Layer_2 --> Layer_3
    Layer_3 --> Layer_4
```

---

## 2. Two-Stage Processing

To ensure the system is both fast and accurate, it uses a funnel strategy:

1.  **Step 1:** The system locates all cans on the conveyor belt and assigns a number to each one.
2.  **Step 2 (VisionFracture):** It crops the image of each can and performs a deep analysis looking for cracks.

![AI Fracture Detection](assets/images/heatmap.png)

!!! tip "Heatmap Analysis"
    The system uses heatmaps to highlight exactly where the flaw was found, making visual verification easier for the operator.

```mermaid
graph LR
    A[Camera] --> B(Locate cans)
    B --> C(Crop can image)
    C --> D(Analyze for cracks)
    D --> E{Result}
```

---

## 3. Voting System (Preventing Errors)

This is one of the most important parts of the system. To prevent a simple light reflection from causing a false alarm, the system uses a "voting" process:

The system doesn't decide if there is a crack by looking only once. It looks at the same can multiple times as it passes by the camera.

*   **Positive Vote:** If the system sees a flaw, the can gets +1 point.
*   **Negative Vote:** If the system sees nothing, the can loses 1 point.
*   **Alarm:** The alert is only triggered if the can accumulates **10 points**.

```mermaid
graph TD
    A[Start: 0 points] --> B{Saw a flaw?}
    B -- Yes --> C[Gain +1 point]
    B -- No --> D[Lose 1 point]
    C --> E{Reached 10?}
    E -- Yes --> F[CONFIRMED ALERT]
    E -- No --> B
    D --> B
```

This logic ensures the system is extremely reliable, ignoring temporary flashes on the metal surface.

---

## 4. Performance Evolution

The system is constantly learning. See how the accuracy has improved:

| Version | Project Stage | Detection Accuracy |
|---|---|---|
| V1.0 | Start of Project | 62% |
| V1.2 | Camera Adjustments | 75% |
| V1.5 | Advanced Training | 78% |
| V2.0 | Speed Optimization | 85% |
| V2.1 | Current Version | 93% |

---

Last updated: May 2026
