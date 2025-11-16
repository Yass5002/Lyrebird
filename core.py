"""
Core TTS functionality - shared logic without UI dependencies
"""
import torch
from TTS.api import TTS
import os
import time
import gc
from pathlib import Path
import uuid
from datetime import datetime
import shutil

# --- Configuration ---
os.environ["COQUI_TOS_AGREED"] = "1"

# Codespaces-specific configuration
IS_CODESPACE = os.getenv('CODESPACES') == 'true'
CODESPACE_NAME = os.getenv('CODESPACE_NAME', 'local')

# Device detection with CPU fallback for Codespaces
if torch.cuda.is_available():
    device = "cuda"
    print("🎮 GPU detected - using CUDA acceleration")
elif torch.backends.mps.is_available():
    device = "mps"
    print("🍎 Apple Silicon detected - using MPS acceleration")
else:
    device = "cpu"
    print("💻 Running on CPU (expect slower performance)")

# ✅ Complete XTTS v2 language support
SUPPORTED_LANGUAGES = {
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Polish": "pl",
    "Turkish": "tr",
    "Russian": "ru",
    "Dutch": "nl",
    "Czech": "cs",
    "Arabic": "ar",
    "Chinese": "zh-cn",
    "Japanese": "ja",
    "Hungarian": "hu",
    "Korean": "ko",
    "Hindi": "hi"
}

# --- Storage Configuration for Codespaces ---
if IS_CODESPACE:
    WORKSPACE_DIR = Path("/workspaces").resolve()
    OUTPUT_DIR = WORKSPACE_DIR / "voice_cloning_outputs"
    print(f"☁️ Running in GitHub Codespace: {CODESPACE_NAME}")
else:
    OUTPUT_DIR = Path("./outputs")
    print("💻 Running locally")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"📁 Output directory: {OUTPUT_DIR}")

TEMP_DIR = Path("./temp_audio")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# --- Global variables for progress prediction ---
AVERAGE_RTF = None  # Real-time factor (processing_time / audio_duration)
RTF_HISTORY = []    # Store last 5 RTF values for averaging

# --- Model Initialization ---
MODEL_CACHE_DIR = OUTPUT_DIR.parent / ".cache" / "tts_models"
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TTS_CACHE_PATH"] = str(MODEL_CACHE_DIR)

print(f"🚀 Initializing XTTS v2 on {device.upper()}...")
print(f"📦 Model cache: {MODEL_CACHE_DIR}")

try:
    print("Loading TTS model...")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    print("Moving model to device...")
    tts = tts.to(device)
    print("✅ TTS Model loaded successfully")
    print(f"📊 Supported languages: {len(SUPPORTED_LANGUAGES)}")
    print(f"⚙️ Device: {device.upper()}\n")
except Exception as e:
    print(f"❌ Model loading failed: {e}")
    import traceback
    traceback.print_exc()
    raise

# --- Initialize Punctuation Model ---
print("🔤 Loading punctuation restoration model...")
punct_model = None
try:
    from deepmultilingualpunctuation import PunctuationModel
    punct_model = PunctuationModel()
    print("✅ Punctuation model loaded successfully")
    print("   TTS will use punctuation for automatic sentence splitting\n")
except ImportError:
    print("⚠️ deepmultilingualpunctuation not installed")
    print("   Install with: pip install deepmultilingualpunctuation")
    print("   Without it, TTS splitting may not work properly\n")
except Exception as e:
    print(f"⚠️ Punctuation model failed to load: {e}\n")


def restore_punctuation(text: str) -> str:
    """
    Add punctuation using deepmultilingualpunctuation.
    This allows TTS to automatically split text into sentences.
    """
    if not text or not text.strip():
        return text
    
    text = text.strip()
    
    if punct_model is not None:
        try:
            print("🔤 Restoring punctuation for TTS sentence splitting...")
            punctuated_text = punct_model.restore_punctuation(text)
            print(f"✅ Punctuation added - TTS will now split automatically")
            return punctuated_text
        except Exception as e:
            print(f"⚠️ Punctuation restoration failed: {e}")
            print("   TTS may not split properly without punctuation")
            return text
    else:
        print("⚠️ Punctuation model not available")
        # Basic fallback - add period at end
        if text and text[-1] not in '.!?':
            text += '.'
        return text


