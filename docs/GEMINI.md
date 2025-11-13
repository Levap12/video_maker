# Gemini Code Understanding

## Project Overview

This project is a comprehensive Python-based video automation toolkit named "Video Maker". It is designed to streamline the process of creating video content, from downloading source material to producing final cuts for social media platforms like YouTube Shorts. The project is primarily geared towards working with the "Rick and Morty" TV series but is adaptable for other content as well.

The workflow is modular, with different scripts handling specific tasks such as downloading, clipping, processing, and formatting. The project heavily relies on JSON files for defining video segments and compilations, and it integrates with external tools like FFmpeg and Google Colab for advanced functionalities like video processing and audio transcription.

## Core Technologies

*   **Language:** Python 3
*   **Key Libraries:**
    *   `HdRezkaApi`: For interacting with the HDRezka website to download videos.
    *   `moviepy`: For all video manipulation tasks, including clipping, concatenating, and creating effects.
    *   `requests`: For making HTTP requests.
    *   `Pillow`: For image manipulation, used in `shorts_creator.py`.
    *   `numpy`: For numerical operations, used by `moviepy`.
*   **External Tools:**
    *   **FFmpeg:** Required by `moviepy` for video processing.
    *   **Google Colab:** Used for running the Whisper audio transcription model.

## Building and Running

The project is designed to be run from the command line.

### 1. Setup

1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    ```
2.  **Activate the virtual environment:**
    *   **Windows:**
        ```bash
        venv\Scripts\activate
        ```
    *   **Linux/Mac:**
        ```bash
        source venv/bin/activate
        ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Install FFmpeg:**
    FFmpeg is a critical dependency for `moviepy`. Download it from [ffmpeg.org](https://ffmpeg.org/) and ensure it is available in your system's PATH.

### 2. Running the Scripts

Each script is a standalone tool that can be run from the root of the project. Here are the main scripts and their purposes:

*   `python hdrezka_downloader.py`: Interactively search and download individual video episodes.
*   `python mass_downloader.py`: Bulk download all seasons of "Rick and Morty".
*   `python video_clipper.py`: Cut video files into smaller clips based on a JSON input file.
*   `python video_processor.py`: Create a video compilation by clipping and joining segments defined in a JSON file.
*   `python shorts_creator.py`: Convert existing videos into a 9:16 aspect ratio for YouTube Shorts, adding a blurred background, a banner, and a watermark.
*   `python google_colab/audio_extractor.py`: Extract audio from video files to prepare for transcription.
*   `python utils/transcription_formatter.py`: Clean up the output from the Whisper transcription service.

## Development Conventions

*   **Modularity:** The project is broken down into single-purpose scripts, making it easy to understand and maintain.
*   **Command-Line Interface:** All scripts use the `argparse` library to provide a clear and consistent command-line interface.
*   **Configuration:** The project uses JSON files to configure the video clipping and compilation process. This separates the data (video timestamps) from the code.
*   **Documentation:** The code is well-documented with docstrings and comments, although primarily in Russian. The `README.md` file provides extensive documentation on how to use each script.
*   **Error Handling:** The scripts include basic error handling for issues like missing files or network problems.
*   **File Structure:** The project follows a logical file structure, with separate directories for downloaded videos, clips, output videos, and utility scripts.