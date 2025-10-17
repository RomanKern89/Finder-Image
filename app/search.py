import json
from typing import Any, Dict, List

import httpx

from .config import get_settings
from .models import Product, SearchLog

settings = get_settings()

GOOGLE_ENDPOINT = "https://customsearch.googleapis.com/customsearch/v1"
OPENAI_IMAGE_ENDPOINT = "https://api.openai.com/v1/images/search"


class SearchError(Exception):
    """Raised when a provider request fails."""


def _log(session, product: Product | None, provider: str, request_payload: Dict[str, Any], response_payload: Dict[str, Any] | None, status: str, error_message: str | None = None) -> SearchLog:
    log = SearchLog(
        product=product,
        provider=provider,
        request_payload=json.dumps(request_payload, ensure_ascii=False, indent=2) if request_payload else None,
        response_payload=json.dumps(response_payload, ensure_ascii=False, indent=2) if response_payload else None,
        status=status,
        error_message=error_message,
    )
    session.add(log)
    session.flush()
    return log


def search_with_google(session, product: Product, query_override: str | None = None) -> List[Dict[str, Any]]:
    if not settings.google_api_key or not settings.google_cse_id:
        raise SearchError("Google Custom Search credentials are not configured.")

    query = query_override or f"{product.manufacturer} {product.sku}"
    payload = {
        "q": query,
        "cx": settings.google_cse_id,
        "searchType": "image",
        "num": 5,
        "key": settings.google_api_key,
    }

    _log(session, product, "google", payload, None, status="pending")

    with httpx.Client(timeout=30) as client:
        response = client.get(GOOGLE_ENDPOINT, params=payload)
    response_data = response.json()

    if response.status_code != 200:
        error_message = response_data.get("error", {}).get("message", response.text)
        _log(session, product, "google", payload, response_data, status="failed", error_message=error_message)
        raise SearchError(f"Google search failed: {error_message}")

    items = response_data.get("items", [])
    results: List[Dict[str, Any]] = []
    for item in items:
        link = item.get("link")
        if not link:
            continue
        results.append(
            {
                "image_url": link,
                "thumbnail_url": item.get("image", {}).get("thumbnailLink"),
                "title": item.get("title"),
                "provider": "google",
            }
        )

    _log(session, product, "google", payload, response_data, status="completed")
    return results


def search_with_openai(session, product: Product, query_override: str | None = None) -> List[Dict[str, Any]]:
    if not settings.openai_api_key:
        raise SearchError("OpenAI API key is not configured.")

    query = query_override or f"high quality product photo of {product.manufacturer} {product.sku}"
    payload = {
        "model": "gpt-image-1",
        "query": query,
        "size": "1024x1024",
        "quality": "high",
        "n": 4,
    }

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    _log(session, product, "openai", payload, None, status="pending")

    with httpx.Client(timeout=60) as client:
        response = client.post(OPENAI_IMAGE_ENDPOINT, headers=headers, json=payload)
    response_data = response.json()

    if response.status_code != 200:
        error_message = response_data.get("error", {}).get("message", response.text)
        _log(session, product, "openai", payload, response_data, status="failed", error_message=error_message)
        raise SearchError(f"OpenAI image search failed: {error_message}")

    data = response_data.get("data", [])
    results: List[Dict[str, Any]] = []
    for entry in data:
        url = entry.get("url") or entry.get("b64_json")
        if not url:
            continue
        results.append(
            {
                "image_url": url,
                "thumbnail_url": entry.get("thumbnail") or url,
                "title": entry.get("revised_prompt"),
                "provider": "openai",
            }
        )

    _log(session, product, "openai", payload, response_data, status="completed")
    return results
