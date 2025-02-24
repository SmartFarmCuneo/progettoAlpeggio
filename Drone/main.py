from djitellopy import Tello
import time
import cv2
from threading import Thread
from object_detection import detect_animals  # Assuming object_detection.py is present
from movimento import DroneController

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

class Main:
    def __init__(self):
        self.drone_controller = DroneController()
        self.video_drone = None  # Verrà inizializzato nel metodo start()

    def start(self):
        perimetro_area = [[0, 0], [0, 100], [100, 100], [100, 0]]
        print("Avvio del sistema drone...")

        # Inizializza il drone Tello
        tello = Tello()
        time.sleep(1)

        try:
            tello.connect()
            print("Batteria:", tello.get_battery())
            tello.streamon()  # Avvia lo streaming video
            print("Streaming video avviato...")

            # Crea e avvia il thread per lo streaming video
            self.video_drone = VideoDrone(tello)
            video_thread = Thread(target=self.video_drone.start)
            video_thread.start()

            # Loop di controllo (qui è possibile implementare la logica di controllo del drone)
            self.drone_controller.vola_all_interno_area(perimetro_area, spacing=10)

            # Attende la terminazione del thread video
            video_thread.join()

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if self.video_drone:
                self.video_drone.stop()
            tello.streamoff()
            cv2.destroyAllWindows()
            print("Chiusura in corso...")

if __name__ == "__main__":
    main = Main()
    main.start()
