import os
import setuptools

PARDIR = os.path.realpath(os.path.dirname(__file__))

with open(os.path.join(PARDIR, "README.md")) as f:
    long_description = f.read()

with open(os.path.join(PARDIR, "requirements.txt")) as f:
    reqs = f.read().strip().split("\n")


setuptools.setup(
    name="piano_visualizer",
    version=os.getenv("PYPI_VERSION").split("/")[-1].strip(),
    author="Arjun Sahlot",
    author_email="iarjun.sahlot@gmail.com",
    description="A python library that allows you to export a video in which a piano is playing the music you give it.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="GNU GPL v3",
    url="https://github.com/ArjunSahlot/piano_visualizer",
    keywords=["piano", "visualizer"],
    py_modules=["piano_visualizer"],
    packages=setuptools.find_packages(),
    install_requires=reqs,
    python_requires=">=3",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
)
