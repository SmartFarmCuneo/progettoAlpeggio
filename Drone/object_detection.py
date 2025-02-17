import cv2
import numpy as np

# Definiamo le classi del modello MobileNet SSD
CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat",
    "bottle", "bus", "car", "cat", "chair", "cow",
    "diningtable", "dog", "horse", "motorbike", "person",
    "pottedplant", "sheep", "sofa", "train", "tvmonitor"
]

# Insieme delle classi considerate "animali"
ANIMALS = {"bird", "cat", "cow", "dog", "horse", "sheep"}

# Caricamento del modello MobileNet SSD
prototxt = "./models/MobileNetSSD_deploy.prototxt"
model = "./models/MobileNetSSD_deploy.caffemodel"
net = cv2.dnn.readNetFromCaffe(prototxt, model)


def detect_animals(frame):
    """
    Rileva animali nel frame e restituisce il frame annotato.
    """
    # Prepara il frame per il modello (blob)
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    # Variabile per tracciare se abbiamo già stampato un animale in questo frame
    animal_detected = False

    # Ciclo sui rilevamenti
    for i in np.arange(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            idx = int(detections[0, 0, i, 1])
            label = CLASSES[idx] if idx < len(CLASSES) else "Unknown"
            if label in ANIMALS:
                if not animal_detected:
                    print(f"Animale rilevato: {label} (confidenza: {confidence:.2f})")
                    animal_detected = True
                # Disegna il rettangolo sul frame
                box = detections[0, 0, i, 3:7] * np.array([
                    frame.shape[1], frame.shape[0], frame.shape[1], frame.shape[0]
                ])
                (startX, startY, endX, endY) = box.astype("int")
                cv2.rectangle(frame, (startX, startY),
                              (endX, endY), (0, 255, 0), 2)
                cv2.putText(frame, label, (startX, startY - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return frame
