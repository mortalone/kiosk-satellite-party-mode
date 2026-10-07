"""Capability isolation and throttling for the Music Assistant AI DJ bridge."""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from typing import Any


class DjBridge:
    """Keep addon job capabilities private to their originating MA session."""

    def __init__(self, request: Callable[..., Awaitable[dict[str, Any]]]) -> None:
        """Bind the private addon transport."""
        self.request = request
        self.jobs: dict[str, tuple[str, str, float]] = {}
        self.last_request: dict[str, float] = {}

    async def suggest(self, owner: str, queue: str, prompt: str, count: int) -> dict[str, Any]:
        """Create a bounded suggestion job for one session and queue."""
        if not owner or not queue:
            raise ValueError("No authenticated Party session")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1000:
            raise ValueError("Write a music request of 1-1000 characters")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 12:
            raise ValueError("Choose 1-12 tracks")
        now = time.monotonic()
        self.jobs = {key: value for key, value in self.jobs.items() if now - value[2] < 1800}
        self.last_request = {
            key: value for key, value in self.last_request.items() if now - value < 1800
        }
        if now - self.last_request.get(owner, -1000) < 30:
            raise ValueError("Please wait 30 seconds between AI requests")
        if len(self.jobs) >= 64 or len(self.last_request) >= 128:
            raise ValueError("AI DJ is busy; try later")
        self.last_request[owner] = now
        result = await self.request("/api/suggest", {"prompt": prompt.strip(), "count": count})
        job_id = result.get("id")
        if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", job_id):
            raise ValueError("Invalid AI job response")
        self.jobs[job_id] = (owner, queue, now)
        return {"id": job_id}

    async def job(self, owner: str, queue: str, job_id: str) -> dict[str, Any]:
        """Read a job only from the session and queue that created it."""
        job = self.jobs.get(job_id)
        if job is None or job[:2] != (owner, queue) or time.monotonic() - job[2] >= 1800:
            raise ValueError("AI request expired or belongs to another session")
        result = await self.request("/api/jobs/" + job_id, None)
        return {
            key: result[key]
            for key in ("id", "state", "progress", "tracks", "error")
            if key in result
        }
