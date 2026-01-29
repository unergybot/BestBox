"""
Unit tests for Xunfei speech adapters.

Tests configuration, authentication, and basic streaming functionality.
"""

import asyncio
import base64
import hashlib
import hmac
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

# Import modules under test
from services.xunfei_adapters import (
    XunfeiConfig,
    XunfeiSTT,
    XunfeiTTS,
    XunfeiSTTStream,
    XunfeiTTSStream,
    resample_16k_to_48k,
)


class TestXunfeiConfig:
    """Test XunfeiConfig configuration management"""

    def test_config_init(self):
        """Test basic configuration initialization"""
        config = XunfeiConfig(
            app_id="test_app_id",
            api_key="test_api_key",
            api_secret="test_api_secret",
            language="zh_cn"
        )

        assert config.app_id == "test_app_id"
        assert config.api_key == "test_api_key"
        assert config.api_secret == "test_api_secret"
        assert config.language == "zh_cn"
        assert config.stt_endpoint == "wss://iat-api.xfyun.cn/v2/iat"
        assert config.tts_endpoint == "wss://tts-api.xfyun.cn/v2/tts"
        assert config.tts_voice == "xiaoyan"

    def test_config_custom_endpoints(self):
        """Test configuration with custom endpoints"""
        config = XunfeiConfig(
            app_id="test_app_id",
            api_key="test_api_key",
            api_secret="test_api_secret",
            stt_endpoint="wss://custom-stt.example.com/v2/iat",
            tts_endpoint="wss://custom-tts.example.com/v2/tts",
            tts_voice="xiaofeng"
        )

        assert config.stt_endpoint == "wss://custom-stt.example.com/v2/iat"
        assert config.tts_endpoint == "wss://custom-tts.example.com/v2/tts"
        assert config.tts_voice == "xiaofeng"

    def test_config_from_env(self):
        """Test loading configuration from environment variables"""
        with patch.dict(os.environ, {
            "XUNFEI_APP_ID": "env_app_id",
            "XUNFEI_API_KEY": "env_api_key",
            "XUNFEI_API_SECRET": "env_api_secret",
            "XUNFEI_LANGUAGE": "en_us",
            "XUNFEI_TTS_VOICE": "xiaofeng"
        }):
            config = XunfeiConfig.from_env()

            assert config.app_id == "env_app_id"
            assert config.api_key == "env_api_key"
            assert config.api_secret == "env_api_secret"
            assert config.language == "en_us"
            assert config.tts_voice == "xiaofeng"

    def test_config_from_env_missing_credentials(self):
        """Test error handling when credentials are missing"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing Xunfei credentials"):
                XunfeiConfig.from_env()


class TestXunfeiAuth:
    """Test Xunfei authentication URL generation"""

    def test_tts_auth_url_format(self):
        """Test TTS authentication URL has correct format"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        tts = XunfeiTTS(config=config)

        auth_url = tts._create_auth_url()

        # Parse URL
        parsed = urlparse(auth_url)
        assert parsed.scheme == "wss"
        assert parsed.netloc == "tts-api.xfyun.cn"
        assert parsed.path == "/v2/tts"

        # Check query parameters
        params = parse_qs(parsed.query)
        assert "host" in params
        assert "date" in params
        assert "authorization" in params

    def test_stt_auth_url_format(self):
        """Test STT authentication URL has correct format"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        stt = XunfeiSTT(config=config)

        auth_url = stt._create_auth_url()

        # Parse URL
        parsed = urlparse(auth_url)
        assert parsed.scheme == "wss"
        assert parsed.netloc == "iat-api.xfyun.cn"
        assert parsed.path == "/v2/iat"

    def test_auth_signature_format(self):
        """Test authentication signature is properly encoded"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        tts = XunfeiTTS(config=config)

        auth_url = tts._create_auth_url()
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query)

        # Authorization should be base64-encoded
        auth_b64 = params["authorization"][0]
        try:
            auth_decoded = base64.b64decode(auth_b64).decode('utf-8')
            assert 'api_key="test_key"' in auth_decoded
            assert 'algorithm="hmac-sha256"' in auth_decoded
            assert 'signature=' in auth_decoded
        except Exception as e:
            pytest.fail(f"Authorization not properly base64-encoded: {e}")


