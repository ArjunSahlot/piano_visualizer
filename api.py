import os
import time
import cv2
import pygame


class Video:
    def __init__(self, resolution, fps):
        self.resolution = resolution
        self.fps = fps
        self.piano = Piano()
    
    def add_midi(self, path):
        pass

    def export(self, path, frames):
        pardir = os.path.realpath(os.path.dirname(__file__))

        export_dir = os.path.join(pardir, "export")
        os.makedirs(export_dir)
        tmp_file = os.path.join(export_dir, "frame.png")
        video = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MPEG"), self.fps, self.resolution)

        for frame in range(frames):
            self.export_frame(video, tmp_file, frame)

        video.release()
        cv2.destroyAllWindows()

        os.remove(tmp_file)

    def export_frame(self, video, path, frame):
        surface = pygame.Surface(self.resolution)
        surface.blit(self.piano.render(frame, self.resolution), (0, 0))
        pygame.image.save(surface, path)
        image = cv2.imread(path)
        video.write(image)
        cv2.destroyAllWindows()
        cv2.imshow(image)



class Piano:
    def __init__(self):
        pass

    def render(self, frame, resolution):
        pass