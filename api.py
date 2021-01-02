import os
import random
import cv2
import pygame
import shutil
from animutils import XMido
from constants import *


class Piano:
    gap = 4

    def __init__(self, resolution, fps):
        self.resolution = resolution
        self.fps = fps
        self.pianos = {}
    
    def add_piano(self, path):
        midi = XMido(path)
        parsed = midi.parse(self.fps, 0)
        minimum, maximum = float("inf"), float("-inf")
        for note in parsed:
            val = note["note"]
            maximum = max(val, maximum)
            minimum = min(val, minimum)

        self.pianos[(minimum - self.gap, maximum + self.gap)] = parsed

    def export(self, path, frames):
        pardir = os.path.realpath(os.path.dirname(__file__))

        export_dir = os.path.join(pardir, "export")
        os.makedirs(export_dir, exist_ok=True)
        tmp_file = os.path.join(export_dir, "frame.png")
        video = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MPEG"), self.fps, self.resolution)

        for frame in range(frames):
            surface = self.render(frame)
            pygame.image.save(surface, tmp_file)
            image = cv2.imread(tmp_file)
            video.write(image)

        video.release()
        cv2.destroyAllWindows()

        shutil.rmtree(export_dir)

    def render(self, frame):
        surf = pygame.Surface(self.resolution, pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        width, height = self.resolution
        max_height = height/3
        min_height = height/12
        whitekey_height = min(max_height, max(min_height, (height-100)/(len(self.pianos)+2)))
        blackkey_height = whitekey_height/2.4
        offset = height - height/(len(self.pianos)+1)
        for i, range_keys in enumerate(self.pianos.keys()):
            y = offset*(i+1) - whitekey_height/2
            status = self.get_play_status(frame, range_keys, self.pianos[range_keys])
            counter = 0
            for j in range(*range_keys):
                if self.is_black(j):
                    pass
                else:
                    key_width = min(width/50, width/(range_keys[1] - range_keys[0]))
                    gap = 5
                    keys_width = (range_keys[1] - range_keys[0]) * (key_width + gap)
                    pygame.draw.rect(surf, RED if status[i] else WHITE, (width/2 - keys_width/2 + counter*(key_width + gap), y, key_width, whitekey_height))
                    counter += 1

        return surf
    
    def is_black(self, key):
        return False
    
    def get_play_status(self, frame, range, midi):
        return [False] * (range[1] - range[0])


piano = Piano((1920, 1080), 30)
piano.add_piano("/home/arjun/jojo.mid")
piano.export(os.path.join(os.path.realpath(os.path.dirname(__file__)), "asdf.mp4"), 200)
