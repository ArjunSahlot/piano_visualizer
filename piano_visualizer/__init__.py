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
import mido
import multiprocessing
import ffmpeg
from notifypy import Notify
from midi2audio import FluidSynth
from random_utils.colors.conversions import hsv_to_rgb
from random_utils.funcs import crash
from pydub import AudioSegment
from tqdm import tqdm

class Video:
    def get_piano_dimensions(self):
        """
        Compute and return piano dimensions for rendering and block fall calculations.
        Returns a dict with keys: whitekey_height, blackkey_height, block_fall_height, etc.
        """
        height = self.requested_resolution[1]
        width = self.requested_resolution[0]
        min_height = height / 12
        p_height = height / len(self.pianos)
        num_white_keys = 52
        gap = 2
        # calculates keys dimensions based on actual piano proportions and video resolution
        total_seps = (num_white_keys - 1) * gap
        ideal_keys_width = width - total_seps
        whitekey_width = int(ideal_keys_width // num_white_keys)
        actual_whitekey_height = whitekey_width * 6
        whitekey_height = min(actual_whitekey_height, max(min_height, height / (len(self.pianos) + 2)))
        blackkey_width = whitekey_width * 0.65
        blackkey_height = whitekey_height * 0.65
        block_fall_height = p_height - whitekey_height
        blackkey_x_offsets = [0, 0.65, 0, 0.35, 0, 0, 0.75, 0, 0.5, 0, 0.3, 0]
        used_width = whitekey_width * num_white_keys + total_seps
        margin = (width - used_width) // 2
        return {
            'whitekey_height': whitekey_height,
            'blackkey_height': blackkey_height,
            'block_fall_height': block_fall_height,
            'whitekey_width': whitekey_width,
            'blackkey_width': blackkey_width,
            'gap': gap,
            'blackkey_x_offsets': blackkey_x_offsets,
            'margin': margin,
            'p_height': p_height,
            'p_width': width,
        }

    def __init__(self, resolution=(1920, 1080), fps=30, start_offset=0, end_offset=0, keyboard_crop=False):
        self.requested_resolution = resolution
        self.fps = fps
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.audio = ["default"]
        self.pianos = []
        self.keyboard_crop = keyboard_crop
        self.resolution = resolution

    def add_piano(self, piano):
        self.pianos.append(piano)
        # Adjust resolution if keyboard_crop is enabled
        if self.keyboard_crop:
            dims = self.get_piano_dimensions()
            cropped_height = int(dims['whitekey_height'] * len(self.pianos))
            self.resolution = (self.requested_resolution[0], cropped_height)

    def set_audio(self, audio, overwrite=True):
        if overwrite:
            self.audio = [audio]
        else:
            self.audio.append(audio)

    def export(self, path, num_cores=4, music=False, notify=True, **kwargs):
        """
        Export the video to the given path.

        :param path: destination to where the video will be
        :param num_cores: number of cores to use for exporting, defaults to 4
        :param music: whether or not you want music (it is usually not aligned with video unfortunately), defaults to False
        :param notify: notify the user through a system notification when exporting is done, defaults to True
        """
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
                # Convert from RGB to BGR for OpenCV
                surf_bgr = cv2.cvtColor(surf, cv2.COLOR_RGB2BGR)
                video.write(surf_bgr)
            video.release()
            cv2.destroyAllWindows()

        pardir = os.path.realpath(os.path.dirname(__file__))

        print("Parsing midis...")
        for i, piano in enumerate(self.pianos):
            piano.register(self.fps, self.start_offset)
            print(f"Piano {i+1} done")
        print("All pianos done.")

        # Calculate MIDI time boundaries and export range
        min_frame = min(self.pianos, key=lambda x: x.get_min_time()).get_min_time()
        max_note_frame = max(self.pianos, key=lambda x: x.get_max_time()).get_max_time()
        # True end of MIDI (including trailing silence)
        midi_end_frame = max(
            max((note['end'] for note in piano.notes), default=0) for piano in self.pianos
        )

        # Block fall duration (frames for last notes to reach the keyboard)
        if self.pianos:
            piano = self.pianos[0]
            dims = self.get_piano_dimensions()
            block_fall_height = dims['block_fall_height']
            block_speed = getattr(piano, 'block_speed', 200)
            block_fall_duration = int(block_fall_height / (block_speed / self.fps))
        else:
            block_fall_duration = 0

        # Silence before first note (in frames)
        silence_start = min_frame
        # Silence after last note (in frames)
        silence_end = max(0, midi_end_frame - max_note_frame)

        # Export range: from frame 0 to the end of the last block fall and trailing silence
        export_start = 0
        export_end = int(silence_start + (frac_frames * (max_note_frame - min_frame)) + block_fall_duration + silence_end + self.start_offset + self.end_offset)
        frames = export_end - export_start + 1
        print(f"  Resolution: {' by '.join(map(str, self.resolution))}")
        print(f"  FPS: {self.fps}")


        print(f"  Frames: {frames}")
        print(f"  Duration: {int(frames/self.fps)} secs\n")

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
                curr_frame = export_start
                frame_inc = (frames) / num_cores

                print(
                    f"Exporting {int(frame_inc)} on each of {num_cores} cores...")

                for i in range(num_cores):
                    start_f = int(curr_frame)
                    end_f = int(min(export_end, curr_frame + frame_inc - 1))
                    p = multiprocessing.Process(target=quick_export, args=(
                        i, start_f, end_f))
                    p.start()
                    processes.append(p)

                    curr_frame += frame_inc

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
                with tqdm(total=frames+num_cores, unit="frames", desc="Concatenating") as t:
                    for v in videos:
                        curr_v = cv2.VideoCapture(v)
                        while curr_v.isOpened():
                            r, frame = curr_v.read()
                            if not r:
                                break
                            video.write(frame)
                            t.update()

            else:
                # Export all frames including the block fall duration
                for frame in tqdm(range(export_start, export_end + 1), desc="Exporting", unit="frames"):
                    # Shift all rendering by the silence at the start
                    surf = pygame.surfarray.pixels3d(self.render(
                        frame - silence_start - self.start_offset)).swapaxes(0, 1)
                    # Convert from RGB to BGR for OpenCV
                    surf_bgr = cv2.cvtColor(surf, cv2.COLOR_RGB2BGR)
                    video.write(surf_bgr)

            video.release()
            cv2.destroyAllWindows()

            print(f"Finished in {round(time.time()-time_start, 3)} seconds.")
            print("Releasing video...")

            if music:
                millisecs = (frames + 1)/self.fps * 1000
                sounds = []
                print("Creating music...")
                for audio_path in self.audio:
                    if audio_path == "default":
                        for i, piano in enumerate(self.pianos):
                            sounds.extend(piano.gen_flac(export_dir, millisecs))
                    else:
                        sounds.append(AudioSegment.from_file(
                            audio_path, format=audio_path.split(".")[-1])[0:millisecs])
                print("Created music.")

                print("Combining all audios into 1...")
                music_file = os.path.join(export_dir, "piano.flac")
                sound = sounds.pop(sounds.index(max(sounds, key=lambda x: len(x))))
                for i in sounds:
                    sound = sound.overlay(i)

                sound.export(music_file, format="flac")
                # Compress audio to length of video
                # new_sound = sound._spawn(sound.raw_data, overrides={"frame_rate": int(sound.frame_rate*(len(sound)/millisecs))})
                # new_sound.set_frame_rate(sound.frame_rate)

                # new_sound.export(music_file, format="flac")
                print("Done")

                if self.start_offset or self.end_offset:
                    print("Offsetting music...")
                    s_silent = AudioSegment.silent(
                        self.start_offset/self.fps * 1000)
                    e_silent = AudioSegment.silent(self.end_offset/self.fps * 1000)
                    (s_silent + AudioSegment.from_file(music_file, "flac") + e_silent).export(music_file, format="flac")
                    print("Music offsetted successfully")

                print("Compiling video")
                video = ffmpeg.input(os.path.join(export_dir, "video.mp4")).video
                audio = ffmpeg.input(music_file).audio
                video = ffmpeg.output(
                    video, audio, path, vcodec="copy", acodec="aac", strict="experimental")
                if os.path.isfile(path):
                    os.remove(path)
                ffmpeg.run(video)

            else:
                print("Skipping music...")
                src = os.path.join(export_dir, "video.mp4")
                try:
                    os.rename(src, path)
                except OSError as e:
                    if getattr(e, 'errno', None) == 18:  # Invalid cross-device link
                        print("Cross-device link error detected, using shutil.copy2 as fallback.")
                        shutil.copy2(src, path)
                        os.remove(src)
                    else:
                        raise

            print(f"Video Done")
            print("Cleaning up...")

        except (Exception, KeyboardInterrupt) as e:
            print(f"Export interrupted due to {e}")
            shutil.rmtree(export_dir)
            if notify:
                notification = Notify()
                notification.title = "Piano Visualizer"
                notification.message = f"Export interrupted due to {e}"
                notification.send()
            crash()

        shutil.rmtree(export_dir)
        total_time = time.time()-time_start
        print(
            f"Finished exporting video in {total_time//60} mins and {round(total_time%60, 3)} secs.")
        print("-"*50)

        if notify:
            notification = Notify()
            notification.title = "Piano Visualizer"
            notification.message = f"Finished exporting {path.split('/')[-1]}"
            notification.send()

    def render(self, frame):
        surf = pygame.Surface(self.resolution, pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        dims = self.get_piano_dimensions()
        for i, piano in enumerate(self.pianos):
            if getattr(self, 'keyboard_crop', False):
                p_y = 0
                p_height = dims['whitekey_height']
            else:
                p_y = dims['p_height'] * i
                p_height = dims['p_height']
            piano.render(
                surf, frame, p_y, dims['p_width'], p_height,
                dims['whitekey_height'], dims['blackkey_height'],
                dims['whitekey_width'], dims['blackkey_width'],
                dims['gap'], dims['blackkey_x_offsets'], dims['margin']
            )
        return surf

class Piano:
    def __init__(self, midis=[], blocks=True, color="rainbow", no_gradient=False, realistic_render=False):
        self.midis = list(midis)
        self.blocks = bool(blocks)
        self.block_speed = 200
        self.block_rounding = 5
        self.white_key_rounding = 3
        self.color = color
        self.no_gradient = no_gradient
        self.realistic_render = realistic_render
        self.notes = []
        self.fps = None
        self.offset = None
        self.block_col = (255, 255, 255) if color == "rainbow" else color
        self.white_hit_col = (255, 0, 0) if color == "rainbow" else color
        self.white_col = (255, 255, 255)
        self.black_hit_col = (255, 0, 0) if color == "rainbow" else color
        self.black_col = (20, 20, 20)

    def configure(self, datapath, value):
        if datapath in self.__dict__.keys():
            setattr(self, datapath, value)

    def render_key(self, surf, x, y, width, height, color, is_black, gap):
        bottom_rounding = 0 if is_black or not self.realistic_render else self.white_key_rounding
        if is_black:
            #  draw black key borders
            pygame.draw.rect(surf, self.black_col, (x, y, width, height))
            # define black key size (without borders)
            x += 1 + gap // 2
            width = max(0, width - 2 - gap)
            height = max(0, height - gap)
        else:
            # draw white key background
            pygame.draw.rect(surf, self.white_col, (x, y, width, height), \
                border_top_left_radius=0, border_top_right_radius=0, \
                border_bottom_left_radius=bottom_rounding, border_bottom_right_radius=bottom_rounding)

        s = pygame.Surface((width, height), pygame.SRCALPHA)

        if self.no_gradient:
            pygame.draw.rect(surf, color, (x, y, width, height), \
                border_top_left_radius=0, border_top_right_radius=0, \
                border_bottom_left_radius=bottom_rounding, border_bottom_right_radius=bottom_rounding)
        else:
            for cy in range(int(height+1)):
                pygame.draw.rect(s, list(color) + [255*((height-cy)/height)], (0, cy, width, 1))

        surf.blit(s, (x, y))

    def render(self, surf, frame, y, width, height, wheight, bheight, wwidth, bwidth, gap, blackkey_x_offsets, margin=0):
        # num_white_keys = 52
        key_xs = [0]*88
        white_xs = []
        white_indices = [None]*88
        white_index = 0
        for key in range(88):
            if not self.is_black(key):
                key_xs[key] = margin + white_index*(wwidth + gap)
                white_xs.append(key_xs[key])
                white_indices[key] = white_index
                white_index += 1
            else:
                # black key position according to surrounding white keys
                left_index = key - 1
                if left_index >= 0 and white_indices[left_index] is not None:
                    key_xs[key] = key_xs[left_index] + wwidth - (bwidth * blackkey_x_offsets[self.get_black_key_scale_index(key)]) + gap
                else:
                    key_xs[key] = 0

        # render falling notes
        if self.blocks:
            self.render_blocks(surf, frame, y, width, height - wheight , wwidth, bwidth, gap, key_xs)

        py = y + height - wheight
        # fill black background under piano (for margins around centered keyboard)
        surf.fill((0, 0, 0), (0, py, width, wheight))

        playing_keys = self.get_play_status(frame)

        # draw all white keys
        for key in range(88):
            x = key_xs[key]
            # i = 0
            if not self.is_black(key):
                # white keys
                color = self.get_rainbow(x, width) if (key in playing_keys and self.color == "rainbow") else (self.white_hit_col if key in playing_keys else self.white_col)
                self.render_key(surf, x, py, wwidth, wheight, color, False, gap)

        # draw all black keys
        for key in range(88):
            x = key_xs[key]
            if self.is_black(key):
                # black keys
                if key in playing_keys:
                    color = self.get_rainbow(x, width) if self.color == "rainbow" else self.black_hit_col
                    self.render_key(surf, x, py, bwidth, bheight, color, True, gap)
                else:
                    color = self.black_col
                    self.render_key(surf, x, py, bwidth, bheight, color, True, gap)
                    if self.realistic_render:
                        bevel_color = (70, 70, 70)
                        bevel_s_color = (60, 60, 60)
                        bevel_b = 4
                        bevel_r = 6
                        bevel_w = max(0, bwidth - bevel_b)
                        bevel_w_s = 2
                        bevel_h = bheight * 0.1
                        bevel_h_s = bheight - 2
                        bevel_x = x + bevel_b / 2
                        bevel_x_sl = x + bwidth - bevel_b
                        bevel_x_sr = x + bevel_b / 2
                        bevel_y = py + bheight - bevel_h - 3
                        bevel_y_s = py
                        pygame.draw.rect(surf, bevel_color, (bevel_x, bevel_y, bevel_w, bevel_h), \
                            border_top_left_radius=bevel_r, border_top_right_radius=bevel_r, \
                            border_bottom_left_radius=0, border_bottom_right_radius=0)
                        pygame.draw.rect(surf, bevel_s_color, (bevel_x_sl, bevel_y_s, bevel_w_s, bevel_h_s))
                        pygame.draw.rect(surf, bevel_s_color, (bevel_x_sr, bevel_y_s, bevel_w_s, bevel_h_s))

    # falling notes
    def render_blocks(self, surf, frame, y, width, height, wwidth, bwidth, gap, key_xs):
        for note in self.notes:
            bottom = (frame - note["start"]) * \
                self.block_speed / self.fps + y + height
            top = bottom - (note["end"] - note["start"]) * \
                self.block_speed / self.fps
            if top <= y + height and bottom >= y:
                key = note["note"]
                x = key_xs[key]
                w = wwidth
                color = self.get_rainbow(x, width) if self.color == "rainbow" else self.block_col
                if self.is_black(key):
                    x = x + 1 + gap // 2
                    w = max(0, bwidth - 2 - gap)
                pygame.draw.rect(surf, color, (
                        x, top, w, bottom-top), border_radius=self.block_rounding)

    def get_rainbow(self, x, width):
        rgb = hsv_to_rgb(((x/width)*255, 255, 255))
        # invert values to preserve the same final rainbow as before fixing BGR format for OpenCV
        return (rgb[2], rgb[1], rgb[0])

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
                    frame += (msg.time * tempo / midi.ticks_per_beat / 1_000_000) * self.fps
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

    def get_black_key_scale_index(self, key):
        # offset 3 notes to align MIDI A0 with a C
        return (key - 3) % 12

    def is_black(self, key):
        key_scale_index = self.get_black_key_scale_index(key)
        return key_scale_index in (1, 3, 6, 8, 10)

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

    def gen_flac(self, export_dir, silent_len):
        flacs = []
        flacs_path = os.path.join(export_dir, "pianoflac.flac")
        for midi in self.midis:
            fs = FluidSynth()
            fs.midi_to_audio(midi, flacs_path)
            flacs.append(AudioSegment.from_file(flacs_path, format="flac"))
        return flacs

    def register(self, fps, offset):
        self.fps = fps
        self.offset = offset
        self.parse_midis()
