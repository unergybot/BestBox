"""
GPU Scheduler Service for Mutual Exclusion
Manages exclusive access to RTX 3080 GPU between LLM and OCR-VL workloads
"""

import os
import time
import fcntl
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gpu-scheduler")

# Configuration
LOCK_FILE = "/tmp/gpu-locks/rtx3080.lock"
LOCK_TIMEOUT = int(os.environ.get("LOCK_TIMEOUT", "300"))  # 5 minutes
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
LOCK_KEY = "gpu:rtx3080:lock"


class LockRequest(BaseModel):
    """Request to acquire GPU lock."""
    worker_id: str
    workload_type: str  # "llm" or "ocr-vl"
    timeout: int = 300


class LockResponse(BaseModel):
    """Response for lock acquisition."""
    acquired: bool
    worker_id: str
    workload_type: str
    expires_at: Optional[str] = None
    message: str


class LockStatus(BaseModel):
    """Current lock status."""
    locked: bool
    worker_id: Optional[str] = None
    workload_type: Optional[str] = None
    acquired_at: Optional[str] = None
    expires_at: Optional[str] = None


class GPUScheduler:
    """Manages mutual exclusion for RTX 3080 GPU."""
    
    def __init__(self):
        self.lock_file_path = Path(LOCK_FILE)
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._redis_client: Optional[redis.Redis] = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection if available."""
        if REDIS_AVAILABLE:
            try:
                self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis_client.ping()
                logger.info("✅ Redis connection established")
            except Exception as e:
                logger.warning(f"⚠️ Redis unavailable, using file-based locks: {e}")
                self._redis_client = None
    
    def _get_file_lock(self) -> bool:
        """Check if file lock is held."""
        try:
            if not self.lock_file_path.exists():
                return False
            
            with open(self.lock_file_path, "r") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    return False  # Lock is free
                except IOError:
                    return True  # Lock is held
        except Exception as e:
            logger.error(f"Error checking file lock: {e}")
            return False
    
    def _acquire_file_lock(self, worker_id: str, workload_type: str, timeout: int) -> bool:
        """Acquire file-based lock."""
        try:
            with open(self.lock_file_path, "w") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # Write lock info
                    expires = datetime.now() + timedelta(seconds=timeout)
                    f.write(f"{worker_id}\n{workload_type}\n{expires.isoformat()}")
                    f.flush()
                    # Keep lock open (don't release)
                    return True
                except IOError:
                    return False
        except Exception as e:
            logger.error(f"Error acquiring file lock: {e}")
            return False
    
    def _release_file_lock(self) -> bool:
        """Release file-based lock."""
        try:
            if self.lock_file_path.exists():
                with open(self.lock_file_path, "r+") as f:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except IOError:
                        pass
                self.lock_file_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Error releasing file lock: {e}")
            return False
    
    def _get_redis_lock(self) -> Optional[dict]:
        """Get current Redis lock info."""
        if not self._redis_client:
            return None
        
        try:
            lock_data = self._redis_client.hgetall(LOCK_KEY)
            if lock_data:
                return {
                    "worker_id": lock_data.get("worker_id"),
                    "workload_type": lock_data.get("workload_type"),
                    "acquired_at": lock_data.get("acquired_at"),
                    "expires_at": lock_data.get("expires_at")
                }
        except Exception as e:
            logger.error(f"Error getting Redis lock: {e}")
        
        return None
    
    def acquire_lock(self, worker_id: str, workload_type: str, timeout: int = 300) -> LockResponse:
        """Acquire GPU lock with mutual exclusion."""
        
        # Check if already locked
        if self.is_locked():
            status = self.get_status()
            return LockResponse(
                acquired=False,
                worker_id=worker_id,
                workload_type=workload_type,
                message=f"GPU is locked by {status.worker_id} ({status.workload_type})"
            )
        
        # Try Redis first, fallback to file
        if self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.watch(LOCK_KEY)
                
                if pipe.exists(LOCK_KEY):
                    pipe.unwatch()
                    return LockResponse(
                        acquired=False,
                        worker_id=worker_id,
                        workload_type=workload_type,
                        message="GPU is locked by another worker"
                    )
                
                expires = datetime.now() + timedelta(seconds=timeout)
                pipe.multi()
                pipe.hset(LOCK_KEY, mapping={
                    "worker_id": worker_id,
                    "workload_type": workload_type,
                    "acquired_at": datetime.now().isoformat(),
                    "expires_at": expires.isoformat()
                })
                pipe.expire(LOCK_KEY, timeout)
                pipe.execute()
                
                logger.info(f"🔒 Redis lock acquired: {worker_id} ({workload_type})")
                return LockResponse(
                    acquired=True,
                    worker_id=worker_id,
                    workload_type=workload_type,
                    expires_at=expires.isoformat(),
                    message="Lock acquired successfully"
                )
                
            except redis.WatchError:
                return LockResponse(
                    acquired=False,
                    worker_id=worker_id,
                    workload_type=workload_type,
                    message="Lock contention detected"
                )
            except Exception as e:
                logger.error(f"Redis lock error: {e}, falling back to file lock")
        
        # File-based lock fallback
        if self._acquire_file_lock(worker_id, workload_type, timeout):
            expires = datetime.now() + timedelta(seconds=timeout)
            logger.info(f"🔒 File lock acquired: {worker_id} ({workload_type})")
            return LockResponse(
                acquired=True,
                worker_id=worker_id,
                workload_type=workload_type,
                expires_at=expires.isoformat(),
                message="Lock acquired successfully (file-based)"
            )
        
        return LockResponse(
            acquired=False,
            worker_id=worker_id,
            workload_type=workload_type,
            message="Failed to acquire lock"
        )
    
    def release_lock(self, worker_id: str) -> bool:
        """Release GPU lock."""
        released = False
        
        # Release Redis lock
        if self._redis_client:
            try:
                current = self._redis_client.hget(LOCK_KEY, "worker_id")
                if current == worker_id:
                    self._redis_client.delete(LOCK_KEY)
                    logger.info(f"🔓 Redis lock released: {worker_id}")
                    released = True
            except Exception as e:
                logger.error(f"Error releasing Redis lock: {e}")
        
        # Release file lock
        if self._release_file_lock():
            logger.info(f"🔓 File lock released: {worker_id}")
            released = True
        
        return released
    
    def is_locked(self) -> bool:
        """Check if GPU is currently locked."""
        # Check Redis
        if self._redis_client:
            try:
                if self._redis_client.exists(LOCK_KEY):
                    return True
            except Exception:
                pass
        
        # Check file
        return self._get_file_lock()
    
    def get_status(self) -> LockStatus:
        """Get current lock status."""
        # Try Redis first
        if self._redis_client:
            try:
                lock_data = self._get_redis_lock()
                if lock_data:
                    return LockStatus(
                        locked=True,
                        worker_id=lock_data.get("worker_id"),
                        workload_type=lock_data.get("workload_type"),
                        acquired_at=lock_data.get("acquired_at"),
                        expires_at=lock_data.get("expires_at")
                    )
            except Exception as e:
                logger.error(f"Error getting Redis status: {e}")
        
        # Try file
        try:
            if self.lock_file_path.exists():
                with open(self.lock_file_path, "r") as f:
                    lines = f.read().strip().split("\n")
                    if len(lines) >= 3:
                        return LockStatus(
                            locked=True,
                            worker_id=lines[0],
                            workload_type=lines[1],
                            expires_at=lines[2]
                        )
        except Exception as e:
            logger.error(f"Error getting file lock status: {e}")
        
        return LockStatus(locked=False)


# Global scheduler instance
scheduler = GPUScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize scheduler."""
    logger.info("🚀 GPU Scheduler starting...")
    yield
    logger.info("🛑 GPU Scheduler shutting down...")


app = FastAPI(
    title="GPU Scheduler Service",
    description="Manages mutual exclusion for RTX 3080 GPU between LLM and OCR-VL",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "redis_available": scheduler._redis_client is not None,
        "locked": scheduler.is_locked()
    }


@app.post("/lock", response_model=LockResponse)
async def acquire_lock(request: LockRequest):
    """Acquire GPU lock."""
    return scheduler.acquire_lock(
        worker_id=request.worker_id,
        workload_type=request.workload_type,
        timeout=request.timeout
    )


@app.post("/lock/release")
async def release_lock(worker_id: str):
    """Release GPU lock."""
    released = scheduler.release_lock(worker_id)
    return {"released": released, "worker_id": worker_id}


@app.get("/status", response_model=LockStatus)
async def get_status():
    """Get current lock status."""
    return scheduler.get_status()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "GPU Scheduler",
        "version": "1.0.0",
        "purpose": "Mutual exclusion for RTX 3080 GPU",
        "endpoints": {
            "health": "/health",
            "acquire_lock": "POST /lock",
            "release_lock": "POST /lock/release",
            "status": "/status"
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SCHEDULER_PORT", 8086))
    uvicorn.run(app, host="0.0.0.0", port=port)
