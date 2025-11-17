"""
FastAPI Voice Cloning API
High-quality multilingual voice cloning with XTTS v2
"""
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
from pathlib import Path
import shutil
import asyncio
from datetime import datetime
import psutil
import time

# Import core TTS functionality
from core import (
    clone_voice_sync,
    SUPPORTED_LANGUAGES,
    OUTPUT_DIR,
    TEMP_DIR,
    get_system_info,
    device,
    IS_CODESPACE,
    CODESPACE_NAME
)

# --- FastAPI App ---
app = FastAPI(
    title="XTTS Voice Cloning API",
    description="High-quality multilingual voice cloning powered by Coqui XTTS v2",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend access - restricted to trusted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yassineai01-lyrebird.hf.space",
        "https://yass5002.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job storage (use Redis in production for scalability)
jobs: Dict[str, dict] = {}

# Job cleanup configuration
MAX_JOBS_IN_MEMORY = 100  # Maximum number of jobs to keep
JOB_TTL_SECONDS = 3600  # Jobs expire after 1 hour

# Track server start time
SERVER_START_TIME = time.time()

def cleanup_old_jobs():
    """Remove old completed/failed jobs to prevent memory leaks"""
    global jobs
    
    current_time = time.time()
    jobs_to_remove = []
    
    # Find expired jobs
    for job_id, job_data in jobs.items():
        if job_data.get('status') in ['completed', 'failed']:
            completed_at = job_data.get('completed_at')
            if completed_at:
                try:
                    completed_time = datetime.fromisoformat(completed_at).timestamp()
                    if current_time - completed_time > JOB_TTL_SECONDS:
                        jobs_to_remove.append(job_id)
                except Exception:
                    pass
    
    # Remove expired jobs
    for job_id in jobs_to_remove:
        del jobs[job_id]
    
    # If still too many jobs, remove oldest completed/failed ones
    if len(jobs) > MAX_JOBS_IN_MEMORY:
        completed_jobs = [
            (jid, jdata.get('completed_at', ''))
            for jid, jdata in jobs.items()
            if jdata.get('status') in ['completed', 'failed']
        ]
        completed_jobs.sort(key=lambda x: x[1])
        
        excess = len(jobs) - MAX_JOBS_IN_MEMORY
        for job_id, _ in completed_jobs[:excess]:
            del jobs[job_id]

# --- Models ---
class CloneRequest(BaseModel):
    text: str
    language: str = "English"

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    message: Optional[str] = None
    audio_url: Optional[str] = None
    error: Optional[str] = None

# --- Root Endpoint ---
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML interface"""
    html_file = Path("static/index.html")
    if html_file.exists():
        return html_file.read_text()
    
    # Fallback if static files not set up
    return """
    <html>
        <head><title>XTTS Voice Cloning API</title></head>
        <body>
            <h1>🎙️ XTTS Voice Cloning API</h1>
            <p>API is running! Visit <a href="/docs">/docs</a> for API documentation.</p>
            <ul>
                <li><strong>Device:</strong> """ + device.upper() + """</li>
                <li><strong>Languages:</strong> """ + str(len(SUPPORTED_LANGUAGES)) + """</li>
                <li><strong>Model:</strong> XTTS v2</li>
            </ul>
        </body>
    </html>
    """

# --- Health Check ---
@app.get("/api/health")
async def health_check():
    """Check API health and system status"""
    info = get_system_info()
    
    # Add job stats
    active_jobs = len([j for j in jobs.values() if j.get('status') in ['queued', 'processing']])
    total_jobs = len(jobs)
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "jobs": {
            "active": active_jobs,
            "total_in_memory": total_jobs,
            "max_capacity": MAX_JOBS_IN_MEMORY
        },
        **info
    }

# --- Resource Monitoring ---
@app.get("/api/resources")
async def get_resources():
    """Get real-time system resource usage"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # RAM usage
        memory = psutil.virtual_memory()
        ram_percent = memory.percent
        ram_used_gb = memory.used / (1024 ** 3)
        ram_total_gb = memory.total / (1024 ** 3)
        
        # Queue count
        queue_count = len([j for j in jobs.values() if j.get('status') in ['queued', 'processing']])
        
        # Uptime
        uptime_seconds = int(time.time() - SERVER_START_TIME)
        
        return {
            "cpu": {
                "percent": round(cpu_percent, 1),
                "cores": psutil.cpu_count()
            },
            "ram": {
                "percent": round(ram_percent, 1),
                "used_gb": round(ram_used_gb, 2),
                "total_gb": round(ram_total_gb, 2)
            },
            "queue": {
                "count": queue_count,
                "jobs": {
                    "queued": len([j for j in jobs.values() if j.get('status') == 'queued']),
                    "processing": len([j for j in jobs.values() if j.get('status') == 'processing']),
                    "completed": len([j for j in jobs.values() if j.get('status') == 'completed']),
                    "failed": len([j for j in jobs.values() if j.get('status') == 'failed'])
                }
            },
            "uptime": {
                "seconds": uptime_seconds,
                "formatted": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "cpu": {"percent": 0},
            "ram": {"percent": 0},
            "queue": {"count": 0},
            "uptime": {"seconds": 0}
        }

# --- Language List ---
@app.get("/api/languages")
async def get_languages():
    """Get list of supported languages"""
    return {
        "languages": list(SUPPORTED_LANGUAGES.keys()),
        "total": len(SUPPORTED_LANGUAGES)
    }

# --- Synchronous Voice Cloning ---
@app.post("/api/clone")
async def clone_voice_api(
    text: str = Form(..., description="Text to synthesize (max 2000 characters)"),
    audio: UploadFile = File(..., description="Reference audio file (WAV, MP3, FLAC, OGG, M4A)"),
    language: str = Form("English", description="Output language")
):
    """
    Synchronous voice cloning endpoint.
    
    Upload a reference audio file and text, returns the generated audio file.
    This endpoint waits for processing to complete before responding.
    
    For long texts or to avoid timeouts, use /api/clone/async instead.
    """
    
    # Cleanup old jobs periodically
    cleanup_old_jobs()
    
    # Validate text length
    if len(text) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Text too long. Maximum 2000 characters allowed."
        )
    
    if len(text.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty."
        )
    
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language. Use one of: {', '.join(SUPPORTED_LANGUAGES.keys())}"
        )
    
    # Validate file type
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_ext = audio.filename.split('.')[-1].lower()
    if file_ext not in ['wav', 'mp3', 'flac', 'ogg', 'm4a']:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format. Use: WAV, MP3, FLAC, OGG, or M4A"
        )
    
    # Validate file size (max 10MB)
    audio.file.seek(0, 2)  # Seek to end
    file_size = audio.file.tell()
    audio.file.seek(0)  # Reset to beginning
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=400,
            detail="Audio file too large. Maximum 10MB allowed."
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty."
        )
    
    # Save uploaded audio to temp file
    temp_audio = TEMP_DIR / f"{uuid.uuid4().hex}.{file_ext}"
    
    try:
        with temp_audio.open("wb") as f:
            shutil.copyfileobj(audio.file, f)
        
        # Process voice cloning
        result_path, status = clone_voice_sync(text, str(temp_audio), language)
        
        if result_path and Path(result_path).exists():
            # Get filename for URL
            filename = Path(result_path).name
            
            return JSONResponse({
                "success": True,
                "audio_url": f"/api/audio/{filename}",
                "message": status,
                "language": language,
                "text_length": len(text)
            })
        else:
            raise HTTPException(status_code=500, detail=status)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Cleanup temp audio file
        if temp_audio.exists():
            temp_audio.unlink()

