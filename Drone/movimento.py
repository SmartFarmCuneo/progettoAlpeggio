import os
import cv2
import mysql.connector
import json
import time
from djitellopy import Tello

def calcola_perimetro_da_coordinate(host='localhost', user='your_username', password='your_password', database='alpeggio', area_id=1):
    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        cursor = conn.cursor()
        query = "SELECT coordinates FROM coordinate WHERE id = %s"
        cursor.execute(query, (area_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result is not None:
            coordinates = json.loads(result[0])

            lat0, lon0 = coordinates[0]
            perimetro_area = [[int((lat - lat0) * 11132000), int((lon - lon0) * 11132000)] for lat, lon in coordinates]

            print("Il calcolo dell'area risulta:", perimetro_area)

            conferma = input("Confermi? (s/n): ").strip().lower()
            if conferma == 's':
                return perimetro_area
            else:
                print("Riprova l'inserimento delle coordinate.")
                return calcola_perimetro_da_coordinate(host, user, password, database, area_id)
        else:
            print(f"Nessuna area trovata con id: {area_id}")
            return None
    except mysql.connector.Error as e:
        print("Errore durante il recupero dal database MySQL:", e)
        return None
    
def point_in_polygon(x, y, polygon):
    """
    Controlla se il punto (x, y) è all'interno del poligono definito dalla lista di tuple.
    Implementa l'algoritmo ray-casting.
    """
    num = len(polygon)
    j = num - 1
    inside = False
    for i in range(num):
        if ((polygon[i][1] > y) != (polygon[j][1] > y)) and \
           (x < (polygon[j][0] - polygon[i][0]) * (y - polygon[i][1]) / ((polygon[j][1] - polygon[i][1]) or 1e-9) + polygon[i][0]):
            inside = not inside
        j = i
    return inside

class DroneController:
    def __init__(self):
        self.drone = Tello()
        self.drone.connect()
        print(f"Batteria drone: {self.drone.get_battery()}%")
        # Posizione iniziale assunta: (0,0)
        self.current_position = (0, 0)
        self.captured_images = []
        # Directory in cui salvare le immagini: immagini/drone
        self.image_dir = "images"
        os.makedirs(self.image_dir, exist_ok=True)
    
    def move_to(self, target_x, target_y):
        """
        Muove il drone da self.current_position a (target_x, target_y)
        utilizzando i comandi di spostamento relativi.
        Per gli spostamenti in cui il delta x è negativo (cioè deve andare "indietro"),
        il drone ruota di 180° e si muove in avanti, evitando così la retromarcia.
        """
        dx = target_x - self.current_position[0]
        dy = target_y - self.current_position[1]
        
        # Movimento lungo l'asse x (avanti/indietro)
        if dx > 0:
            print(f"Avanti di {dx} cm")
            self.drone.move_forward(dx)
        elif dx < 0:
            # Invece di usare move_back, ruota 180° e muovi in avanti
            print("Ruota di 180° per evitare il movimento all'indietro")
            self.drone.rotate_clockwise(180)
            print(f"Avanti di {-dx} cm")
            self.drone.move_forward(-dx)
            print("Ruota di 180° per ripristinare l'orientamento originale")
            self.drone.rotate_clockwise(180)
        
        # Movimento lungo l'asse y (destra/sinistra)
        if dy > 0:
            print(f"Destra di {dy} cm")
            self.drone.move_right(dy)
        elif dy < 0:
            print(f"Sinistra di {-dy} cm")
            self.drone.move_left(-dy)
        
        self.current_position = (target_x, target_y)

    
    def vola_all_interno_area(self, perimetro, spacing=50):
        """
        Vola all'interno di un'area definita dal perimetro.
        
        Args:
            perimetro (list di tuple): coordinate (x, y) in cm che definiscono il perimetro.
            spacing (int): distanza in cm tra i punti della griglia (min:20cm, max:5m).
        """
        # Calcola il bounding box dell'area
        xs = [p[0] for p in perimetro]
        ys = [p[1] for p in perimetro]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # Genera la griglia di punti all'interno del bounding box
        punti_interni = []
        for x in range(min_x, max_x + 1, spacing):
            for y in range(min_y, max_y + 1, spacing):
                if point_in_polygon(x, y, perimetro):
                    punti_interni.append((x, y))
        
        if not punti_interni:
            print("Nessun punto interno trovato. Verifica il perimetro fornito.")
            return
        
        # Ordina i punti per creare un percorso a "rullo" (lawn mower pattern)
        punti_interni.sort(key=lambda p: (p[1], p[0]))
        righe = []
        current_row = []
        current_y = None
        row_threshold = spacing // 2  # tolleranza per considerare punti sulla stessa "riga"
        
        for p in punti_interni:
            if current_y is None or abs(p[1] - current_y) <= row_threshold:
                current_row.append(p)
                if current_y is None:
                    current_y = p[1]
            else:
                righe.append(current_row)
                current_row = [p]
                current_y = p[1]
        if current_row:
            righe.append(current_row)
        
        percorso = []
        for i, riga in enumerate(righe):
            # Inverte l'ordine dei punti in righe alternate per un percorso a zig-zag
            riga_ordinata = sorted(riga, key=lambda p: p[0], reverse=(i % 2 == 1))
            percorso.extend(riga_ordinata)
        
        # Decollo
        print("Decollo...")
        self.drone.takeoff()
        time.sleep(2)
        
        # Volo seguendo il percorso pianificato e acquisizione immagini ad ogni punto
        try:
            for punto in percorso:
                print(f"Volando verso: {punto}")
                self.move_to(punto[0], punto[1])
                time.sleep(1)  # pausa per stabilizzare il volo

                # Acquisizione dell'immagine al punto raggiunto
                frame_read = self.drone.get_frame_read()  # avvia la lettura del video se non già attivo
                image = frame_read.frame
                self.captured_images.append(image)
                # Salva la foto nella cartella immagini/drone
                filename = os.path.join(self.image_dir, f"immagine_{punto[0]}_{punto[1]}.jpg")
                cv2.imwrite(filename, image)
                print(f"Foto salvata: {filename}")
        except KeyboardInterrupt:
            print("Interruzione manuale durante il volo.")
        
        # Atterraggio
        print("Atterraggio...")
        self.drone.land()
        time.sleep(2)

        # Stitching delle immagini acquisite: unione delle foto eliminando le parti in comune
        print("Creazione immagine finale unendo le foto acquisite...")
        if len(self.captured_images) > 1:
            # Crea lo stitcher; alcune versioni di OpenCV usano cv2.Stitcher_create()
            stitcher = cv2.Stitcher_create() if hasattr(cv2, 'Stitcher_create') else cv2.createStitcher()
            status, stitched_image = stitcher.stitch(self.captured_images)
            if status == cv2.Stitcher_OK:
                final_filename = os.path.join(self.image_dir, "immagine_finale.jpg")
                cv2.imwrite(final_filename, stitched_image)
                print(f"Immagine finale creata e salvata come '{final_filename}'")
            else:
                print("Errore durante la creazione dell'immagine finale. Codice di status:", status)
        else:
            print("Non ci sono abbastanza immagini per creare un'immagine finale.")
