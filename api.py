import os
import cv2
import pygame
import shutil
from constants import *
import time
import sys
import mido
import ffmpeg
from pydub import AudioSegment

class Piano:
    gap = 4

    def __init__(self, resolution, fps):
        self.resolution = resolution
        self.fps = fps
        self.status = []
        self.midis = []
        self.midi_paths = []
        self.ranges = []
    
    def add_piano(self, path):
        self.midi_paths.append(path)
        midi = mido.MidiFile(path)
        parsed = self.parse_midi(midi)
        minimum, maximum = float("inf"), float("-inf")
        for note in parsed:
            val = note["note"]
            maximum = max(val, maximum)
            minimum = min(val, minimum)

        self.ranges.append((minimum - self.gap, maximum + self.gap))
        self.midis.append(parsed)
        self.status.append([False]*(maximum - minimum + 2*self.gap + 1))


    def export(self, path, verbose=False, frac_frames=1):
        pardir = os.path.realpath(os.path.dirname(__file__))
        min_frame, max_frame = float("inf"), float("-inf")
        for midi in self.midis:
            for msg in midi:
                val = msg["time"]
                max_frame = max(val, max_frame)
                min_frame = min(val, min_frame)
        
        max_frame = int(frac_frames *  (max_frame - min_frame)) + min_frame
        frames = int(max_frame - min_frame)

        if verbose:
            sys.stdout.write("--------------------------------------\n")
            sys.stdout.write("Exporting video:\n")
            sys.stdout.write(f"  Resolution: {' by '.join(map(str, self.resolution))}\n")
            sys.stdout.write(f"  FPS: {self.fps}\n")
            sys.stdout.write(f"  Frames: {frames}\n\n")
            sys.stdout.flush()

            time_start = time.time()
        export_dir = os.path.join(pardir, "export")
        os.makedirs(export_dir, exist_ok=True)
        tmp_file = os.path.join(export_dir, "frame.png")
        video = cv2.VideoWriter(os.path.join(export_dir, "video.mp4"), cv2.VideoWriter_fourcc(*"MPEG"), self.fps, self.resolution)
        for frame in range(min_frame, max_frame):
            if verbose:
                time_elapse = round(time.time()-time_start, 3)
                frame_num = f"{frame+1 - min_frame} of {frames}, "
                secs_elapse = f"{time_elapse} seconds elapsed. "
                if frames > 1:
                    perc = f"{int(100 * ((frame - min_frame)/(frames-1)))}% finished. "
                else:
                    perc = f"100% finished. "
                rem_secs = round((frames-(frame - min_frame)) * (time_elapse/((frame - min_frame)+1)))
                mins = rem_secs // 60
                secs = rem_secs % 60
                remaining = f"{mins} mins and {secs} secs remaining."
                message = frame_num + secs_elapse + perc + remaining
                sys.stdout.write(message)
                sys.stdout.flush()
            surface = self.render(frame)
            pygame.image.save(surface, tmp_file)
            image = cv2.imread(tmp_file)
            video.write(image)
            if verbose:
                sys.stdout.write("\b" * len(message))
                sys.stdout.write(" " * len(message))
                sys.stdout.write("\b" * len(message))

        if verbose:
            sys.stdout.write(f"Finished in {round(time.time()-time_start, 3)} seconds.\n")
            sys.stdout.write("Releasing video...\n")
            sys.stdout.flush()

        video.release()
        cv2.destroyAllWindows()
        if verbose:
            sys.stdout.write("Converting midis to wavs...\n")
            sys.stdout.flush()
        video = ffmpeg.input(os.path.join(export_dir, "video.mp4")).video
        for piano in range(len(self.midi_paths)):
            if verbose:
                sys.stdout.write(f"Piano {piano + 1}...\n")
                sys.stdout.flush()
            os.system(f"timidity {self.midi_paths[piano]} -Ow -o {os.path.join(export_dir, 'piano.wav')}")
            if frac_frames != 1:
                millisecs = frames/self.fps * 1000
                AudioSegment.from_wav(os.path.join(export_dir, "piano.wav"))[0:millisecs].export(os.path.join(export_dir, "piano.wav"), format="wav")
            if verbose:
                sys.stdout.write(f"Adding Piano {piano + 1}'s audio to video...\n")
                sys.stdout.flush()
            audio = ffmpeg.input(os.path.join(export_dir, "piano.wav")).audio
            video = ffmpeg.output(video, audio, path, vcodec='copy', acodec='aac', strict='experimental')
            if verbose:
                sys.stdout.write(f"Piano {piano + 1} Done\n")
                sys.stdout.flush()
        if os.path.isfile(path):
            os.remove(path)
        ffmpeg.run(video)

        if verbose:
            sys.stdout.write("Cleaning up...\n")
            sys.stdout.flush()
        shutil.rmtree(export_dir)
        if verbose:
            sys.stdout.write(f"Finished exporting video in {round(time.time()-time_start, 3)} seconds.\n")
            sys.stdout.write("--------------------------------------\n")
            sys.stdout.flush()

    def render(self, frame):
        surf = pygame.Surface(self.resolution, pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        width, height = self.resolution
        max_height = height/5
        min_height = height/12
        whitekey_height = min(max_height, max(min_height, (height-100)/(len(self.status)+2)))
        blackkey_height = whitekey_height/2.4
        blackkey_width_factor = 3/4
        offset = height - height/(len(self.status)+1)
        for i, range_keys in enumerate(self.ranges):
            y = offset*(i+1) - whitekey_height/2
            status = self.get_play_status(frame, i)
            counter = 0
            range_range = range_keys[1] - range_keys[0]
            gap = 1 if range_range > 50 else 3
            key_width = min(width/5, width/((range_range)*7/12))
            keys_width = (range_range) * (key_width + gap)*7/12
            black_keys = []
            for j in range(range_keys[0], range_keys[1]+1):
                if self.is_black(j):
                    black_keys.append((surf, RED if status[j - range_keys[0]] else BLACK, (width/2 - keys_width/2 + (counter+1)*(key_width + gap) - gap/2 - key_width*blackkey_width_factor/2, y, key_width*blackkey_width_factor, blackkey_height)))
                else:
                    pygame.draw.rect(surf, RED if status[j - range_keys[0]] else WHITE, (width/2 - keys_width/2 + counter*(key_width + gap), y, key_width, whitekey_height))
                    counter += 1
            for key in black_keys:
                pygame.draw.rect(*key)

        return surf

    def parse_midi(self, midi):
        tempo = 500000
        final = []
        frame = 0
        for track in midi.tracks:
            for msg in track:
                frame += msg.time / midi.ticks_per_beat * tempo / 1000000 * self.fps
                if msg.is_meta:
                    if msg.type == "set_tempo":
                        tempo = msg.tempo
                else:
                    if msg.type == "note_on":
                        curr_note = {}
                        curr_note["note"] = msg.note
                        curr_note["volume"] = msg.velocity
                        curr_note["time"] = round(frame)
                        final.append(curr_note)

        return final

    def is_black(self, key):
        normalized = (key - 3) % 12
        if normalized in (2, 4, 7, 9, 11):
            return True
        return False

    def get_play_status(self, frame, i):
        midi = self.midis[i]
        min_range, _ = self.ranges[i]
        for j in range(len(self.status[i])):
            for note in midi:
                if note["time"] == frame and note["note"] == j + min_range:
                    if note["volume"] > 0:
                        self.status[i][j] = True
                    else:
                        self.status[i][j] = False
                    break

        return self.status[i]


piano = Piano((1920, 1080), 30)
piano.add_piano("/home/arjun/asdf.mid")
piano.export(os.path.join(os.path.realpath(os.path.dirname(__file__)), "asdf.mp4"), True, 1/5)
