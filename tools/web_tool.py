"""
maisuclaw v0.3.0 — Tool: Web Search
Search the internet using DuckDuckGo (no API key required).
"""

import httpx
import re
from html import unescape


async def search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo HTML search."""
    if not query:
        return "Error: No search query provided"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )

            if resp.status_code != 200:
                return f"Error: Search returned status {resp.status_code}"

            html = resp.text
            results = []

            # Parse DuckDuckGo HTML results
            # Extract result blocks
            result_pattern = re.compile(
                r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL
            )

            matches = result_pattern.findall(html)

            for i, (url, title, snippet) in enumerate(matches[:num_results]):
                # Clean HTML tags
                title = re.sub(r'<[^>]+>', '', unescape(title)).strip()
                snippet = re.sub(r'<[^>]+>', '', unescape(snippet)).strip()
                url = unescape(url)

                results.append(
                    f"[{i+1}] {title}\n"
                    f"    URL: {url}\n"
                    f"    {snippet}"
                )

            if not results:
                return f"No results found for: {query}"

            return f"Search results for '{query}':\n\n" + "\n\n".join(results)

    except httpx.TimeoutException:
        return "Error: Search timed out. Please try again."
    except Exception as e:
        return f"Error performing search: {e}"


async def fetch_url(url: str) -> str:
    """Fetch and return text content from a URL."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            if resp.status_code != 200:
                return f"Error: HTTP {resp.status_code}"

            # Try to extract text from HTML
            text = _html_to_text(resp.text)
            if len(text) > 10000:
                text = text[:10000] + "\n\n... [truncated]"
            return text

    except Exception as e:
        return f"Error fetching URL: {e}"


def _html_to_text(html: str) -> str:
    """Rough HTML to text conversion."""
    # Remove script/style
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode entities
    text = unescape(text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text
