import os
import sys
import zipfile
import urllib.request
from tkinter import Tk
from tkinter.filedialog import askdirectory
Tk().withdraw()

print("Choose installation location.")
dir = askdirectory()
tmp = os.path.join(dir, "tmp")
file = "piano_visualizer-"
print("Installing...")
try:
    urllib.request.urlretrieve("https://github.com/ArjunSahlot/piano_visualizer/archive/main.zip", tmp)
    file += "main"
except urllib.error.HTTPError:
    urllib.request.urlretrieve("https://github.com/ArjunSahlot/piano_visualizer/archive/master.zip", tmp)
    file += "master"

print("Unzipping")
with zipfile.ZipFile(tmp, 'r') as zip:
    zip.extractall(dir)

print("Cleaning up")
final = os.path.join(dir, file.split("-")[0])
os.rename(os.path.join(dir, file), final)
os.remove(os.path.join(tmp))

with open(os.path.join(final, "requirements.txt"), "r") as f:
    packages = f.read().split("\n")

if sys.platform == "windows":
    cmd = "pip install "
else:
    cmd = "pip3 install "

print("Installing packages")
for package in packages:
    if "n" in input(f"Install" + package + "? [y/n] ").lower():
        continue
    os.system(cmd.format(package))

print("Done!")
