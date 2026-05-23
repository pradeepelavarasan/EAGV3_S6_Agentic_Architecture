import httpx
import json
import os
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from crawl4ai import AsyncWebCrawler, CacheMode
from duckduckgo_search import DDGS

mcp = FastMCP("eag-v3-tools")

import contextlib
import sys

@mcp.tool()
async def fetch_url(url: str) -> str:
    """Fetch text content from a URL."""
    try:
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                async with AsyncWebCrawler(verbose=False) as crawler:
                    result = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
                    if not result.success:
                        return f"Failed to fetch {url}: {result.error_message}"
                    return result.markdown
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"

@mcp.tool()
async def search_web(query: str) -> str:
    """Search the web."""
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={"query": query, "api_key": api_key, "include_raw_content": False},
                    timeout=15.0
                )
                if r.status_code == 200:
                    data = r.json()
                    results = [f"Title: {res['title']}\nURL: {res['url']}\nContent: {res['content']}" for res in data.get('results', [])]
                    return "\n\n".join(results)
        except Exception as e:
            return f"Tavily Search error: {e}"
            
    # Fallback to DuckDuckGo if Tavily fails or is not configured
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"Title: {r.get('title')}\nURL: {r.get('href')}\nContent: {r.get('body')}")
        return "\n\n".join(results)
    except Exception as e:
        return f"DuckDuckGo search error: {e}"

@mcp.tool()
def get_weather(location: str, date: str = None) -> str:
    """Get weather forecast for a location."""
    d = date or 'today'
    return f"Weather in {location} on {d}: 72F, Sunny and pleasant. Perfect for outdoor activities."

@mcp.tool()
def create_calendar_reminder(title: str, date: str) -> str:
    """Create a calendar reminder."""
    return f"Successfully created calendar reminder: '{title}' on {date}."

@mcp.tool()
def get_current_time() -> str:
    """Get current time."""
    return str(datetime.now())

@mcp.tool()
def read_calendar(date: str) -> str:
    """Read calendar events for a date."""
    return f"No existing events on {date}."

if __name__ == "__main__":
    mcp.run(transport="stdio")
