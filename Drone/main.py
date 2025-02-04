from djitellopy import Tello
import time
import cv2
from threading import Thread
from object_detection import detect_animals  # Import della funzione di rilevamento

class VideoDrone(Thread):
    def __init__(self, tello):
        Thread.__init__(self)
        self.tello = tello
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            frame = self.tello.get_frame_read().frame
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Usa la funzione di rilevamento
            frame = detect_animals(frame)

            cv2.imshow("Tello Stream", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.tello.streamoff()
        cv2.destroyAllWindows()

    def stop(self):
        self.stop_flag = True

def main():
    tello = Tello()
    time.sleep(1)
    
    try:
        if not tello.connect():
            print("Failed to connect to Tello drone.")
            return
        print("Batteria:", tello.get_battery())
        if not tello.streamon():
            print("Failed to start video stream.")
            return
        print("Streaming video avviato...")
    except Exception as e:
        print(f"An error occurred: {e}")
        return

    videoDrone = VideoDrone(tello)
    videoDrone.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Chiusura in corso...")
        videoDrone.stop()
        videoDrone.join()
        tello.streamoff()
        print("Streaming video spento.")
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
