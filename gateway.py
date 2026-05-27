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

    import asyncio
    
    max_retries = 3
    for attempt in range(max_retries):
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    GATEWAY_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                print(f"[Gateway HTTP Error] {exc.response.status_code}: {exc.response.text}")
                if exc.response.status_code == 503 and attempt < max_retries - 1:
                    print(f"[Gateway] All providers unavailable. Waiting 15 seconds before retry {attempt + 2}/{max_retries}...")
                    await asyncio.sleep(15)
                    continue
                raise
            except httpx.TimeoutException as exc:
                print(f"[Gateway Timeout Error] The request took longer than 120 seconds.")
                if attempt < max_retries - 1:
                    print(f"[Gateway] Waiting 10 seconds before retry {attempt + 2}/{max_retries}...")
                    await asyncio.sleep(10)
                    continue
                raise Exception("Gateway request timed out after 120 seconds.")
            
            data = response.json()
            return data
