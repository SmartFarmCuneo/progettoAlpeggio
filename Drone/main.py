from djitellopy import Tello
import time
import cv2
from threading import Thread
from object_detection import detect_animals  # Assuming object_detection.py is present
from utils import DroneController

class VideoDrone(Thread):
    def __init__(self, tello):
        Thread.__init__(self)
        self.tello = tello
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            frame = self.tello.get_frame_read().frame
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Use the animal detection function
            frame = detect_animals(frame)

            cv2.imshow("Tello Stream", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.tello.streamoff()
        cv2.destroyAllWindows()

    def stop(self):
        self.stop_flag = True

class Main:
    def __init__(self):
        self.drone_controller = DroneController()
        self.video_drone = None  # This will be initialized in the start() method


    def start(self):
        print("Avvio del sistema drone...")

        # Initialize the Tello drone
        tello = Tello()

        time.sleep(1)

        try:
            tello.connect()  # This should not be checked with an if statement
            print("Batteria:", tello.get_battery())
            tello.streamon()  # Start video stream
            print("Streaming video avviato...")

            # Create and start the video stream thread
            self.video_drone = VideoDrone(tello)
            video_thread = Thread(target=self.video_drone.start)
            video_thread.start()

            # Control loop (you can implement drone control logic here)
            self.drone_controller.start_control_loop()

            # Wait for the video thread to finish
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
