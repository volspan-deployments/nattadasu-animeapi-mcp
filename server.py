from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import httpx
import os
from typing import Optional

mcp = FastMCP("AnimeAPI")

BASE_URL = "https://animeapi.my.id"


@mcp.tool()
async def get_anime_relations(platform: str, id: str) -> dict:
    """Fetch anime relation mapping data for a specific anime title from a given platform/database.
    Use this to find cross-database IDs for an anime (e.g., get the MyAnimeList ID from an AniList ID, or vice versa).
    Supported platforms: anilist, anidb, annict, anisearch, kitsu, letterboxd, livechart, myanimelist, notify, otakotaku, shikimori, shoboi, simkl, themoviedb, thetvdb, trakt, nautiljon, animeplanet
    """
    url = f"{BASE_URL}/{platform}/{id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code == 404:
            return {"error": "Not found", "platform": platform, "id": id, "status_code": 404}
        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}", "platform": platform, "id": id}
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}


@mcp.tool()
async def get_api_status() -> dict:
    """Get the current status and statistics of the AnimeAPI service, including total number of entries,
    supported platforms, last update time, and service health.
    """
    url = f"{BASE_URL}/status"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}"}
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}


@mcp.tool()
async def get_updated_datetime() -> dict:
    """Retrieve the date and time when the AnimeAPI database was last updated.
    Use this to check data freshness or to determine if a re-sync is needed.
    """
    url = f"{BASE_URL}/updated"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}"}
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}


@mcp.tool()
async def get_latency_report() -> dict:
    """Fetch the latency report for the AnimeAPI service, showing response time metrics.
    Use this for performance monitoring or debugging slow responses.
    """
    url = f"{BASE_URL}/latency"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}"}
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}


@mcp.tool()
async def get_master_array() -> dict:
    """Retrieve all anime relation mappings as a complete JSON array (the master array).
    Warning: this can be a very large response. Use only when bulk data is needed.
    """
    url = f"{BASE_URL}/masterArray"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}"}
        try:
            data = response.json()
            if isinstance(data, list):
                return {"count": len(data), "entries": data}
            return data
        except Exception:
            return {"raw": response.text[:5000], "note": "Response truncated for display"}


@mcp.tool()
async def get_tsv_export() -> dict:
    """Download all anime relation mapping data as a TSV (Tab Separated Values) file.
    Returns the TSV content as text for analysis or import into other tools.
    Warning: this can be a very large response.
    """
    url = f"{BASE_URL}/animeapi.tsv"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return {"error": f"API returned status {response.status_code}"}
        content = response.text
        lines = content.split("\n")
        headers = lines[0].split("\t") if lines else []
        return {
            "format": "TSV",
            "total_lines": len(lines),
            "columns": headers,
            "preview_rows": lines[1:6],
            "download_url": url,
            "note": "Full TSV content available at the download_url. Preview shows first 5 data rows."
        }


@mcp.tool()
async def redirect_to_provider(
    platform: str,
    id: str,
    target_platform: Optional[str] = None
) -> dict:
    """Get a redirect URL or follow a redirect to an anime's page on a specific provider/platform.
    Use this to link a user directly to an anime's page on a particular database given its ID on another platform.
    """
    if target_platform:
        url = f"{BASE_URL}/redirect/{platform}/{id}/{target_platform}"
    else:
        url = f"{BASE_URL}/redirect/{platform}/{id}"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        response = await client.get(url)
        result = {
            "source_platform": platform,
            "source_id": id,
            "target_platform": target_platform,
            "status_code": response.status_code,
            "request_url": url
        }
        if response.status_code in (301, 302, 303, 307, 308):
            result["redirect_url"] = response.headers.get("location", "")
            result["message"] = "Redirect URL retrieved successfully"
        elif response.status_code == 200:
            try:
                result["data"] = response.json()
            except Exception:
                result["raw"] = response.text
        elif response.status_code == 404:
            result["error"] = "No redirect found for this platform/ID combination"
        else:
            result["error"] = f"API returned status {response.status_code}"
            try:
                result["details"] = response.json()
            except Exception:
                result["raw"] = response.text
        return result


@mcp.tool()
async def search_anime_by_title(
    query: str,
    limit: int = 10
) -> dict:
    """Search for anime relation mappings by title using fuzzy matching.
    Use this when you have an anime name but no specific database ID.
    """
    url = f"{BASE_URL}/search"
    params = {"q": query, "limit": limit}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        if response.status_code == 404:
            return {"results": [], "query": query, "message": "No results found"}
        if response.status_code != 200:
            # Try alternative search endpoint
            alt_url = f"{BASE_URL}/search/{query}"
            response = await client.get(alt_url)
            if response.status_code != 200:
                return {
                    "error": f"Search API returned status {response.status_code}",
                    "query": query
                }
        try:
            data = response.json()
            if isinstance(data, list):
                limited = data[:limit]
                return {
                    "query": query,
                    "total_found": len(data),
                    "returned": len(limited),
                    "results": limited
                }
            return {"query": query, "data": data}
        except Exception:
            return {"raw": response.text, "query": query}




_SERVER_SLUG = "nattadasu-animeapi"

def _track(tool_name: str, ua: str = ""):
    try:
        import urllib.request, json as _json
        data = _json.dumps({"slug": _SERVER_SLUG, "event": "tool_call", "tool": tool_name, "user_agent": ua}).encode()
        req = urllib.request.Request("https://www.volspan.dev/api/analytics/event", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

sse_app = mcp.http_app(transport="sse")

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", sse_app),
    ],
    lifespan=sse_app.lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
