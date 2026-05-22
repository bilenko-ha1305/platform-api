"""GitHub API data fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


async def get_recent_commits(
    token: str,
    repo: str,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Fetch recent commits from a GitHub repository.

    :param token: GitHub personal access token.
    :param repo: Repository in 'owner/repo' format.
    :param days_back: Days of commit history to retrieve.
    :return: List of commits with message, author, and date.
    """
    since = (datetime.now(tz=UTC) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo}/commits",
            params={"since": since, "per_page": 50},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        commits = response.json()

    results: list[dict[str, Any]] = []
    for c in commits:
        commit = c.get("commit", {})
        author = commit.get("author", {})
        results.append(
            {
                "sha": c.get("sha", "")[:8],
                "message": commit.get("message", "").split("\n")[0][:200],
                "author": author.get("name"),
                "date": author.get("date"),
                "url": c.get("html_url"),
            }
        )

    return results


async def get_recent_releases(
    token: str,
    repo: str,
) -> list[dict[str, Any]]:
    """Fetch the 10 most recent GitHub releases.

    :param token: GitHub personal access token.
    :param repo: Repository in 'owner/repo' format.
    :return: List of releases with tag, name, and publish date.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo}/releases",
            params={"per_page": 10},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        releases = response.json()

    return [
        {
            "tag": r.get("tag_name"),
            "name": r.get("name"),
            "published_at": r.get("published_at"),
            "prerelease": r.get("prerelease", False),
            "body_preview": (r.get("body") or "")[:300],
        }
        for r in releases
    ]
