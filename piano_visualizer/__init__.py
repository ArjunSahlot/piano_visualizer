#
#  Piano visualizer
#  A tool that allows you to export a video in which a piano is playing the music you give it.
#  Copyright Arjun Sahlot 2021
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import os
import cv2
import pygame
import shutil
import time
import sys
import mido
import multiprocessing
import ctypes
import ffmpeg
import threading
from random_utils.colors.conversions import hsv_to_rgb
from random_utils.funcs import crash
from pydub import AudioSegment
from tqdm import tqdm


class Video:
    def __init__(self, resolution=(1920, 1080), fps=30, start_offset=0, end_offset=0):
        self.resolution = resolution
        self.fps = fps
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.audio = ["default"]
        self.pianos = []

    def add_piano(self, piano):
        self.pianos.append(piano)

    def set_audio(self, audio, overwrite=True):
        if overwrite:
            self.audio = [audio]
        else:
            self.audio.append(audio)

    def export(self, path, num_cores=4, notify=True, **kwargs):
        if "frac_frames" in kwargs:
            frac_frames = kwargs["frac_frames"]
        else:
            frac_frames = 1

        def quick_export(core, start, end):
            video = cv2.VideoWriter(os.path.join(export_dir, f"video{core}.mp4"), cv2.VideoWriter_fourcc(
                *"MPEG"), self.fps, self.resolution)
            for frame in range(start, end+1):
                with open(os.path.join(export_dir, f"frame{frame}"), "w"):
                    pass
                surf = pygame.surfarray.pixels3d(self.render(
                    frame-self.start_offset)).swapaxes(0, 1)
                video.write(surf)
            video.release()
            cv2.destroyAllWindows()

        pardir = os.path.realpath(os.path.dirname(__file__))

        print("Parsing midis...")
        for i, piano in enumerate(self.pianos):
            piano.register(self.fps, self.start_offset)
            print(f"Piano {i+1} done")
        print("All pianos done.")

        min_frame, max_frame = min(self.pianos, key=lambda x: x.get_min_time()).get_min_time(
        ), max(self.pianos, key=lambda x: x.get_max_time()).get_max_time()

        max_frame = int(frac_frames * (max_frame - min_frame) + min_frame)
        frames = int(max_frame - min_frame)

        print("-"*50)
        print("Exporting video:")
        print(f"  Resolution: {' by '.join(map(str, self.resolution))}")
        print(f"  FPS: {self.fps}")
        print(f"  Frames: {frames}")
        print(
            f"  Duration: {int((frames+self.start_offset+self.end_offset)/self.fps)} secs\n")

        time_start = time.time()

        export_dir = os.path.join(pardir, "export")
        os.makedirs(export_dir, exist_ok=True)
        try:
            video = cv2.VideoWriter(os.path.join(export_dir, "video.mp4"), cv2.VideoWriter_fourcc(
                *"MPEG"), self.fps, self.resolution)
            if num_cores > 1:
                if num_cores >= multiprocessing.cpu_count():
                    print("High chance of computer freezing")
                    core_input = input(
                        f"Are you sure you want to use {num_cores}: ")
                    try:
                        num_cores = int(core_input)
                    except ValueError:
                        if "y" in core_input.lower():
                            print(
                                "Piano Visualizer is not at fault if your computer freezes...")
                        else:
                            num_cores = int(input("New core count: "))
                num_cores = min(num_cores, multiprocessing.cpu_count())
                processes = []
                curr_frame = 0
                frame_inc = (frames + self.start_offset +
                             self.end_offset) / num_cores

                print(
                    f"Exporting {int(frame_inc)} on each of {num_cores} cores...")

                for i in range(num_cores):
                    p = multiprocessing.Process(target=quick_export, args=(
                        i, int(curr_frame), int(curr_frame + frame_inc)))
                    p.start()
                    processes.append(p)

                    curr_frame += frame_inc + 1

                time.sleep(.1)  # Wait for all processes to start.

                with tqdm(total=frames, unit="frames", desc="Exporting") as t:
                    p = 0
                    while True:
                        t.update((l := len(os.listdir(export_dir)))-p)
                        p = l
                        if l == frames:
                            break

                for i, process in enumerate(processes):
                    process.join()

                videos = [os.path.join(
                    export_dir, f"video{c}.mp4") for c in range(num_cores)]
                with tqdm(total=frames+self.start_offset+self.end_offset+num_cores, unit="frames", desc="Concatenating") as t:
                    for v in videos:
                        curr_v = cv2.VideoCapture(v)
                        while curr_v.isOpened():
                            r, frame = curr_v.read()
                            if not r:
                                break
                            video.write(frame)
                            t.update()

            else:
                for frame in tqdm(range(min_frame, max_frame + self.start_offset + self.end_offset + 1), desc="Exporting", unit="frames"):
                    surf = pygame.surfarray.pixels3d(self.render(
                        frame-self.start_offset)).swapaxes(0, 1)
                    video.write(surf)

            video.release()
            cv2.destroyAllWindows()

            print(f"Finished in {round(time.time()-time_start, 3)} seconds.")
            print("Releasing video...")

            millisecs = (frames + 1)/self.fps * 1000
            sounds = []
            print("Creating music...")
            for audio_path in self.audio:
                if audio_path == "default":
                    for i, piano in enumerate(self.pianos):
                        sounds.extend(piano.gen_wavs(export_dir, millisecs))
                else:
                    sounds.append(AudioSegment.from_file(
                        audio_path, format=audio_path.split(".")[-1])[0:millisecs])
            print("Created music.")

            print("Combining all audios into 1...")
            music_file = os.path.join(export_dir, "piano.wav")
            sound = sounds.pop(sounds.index(max(sounds, key=lambda x: len(x))))
            for i in sounds:
                sound = sound.overlay(i)

            # Compress audio to length of video
            new_sound = sound._spawn(sound.raw_data, overrides={
                                     "frame_rate": int(sound.frame_rate*(len(sound)/millisecs))})
            new_sound.set_frame_rate(sound.frame_rate)

            new_sound.export(music_file, format="wav")
            print("Done")

            if self.start_offset or self.end_offset:
                print("Offsetting music...")
                s_silent = AudioSegment.silent(
                    self.start_offset/self.fps * 1000)
                e_silent = AudioSegment.silent(self.end_offset/self.fps * 1000)
                (s_silent + AudioSegment.from_wav(music_file) +
                 e_silent).export(music_file, format="wav")
                print("Music offsetted successfully")

            print("Compiling video")
            video = ffmpeg.input(os.path.join(export_dir, "video.mp4")).video
            audio = ffmpeg.input(music_file).audio
            video = ffmpeg.output(
                video, audio, path, vcodec="copy", acodec="aac", strict="experimental")
            if os.path.isfile(path):
                os.remove(path)
            ffmpeg.run(video)
            print(f"Video Done")
            print("Cleaning up...")

        except (Exception, KeyboardInterrupt) as e:
            print(f"Export interruputed due to {e}")
            shutil.rmtree(export_dir)
            if sys.platform == "linux" and notify:
                os.system(
                    f"notify-send 'Piano Visualizer' 'Export interrupted due to {e}'")
            crash()

        shutil.rmtree(export_dir)
        total_time = time.time()-time_start
        print(
            f"Finished exporting video in {total_time//60} mins and {round(total_time%60, 3)} secs.")
        print("-"*50)

        if sys.platform == "linux" and notify:
            os.system(
                f"notify-send 'Piano Visualizer' 'Finished exporting {path.split('/')[-1]}'")

    def render(self, frame):
        surf = pygame.Surface(self.resolution, pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        width, height = self.resolution
        max_height = height/5
        min_height = height/12
        whitekey_height = min(max_height, max(
            min_height, (height-100)/(len(self.pianos)+2)))
        blackkey_height = whitekey_height/2
        blackkey_width_factor = 3/4
        offset = height/len(self.pianos)
        p_height = offset
        p_width = width
        whitekey_width = width/(88*7/12) - 1

        for i, piano in enumerate(self.pianos):
            p_y = offset * i
            piano.render(surf, frame, p_y, p_width, p_height, whitekey_height,
                         blackkey_height, whitekey_width, whitekey_width * blackkey_width_factor, 1)

        return surf


class Piano:
    def __init__(self, midis=[], blocks=True, color="rainbow"):
        self.midis = list(midis)
        self.blocks = bool(blocks)
        self.block_speed = 200
        self.block_rounding = 5
        self.color = color.lower()
        self.notes = []
        self.fps = None
        self.offset = None
        self.block_col = (255, 255, 255)
        self.white_hit_col = (255, 0, 0)
        self.white_col = (255, 255, 255)
        self.black_hit_col = (255, 0, 0)
        self.black_col = (0, 0, 0)

    def configure(self, datapath, value):
        if datapath in self.__dict__.keys():
            setattr(self, datapath, value)

    def render_rect(self, surf, x, y, width, height, color):
        s = pygame.Surface((width, height), pygame.SRCALPHA)
        for cy in range(int(height+1)):
            pygame.draw.rect(s, list(color) +
                             [255*((height-cy)/height)], (0, cy, width, 1))
        surf.blit(s, (x, y))

    def render(self, surf, frame, y, width, height, wheight, bheight, wwidth, bwidth, gap):
        counter = 0
        playing_keys = self.get_play_status(frame)
        black_keys = []
        if self.blocks:
            self.render_blocks(surf, frame, y, width, height -
                           wheight, wwidth, bwidth, gap)
        py = y + height - wheight
        surf.fill((0, 0, 0), (0, py, width, wheight))

        for key in range(88):
            if self.is_black(key):
                x = (counter+1)*(wwidth + gap) - gap/2 - bwidth/2
                if key in playing_keys:
                    color = self.get_rainbow(
                        x, width) if self.color == "rainbow" else self.black_hit_col
                else:
                    color = self.black_col
                black_keys.append(
                    ((surf, self.black_col, (x, py, bwidth, bheight)), (surf, x, py, bwidth, bheight, color)))
            else:
                counter += 1
                x = counter*(wwidth + gap)
                if key in playing_keys:
                    color = self.get_rainbow(
                        x, width) if self.color == "rainbow" else self.white_hit_col
                else:
                    color = self.white_col
                pygame.draw.rect(surf, self.white_col,
                                 (x, py, wwidth, wheight))
                self.render_rect(surf, x, py, wwidth, wheight, color)

        for key in black_keys:
            pygame.draw.rect(*key[0])
            self.render_rect(*key[1])

    def render_blocks(self, surf, frame, y, width, height, wwidth, bwidth, gap):
        for note in self.notes:
            bottom = (frame - note["start"]) * \
                self.block_speed / self.fps + y + height
            top = bottom - (note["end"] - note["start"]) * \
                self.block_speed / self.fps
            if top <= y + height and bottom >= y:
                x = self.get_key_x(note["note"], wwidth, gap, bwidth)
                pygame.draw.rect(surf, self.get_rainbow(x, width) if self.color == "rainbow" else self.block_col, (
                    x, top, bwidth if self.is_black(note["note"]) else wwidth, bottom-top), border_radius=self.block_rounding)

    def get_key_x(self, key, wwidth, gap, bwidth):
        counter = 1

        for k in range(key):
            if not self.is_black(k):
                counter += 1

        if self.is_black(key):
            return counter*(wwidth + gap) - gap/2 - bwidth/2
        else:
            return counter*(wwidth + gap)

    def get_rainbow(self, x, width):
        return hsv_to_rgb(((x/width)*255, 255, 255))

    def add_midi(self, path):
        self.midis.append(path)

    def parse_midis(self):
        self.notes = []
        for mid in self.midis:
            midi = mido.MidiFile(mid)
            for track in midi.tracks:
                tempo = 500000
                frame = 0
                start_keys = [None] * 88
                for msg in track:
                    frame += msg.time/midi.ticks_per_beat * tempo/1000000 * self.fps
                    if msg.is_meta:
                        if msg.type == "set_tempo":
                            tempo = msg.tempo
                    else:
                        if msg.type in ("note_on", "note_off"):
                            if not msg.velocity or msg.type == "note_off":
                                self.notes.append(
                                    {"note": msg.note - 21, "start": start_keys[msg.note - 21], "end": int(frame)})
                            else:
                                start_keys[msg.note - 21] = int(frame)

    def is_black(self, key):
        return (key - 3) % 12 in (1, 3, 6, 8, 10)

    def get_play_status(self, frame):
        keys = set()
        for note in self.notes:
            if note["start"] <= frame <= note["end"]:
                keys.add(note["note"])
        return keys

    def get_min_time(self):
        return min(self.notes, key=lambda x: x["start"])["start"]

    def get_max_time(self):
        return max(self.notes, key=lambda x: x["end"])["end"]

    def gen_wavs(self, export_dir, silent_len):
        wavs = []
        wav_path = os.path.join(export_dir, "pianowav.wav")
        for midi in self.midis:
            os.system(f"timidity {midi} -Ow -o {wav_path}")
            try:
                wavs.append(a := AudioSegment.from_wav(wav_path))
            except FileNotFoundError:
                print(
                    "You might not have timidity installed on your machine.", file=sys.stderr)
                print(
                    "Please have that installed if you are using the midi files as audio.", file=sys.stderr)
                return [AudioSegment.silent(silent_len)]
        return wavs

    def register(self, fps, offset):
        self.fps = fps
        self.offset = offset
        self.parse_midis()