def estimate_audio_duration(text: str, language: str = "en") -> float:
    """
    Estimate audio duration based on text length.
    Average speaking rates:
    - English: ~150 words/minute = 2.5 words/second
    - Other languages: ~140 words/minute = 2.33 words/second
    """
    words = len(text.split())
    
    if language == "en":
        words_per_second = 2.5
    else:
        words_per_second = 2.33
    
    estimated_duration = words / words_per_second
    return estimated_duration


def update_rtf(processing_time: float, audio_duration: float):
    """Update real-time factor history for better predictions."""
    global AVERAGE_RTF, RTF_HISTORY
    
    rtf = processing_time / audio_duration if audio_duration > 0 else 2.0
    
    RTF_HISTORY.append(rtf)
    if len(RTF_HISTORY) > 5:  # Keep last 5 measurements
        RTF_HISTORY.pop(0)
    
    AVERAGE_RTF = sum(RTF_HISTORY) / len(RTF_HISTORY)
    
    print(f"📊 Real-time factor: {rtf:.2f}x (avg: {AVERAGE_RTF:.2f}x)")


def get_audio_duration(file_path: str) -> float:
    """Get actual audio duration from generated file."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(file_path)
        return len(audio) / 1000.0  # Convert ms to seconds
    except ImportError:
        # Fallback: estimate from file size (very rough)
        file_size = Path(file_path).stat().st_size
        # WAV: ~176KB per second (44.1kHz, 16-bit, stereo)
        return file_size / 176000
    except Exception as e:
        print(f"⚠️ Could not get audio duration: {e}")
        return 0


def cleanup_old_outputs(directory: Path, max_age_hours: int = 4):
    """Remove old output files."""
    if not directory.exists():
        return
    
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0
    
    for file in directory.glob("*.wav"):
        try:
            if file.stat().st_mtime < cutoff:
                file.unlink()
                removed += 1
        except Exception:
            pass
    
    if removed > 0:
        print(f"🗑️ Cleaned up {removed} old file(s)")


def save_with_organization(local_file: Path, language: str) -> tuple[str, str]:
    """Organize files by date and language."""
    try:
        date_folder = OUTPUT_DIR / datetime.now().strftime("%Y-%m-%d")
        date_folder.mkdir(exist_ok=True)
        
        lang_folder = date_folder / language
        lang_folder.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%H%M%S")
        organized_file = lang_folder / f"clone_{timestamp}_{local_file.stem}.wav"
        
        shutil.copy(str(local_file), str(organized_file))
        
        try:
            relative_path = organized_file.relative_to(OUTPUT_DIR)
        except ValueError:
            relative_path = organized_file.name
        
        print(f"💾 Saved to: {relative_path}")
        
        return str(organized_file), str(relative_path)
        
    except Exception as e:
        print(f"⚠️ Organization failed: {e}")
        return str(local_file), str(local_file.name)


def clone_voice_sync(text: str, audio_path: str, language: str, progress_callback=None) -> tuple[str | None, str]:
    """
    Generate cloned voice with automatic punctuation restoration.
    
    Args:
        text: Text to synthesize
        audio_path: Path to reference audio file
        language: Language name (e.g., "English")
        progress_callback: Optional callback function(progress: float, message: str)
    
    Returns:
        tuple: (audio_file_path, status_message)
    """
    
    def report_progress(progress: float, message: str):
        """Helper to report progress if callback provided"""
        if progress_callback:
            progress_callback(progress, message)
        print(f"[{int(progress*100)}%] {message}")
    
    # Validation
    report_progress(0.1, "🔍 Validating inputs...")
    
    if not text or not text.strip():
        return None, "⚠️ Please enter text to synthesize."
    
    text = text.strip()
    
    if len(text) > 2000:
        return None, f"⚠️ Text too long ({len(text)} chars). Maximum: 2000 characters."
    
    if len(text) < 3:
        return None, "⚠️ Text too short. Please enter at least 3 characters."
    
    if not audio_path:
        return None, "⚠️ Please upload a voice reference audio file."
    
    if not audio_path.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
        return None, "⚠️ Unsupported format. Use: WAV, MP3, FLAC, OGG, or M4A."
    
    # Restore punctuation (critical for TTS sentence splitting!)
    report_progress(0.3, "🔤 Processing text...")
    
    original_text = text
    text = restore_punctuation(text)
    
    if text != original_text:
        print(f"\n📝 Original text: {original_text[:150]}...")
        print(f"✅ With punctuation: {text[:150]}...\n")
    
    # Estimate processing time
    lang_code = SUPPORTED_LANGUAGES[language]
    estimated_audio_duration = estimate_audio_duration(text, lang_code)
    
    if AVERAGE_RTF is not None:
        estimated_processing_time = estimated_audio_duration * AVERAGE_RTF
        print(f"📊 Using learned RTF: {AVERAGE_RTF:.2f}x")
        print(f"📊 Estimated processing time: {estimated_processing_time:.1f}s")
    else:
        default_rtf = 3.0 if device == "cpu" else 0.5
        estimated_processing_time = estimated_audio_duration * default_rtf
        print(f"📊 First run - using default RTF: {default_rtf:.2f}x")
        print(f"📊 Estimated processing time: {estimated_processing_time:.1f}s")
    
    report_progress(0.5, f"🎙️ Generating {language} speech...")
    
    temp_file = TEMP_DIR / f"temp_{uuid.uuid4().hex[:8]}.wav"
    
    try:
        preview = text[:100] + "..." if len(text) > 100 else text
        print(f"🎤 Generating speech in {language}")
        print(f"📝 Text: {preview}")
        
        # Track actual processing time
        start_time = time.time()
        
        # TTS will automatically split by sentences (using punctuation)
        tts.tts_to_file(
            text=text,
            speaker_wav=audio_path,
            language=lang_code,
            file_path=str(temp_file)
        )
        
        processing_time = time.time() - start_time
        
        # Get actual audio duration and update RTF
        audio_duration = get_audio_duration(str(temp_file))
        if audio_duration > 0:
            update_rtf(processing_time, audio_duration)
        
        report_progress(0.85, "📁 Saving file...")
        
        final_path, relative_path = save_with_organization(temp_file, language)
        
        report_progress(0.95, "🧹 Cleaning up...")
        
        # Cleanup
        if device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()
        cleanup_old_outputs(TEMP_DIR, max_age_hours=2)
        
        report_progress(1.0, "✅ Complete!")
        
        print(f"✅ Generation complete\n")
        
        # Success message
        success_msg = f"✅ Voice cloning completed successfully!\n\n"
        success_msg += f"📁 File: {relative_path}\n"
        success_msg += f"🌍 Language: {language}\n"
        success_msg += f"⏱️ Processing time: {processing_time:.1f}s\n"
        success_msg += f"🎵 Audio duration: {audio_duration:.1f}s\n"
        
        return final_path, success_msg
        
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
        error_msg = f"❌ Generation failed: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return None, error_msg


def get_system_info():
    """Get system information for health checks"""
    return {
        "device": device,
        "is_codespace": IS_CODESPACE,
        "codespace_name": CODESPACE_NAME if IS_CODESPACE else None,
        "supported_languages": len(SUPPORTED_LANGUAGES),
        "model": "XTTS v2",
        "punctuation_model": punct_model is not None,
        "output_dir": str(OUTPUT_DIR),
        "temp_dir": str(TEMP_DIR)
    }
