from ultralytics import YOLO, checks, hub
checks()

hub.login('2e1baba7e42521514ac58cfe180e69cf465f1da03a')

model = YOLO('https://hub.ultralytics.com/models/9RBK8XmWMm4x0UehXUNl')
results = model.train()