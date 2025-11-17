---
title: Lyrebird Voice Cloning
emoji: 🎙️
colorFrom: purple
colorTo: blue
sdk: docker
app_file: api.py
pinned: false
---

# 🎙️ Lyrebird Voice Cloning

A simple and powerful tool for high-quality multilingual voice cloning. Give it a few seconds of audio, and it can generate speech in over 15 languages using that voice.

This project provides a clean web interface and a RESTful API for voice cloning, powered by the Coqui XTTS v2 model. It's optimized to run efficiently on a CPU.

## 🌐 Live Demo

You can try Lyrebird live at: **[yass5002.github.io/Lyrebird/](https://yass5002.github.io/Lyrebird/)**

## ✨ Features

- **Multilingual Cloning**: Supports 17 languages.
- **Web Interface**: Easy-to-use UI for quick voice cloning.
- **RESTful API**: Integrate voice cloning into your own applications.
- **CPU Optimized**: Runs efficiently without a dedicated GPU.

## 🚀 Getting Started

You can run Lyrebird using Docker, locally with Python, or deploy it to a Hugging Face Space.

### With Docker (Recommended)

1.  **Build the Docker image:**
    ```bash
    docker build -t lyrebird .
    ```
2.  **Run the container:**
    ```bash
    docker run -p 7860:7860 lyrebird
    ```
3.  Open your browser and go to `http://localhost:7860`.

### Locally with Python

1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the application:**
    ```bash
    python api.py
    ```
4.  Open your browser and go to `http://localhost:7860`.

### Deploy to Hugging Face Spaces

1.  **Create a Space**: Click [here](https://huggingface.co/new-space) to create a new Hugging Face Space.
2.  **Choose Docker**: Select `Docker` as the Space SDK and choose a hardware configuration (the free CPU option is sufficient).
3.  **Upload Files**: Upload all the project files (`api.py`, `core.py`, `Dockerfile`, `requirements.txt`, etc.) to the repository created for your Space.
4.  **Deploy**: Hugging Face will automatically build the Docker image and deploy your application. You can then access it from the Space's URL.

## 📋 Supported Languages

English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, Chinese, Japanese, Hungarian, Korean, and Hindi.

## ⚖️ License

The Coqui XTTS v2 model is released under the [CPML License](https://coqui.ai/cpml.txt). This tool is intended for personal and research use.

> **Important**: Always obtain consent before cloning a voice.

