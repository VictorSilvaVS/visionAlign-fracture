# Training and OTX

**OpenVINO Training Extensions (OTX)** is the primary tool for model refinement within VisionAlign. It enables the updating of detection weights without complex manual intervention.

## Autonomous and Intelligent Training

The hallmark of VisionAlign is its **self-training** capability. Through OTX integration, the system does not just detect failures; it manages its own technical evolution:

- **Automatic Triggers:** The system monitors the density of images collected in the "uncertainty dataset." Upon reaching a critical threshold, the backend triggers a background retraining process.
- **Zero Intervention:** The entire pipeline (data preparation, training, OpenVINO optimization, and model deployment) occurs without the need for manual commands or production line downtime.
- **Auto-Validation and Backup:** The system automatically isolates **30% of new images** for rigorous validation. The new model is only deployed if it demonstrates **superiority above 90%** in key metrics or a significant reduction in **LOSS**. If approved, the old model is moved to a backup directory, allowing for instant rollback if necessary.

### Operational Benefits
- **Automation:** Reduced reliance on on-site data science specialists.
- **Efficiency:** Optimization for available hardware accelerators.
- **Customization:** Models perfectly adjusted to real production line conditions.

---

## Operational Commands
The backend engine executes the following operations:
```bash
otx train --model detection --data data.yaml
otx export --model model.pth --format openvino
```
