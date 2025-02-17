import cv2
import numpy as np
import tensorflow as tf
from sklearn.metrics.pairwise import cosine_similarity

# ------------------------------
# Parametri e caricamento modelli
# ------------------------------

# Definizione delle classi del modello MobileNet SSD
CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat",
    "bottle", "bus", "car", "cat", "chair", "cow",
    "diningtable", "dog", "horse", "motorbike", "person",
    "pottedplant", "sheep", "sofa", "train", "tvmonitor"
]

# Soglia di confidenza per il rilevamento
DETECTION_CONFIDENCE = 0.7

# La classe che vogliamo analizzare (in questo caso "cow")
TARGET_CLASS = "cow"

# Caricamento del modello MobileNet SSD
prototxt_path = "./models/MobileNetSSD_deploy.prototxt.txt"
model_path = "./models/MobileNetSSD_deploy.caffemodel"
net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

# Caricamento del modello di embedding (ResNet50 pre-addestrata)
# Usiamo include_top=False e pooling='avg' per ottenere un vettore di feature
# Crea il modello senza pesi predefiniti
embedding_model = tf.keras.applications.ResNet50(weights=None, include_top=False, pooling='avg')

# Carica i pesi da un file locale
embedding_model.load_weights('./models/resnet50_weights.h5')

# Lista globale per memorizzare gli embedding delle mucche già conteggiate
registered_embeddings = []

# Soglia per la similarità (valori vicini a 1 indicano alta similarità)
SIMILARITY_THRESHOLD = 0.9


def extract_embedding(crop):
    """
    Data una porzione di immagine (crop) contenente una mucca,
    la funzione ridimensiona, pre-processa e utilizza ResNet50 per
    estrarre un embedding (feature vector).
    """
    # Converti da BGR a RGB
    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    # Ridimensiona a 224x224 come richiesto da ResNet50
    crop_resized = cv2.resize(crop_rgb, (224, 224))
    # Converte l'immagine in array e aggiunge una dimensione per il batch
    img_array = np.expand_dims(crop_resized, axis=0)
    # Preprocessa l'immagine (normalizzazione richiesta da ResNet50)
    img_array = tf.keras.applications.resnet50.preprocess_input(img_array)
    # Estrae l'embedding
    embedding = embedding_model.predict(img_array)
    # Appiattisci il vettore
    embedding = embedding.flatten()
    return embedding

def is_new_cow(crop):
    """
    Data l'immagine ritagliata della mucca, la funzione estrae l'embedding
    e lo confronta con quelli già registrati. Se la similarità coseno con
    uno degli embedding registrati supera la soglia, si considera la stessa mucca.
    Altrimenti, la mucca viene considerata nuova e il suo embedding viene registrato.
    """
    global registered_embeddings
    new_embedding = extract_embedding(crop)
    
    # Se non ci sono embedding registrati, questa è la prima mucca
    if not registered_embeddings:
        registered_embeddings.append(new_embedding)
        return True

    # Confronta il nuovo embedding con ciascuno di quelli registrati
    for emb in registered_embeddings:
        sim = cosine_similarity(new_embedding.reshape(1, -1), emb.reshape(1, -1))[0][0]
        if sim >= SIMILARITY_THRESHOLD:
            # Trovata mucca già registrata
            return False

    # Se non troviamo una corrispondenza, registra il nuovo embedding
    registered_embeddings.append(new_embedding)
    return True

def detect_animals(frame):
    """
    Rileva le mucche nel frame usando MobileNet SSD, estrae il crop
    dell'area rilevata, controlla se si tratta di una nuova mucca tramite
    l'embedding e annota il frame di conseguenza.
    """
    # Prepara il frame per il rilevamento
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    # Ciclo su tutti i rilevamenti
    for i in np.arange(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > DETECTION_CONFIDENCE:
            idx = int(detections[0, 0, i, 1])
            label = CLASSES[idx] if idx < len(CLASSES) else "Unknown"
            if label == TARGET_CLASS:
                # Calcola le coordinate del bounding box
                box = detections[0, 0, i, 3:7] * np.array([ 
                    frame.shape[1], frame.shape[0], 
                    frame.shape[1], frame.shape[0]
                ])
                (startX, startY, endX, endY) = box.astype("int")
                
                # Estrai il crop dell'immagine; controlla che il crop sia valido
                crop = frame[startY:endY, startX:endX]
                if crop.size == 0:
                    continue

                # Determina se la mucca è nuova o già registrata
                if is_new_cow(crop):
                    text = f"Nuova Mucca! Totale: {len(registered_embeddings)}"
                    
                    color = (0, 255, 0)  # verde per nuovo
                else:
                    text = "Mucca contata"
                    color = (0, 0, 255)  # rosso per già visto

                # Disegna il bounding box e l'etichetta sul frame
                cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
                cv2.putText(frame, text, (startX, startY - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                print(f"totale mucche: {len(registered_embeddings)}")

    return frame