# --- Asynchronous Voice Cloning ---
@app.post("/api/clone/async")
async def clone_voice_async(
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="Text to synthesize (max 2000 characters)"),
    audio: UploadFile = File(..., description="Reference audio file"),
    language: str = Form("English", description="Output language")
):
    """
    Asynchronous voice cloning endpoint.
    
    Immediately returns a job ID. Use /api/jobs/{job_id} to check status
    and retrieve the generated audio when complete.
    
    Recommended for longer texts or to avoid HTTP timeouts.
    """
    
    # Cleanup old jobs periodically
    cleanup_old_jobs()
    
    # Validate text length
    if len(text) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Text too long. Maximum 2000 characters allowed."
        )
    
    if len(text.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty."
        )
    
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language. Use one of: {', '.join(SUPPORTED_LANGUAGES.keys())}"
        )
    
    # Validate file type
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_ext = audio.filename.split('.')[-1].lower()
    if file_ext not in ['wav', 'mp3', 'flac', 'ogg', 'm4a']:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format. Use: WAV, MP3, FLAC, OGG, or M4A"
        )
    
    # Validate file size (max 10MB)
    audio.file.seek(0, 2)  # Seek to end
    file_size = audio.file.tell()
    audio.file.seek(0)  # Reset to beginning
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=400,
            detail="Audio file too large. Maximum 10MB allowed."
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty."
        )
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded audio
    temp_audio = TEMP_DIR / f"{job_id}.{file_ext}"
    with temp_audio.open("wb") as f:
        shutil.copyfileobj(audio.file, f)
    
    # Initialize job status
    jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "message": "Job queued for processing...",
        "audio_url": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "language": language,
        "text_length": len(text)
    }
    
    # Process in background
    background_tasks.add_task(
        process_clone_background,
        job_id, text, str(temp_audio), language
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/api/jobs/{job_id}",
        "message": "Job created successfully. Check status_url for progress."
    }

