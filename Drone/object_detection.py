import cv2
import numpy as np
import tensorflow as tf
from sklearn.metrics.pairwise import cosine_similarity
from inference import get_model
import supervision as sv

# ------------------------------
# Parametri e caricamento modelli
# ------------------------------

# Definizione delle classi per MobileNet SSD
CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat",
    "bottle", "bus", "car", "cat", "chair", "cow",
    "diningtable", "dog", "horse", "motorbike", "person",
    "pottedplant", "sheep", "sofa", "train", "tvmonitor"
]

# Soglia di confidenza per MobileNet SSD e target da rilevare
DETECTION_CONFIDENCE = 0.8
TARGET_CLASS = "cow"

# Soglia per la similarità degli embedding (valori vicini a 1 indicano alta similarità)
SIMILARITY_THRESHOLD = 0.9

# Caricamento del modello MobileNet SSD
prototxt_path = "./models/MobileNetSSD_deploy.prototxt.txt"
model_path = "./models/MobileNetSSD_deploy.caffemodel"
net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

# Caricamento del modello di embedding (ResNet50 pre-addestrata)
embedding_model = tf.keras.applications.ResNet50(weights=None, include_top=False, pooling='avg')
embedding_model.load_weights('./models/resnet50_weights.h5')

# Caricamento del modello fallback "cowspots/3"
# rf_zVOZSK5PCSUmyGNnkkbptqlf4XN2  <-- For use exclusively with inferencejs, the client-side library.
cowspots_model = get_model(model_id="cowspots/3", api_key="QhPX2OgmIjlrhcDdpwDC")

# Inizializza annotatori per Supervision (non utilizzati nella logica modificata del fallback)
bounding_box_annotator = sv.BoxAnnotator()
label_annotator = sv.LabelAnnotator()

# Lista globale per memorizzare gli embedding delle mucche già registrate
registered_embeddings = []

def extract_embedding(crop):
    """
    Estrae l'embedding dal ritaglio (crop) della mucca usando ResNet50.
    """
    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    crop_resized = cv2.resize(crop_rgb, (224, 224))
    img_array = np.expand_dims(crop_resized, axis=0)
    img_array = tf.keras.applications.resnet50.preprocess_input(img_array)
    embedding = embedding_model.predict(img_array)
    return embedding.flatten()

def is_new_cow(crop):
    """
    Confronta l'embedding del crop con quelli già registrati per determinare se si tratta di una nuova mucca.
    Se è nuova, l'embedding viene aggiunto alla lista.
    """
    global registered_embeddings
    new_embedding = extract_embedding(crop)
    
    if not registered_embeddings:
        registered_embeddings.append(new_embedding)
        return True

    for emb in registered_embeddings:
        sim = cosine_similarity(new_embedding.reshape(1, -1), emb.reshape(1, -1))[0][0]
        if sim >= SIMILARITY_THRESHOLD:
            return False

    registered_embeddings.append(new_embedding)
    return True

def detect_animals(frame):
    """
    Rileva le mucche nel frame utilizzando MobileNet SSD come rilevamento primario.
    Se viene rilevata almeno una mucca, la logica di registrazione (embeddings) viene applicata.
    Se MobileNet SSD non rileva alcuna mucca, viene usato il modello fallback "cowspots/3".
    In entrambi i casi, le mucche rilevate vengono annotate e, se nuove, registrate.
    """
    found_cow = False
    # Rilevamento tramite MobileNet SSD
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    for i in np.arange(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > DETECTION_CONFIDENCE:
            idx = int(detections[0, 0, i, 1])
            label = CLASSES[idx] if idx < len(CLASSES) else "Unknown"
            if label == TARGET_CLASS:
                found_cow = True
                box = detections[0, 0, i, 3:7] * np.array([frame.shape[1], frame.shape[0],
                                                            frame.shape[1], frame.shape[0]])
                (startX, startY, endX, endY) = box.astype("int")
                crop = frame[startY:endY, startX:endX]
                if crop.size == 0:
                    continue

                if is_new_cow(crop):
                    text = f"Nuova Mucca! Totale: {len(registered_embeddings)}"
                    color = (0, 255, 0)  # verde per nuova
                else:
                    text = "Mucca contata"
                    color = (0, 0, 255)  # rosso per già vista

                cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
                cv2.putText(frame, text, (startX, startY - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                print(f"Totale mucche: {len(registered_embeddings)}")

    # Fallback: se MobileNet SSD non rileva alcuna mucca, usa cowspots/3
    if not found_cow:
        results = cowspots_model.infer(frame)[0]
        detections_sv = sv.Detections.from_inference(results)
        # Itera su ogni bounding box rilevato dal modello cowspots/3
        for bbox in detections_sv.xyxy:
            (startX, startY, endX, endY) = map(int, bbox)
            crop = frame[startY:endY, startX:endX]
            if crop.size == 0:
                continue
            # Verifica se la mucca è nuova e, in caso, la registra
            if is_new_cow(crop):
                text = f"Nuova Mucca! Totale: {len(registered_embeddings)}"
                color = (0, 255, 0)
            else:
                text = "Mucca contata"
                color = (0, 0, 255)
            cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
            cv2.putText(frame, text, (startX, startY - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            print(f"Totale mucche: {len(registered_embeddings)}")
            
    return frame
