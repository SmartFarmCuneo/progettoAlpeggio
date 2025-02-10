from djitellopy import Tello
import cv2

class VideoDrone:
    def __init__(self, drone_controller):
        self.drone = drone_controller.drone

    def start_video_stream(self):
        self.drone.streamon()
        print("Streaming video avviato...")
        try:
            while True:
                frame = self.drone.get_frame_read().frame
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imshow("Drone Video", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except KeyboardInterrupt:
            print("Interruzione dello streaming video.")
        finally:
            self.drone.streamoff()
            cv2.destroyAllWindows()
