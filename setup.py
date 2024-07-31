import sys
from cx_Freeze import setup, Executable

"""
Created by: https://github.com/JSapun/. This code is released under the MIT license. 
"""

setup(
    name = "MovieDownloader",
    version = "1.0",
    description = "Download m3u8 streaming files to mp4 format for local file storage.",
    author = "JS",
    options={"build_exe": {'include_files': ['movieIds.csv', 'ffmpeg.exe', 'QUICKSTART.txt']}},
    executables = [Executable("m3u8Downloader.py",icon="download_image.ico")]) # base="Win32GUI"

