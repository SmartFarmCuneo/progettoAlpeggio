import mysql.connector
import json
import time
from djitellopy import Tello

def get_perimeter_from_db(host='localhost', user='your_username', password='your_password', database='alpeggio', area_id=1):
    """
    Recupera dal database MySQL le coordinate dell'area.
    Si assume che nella tabella 'area' esista una colonna 'coordinates' contenente
    una stringa in formato JSON, ad esempio: "[[0,0], [0,200], [300,200], [300,0]]".

    Args:
        host (str): indirizzo del server MySQL.
        user (str): nome utente per il database.
        password (str): password per il database.
        database (str): nome del database.
        area_id (int): id dell'area da recuperare.

    Returns:
        list di tuple: le coordinate dell'area oppure None in caso di errore.
    """
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
            # Converte la stringa JSON in una lista di liste
            coordinates = json.loads(result[0])
            # Converte ogni coppia in una tupla (x, y)
            perimeter = [tuple(coord) for coord in coordinates]
            return perimeter
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
    
    def move_to(self, target_x, target_y):
        """
        Muove il drone da self.current_position a (target_x, target_y)
        utilizzando i comandi di spostamento relativi.
        """
        dx = target_x - self.current_position[0]
        dy = target_y - self.current_position[1]
        
        # Movimento lungo l'asse x (avanti/indietro)
        if dx > 0:
            print(f"Avanti di {dx} cm")
            self.drone.move_forward(dx)
        elif dx < 0:
            print(f"Indietro di {-dx} cm")
            self.drone.move_back(-dx)
        
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
            spacing (int): distanza in cm tra i punti della griglia.
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
        
        # Volo seguendo il percorso pianificato
        try:
            for punto in percorso:
                print(f"Volando verso: {punto}")
                self.move_to(punto[0], punto[1])
                time.sleep(1)  # pausa per stabilizzare il volo
        except KeyboardInterrupt:
            print("Interruzione manuale durante il volo.")
        
        # Atterraggio
        print("Atterraggio...")
        self.drone.land()
        time.sleep(2)
    
    def start_control_loop(self):
        """
        Loop di controllo manuale basato su input testuale.
        """
        try:
            while True:
                comando = input("Inserisci comando (decollo, atterraggio, avanti, indietro, fine): ")
                if comando == "decollo":
                    self.drone.takeoff()
                elif comando == "atterraggio":
                    self.drone.land()
                elif comando == "avanti":
                    self.drone.move_forward(30)
                elif comando == "indietro":
                    self.drone.move_back(30)
                elif comando == "fine":
                    print("Chiusura del controllo del drone.")
                    break
                else:
                    print("Comando non riconosciuto.")
        except KeyboardInterrupt:
            print("Interruzione manuale.")
            self.drone.land()