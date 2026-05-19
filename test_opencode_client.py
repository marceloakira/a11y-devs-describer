import asyncio
import httpx

from config.settings import settings


async def test_session_create():
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{settings.opencode_url}/session", json={})
        print(f"Create session status: {resp.status_code}")
        data = resp.json()
        session_id = data.get("id")
        print(f"Session ID: {session_id}")
        return session_id


async def test_send_message(session_id: str):
    payload = {
        "parts": [{"type": "text", "text": "Diga apenas 'ok' em uma palavra."}],
        "model": {"modelID": settings.opencode_model, "providerID": "opencode"},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.opencode_url}/session/{session_id}/message",
            json=payload,
        )
        print(f"Send message status: {resp.status_code}")
        data = resp.json()
        parts = data.get("parts", [])
        for part in parts:
            if part.get("type") == "text":
                print(f"Response: {part.get('text', '')[:500]}")


async def main():
    print(f"Testing against: {settings.opencode_url}")
    print(f"Model: {settings.opencode_model}")
    print()

    session_id = await test_session_create()
    print()
    await test_send_message(session_id)


asyncio.run(main())
