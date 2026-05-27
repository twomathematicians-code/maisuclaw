"""
services/research.py — deep research agent
Breaks a broad question into sub-questions, searches the web for each,
extracts content from top results, and synthesizes a comprehensive report.

Designed to work with the maisuclaw Ollama stack and the browser search tool.
"""

import asyncio
import json
import re
from typing import Callable, Generator

from config import MODEL_GENERAL, OLLAMA_BASE_URL
from services.ollama import chat as ollama_chat


# ── types ──────────────────────────────────────────────────────────

# The ollama_chat_fn signature: (model, messages) -> str
OllamaChatFn = Callable[[str, list[dict]], str]

# The search_fn signature: (query, max_results) -> str (text with numbered results)
SearchFn = Callable[[str, int], str]


class ResearchAgent:
    """Multi-step research agent that decomposes queries, searches, and synthesizes.

    Usage:
        agent = ResearchAgent(ollama_chat, search_web)
        result = await agent.execute_research("How does quantum computing work?")
        # result = {"report": "...", "sources": [...], "sub_questions": [...]}

        # Or use the streaming version for progress updates:
        for event in agent.research_stream("What is RAG?"):
            print(event)
    """

    def __init__(
        self,
        ollama_chat_fn: OllamaChatFn,
        search_fn: SearchFn,
        model: str | None = None,
    ):
        """Initialize the research agent.

        Args:
            ollama_chat_fn: A function that takes (model, messages) and returns text.
                            Typically services.ollama.chat.
            search_fn: A function that takes (query, max_results) and returns search
                       results as text. Typically tools.browser.search_web.
            model: The model to use for planning and synthesis.
                   Defaults to MODEL_GENERAL from config.
        """
        self.ollama_chat = ollama_chat_fn
        self.search = search_fn
        self.model = model or MODEL_GENERAL

    # ── sub-question planning ─────────────────────────────────────

    def plan_research(self, query: str, depth: int = 2) -> list[str]:
        """Break a research query into focused sub-questions.

        Args:
            query: The user's research question.
            depth: How many levels of decomposition (1 = broad, 2 = detailed).
                   For now, only depth=1 produces sub-questions; depth=2 adds follow-ups.

        Returns:
            List of sub-question strings to investigate.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research planner. Given a research topic, break it into "
                    "3-5 specific, searchable sub-questions that together would give a "
                    "comprehensive understanding of the topic. Output ONLY a JSON array "
                    "of question strings. No explanation, no markdown, just the array."
                ),
            },
            {"role": "user", "content": f"Research topic: {query}"},
        ]

        try:
            response = self.ollama_chat(self.model, messages)
            # Extract JSON array from the response
            cleaned = response.strip()
            # Remove markdown code fences if present
            cleaned = re.sub(r"```json?\s*", "", cleaned)
            cleaned = re.sub(r"```", "", cleaned)
            cleaned = cleaned.strip()

            questions: list[str] = json.loads(cleaned)
            if not isinstance(questions, list):
                return [query]

            # Validate and clean
            valid = [str(q).strip() for q in questions if str(q).strip()]
            return valid if valid else [query]
        except (json.JSONDecodeError, Exception):
            # If LLM fails to produce valid JSON, fall back to simple decomposition
            return [query]

    # ── content extraction from search results ────────────────────

    def _extract_urls(self, search_text: str) -> list[str]:
        """Extract URLs from search result text.

        Search results typically have format:
          1. Title
             https://example.com
             Snippet text
        """
        url_pattern = re.compile(r"https?://[^\s\n]+")
        return list(set(url_pattern.findall(search_text)))

    def _scrape_url(self, url: str) -> str:
        """Try to fetch and extract text content from a URL.

        Uses requests for simple page fetching with basic HTML stripping.
        Returns extracted text or an error message.
        """
        try:
            import requests

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            # Basic HTML tag stripping
            text = resp.text
            # Remove script and style blocks
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            # Remove all remaining HTML tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()

            # Truncate to avoid sending enormous text to the LLM
            if len(text) > 4000:
                text = text[:4000] + "... [truncated]"

            return text
        except Exception as e:
            return f"[Failed to fetch {url}: {e}]"

    # ── parallel search ──────────────────────────────────────────

    def _search_all_questions(
        self, questions: list[str], max_sources: int
    ) -> dict[str, str]:
        """Search for all sub-questions in parallel (thread pool).

        Returns a dict mapping each question to its search results text.
        """
        results: dict[str, str] = {}

        def _do_search(q: str) -> tuple[str, str]:
            try:
                return q, self.search(q, max_results=max_sources)
            except Exception as e:
                return q, f"Search error: {e}"

        # Use ThreadPoolExecutor for blocking search functions
        with asyncio.ThreadPoolExecutor(max_workers=min(len(questions), 5)) as pool:
            loop = asyncio.new_event_loop()
            try:
                tasks = [
                    loop.run_in_executor(pool, _do_search, q)
                    for q in questions
                ]
                for future in asyncio.gather(*tasks, loop=loop):
                    q, text = future.result()
                    results[q] = text
            finally:
                loop.close()

        return results

    # ── full research execution ──────────────────────────────────

    def execute_research(
        self,
        query: str,
        max_sources: int = 5,
    ) -> dict:
        """Run a full multi-step research pipeline.

        Steps:
          1. Generate sub-questions from the query
          2. Search the web for each sub-question
          3. Extract content from top URLs found
          4. Synthesize all findings into a comprehensive report

        Args:
            query: The research question.
            max_sources: Maximum search results per sub-question.

        Returns:
            Dict with keys:
              - "report": str  — the synthesized research report
              - "sources": list[str] — URLs used as sources
              - "sub_questions": list[str] — the sub-questions investigated
        """
        # Step 1: Plan sub-questions
        sub_questions = self.plan_research(query)

        # Step 2: Search for each sub-question
        search_results = self._search_all_questions(sub_questions, max_sources)

        # Step 3: Extract content from top URLs
        all_sources: list[str] = []
        all_content_parts: list[str] = []

        for question, result_text in search_results.items():
            all_content_parts.append(f"## Question: {question}\n{result_text}")
            urls = self._extract_urls(result_text)
            all_sources.extend(urls[:3])  # Top 3 URLs per question

            # Try to scrape the first 2 URLs for deeper content
            for url in urls[:2]:
                scraped = self._scrape_url(url)
                if not scraped.startswith("[Failed"):
                    all_content_parts.append(
                        f"### Content from {url}\n{scraped}"
                    )

        # Deduplicate sources while preserving order
        seen: set[str] = set()
        unique_sources: list[str] = []
        for src in all_sources:
            if src not in seen:
                seen.add(src)
                unique_sources.append(src)

        # Step 4: Synthesize the report
        gathered = "\n\n---\n\n".join(all_content_parts)

        synthesis_messages = [
            {
                "role": "system",
                "content": (
                    "You are a research synthesizer. Given gathered information from multiple "
                    "sources, write a comprehensive, well-structured research report. "
                    "Include sections, key findings, and cite sources where relevant. "
                    "Be factual — if the sources contradict, note the disagreement. "
                    "If information is missing, say so rather than guessing."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"## Research Topic\n{query}\n\n"
                    f"## Gathered Information\n{gathered}\n\n"
                    "Write a comprehensive report based on the above information."
                ),
            },
        ]

        try:
            report = self.ollama_chat(self.model, synthesis_messages)
        except Exception as e:
            report = f"Error synthesizing report: {e}"

        return {
            "report": report,
            "sources": unique_sources,
            "sub_questions": sub_questions,
        }

    # ── streaming version ────────────────────────────────────────

    def research_stream(
        self,
        query: str,
        max_sources: int = 5,
    ) -> Generator[dict, None, None]:
        """Run research with yielding progress updates.

        Yields dicts with keys:
          - "stage": str  — current stage name
          - "message": str  — human-readable progress message
          - "data": any  — stage-specific data (optional)
          - "done": bool  — True on the final event

        The final event also contains the full result dict as "result".
        """
        # Stage 1: Planning
        yield {
            "stage": "planning",
            "message": "Decomposing research question into sub-questions...",
            "done": False,
        }

        try:
            sub_questions = self.plan_research(query)
        except Exception as e:
            yield {
                "stage": "error",
                "message": f"Failed to plan research: {e}",
                "done": True,
            }
            return

        yield {
            "stage": "planning",
            "message": f"Generated {len(sub_questions)} sub-questions",
            "data": {"sub_questions": sub_questions},
            "done": False,
        }

        # Stage 2: Searching
        yield {
            "stage": "searching",
            "message": f"Searching for {len(sub_questions)} sub-questions...",
            "done": False,
        }

        try:
            search_results = self._search_all_questions(sub_questions, max_sources)
        except Exception as e:
            yield {
                "stage": "error",
                "message": f"Search failed: {e}",
                "done": True,
            }
            return

        yield {
            "stage": "searching",
            "message": f"Search complete for {len(search_results)} questions",
            "data": {"questions_searched": list(search_results.keys())},
            "done": False,
        }

        # Stage 3: Extracting content
        yield {
            "stage": "extracting",
            "message": "Extracting content from top results...",
            "done": False,
        }

        all_sources: list[str] = []
        all_content_parts: list[str] = []

        for question, result_text in search_results.items():
            all_content_parts.append(f"## Question: {question}\n{result_text}")
            urls = self._extract_urls(result_text)
            all_sources.extend(urls[:3])

            for url in urls[:2]:
                scraped = self._scrape_url(url)
                if not scraped.startswith("[Failed"):
                    all_content_parts.append(
                        f"### Content from {url}\n{scraped}"
                    )
                    yield {
                        "stage": "extracting",
                        "message": f"Extracted content from {url[:60]}...",
                        "done": False,
                    }

        # Deduplicate sources
        seen: set[str] = set()
        unique_sources: list[str] = []
        for src in all_sources:
            if src not in seen:
                seen.add(src)
                unique_sources.append(src)

        # Stage 4: Synthesizing
        yield {
            "stage": "synthesizing",
            "message": "Synthesizing research report...",
            "done": False,
        }

        gathered = "\n\n---\n\n".join(all_content_parts)

        synthesis_messages = [
            {
                "role": "system",
                "content": (
                    "You are a research synthesizer. Given gathered information from multiple "
                    "sources, write a comprehensive, well-structured research report. "
                    "Include sections, key findings, and cite sources where relevant. "
                    "Be factual — if the sources contradict, note the disagreement. "
                    "If information is missing, say so rather than guessing."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"## Research Topic\n{query}\n\n"
                    f"## Gathered Information\n{gathered}\n\n"
                    "Write a comprehensive report based on the above information."
                ),
            },
        ]

        try:
            report = self.ollama_chat(self.model, synthesis_messages)
        except Exception as e:
            report = f"Error synthesizing report: {e}"

        result = {
            "report": report,
            "sources": unique_sources,
            "sub_questions": sub_questions,
        }

        # Final event
        yield {
            "stage": "complete",
            "message": "Research complete.",
            "data": result,
            "done": True,
            "result": result,
        }
