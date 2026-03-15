"""Service C - Tight coupling scenario (calls both A and B)."""
import requests
import httpx


def get_user_and_enrich(user_id: str) -> dict:
    """Call service A and service B - tight coupling pattern."""
    user_response = requests.get(f"http://service-a:8000/api/users/{user_id}")
    user = user_response.json()

    enrichment = requests.get(f"http://service-b:8000/api/enrich/{user_id}")
    user["enrichment"] = enrichment.json()

    return user


def sync_user_data(user_id: str) -> None:
    """Another call to service A - chatty interface pattern."""
    requests.post(f"http://service-a:8000/api/users/{user_id}/sync")
    requests.post(f"http://service-a:8000/api/users/{user_id}/validate")
    requests.post(f"http://service-a:8000/api/users/{user_id}/notify")
    requests.post(f"http://service-a:8000/api/users/{user_id}/audit")


async def get_service_b_status() -> dict:
    """Async HTTP call to service B."""
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://service-b:8000/api/status")
        return resp.json()
