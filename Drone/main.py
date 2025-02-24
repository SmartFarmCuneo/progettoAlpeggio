from djitellopy import Tello
import time
import cv2
from threading import Thread
from object_detection import detect_animals
from movimento import DroneController, calcola_perimetro_da_coordinate

class VideoDrone(Thread):
    def __init__(self, tello):
        Thread.__init__(self)
        self.tello = tello
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            frame = self.tello.get_frame_read().frame
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Uso della funzione di rilevamento animali
            frame = detect_animals(frame)

            cv2.imshow("Tello Stream", frame)

            # Se viene premuto il tasto 'q', atterra il drone e interrompe il loop
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Tasto 'q' premuto: atterraggio in corso...")
                try:
                    self.tello.land()
                except Exception as e:
                    print("Errore durante l'atterraggio:", e)
                break

        self.stop_flag = True
        self.tello.streamoff()
        cv2.destroyAllWindows()

    def stop(self):
        self.stop_flag = True

def main():
    drone_controller = DroneController()
    #[[0, 0], [0, 200], [200, 200], [200, 0]]
    perimetro_area = calcola_perimetro_da_coordinate()
    print("Avvio del sistema drone...")

    # Inizializza il drone Tello
    tello = Tello()
    time.sleep(0.5)

    try:
        tello.connect()
        print("Batteria:", tello.get_battery())
        tello.streamon()  # Avvia lo streaming video

        # Crea e avvia il thread per lo streaming video
        video_drone = VideoDrone(tello)
        video_thread = Thread(target=video_drone.start)
        video_thread.start()

        # Loop di controllo 
        # lo spacing è la distanza coperta per movimento es. 100 fa passi di 1m
        # lo spacing può essere tra 20cm e 5m
        drone_controller.vola_all_interno_area(perimetro_area, spacing=40)

        # Attende la terminazione del thread video
        video_thread.join()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        video_drone.stop()
        tello.streamoff()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
