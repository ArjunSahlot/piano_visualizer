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
from random_utils.colors.conversions import rgb_to_hsv, hsv_to_rgb
from pydub import AudioSegment


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

    def export(self, path, verbose=False, num_cores=4, notify=True, quick=True, **kwargs):
        if "frac_frames" in kwargs:
            frac_frames = kwargs["frac_frames"]
        else:
            frac_frames = 1
        
        def quick_export(core, start, end):
            tmp_path = os.path.join(export_dir, "frame{}" + ".jpg" if quick else ".png")
            for frame in range(start, end+1):
                surf = self.render(frame-self.start_offset)
                pygame.image.save(surf, tmp_path.format(frame))

        pardir = os.path.realpath(os.path.dirname(__file__))

        if verbose:
            print("Parsing midis...")
        for i, piano in enumerate(self.pianos):
            piano.register(self.fps, self.start_offset)
            if verbose:
                print(f"Piano {i+1} done")
        if verbose:
            print("All pianos done.")

        min_frame, max_frame = min(self.pianos, key=lambda x: x.get_min_time()).get_min_time(), max(self.pianos, key=lambda x: x.get_max_time()).get_max_time()

        max_frame = int(frac_frames *  (max_frame - min_frame) + min_frame)
        frames = int(max_frame - min_frame)

        if verbose:
            print("-"*50)
            print("Exporting video:")
            print(f"  Resolution: {' by '.join(map(str, self.resolution))}")
            print(f"  FPS: {self.fps}")
            print(f"  Frames: {frames}\n")

            time_start = time.time()


        export_dir = os.path.join(pardir, "export")
        os.makedirs(export_dir, exist_ok=True)
        tmp_file = os.path.join(export_dir, "frame." + "jpg" if quick else "png")
        try:
            if num_cores > 1:
                if num_cores >= multiprocessing.cpu_count():
                    print("High chance of computer freezing")
                    core_input = input(f"Are you sure you want to use {num_cores}: ")
                    try:
                        core_input = int(core_input)
                        num_cores = core_input
                    except ValueError:
                        if "y" in core_input.lower():
                            print("Piano Visualizer is not at fault if your computer freezes...")
                        else:
                            num_cores = int(input("New core count: "))
                num_cores = min(num_cores, multiprocessing.cpu_count())
                processes = []
                curr_frame = 0
                frame_inc = (frames + self.start_offset + self.end_offset) / num_cores

                for i in range(num_cores):
                    p = multiprocessing.Process(target=quick_export, args=(i, int(curr_frame), int(curr_frame + frame_inc)))
                    p.start()
                    processes.append(p)

                    curr_frame += frame_inc + 1

                if verbose:
                    print(f"Exporting {int(frame_inc)} on each of {num_cores} cores...")

                for i, process in enumerate(processes):
                    process.join()
                    if verbose:
                        print(f"Core {i+1} is done.")

                if verbose:
                    print("Finsihed exporting frames.")

                video = cv2.VideoWriter(os.path.join(export_dir, "video.mp4"), cv2.VideoWriter_fourcc(*"MPEG"), self.fps, self.resolution)

                if verbose:
                    time_frame_start = time.time()
                for frame in range(min_frame, max_frame + self.start_offset + self.end_offset + 1):
                    if verbose:
                        time_elapse = round(time.time()-time_frame_start, 3)
                        frame_num = f"{frame+1 - min_frame} of {frames+self.start_offset+self.end_offset}, "
                        mins_elapse = time_elapse // 60
                        secs_elapse = round(time_elapse % 60, 3)
                        elapse = f"{mins_elapse} mins and {secs_elapse} secs elapsed. "
                        if frames > 1:
                            perc = f"{int(100 * ((frame - min_frame)/(frames-1)))}% finished. "
                        else:
                            perc = f"100% finished. "
                        rem_secs = round((frames-(frame - min_frame)) * (time_elapse/((frame - min_frame)+1)))
                        mins = rem_secs // 60
                        secs = rem_secs % 60
                        remaining = f"{mins} mins and {secs} secs remaining."
                        message = frame_num + elapse + perc + remaining
                        sys.stdout.write(message)
                        sys.stdout.flush()

                    video.write(cv2.imread(os.path.join(export_dir, f"frame{frame}." + "jpg" if quick else "png")))

                    if verbose:
                        sys.stdout.write("\r")
                        sys.stdout.write(" " * len(message))
                        sys.stdout.write("\r")

            else:
                video = cv2.VideoWriter(os.path.join(export_dir, "video.mp4"), cv2.VideoWriter_fourcc(*"MPEG"), self.fps, self.resolution)

                for frame in range(min_frame, max_frame + self.start_offset + self.end_offset + 1):
                    if verbose:
                        time_elapse = round(time.time()-time_start, 3)
                        frame_num = f"{frame+1 - min_frame} of {frames}, "
                        mins_elapse = time_elapse // 60
                        secs_elapse = round(time_elapse % 60, 3)
                        elapse = f"{mins_elapse} mins and {secs_elapse} secs elapsed. "
                        if frames > 1:
                            perc = f"{int(100 * ((frame - min_frame)/(frames-1)))}% finished. "
                        else:
                            perc = f"100% finished. "
                        rem_secs = round((frames-(frame - min_frame)) * (time_elapse/((frame - min_frame)+1)))
                        mins = rem_secs // 60
                        secs = rem_secs % 60
                        remaining = f"{mins} mins and {secs} secs remaining."
                        message = frame_num + elapse + perc + remaining
                        sys.stdout.write(message)
                        sys.stdout.flush()
                    surface = self.render(frame)
                    pygame.image.save(surface, tmp_file)
                    image = cv2.imread(tmp_file)
                    video.write(image)
                    if verbose:
                        sys.stdout.write("\r")
                        sys.stdout.write(" " * len(message))
                        sys.stdout.write("\r")

            if verbose:
                print(f"Finished in {round(time.time()-time_start, 3)} seconds.")
                print("Releasing video...")

            video.release()
            cv2.destroyAllWindows()
            millisecs = (frames + 1)/self.fps * 1000
            sounds = []
            if verbose:
                print("Creating music...")
            for audio_path in self.audio:
                if audio_path == "default":
                    for i, piano in enumerate(self.pianos):
                        sounds.extend(piano.gen_wavs(export_dir, frames))
                else:
                    sounds.append(AudioSegment.from_file(audio_path, format=audio_path.split(".")[-1])[0:millisecs])
            if verbose:
                print("Created music.")

            if verbose:
                print("Combining all audios into 1...")

            music_file = os.path.join(export_dir, "piano.wav")
            sound = sounds.pop(sounds.index(max(sounds, key=lambda x: len(x))))
            for i in sounds:
                sound = sound.overlay(i)
            sound.export(music_file, format="wav")

            if verbose:
                print("Done")

            if self.start_offset or self.end_offset:
                if verbose:
                    print("Offsetting music...")
                    s_silent = AudioSegment.silent(self.start_offset/self.fps * 1000)
                    e_silent = AudioSegment.silent(self.end_offset/self.fps * 1000)
                    (s_silent + AudioSegment.from_wav(music_file) + e_silent).export(music_file, format="wav")
                    print("Music offsetted successfully")

            print("Compiling video")
            video = ffmpeg.input(os.path.join(export_dir, "video.mp4")).video
            audio = ffmpeg.input(music_file).audio
            video = ffmpeg.output(video, audio, path, vcodec="copy", acodec="aac", strict="experimental")
            if os.path.isfile(path):
                os.remove(path)
            ffmpeg.run(video)
            if verbose:
                print(f"Video Done")

            if verbose:
                print("Cleaning up...")

        except Exception as e:
            print(f"Export interrputed due to {e}")
            shutil.rmtree(export_dir)
            if sys.platform == "linux" and notify:
                os.system(f"notify-send 'Piano Visualizer' 'Export interrupted due to {e}'")
            ctypes.pointer(ctypes.c_char.from_address(5))[0]

        shutil.rmtree(export_dir)
        if verbose:
            total_time = time.time()-time_start
            print(f"Finished exporting video in {total_time // 60} mins and {round(total_time % 60, 3)} secs.")
            print("-"*50)
        
        if sys.platform == "linux" and notify:
            os.system(f"notify-send 'Piano Visualizer' 'Finished exporting {path.split('/')[-1]}'")
    
    def render(self, frame):
        surf = pygame.Surface(self.resolution, pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        width, height = self.resolution
        max_height = height/5
        min_height = height/12
        whitekey_height = min(max_height, max(min_height, (height-100)/(len(self.pianos)+2)))
        blackkey_height = whitekey_height/2.4
        blackkey_width_factor = 3/4
        offset = height/len(self.pianos)
        p_height = offset
        p_width = width
        whitekey_width = width/(88*7/12) - 1

        for i, piano in enumerate(self.pianos):
            p_y = offset * i
            piano.render(surf, frame, p_y, p_width, p_height, whitekey_height, blackkey_height, whitekey_width, whitekey_width * blackkey_width_factor, 1)

        return surf


class Piano:
    def __init__(self, midis=[], blocks=True, color="default"):
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
            pygame.draw.rect(s, list(color) + [255*((height-cy)/height)], (0, cy, width, 1))
        surf.blit(s, (x, y))

    def render(self, surf, frame, y, width, height, wheight, bheight, wwidth, bwidth, gap):
        counter = 0
        playing_keys = self.get_play_status(frame)
        black_keys = []
        self.render_blocks(surf, frame, y, width, height - wheight, wwidth, bwidth, gap)
        pheight = y + height - wheight
        surf.fill((0, 0, 0), (0, pheight, width, wheight))

        for key in range(88):
            if self.is_black(key):
                x = (counter+1)*(wwidth + gap) - gap/2 - bwidth/2
                if key in playing_keys:
                    color = self.get_rainbow(x, width) if self.color == "rainbow" else self.black_hit_col
                else:
                    color = self.black_col
                black_keys.append(((surf, color, (x, pheight, bwidth, bheight)), (surf, x, pheight, bwidth, bheight, color)))
            else:
                counter += 1
                x = counter*(wwidth + gap)
                if key in playing_keys:
                    color = self.get_rainbow(x, width) if self.color == "rainbow" else self.white_hit_col
                else:
                    color = self.white_col
                pygame.draw.rect(surf, self.white_col, (x, pheight, wwidth, wheight))
                self.render_rect(surf, x, pheight, wwidth, wheight, color)

        for key in black_keys:
            pygame.draw.rect(*key[0])
            self.render_rect(*key[1])
    
    def render_blocks(self, surf, frame, y, width, height, wwidth, bwidth, gap):
        for note in self.notes:
            bottom = (frame - note["start"]) * self.block_speed / self.fps + y + height
            top = bottom - (note["end"] - note["start"]) * self.block_speed / self.fps
            if top <= y + height and bottom >= y:
                x = self.get_key_x(note["note"], wwidth, gap, bwidth)
                pygame.draw.rect(surf, self.get_rainbow(x, width) if self.color == "rainbow" else self.block_col, (x, top, bwidth if self.is_black(note["note"]) else wwidth, bottom-top), border_radius=self.block_rounding)

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
        return hsv_to_rgb(((x/width)*255, 225, 255))

    def add_midi(self, path):
        self.midis.append(path)

    def parse_midis(self):
        self.notes = []
        for mid in self.midis:
            midi = mido.MidiFile(mid)
            for track in midi.tracks:
                tempo = 500000
                frame = self.offset
                start_keys = [None] * 88
                for msg in track:
                    frame += msg.time / midi.ticks_per_beat * tempo / 1000000 * self.fps
                    if msg.is_meta:
                        if msg.type == "set_tempo":
                            tempo = msg.tempo
                    else:
                        if msg.type == "note_on":
                            if not msg.velocity:
                                self.notes.append({"note": msg.note - 21, "start": start_keys[msg.note - 21], "end": int(frame)})
                            else:
                                start_keys[msg.note - 21] = int(frame)

    def is_black(self, key):
        normalized = (key - 3) % 12
        return normalized in (1, 3, 6, 8, 10)

    def get_play_status(self, frame):
        playing_keys = []
        for note in self.notes:
            if note["start"] <= frame <= note["end"]:
                playing_keys.append(note["note"])

        return playing_keys
    
    def get_min_time(self):
        return min(self.notes, key=lambda x: x["start"])["start"]
    
    def get_max_time(self):
        return max(self.notes, key=lambda x: x["end"])["end"]

    def gen_wavs(self, export_dir, frames):
        wavs = []
        for midi in self.midis:
            wav_path = os.path.join(export_dir, "pianowav.wav")
            os.system(f"timidity {midi} -Ow -o {wav_path}")
            try:
                wavs.append(AudioSegment.from_wav(wav_path))
            except FileNotFoundError:
                sys.stderr.write("You might not have timidity installed on your machine.\n")
                sys.stderr.write("Please have that installed if you are using the midi files as audio.\n")
                sys.stderr.flush()
                return [AudioSegment.silent(frames)]
        return wavs

    def register(self, fps, offset):
        self.fps = fps
        self.offset = offset
        self.parse_midis()


p = Piano(["/home/arjun/happy_birthday.mid"], True, "rainbow")
v = Video(start_offset=10, end_offset=10)
v.add_piano(p)
v.export("/home/arjun/shuhul_birthday.mp4", True, frac_frames=1/4)
