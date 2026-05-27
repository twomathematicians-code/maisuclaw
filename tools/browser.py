"""
tools/browser.py — web search / scrape via Playwright (optional)
"""
import asyncio
from pathlib import Path


async def _search(query: str, max_results: int = 5) -> str:
    """Use Playwright to do a DuckDuckGo search and return snippets."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(f"https://lite.duckduckgo.com/lite?q={query}", timeout=15000)
            await page.wait_for_selector("td.result-link", timeout=10000)

            links = await page.query_selector_all("td.result-link a")
            snippets = await page.query_selector_all("td.result-snippet")

            results = []
            for i in range(min(len(links), max_results)):
                link_el = links[i]
                title = await link_el.inner_text()
                href = await link_el.get_attribute("href")
                snippet = ""
                if i < len(snippets):
                    snippet = await snippets[i].inner_text()
                results.append(f"{i+1}. {title}\n   {href}\n   {snippet}\n")

            await browser.close()
            return "\n".join(results) if results else "(no results found)"

    except ImportError:
        return "Error: Playwright is not installed. Run: pip install playwright && playwright install"
    except Exception as e:
        return f"Error during search: {e}"


def search_web(query: str, max_results: int = 5) -> str:
    """Blocking wrapper for the async search function."""
    return asyncio.run(_search(query, max_results))