class TestResamplingFunction:
    """Test audio resampling function"""

    def test_resample_basic(self):
        """Test basic 16kHz to 48kHz resampling"""
        import numpy as np

        # Create simple 16kHz test signal (100 samples)
        samples_16k = np.array([i for i in range(100)], dtype=np.int16)
        pcm_bytes_16k = samples_16k.tobytes()

        # Resample to 48kHz
        pcm_bytes_48k = resample_16k_to_48k(pcm_bytes_16k)
        samples_48k = np.frombuffer(pcm_bytes_48k, dtype=np.int16)

        # Should have 3x samples (simple linear interpolation)
        assert len(samples_48k) == len(samples_16k) * 3

    def test_resample_preserves_range(self):
        """Test resampling preserves value range"""
        import numpy as np

        # Create signal with full range
        samples_16k = np.array([0, 100, 200, -100, -200], dtype=np.int16)
        pcm_bytes_16k = samples_16k.tobytes()

        pcm_bytes_48k = resample_16k_to_48k(pcm_bytes_16k)
        samples_48k = np.frombuffer(pcm_bytes_48k, dtype=np.int16)

        # Min/max should be preserved approximately
        assert samples_48k.min() >= samples_16k.min() - 1
        assert samples_48k.max() <= samples_16k.max() + 1


class TestXunfeiSTT:
    """Test XunfeiSTT implementation"""

    def test_stt_initialization(self):
        """Test STT initialization"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        stt = XunfeiSTT(config=config)

        assert stt.config == config
        assert stt.ws_url == config.stt_endpoint

    def test_stt_capabilities(self):
        """Test STT reports correct capabilities"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        stt = XunfeiSTT(config=config)

        assert stt._capabilities.streaming is True
        assert stt._capabilities.interim_results is True

    @pytest.mark.asyncio
    async def test_stt_stream_creation(self):
        """Test STT stream can be created"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        stt = XunfeiSTT(config=config)

        stream = stt.stream()

        assert isinstance(stream, XunfeiSTTStream)
        assert stream._xunfei_stt == stt

        # Clean up
        await stream.aclose()


class TestXunfeiTTS:
    """Test XunfeiTTS implementation"""

    def test_tts_initialization(self):
        """Test TTS initialization"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret",
            tts_voice="xiaofeng"
        )
        tts = XunfeiTTS(config=config, voice="xiaofeng")

        assert tts.config == config
        assert tts.voice == "xiaofeng"
        assert tts.ws_url == config.tts_endpoint

    def test_tts_capabilities(self):
        """Test TTS reports correct capabilities"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        tts = XunfeiTTS(config=config)

        assert tts._capabilities.streaming is True

    @pytest.mark.asyncio
    async def test_tts_stream_creation(self):
        """Test TTS stream can be created"""
        config = XunfeiConfig(
            app_id="test_app",
            api_key="test_key",
            api_secret="test_secret"
        )
        tts = XunfeiTTS(config=config)

        stream = tts.stream()

        assert isinstance(stream, XunfeiTTSStream)
        assert stream._xunfei_tts == tts

        # Clean up
        await stream.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
class TestXunfeiWebSocketConnection:
    """
    Integration tests for live WebSocket connections.

    Requires valid Xunfei credentials in environment.
    Marked as integration tests - run with: pytest -m integration
    """

    @pytest.fixture
    def xunfei_config(self):
        """Load config from environment or skip test"""
        try:
            return XunfeiConfig.from_env()
        except ValueError:
            pytest.skip("Xunfei credentials not available in environment")

    async def test_stt_websocket_connection(self, xunfei_config):
        """Test STT can connect to WebSocket endpoint"""
        import websockets

        stt = XunfeiSTT(config=xunfei_config)
        auth_url = stt._create_auth_url()

        # Try to connect
        try:
            async with websockets.connect(auth_url, ping_interval=None) as ws:
                # Send initial params
                business_params = {
                    "common": {"app_id": xunfei_config.app_id},
                    "business": {
                        "language": xunfei_config.language,
                        "domain": "iat",
                        "accent": "mandarin",
                    },
                    "data": {
                        "status": 0,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": ""
                    }
                }

                await ws.send(str(business_params))

                # Should receive acknowledgment
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                assert response is not None

        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")

    async def test_tts_websocket_connection(self, xunfei_config):
        """Test TTS can connect to WebSocket endpoint"""
        import websockets

        tts = XunfeiTTS(config=xunfei_config)
        auth_url = tts._create_auth_url()

        # Try to connect
        try:
            async with websockets.connect(auth_url, ping_interval=None) as ws:
                # Send simple synthesis request
                request = {
                    "common": {"app_id": xunfei_config.app_id},
                    "business": {
                        "vcn": "xiaoyan",
                        "aue": "raw",
                        "tte": "UTF8"
                    },
                    "data": {
                        "text": base64.b64encode("测试".encode('utf-8')).decode('utf-8'),
                        "status": 2
                    }
                }

                await ws.send(str(request))

                # Should receive audio response
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                assert response is not None

        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
