# piano_visualizer

A python library that allows you to export a video in which a piano is playing the music you give it.

![example gif](https://github.com/ArjunSahlot/piano_visualizer/blob/main/assets/example.gif?raw=true)

## Features

-   Export a video of a custom midi file
-   Easy interface
-   Multi-core export
-   Multiple piano support
-   Multiple midi support
-   Automatically generate audio for midi files

## How to

`piano_visualizer` was built with the intent to for it to be simple to use. You can render a piano video with simply 4 lines of code!

There are 2 main classes: `Piano` and `Video`
`Piano` takes care of the piano rendering and the midi file parsing
`Video` takes care of video management (fps, resolution) and exporting

**INSTALL**
`pip install piano_visualizer`

Working in `example.py`

```py
# Import the library after you have installed it
import piano_visualizer

# Create a piano with a midi file(s)
piano = piano_visualizer.Piano(["/path/to/your/midi/file.mid"])

# Create a video with resolution/fps
video = piano_visualizer.Video((1920, 1080), 30)

# Add piano to video
video.add_piano(piano)

# Export video on multiple cores (1 for single)
video.export("your/export/path.mp4", num_cores=6)

# You can add music too! (although it is sometimes offset from video)
# video.export("your/export/path.mp4", num_cores=6, music=True)

# Progress bars should show up
# Once your video is exported it will be at the path you specified!
```

NOTE: For music to work, you need [fluidsynth](https://github.com/FluidSynth/fluidsynth/wiki/Download)
