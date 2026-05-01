# VisionAlign Module

**VisionAlign** is the gateway to the VisionSystem intelligence pipeline. Its primary function is the global detection and alignment of objects on the production line.

## Technical Operation

The VisionAlign model is trained to identify the complete structure of the can and determine its geometric center and spatial orientation.

### 1. Global Detection
Utilizing a YOLO network optimized by OpenVINO, the system scans the frame for cylindrical or circular patterns that characterize the product.

### 2. ROI (Region of Interest) Handoff
The most critical feature of VisionAlign is not just detecting the can, but isolating the area of interest for subsequent modules.
- The system calculates a bounding box around the part.
- This area (ROI) is cropped with sub-pixel precision.
- The isolated image is then normalized and sent to **VisionFracture**.

## Operational Advantages
- **Noise Reduction:** By isolating the can, the system ignores background elements, shadows, and external interference.
- **Processing Efficiency:** The second stage of the AI (VisionFracture) processes only the ROI, saving computational resources and increasing overall speed.
- **Positioning Robustness:** VisionAlign compensates for vibrations and mechanical misalignments of the conveyor belt.
