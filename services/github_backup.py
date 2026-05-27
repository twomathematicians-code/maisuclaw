"""
maisuclaw v0.3.0 — GitHub Backup Service
Backs up chat history to a GitHub repository.
"""

import json
import httpx
from datetime import datetime
from typing import Optional

from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BACKUP_BRANCH


class GitHubBackup:
    """Back up conversations to GitHub."""

    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repo = GITHUB_REPO
        self.branch = GITHUB_BACKUP_BRANCH
        self.base_url = "https://api.github.com"

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.repo)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def backup_conversation(self, conv_id: str, title: str, messages: list[dict]):
        """Backup a conversation to GitHub."""
        if not self.is_configured:
            return {"status": "not_configured", "message": "GitHub token/repo not set"}

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = f"chats/{conv_id}_{timestamp}.json"
        content = json.dumps({
            "conversation_id": conv_id,
            "title": title,
            "backed_up_at": datetime.utcnow().isoformat(),
            "messages": messages,
        }, indent=2, ensure_ascii=False)

        # Convert to base64
        import base64
        b64_content = base64.b64encode(content.encode()).decode()

        # Check if branch exists, create if not
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check/create branch
            default_resp = await client.get(
                f"{self.base_url}/repos/{self.repo}",
                headers=self._headers()
            )
            if default_resp.status_code != 200:
                return {"status": "error", "message": f"Cannot access repo: {default_resp.status_code}"}

            default_branch = default_resp.json().get("default_branch", "main")
            sha_resp = await client.get(
                f"{self.base_url}/repos/{self.repo}/git/ref/heads/{self.branch}",
                headers=self._headers()
            )
            if sha_resp.status_code == 404:
                # Create branch from default
                ref_resp = await client.get(
                    f"{self.base_url}/repos/{self.repo}/git/ref/heads/{default_branch}",
                    headers=self._headers()
                )
                if ref_resp.status_code != 200:
                    return {"status": "error", "message": "Cannot get default branch SHA"}
                sha = ref_resp.json()["object"]["sha"]
                await client.post(
                    f"{self.base_url}/repos/{self.repo}/git/refs",
                    headers=self._headers(),
                    json={"ref": f"refs/heads/{self.branch}", "sha": sha}
                )

            # Create or update file
            # First check if file exists
            existing = await client.get(
                f"{self.base_url}/repos/{self.repo}/contents/{path}",
                headers=self._headers(),
                params={"ref": self.branch}
            )
            payload = {
                "message": f"Backup chat: {title}",
                "content": b64_content,
                "branch": self.branch,
            }
            if existing.status_code == 200:
                payload["sha"] = existing.json()["sha"]

            resp = await client.put(
                f"{self.base_url}/repos/{self.repo}/contents/{path}",
                headers=self._headers(),
                json=payload
            )

            if resp.status_code in (200, 201):
                return {"status": "success", "path": path}
            else:
                return {"status": "error", "message": resp.text}


github_backup = GitHubBackup()
