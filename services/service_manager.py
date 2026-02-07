"""Service manager for BestBox - handles service lifecycle and health monitoring."""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service operational status."""

    UNKNOWN = "unknown"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"


@dataclass
class ServiceInfo:
    """Information about a managed service."""

    name: str
    display_name: str
    port: int
    health_url: str
    status: ServiceStatus
    process_pattern: str
    start_script: str
    stop_script: Optional[str] = None
    description: str = ""
    last_check: Optional[datetime] = None
    health_details: Optional[Dict] = None
    pid: Optional[int] = None


SERVICES = {
    "agent_api": ServiceInfo(
        name="agent_api",
        display_name="Agent API",
        port=8000,
        health_url="http://localhost:8000/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="services.agent_api",
        start_script="./scripts/start-agent-api.sh",
        description="Main LangGraph agent API",
    ),
    "llm_server": ServiceInfo(
        name="llm_server",
        display_name="LLM Server (llama.cpp)",
        port=8001,
        health_url="http://localhost:8001/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="llama-server.*--port 8001",
        start_script="./scripts/start-llm.sh",
        description="LLM inference server (llama.cpp Vulkan)",
    ),
    "embeddings": ServiceInfo(
        name="embeddings",
        display_name="Embeddings (Local)",
        port=8081,
        health_url="http://localhost:8081/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="uvicorn.*8081",
        start_script="./scripts/start-embeddings.sh",
        description="Local embeddings service (port 8081)",
    ),
    "embeddings_external": ServiceInfo(
        name="embeddings_external",
        display_name="Embeddings (External)",
        port=8004,
        health_url="http://localhost:8004/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="",
        start_script="External service on port 8004",
        description="External embeddings/reranker service (port 8004)",
    ),
    "reranker": ServiceInfo(
        name="reranker",
        display_name="Reranker",
        port=8082,
        health_url="http://localhost:8082/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="reranker.py",
        start_script="./scripts/start-reranker.sh",
        description="Reranking service for search",
    ),
    "s2s_gateway": ServiceInfo(
        name="s2s_gateway",
        display_name="S2S Gateway",
        port=8765,
        health_url="http://localhost:8765/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="services.speech.s2s_server",
        start_script="./scripts/start-s2s.sh",
        description="Speech-to-speech gateway",
    ),
    "livekit_server": ServiceInfo(
        name="livekit_server",
        display_name="LiveKit Server",
        port=7880,
        health_url="http://localhost:7880",
        status=ServiceStatus.UNKNOWN,
        process_pattern="livekit-server",
        start_script="docker run -d --name livekit-server -p 7880:7880 -p 7881:7881/tcp -p 50000-50020:50000-50020/udp -v $(pwd)/livekit.yaml:/etc/livekit.yaml livekit/livekit-server:latest --config /etc/livekit.yaml",
        description="LiveKit WebRTC server for voice",
    ),
    "livekit_agent": ServiceInfo(
        name="livekit_agent",
        display_name="LiveKit Agent",
        port=0,
        health_url="",
        status=ServiceStatus.UNKNOWN,
        process_pattern="livekit_agent.py",
        start_script="./scripts/start-livekit-agent.sh dev",
        description="LiveKit voice agent (ASR/TTS)",
    ),
    "vl_service": ServiceInfo(
        name="vl_service",
        display_name="VL Service",
        port=8083,
        health_url="http://localhost:8083/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="qwen2_vl_server",
        start_script="./scripts/start-vl.sh",
        description="Vision-language service",
    ),
    "ocr_service": ServiceInfo(
        name="ocr_service",
        display_name="OCR Service",
        port=8084,
        health_url="http://localhost:8084/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="got_ocr_service",
        start_script="./scripts/start-ocr.sh",
        description="OCR (text extraction) service",
    ),
    "docling": ServiceInfo(
        name="docling",
        display_name="Docling",
        port=5001,
        health_url="http://localhost:5001/health",
        status=ServiceStatus.UNKNOWN,
        process_pattern="docling-serve",
        start_script="./scripts/start-docling.sh",
        description="Document conversion service",
    ),
    "frontend": ServiceInfo(
        name="frontend",
        display_name="Frontend Dev Server",
        port=3000,
        health_url="http://localhost:3000",
        status=ServiceStatus.UNKNOWN,
        process_pattern="next-server",
        start_script="cd frontend/copilot-demo && npm run dev",
        description="Next.js development server",
    ),
}


class ServiceManager:
    """Manages BestBox services lifecycle."""

    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
        self._lock = asyncio.Lock()
        self._active_operations: Dict[str, asyncio.Task] = {}

    async def get_all_services(self) -> List[ServiceInfo]:
        """Get status of all registered services."""
        services = []
        for service_def in SERVICES.values():
            info = await self.get_service_status(service_def.name)
            services.append(info)
        return services

    async def get_service_status(self, name: str) -> ServiceInfo:
        """Get current status of a service."""
        if name not in SERVICES:
            raise ValueError(f"Unknown service: {name}")

        service = SERVICES[name]

        try:
            if service.process_pattern:
                pid = await self._find_process(service.process_pattern)
                service.pid = pid

                if pid:
                    if service.health_url:
                        health = await self._check_health(service.health_url)
                        service.status = (
                            ServiceStatus.RUNNING
                            if health.get("healthy")
                            else ServiceStatus.ERROR
                        )
                        service.health_details = health
                    else:
                        service.status = ServiceStatus.RUNNING
                        service.health_details = {"healthy": True, "note": "Process-based check only"}
                else:
                    service.status = ServiceStatus.STOPPED
                    service.health_details = None
            else:
                if service.health_url:
                    health = await self._check_health(service.health_url)
                    service.status = (
                        ServiceStatus.RUNNING
                        if health.get("healthy")
                        else ServiceStatus.ERROR
                    )
                    service.health_details = health
                    service.pid = None
                else:
                    service.status = ServiceStatus.UNKNOWN
                    service.health_details = None

        except Exception as e:
            logger.error(f"Error checking service {name}: {e}")
            service.status = ServiceStatus.ERROR
            service.health_details = {"error": str(e)}

        service.last_check = datetime.now()
        return service

    async def start_service(self, name: str) -> ServiceInfo:
        """Start a service."""
        if name not in SERVICES:
            raise ValueError(f"Unknown service: {name}")

        async with self._lock:
            if name in self._active_operations:
                raise RuntimeError(f"Operation already in progress for {name}")

            service = SERVICES[name]

            try:
                service.status = ServiceStatus.STARTING

                if await self._is_port_in_use(service.port):
                    raise RuntimeError(f"Port {service.port} is already in use")

                await self._run_start_script(service.start_script)

                await asyncio.sleep(2)

                for _ in range(30):
                    info = await self.get_service_status(name)
                    if info.status == ServiceStatus.RUNNING:
                        return info
                    await asyncio.sleep(1)

                raise RuntimeError(f"Service {name} failed to start within timeout")

            except Exception as e:
                logger.error(f"Failed to start {name}: {e}")
                service.status = ServiceStatus.ERROR
                raise

    async def stop_service(self, name: str) -> ServiceInfo:
        """Stop a service."""
        if name not in SERVICES:
            raise ValueError(f"Unknown service: {name}")

        async with self._lock:
            service = SERVICES[name]

            try:
                service.status = ServiceStatus.STOPPING

                pid = await self._find_process(service.process_pattern)
                if pid:
                    await self._kill_process(pid)
                    await asyncio.sleep(1)

                for _ in range(10):
                    if not await self._find_process(service.process_pattern):
                        service.status = ServiceStatus.STOPPED
                        service.pid = None
                        return service
                    await asyncio.sleep(0.5)

                raise RuntimeError(f"Service {name} failed to stop")

            except Exception as e:
                logger.error(f"Failed to stop {name}: {e}")
                raise

    async def restart_service(self, name: str) -> ServiceInfo:
        """Restart a service."""
        await self.stop_service(name)
        await asyncio.sleep(2)
        return await self.start_service(name)

    async def _find_process(self, pattern: str) -> Optional[int]:
        """Find process by pattern and return PID."""
        try:
            result = await asyncio.create_subprocess_exec(
                "pgrep", "-f", pattern,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await result.communicate()

            if stdout:
                pids = stdout.decode().strip().split("\n")
                return int(pids[0])
            return None

        except Exception:
            return None

    async def _check_health(self, url: str) -> Dict:
        """Check service health via HTTP."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                is_healthy = response.status_code == 200

                if is_healthy:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        try:
                            json_data = response.json()
                            return {
                                "healthy": True,
                                "status_code": response.status_code,
                                "response": json_data,
                            }
                        except Exception:
                            return {
                                "healthy": True,
                                "status_code": response.status_code,
                                "response_text": response.text[:200],
                            }
                    else:
                        return {
                            "healthy": True,
                            "status_code": response.status_code,
                            "response_text": response.text[:200],
                        }
                else:
                    return {
                        "healthy": False,
                        "status_code": response.status_code,
                        "response_text": response.text[:200] if response.text else None,
                    }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use."""
        try:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(("localhost", port)) == 0
        except Exception:
            return False

    async def _run_start_script(self, script: str):
        """Execute a start script."""
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            process = await asyncio.create_subprocess_shell(
                script,
                cwd=self.working_dir,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            await asyncio.sleep(0.5)

            if process.returncode is not None and process.returncode != 0:
                raise RuntimeError(f"Script exited with code {process.returncode}")

        except Exception as e:
            raise RuntimeError(f"Failed to execute script: {e}")

    async def _kill_process(self, pid: int):
        """Kill a process by PID."""
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.error(f"Error killing process {pid}: {e}")
            raise


_service_manager: Optional[ServiceManager] = None


def get_service_manager() -> ServiceManager:
    """Get or create singleton service manager instance."""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
