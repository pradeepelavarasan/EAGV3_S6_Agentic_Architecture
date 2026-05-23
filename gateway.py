import httpx
import os

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8300/v1/chat")

async def generate(
    messages: list[dict],
    auto_route: str = None,
    provider: str = None,
    temperature: float = 0.7,
    response_format: dict = None,
) -> dict:
    """
    Calls the local V3 Gateway.
    """
    payload = {
        "messages": messages,
        "temperature": temperature
    }
    
    if auto_route:
        payload["auto_route"] = auto_route
    if provider:
        payload["provider"] = provider
        
    if response_format:
        payload["response_format"] = response_format

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            GATEWAY_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(f"[Gateway HTTP Error] {exc.response.status_code}: {exc.response.text}")
            raise
        data = response.json()
        return data
