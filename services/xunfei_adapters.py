"""
Xunfei (iFlytek) ASR and TTS adapters for LiveKit.

Integrates Xunfei's cloud speech services with LiveKit voice pipelines.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import AsyncIterator
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import websockets
from livekit import agents, rtc
from livekit.agents import stt, tts

logger = logging.getLogger("xunfei")


def resample_16k_to_48k(pcm_bytes: bytes) -> bytes:
    """
    Resample audio from 16kHz to 48kHz for LiveKit.

    Simple linear interpolation (3x upsampling).
    For production, consider using librosa or scipy for higher quality.
    """
    import numpy as np

    # Convert bytes to int16 array
    samples_16k = np.frombuffer(pcm_bytes, dtype=np.int16)

    # Simple 3x linear interpolation
    num_samples_48k = len(samples_16k) * 3
    samples_48k = np.zeros(num_samples_48k, dtype=np.int16)

    for i in range(len(samples_16k)):
        samples_48k[i * 3] = samples_16k[i]
        if i < len(samples_16k) - 1:
            # Linear interpolation for intermediate samples
            diff = int(samples_16k[i + 1]) - int(samples_16k[i])
            samples_48k[i * 3 + 1] = samples_16k[i] + diff // 3
            samples_48k[i * 3 + 2] = samples_16k[i] + 2 * diff // 3

    return samples_48k.tobytes()


class XunfeiConfig:
    """Xunfei API configuration"""
    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        language: str = "zh_cn",  # or "en_us"
        stt_endpoint: str = "wss://iat-api.xfyun.cn/v2/iat",
        tts_endpoint: str = "wss://tts-api.xfyun.cn/v2/tts",
        tts_voice: str = "xiaoyan"
    ):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.language = language
        self.stt_endpoint = stt_endpoint
        self.tts_endpoint = tts_endpoint
        self.tts_voice = tts_voice

    @classmethod
    def from_env(cls) -> "XunfeiConfig":
        """Load configuration from environment variables"""
        import os

        app_id = os.getenv("XUNFEI_APP_ID")
        api_key = os.getenv("XUNFEI_API_KEY")
        api_secret = os.getenv("XUNFEI_API_SECRET")

        if not all([app_id, api_key, api_secret]):
            raise ValueError(
                "Missing Xunfei credentials. Set XUNFEI_APP_ID, XUNFEI_API_KEY, XUNFEI_API_SECRET"
            )

        return cls(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret,
            language=os.getenv("XUNFEI_LANGUAGE", "zh_cn"),
            stt_endpoint=os.getenv("XUNFEI_STT_ENDPOINT", "wss://iat-api.xfyun.cn/v2/iat"),
            tts_endpoint=os.getenv("XUNFEI_TTS_ENDPOINT", "wss://tts-api.xfyun.cn/v2/tts"),
            tts_voice=os.getenv("XUNFEI_TTS_VOICE", "xiaoyan")
        )


class XunfeiTTS(tts.TTS):
    """
    Xunfei TTS adapter for LiveKit.

    Uses Xunfei's WebSocket streaming TTS API.
    """

    def __init__(self, config: XunfeiConfig, voice: str = "xiaoyan"):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=16000,  # Xunfei default
            num_channels=1
        )
        self.config = config
        self.voice = voice
        self.ws_url = config.tts_endpoint

    def _create_auth_url(self) -> str:
        """Create authenticated WebSocket URL with signature"""
        # Parse URL
        parsed = urlparse(self.ws_url)
        host = parsed.netloc
        path = parsed.path

        # Generate RFC1123 GMT date (must use UTC)
        from datetime import timezone
        date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')

        # Build signature string
        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"

        # Sign with HMAC-SHA256
        signature_sha = hmac.new(
            self.config.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')

        # Build authorization string
        authorization_origin = (
            f'api_key="{self.config.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        # Build final URL with auth params
        auth_params = {
            "host": host,
            "date": date,
            "authorization": authorization
        }

        return f"{self.ws_url}?{urlencode(auth_params)}"

    def _synthesize_impl(self, text: str):
        """Not used - use stream() instead"""
        raise NotImplementedError("Use stream() for streaming synthesis")

    def synthesize(self, text: str):
        """Not used - use stream() instead"""
        raise NotImplementedError("Use stream() for streaming synthesis")

    def stream(self, **kwargs) -> "XunfeiTTSStream":
        """Return streaming synthesis interface"""
        return XunfeiTTSStream(tts=self, conn_options=kwargs.get("conn_options"))


class XunfeiTTSStream(tts.SynthesizeStream):
    """Streaming TTS synthesis using Xunfei API"""

    def __init__(self, tts: XunfeiTTS, conn_options=None):
        super().__init__(tts=tts, conn_options=conn_options)
        self._xunfei_tts = tts
        self._closed = False

    async def _run(self, output_emitter) -> None:
        """Main synthesis loop - reads text from self._input_ch, emits audio"""
        logger.info("🔊 Xunfei TTS: Starting synthesis stream")

        try:
            # Initialize output emitter
            await output_emitter.initialize()

            # Connect to Xunfei WebSocket
            auth_url = self._xunfei_tts._create_auth_url()

            async with websockets.connect(auth_url) as ws:
                # Process text from input channel
                while not self._closed:
                    try:
                        # Get text from input channel
                        text_chunk = await self._input_ch.recv()

                        # Check for flush sentinel
                        if isinstance(text_chunk, tts.SynthesizeStream._FlushSentinel):
                            logger.info("✅ Xunfei TTS: Received flush sentinel")
                            break

                        # Build TTS request
                        request = {
                            "common": {
                                "app_id": self._xunfei_tts.config.app_id
                            },
                            "business": {
                                "vcn": self._xunfei_tts.voice,
                                "aue": "raw",  # PCM16
                                "speed": 50,   # 0-100
                                "volume": 50,  # 0-100
                                "pitch": 50,   # 0-100
                                "tte": "UTF8"
                            },
                            "data": {
                                "text": base64.b64encode(text_chunk.encode('utf-8')).decode('utf-8'),
                                "status": 2  # Final frame
                            }
                        }

                        # Send request
                        await ws.send(json.dumps(request))
                        logger.info(f"🔊 Xunfei TTS: Sent request for text: {text_chunk[:50]}...")

                        # Receive audio chunks
                        while True:
                            response_text = await ws.recv()
                            response = json.loads(response_text)

                            code = response.get("code")
                            if code != 0:
                                logger.error(f"❌ Xunfei TTS error: {response.get('message')}")
                                break

                            # Extract audio data
                            data = response.get("data", {})
                            audio_b64 = data.get("audio")
                            status = data.get("status", 0)

                            if audio_b64:
                                audio_bytes_16k = base64.b64decode(audio_b64)
                                # Resample 16kHz -> 48kHz for LiveKit
                                audio_bytes_48k = resample_16k_to_48k(audio_bytes_16k)

                                # Push audio frame
                                frame = tts.SynthesizedAudio(
                                    text=text_chunk,
                                    data=audio_bytes_48k
                                )
                                await output_emitter.push(frame)

                            # Check if synthesis complete
                            if status == 2:
                                logger.info("✅ Xunfei TTS: Chunk complete")
                                break

                    except Exception as e:
                        if self._closed:
                            break
                        logger.error(f"❌ Xunfei TTS synthesis error: {e}", exc_info=True)
                        break

            # Flush output
            await output_emitter.flush()
            logger.info("✅ Xunfei TTS: Synthesis complete")

        except Exception as e:
            logger.error(f"❌ Xunfei TTS stream failed: {e}", exc_info=True)

    async def aclose(self) -> None:
        """Close the stream"""
        self._closed = True
        await super().aclose()


class XunfeiSTT(stt.STT):
    """
    Xunfei ASR (Speech-to-Text) adapter for LiveKit.

    Uses Xunfei's WebSocket streaming ASR API.
    """

    def __init__(self, config: XunfeiConfig):
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=True, interim_results=True)
        )
        self.config = config
        self.ws_url = config.stt_endpoint

    def _recognize_impl(self, buffer: bytes, *, language: str | None = None):
        """Required abstract method - not used for streaming"""
        raise NotImplementedError("Use stream() for streaming recognition")

    def _create_auth_url(self) -> str:
        """Create authenticated WebSocket URL with signature"""
        # Same auth logic as TTS
        parsed = urlparse(self.ws_url)
        host = parsed.netloc
        path = parsed.path

        # Generate RFC1123 GMT date (must use UTC)
        from datetime import timezone
        date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')

        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(
            self.config.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')

        authorization_origin = (
            f'api_key="{self.config.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        auth_params = {
            "host": host,
            "date": date,
            "authorization": authorization
        }

        return f"{self.ws_url}?{urlencode(auth_params)}"

    def stream(self, **kwargs) -> "XunfeiSTTStream":
        """Return streaming recognition interface"""
        return XunfeiSTTStream(stt=self, conn_options=kwargs.get("conn_options"))


class XunfeiSTTStream(stt.SpeechStream):
    """Streaming ASR using Xunfei API"""

    def __init__(self, stt: XunfeiSTT, conn_options=None):
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=16000)
        self._xunfei_stt = stt
        self._input_queue = asyncio.Queue()
        self._closed = False

    def push_frame(self, frame: rtc.AudioFrame) -> None:
        """Push an audio frame to the input queue"""
        if not self._closed:
            self._input_queue.put_nowait(frame)

    async def flush(self) -> None:
        """Signal end of input"""
        if not self._closed:
            await self._input_queue.put(stt.SpeechStream._FlushSentinel())

    async def _run(self) -> None:
        """Main recognition loop - reads from self._input_queue, emits to self._event_ch"""
        logger.info("🎤 Xunfei ASR: Starting recognition stream")

        try:
            # Start Xunfei WebSocket connection
            auth_url = self._xunfei_stt._create_auth_url()

            async with websockets.connect(auth_url) as ws:
                # Send initial params
                business_params = {
                    "common": {
                        "app_id": self._xunfei_stt.config.app_id
                    },
                    "business": {
                        "language": self._xunfei_stt.config.language,
                        "domain": "iat",
                        "accent": "mandarin",
                        "vad_eos": 2000,
                        "dwa": "wpgs"
                    },
                    "data": {
                        "status": 0,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": ""
                    }
                }

                await ws.send(json.dumps(business_params))
                logger.info("🎤 Xunfei ASR: Sent initial params")

                # Create concurrent tasks for sending and receiving
                send_task = asyncio.create_task(self._send_audio_task(ws))
                recv_task = asyncio.create_task(self._receive_results_task(ws))

                try:
                    await asyncio.gather(send_task, recv_task)
                except Exception as e:
                    logger.error(f"❌ Xunfei ASR task error: {e}")
                finally:
                    send_task.cancel()
                    recv_task.cancel()

            logger.info("✅ Xunfei ASR: Recognition complete")
        except Exception as e:
            logger.error(f"❌ Xunfei ASR recognition failed: {e}", exc_info=True)

    async def _send_audio_task(self, ws):
        """Send audio frames from self._input_queue to Xunfei"""
        frame_count = 0

        try:
            while not self._closed:
                # Get frame from input queue
                data = await self._input_queue.get()

                # Handle audio frames
                if isinstance(data, rtc.AudioFrame):
                    # Convert AudioFrame to bytes
                    audio_bytes = data.data.tobytes()

                    # Handle resampling if needed (LiveKit 48kHz -> Xunfei 16kHz)
                    if data.sample_rate == 48000:
                        # Simple decimation (take every 3rd sample)
                        # For production, use scipy.signal.resample
                        import numpy as np
                        pcm = np.frombuffer(audio_bytes, dtype=np.int16)
                        pcm_16k = pcm[::3]
                        audio_bytes = pcm_16k.tobytes()
                    elif data.sample_rate != 16000:
                         logger.warning(f"⚠️ Unexpected sample rate: {data.sample_rate}Hz. Sending as is.")

                    # Send audio frame to Xunfei
                    frame_data = {
                        "data": {
                            "status": 1,  # Ongoing
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": base64.b64encode(audio_bytes).decode('utf-8')
                        }
                    }

                    await ws.send(json.dumps(frame_data))
                    frame_count += 1

                    if frame_count % 10 == 0:
                        logger.debug(f"🎤 Xunfei ASR: Sent {frame_count} audio frames")

                elif isinstance(data, stt.SpeechStream._FlushSentinel):
                    # End of input - send final frame
                    final_frame = {
                        "data": {
                            "status": 2,  # End
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": ""
                        }
                    }
                    await ws.send(json.dumps(final_frame))
                    logger.info(f"✅ Xunfei ASR: Sent final frame ({frame_count} total)")
                    break

        except Exception as e:
            logger.error(f"❌ Xunfei ASR send error: {e}")

    async def _receive_results_task(self, ws):
        """Receive recognition results from Xunfei and emit to self._event_ch"""
        try:
            while not self._closed:
                response_text = await ws.recv()
                response = json.loads(response_text)

                code = response.get("code")
                if code != 0:
                    logger.error(f"❌ Xunfei ASR error: {response.get('message')}")
                    break

                # Extract recognition results
                data = response.get("data", {})
                result = data.get("result", {})
                ws_list = result.get("ws", [])

                # Combine word segments
                text_parts = []
                for ws_item in ws_list:
                    for cw in ws_item.get("cw", []):
                        text_parts.append(cw.get("w", ""))

                if text_parts:
                    text = "".join(text_parts)
                    is_final = data.get("status") == 2

                    # Emit event via self._event_ch
                    event = stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT if is_final else stt.SpeechEventType.INTERIM_TRANSCRIPT,
                        alternatives=[stt.SpeechData(text=text, language="zh")]
                    )

                    self._event_ch.send_nowait(event)

                    if is_final:
                        logger.info(f"✅ Xunfei ASR: Final: {text}")
                    else:
                        logger.debug(f"🎤 Xunfei ASR: Interim: {text}")

                # Check if recognition complete
                if data.get("status") == 2:
                    break

        except Exception as e:
            logger.error(f"❌ Xunfei ASR receive error: {e}")

    async def aclose(self) -> None:
        """Close the stream"""
        self._closed = True
        await super().aclose()