# --- Background Processing ---
def process_clone_background(job_id: str, text: str, audio_path: str, language: str):
    """Process voice cloning in background task"""
    
    def update_progress(progress: float, message: str):
        """Update job progress"""
        if job_id in jobs:
            jobs[job_id]["progress"] = progress
            jobs[job_id]["message"] = message
            if progress > 0.1:
                jobs[job_id]["status"] = "processing"
    
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["message"] = "Starting voice cloning..."
        
        # Process with progress callback
        result_path, status = clone_voice_sync(
            text, audio_path, language,
            progress_callback=update_progress
        )
        
        if result_path and Path(result_path).exists():
            filename = Path(result_path).name
            
            jobs[job_id] = {
                **jobs[job_id],
                "status": "completed",
                "progress": 1.0,
                "audio_url": f"/api/audio/{filename}",
                "message": status,
                "completed_at": datetime.now().isoformat()
            }
        else:
            jobs[job_id] = {
                **jobs[job_id],
                "status": "failed",
                "progress": 0.0,
                "error": status,
                "message": "Voice cloning failed",
                "completed_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        jobs[job_id] = {
            **jobs[job_id],
            "status": "failed",
            "progress": 0.0,
            "error": str(e),
            "message": "Processing error occurred",
            "completed_at": datetime.now().isoformat()
        }
    finally:
        # Cleanup temp audio file
        try:
            Path(audio_path).unlink(missing_ok=True)
        except Exception:
            pass

# --- Job Status ---
@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status of an async job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]

# --- List All Jobs ---
@app.get("/api/jobs")
async def list_jobs(limit: int = 50):
    """List recent jobs"""
    job_list = [
        {"job_id": jid, **data}
        for jid, data in list(jobs.items())[-limit:]
    ]
    return {
        "jobs": job_list,
        "total": len(jobs)
    }

# --- Serve Audio Files ---
@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    """Serve generated audio files"""
    
    # Search in output directory and subdirectories
    def find_file(directory: Path, target: str):
        for path in directory.rglob(target):
            if path.is_file():
                return path
        return None
    
    file_path = find_file(OUTPUT_DIR, filename)
    
    if file_path and file_path.exists():
        return FileResponse(
            file_path,
            media_type="audio/wav",
            filename=filename
        )
    
    raise HTTPException(status_code=404, detail="Audio file not found")

# --- Delete Job ---
@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job from memory"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Clean up associated audio file if exists
    job_data = jobs[job_id]
    if job_data.get('audio_url'):
        try:
            filename = job_data['audio_url'].split('/')[-1]
            audio_file = OUTPUT_DIR / filename
            if audio_file.exists():
                audio_file.unlink()
        except Exception:
            pass
    
    del jobs[job_id]
    return {"message": "Job deleted successfully"}

# --- Cleanup Endpoint ---
@app.post("/api/admin/cleanup")
async def trigger_cleanup():
    """Manually trigger job cleanup (removes old completed/failed jobs)"""
    jobs_before = len(jobs)
    cleanup_old_jobs()
    jobs_after = len(jobs)
    
    return {
        "message": "Cleanup completed",
        "jobs_removed": jobs_before - jobs_after,
        "jobs_remaining": jobs_after
    }

# --- Example Voices ---
@app.get("/api/examples")
async def get_examples():
    """Get list of example voice files"""
    audio_dir = Path("./audio")
    
    if not audio_dir.exists():
        return {"examples": []}
    
    examples = []
    for audio_file in audio_dir.glob("*.*"):
        if audio_file.suffix.lower() in ['.wav', '.mp3', '.flac', '.ogg', '.m4a']:
            examples.append({
                "name": audio_file.stem,
                "filename": audio_file.name,
                "path": str(audio_file)
            })
    
    return {"examples": examples}

# Mount static files if directory exists
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Main ---
if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🎙️  XTTS Voice Cloning API")
    print("=" * 60)
    print(f"📊 Device: {device.upper()}")
    print(f"🌍 Languages: {len(SUPPORTED_LANGUAGES)}")
    print(f"📁 Output: {OUTPUT_DIR}")
    print(f"☁️  Codespace: {CODESPACE_NAME if IS_CODESPACE else 'N/A'}")
    print("=" * 60)
    print("\n🚀 Starting server...\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
