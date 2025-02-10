from djitellopy import Tello
import time

class DroneController:
    def __init__(self):
        self.drone = Tello()
        self.drone.connect()
        print(f"Batteria drone: {self.drone.get_battery()}%")

    def start_control_loop(self):
        try:
            while True:
                command = input("Inserisci comando (decollo, atterraggio, avanti, indietro, fine): ")
                if command == "decollo":
                    self.drone.takeoff()
                elif command == "atterraggio":
                    self.drone.land()
                elif command == "avanti":
                    self.drone.move_forward(30)
                elif command == "indietro":
                    self.drone.move_back(30)
                elif command == "fine":
                    print("Chiusura del controllo del drone.")
                    break
                else:
                    print("Comando non riconosciuto.")
        except KeyboardInterrupt:
            print("Interruzione manuale.")
            self.drone.land()