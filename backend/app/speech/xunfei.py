from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import io
import json
from urllib.parse import urlencode, urlparse
import wave

from websockets.asyncio.client import connect


class SpeechTranscriptionError(RuntimeError):
    pass


def pcm_from_wav(payload: bytes) -> bytes:
    try:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
                raise SpeechTranscriptionError("录音必须为 16kHz 单声道 PCM。")
            if audio.getcomptype() != "NONE":
                raise SpeechTranscriptionError("不支持压缩的 WAV 录音。")
            frames = audio.readframes(audio.getnframes())
    except (EOFError, wave.Error) as exc:
        raise SpeechTranscriptionError("录音文件格式无效。") from exc
    if not frames:
        raise SpeechTranscriptionError("录音内容为空。")
    if len(frames) > 16000 * 2 * 60:
        raise SpeechTranscriptionError("单次录音不能超过 60 秒。")
    return frames


@dataclass
class XunfeiTranscriber:
    app_id: str
    api_key: str
    api_secret: str
    endpoint: str

    def _signed_url(self) -> str:
        parsed = urlparse(self.endpoint)
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        request_line = f"GET {parsed.path} HTTP/1.1"
        signature_origin = f"host: {parsed.netloc}\ndate: {date}\n{request_line}"
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), signature_origin.encode(), hashlib.sha256).digest()
        ).decode()
        authorization = base64.b64encode(
            (
                f'api_key="{self.api_key}", algorithm="hmac-sha256", '
                f'headers="host date request-line", signature="{signature}"'
            ).encode()
        ).decode()
        return f"{self.endpoint}?{urlencode({'authorization': authorization, 'date': date, 'host': parsed.netloc})}"

    async def transcribe_wav(self, payload: bytes) -> str:
        if not self.app_id or not self.api_key or not self.api_secret:
            raise SpeechTranscriptionError("语音识别服务尚未配置。")
        pcm = pcm_from_wav(payload)
        segments: dict[int, str] = {}
        try:
            async with connect(self._signed_url(), open_timeout=10, close_timeout=5) as socket:
                for offset in range(0, len(pcm), 1280):
                    chunk = pcm[offset:offset + 1280]
                    first = offset == 0
                    frame = {
                        "data": {
                            "status": 0 if first else 1,
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": base64.b64encode(chunk).decode(),
                        }
                    }
                    if first:
                        frame["common"] = {"app_id": self.app_id}
                        frame["business"] = {"language": "zh_cn", "domain": "iat", "accent": "mandarin", "dwa": "wpgs"}
                    await socket.send(json.dumps(frame))
                    await asyncio.sleep(0.04)
                await socket.send(json.dumps({"data": {"status": 2, "format": "audio/L16;rate=16000", "encoding": "raw", "audio": ""}}))

                while True:
                    message = json.loads(await asyncio.wait_for(socket.recv(), timeout=15))
                    if message.get("code") != 0:
                        raise SpeechTranscriptionError(f"讯飞语音识别失败：{message.get('message', message.get('code'))}")
                    data = message.get("data") or {}
                    result = data.get("result") or {}
                    text = "".join(item.get("cw", [{}])[0].get("w", "") for item in result.get("ws", []))
                    if text:
                        if result.get("pgs") == "rpl" and result.get("rg"):
                            start, end = result["rg"]
                            for index in range(start, end + 1):
                                segments.pop(index, None)
                        segments[int(result.get("sn", len(segments)))] = text
                    if data.get("status") == 2:
                        break
        except SpeechTranscriptionError:
            raise
        except Exception as exc:
            raise SpeechTranscriptionError("暂时无法连接科大讯飞语音识别服务。") from exc
        transcript = "".join(segments[index] for index in sorted(segments)).strip()
        if not transcript:
            raise SpeechTranscriptionError("没有识别到清晰的语音，请重新录制。")
        return transcript
