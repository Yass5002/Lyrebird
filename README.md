---
title: Lyrebird Voice Cloning
emoji: 🎙️
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
license: other
app_port: 7860
---

# 🎙️ Lyrebird - XTTS Voice Cloning API

High-quality multilingual voice cloning powered by Coqui XTTS v2.

## ✨ Features

- **17 Languages**: English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, Chinese, Japanese, Hungarian, Korean, Hindi
- **Easy Web Interface**: Upload audio and generate cloned voices instantly
- **RESTful API**: Full API access with automatic documentation
- **Auto-Punctuation**: Natural sentence splitting for better results
- **CPU Optimized**: Runs efficiently on CPU hardware

## 🚀 How to Use

### Web Interface

1. Visit the Space URL
2. Upload 5-15 seconds of clean reference audio
3. Enter the text you want to synthesize (max 2000 characters)
4. Select output language
5. Click "Generate Voice Clone" and wait
6. Download your generated audio!

### API Usage

**Health Check:**
```bash
curl https://huggingface.co/spaces/YassineAi01/Lyrebird/api/health
```

**Clone Voice (Async):**
```bash
curl -X POST "https://huggingface.co/spaces/YassineAi01/Lyrebird/api/clone/async" \
  -F "text=Hello world! This is a test of voice cloning." \
  -F "audio=@your_voice.wav" \
  -F "language=English"
```

**Get Job Status:**
```bash
curl https://huggingface.co/spaces/YassineAi01/Lyrebird/api/jobs/{job_id}
```

**API Documentation:**  
Visit `/docs` for interactive Swagger documentation.

## 📋 Supported Languages

English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, Chinese, Japanese, Hungarian, Korean, Hindi

## 💡 Tips for Best Results

- Use high-quality reference audio (no background noise)
- Single speaker only in reference audio
- Clear pronunciation in reference
- Reference audio: 5-15 seconds is optimal
- Supported formats: WAV, MP3, FLAC, OGG, M4A
- Add punctuation for natural pacing

## ⚙️ Technical Details

- **Model**: XTTS v2 (Coqui TTS)
- **Framework**: PyTorch + FastAPI
- **Device**: CPU (optimized)
- **Processing Time**: 30-90 seconds depending on text length

## ⚖️ License

Coqui XTTS v2 - [CPML License](https://coqui.ai/cpml.txt)  
**For personal and research use only.**

## ⚠️ Important

Always obtain consent before cloning someone's voice. This tool is for personal and research purposes only.

---

Built with ❤️ using Coqui XTTS v2
