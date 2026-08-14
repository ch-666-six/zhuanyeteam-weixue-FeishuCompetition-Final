import io
import wave

from httpx import AsyncClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.assignments.models import Assignment
from app.speech.xunfei import SpeechTranscriptionError, pcm_from_wav


def make_wav(seconds: float = 0.1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * int(16000 * seconds))
    return output.getvalue()


def test_pcm_from_wav_validates_xunfei_audio_contract() -> None:
    assert len(pcm_from_wav(make_wav())) == 3200
    try:
        pcm_from_wav(b"not a wav")
        assert False, "invalid WAV should fail"
    except SpeechTranscriptionError:
        pass


async def login(client: AsyncClient) -> str:
    response = await client.post("/api/v1/demo/login", json={"student_id": "student-grade-3"})
    return response.json()["access_token"]


async def test_transcription_requires_voice_assignment(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login(client)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "voice-create-text"}
    created = await client.post("/api/v1/sessions", headers=headers, json={"assignment_id": "assignment-grade-3"})
    response = await client.post(
        f"/api/v1/sessions/{created.json()['id']}/transcriptions?stage=initial",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "audio/wav"},
        content=make_wav(),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "VOICE_INPUT_NOT_ALLOWED"


async def test_voice_transcription_uses_backend_service(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as db, db.begin():
        db.get(Assignment, "assignment-grade-3").input_type = "VOICE"

    class StubTranscriber:
        async def transcribe_wav(self, payload: bytes) -> str:
            assert pcm_from_wav(payload)
            return "这是语音转写的答案。"

    client._transport.app.state.speech_transcriber = StubTranscriber()  # type: ignore[attr-defined]
    token = await login(client)
    created = await client.post(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "voice-create-voice"},
        json={"assignment_id": "assignment-grade-3"},
    )
    response = await client.post(
        f"/api/v1/sessions/{created.json()['id']}/transcriptions?stage=initial",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "audio/wav"},
        content=make_wav(),
    )
    assert response.status_code == 200
    assert response.json() == {"text": "这是语音转写的答案。"}
