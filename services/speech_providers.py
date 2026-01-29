"""
Speech provider factory for BestBox LiveKit agent.

Manages selection between local and cloud-based speech services.
"""

import logging
import os
from enum import Enum
from typing import Tuple

logger = logging.getLogger("speech-providers")


class SpeechProvider(Enum):
    """Available speech providers"""
    LOCAL = "local"
    XUNFEI = "xunfei"


def get_speech_provider() -> SpeechProvider:
    """
    Get configured speech provider from environment.

    Returns:
        SpeechProvider enum value

    Environment:
        SPEECH_PROVIDER: "local" or "xunfei" (default: local)
    """
    provider_str = os.getenv("SPEECH_PROVIDER", "local").lower()

    try:
        return SpeechProvider(provider_str)
    except ValueError:
        logger.warning(f"Invalid SPEECH_PROVIDER '{provider_str}', defaulting to local")
        return SpeechProvider.LOCAL


async def create_stt():
    """
    Create STT instance based on configured provider.

    Returns:
        STT instance (XunfeiSTT or LocalSTT)

    Raises:
        Exception: If provider initialization fails
    """
    provider = get_speech_provider()

    if provider == SpeechProvider.XUNFEI:
        try:
            logger.info("Creating Xunfei STT...")
            from services.xunfei_adapters import XunfeiSTT, XunfeiConfig

            config = XunfeiConfig.from_env()
            return XunfeiSTT(config=config)
        except Exception as e:
            logger.error(f"❌ Failed to create Xunfei STT: {e}")
            raise e

    elif provider == SpeechProvider.LOCAL:
        logger.info("Creating local STT...")
        from services.livekit_local import LocalSTT, get_shared_asr

        # Use shared ASR instance to prevent memory accumulation
        shared_asr = await get_shared_asr()
        return LocalSTT(asr_instance=shared_asr)

    else:
        raise ValueError(f"Unknown provider: {provider}")


async def create_tts():
    """
    Create TTS instance based on configured provider.

    Returns:
        TTS instance (XunfeiTTS or LocalTTS)

    Raises:
        Exception: If provider initialization fails
    """
    provider = get_speech_provider()

    if provider == SpeechProvider.XUNFEI:
        try:
            logger.info("Creating Xunfei TTS...")
            from services.xunfei_adapters import XunfeiTTS, XunfeiConfig

            config = XunfeiConfig.from_env()
            return XunfeiTTS(config=config, voice=config.tts_voice)
        except Exception as e:
            logger.error(f"❌ Failed to create Xunfei TTS: {e}")
            raise e

    elif provider == SpeechProvider.LOCAL:
        logger.info("Creating local TTS...")
        from services.livekit_local import LocalTTS, get_shared_tts

        # Use shared TTS instance to prevent memory accumulation
        shared_tts = await get_shared_tts()
        return LocalTTS(tts_instance=shared_tts)

    else:
        raise ValueError(f"Unknown provider: {provider}")


async def create_speech_config() -> Tuple[object, object]:
    """
    Create both STT and TTS with fallback handling.

    Returns:
        Tuple of (stt, tts) instances

    Raises:
        Exception: If provider initialization fails
    """
    provider = get_speech_provider()

    try:
        stt = await create_stt()
        tts = await create_tts()
        logger.info(f"✅ Speech provider configured: {provider.value}")
        return stt, tts
    except Exception as e:
        logger.error(f"❌ Failed to create {provider.value} speech provider: {e}")
        raise
