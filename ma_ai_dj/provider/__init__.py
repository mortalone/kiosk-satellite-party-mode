"""Music Assistant plugin bridge to the existing Party AI DJ addon."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientTimeout
from music_assistant_models.auth import Scope, UserRole
from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.enums import ConfigEntryType
from music_assistant_models.errors import (
    InvalidDataError,
    MusicAssistantError,
    SetupFailedError,
)
from music_assistant_models.media_items import Track

from music_assistant.controllers.webserver.helpers.auth_middleware import (
    get_current_client_id,
    get_current_token,
    get_current_user,
)
from music_assistant.helpers.provider_access import visible_playback_sources
from music_assistant.models.plugin import PluginProvider

from .bridge import DjBridge

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ProviderConfig
    from music_assistant_models.provider import ProviderManifest

    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType
    from music_assistant.providers.party import PartyPlugin


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize the AI DJ plugin."""
    return PartyAiDj(mass, manifest, config, set())


class PartyAiDj(PluginProvider):
    """Expose AI suggestions while keeping MA's existing guest queue actions."""

    async def handle_async_init(self) -> None:
        """Validate the host-controlled connection."""
        self._base = str(self.get_setup_value("addon_url") or "").rstrip("/")
        parsed = urlsplit(self._base)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.query
            or parsed.fragment
        ):
            raise SetupFailedError("Enter the addon's HTTP(S) address without a token or query")
        self._token = str(self.get_setup_value("addon_token") or "")
        if len(self._token) < 24:
            raise SetupFailedError("The addon token must contain at least 24 characters")
        self._bridge = DjBridge(self._request)
        self._unregister: list[Callable[[], None]] = []

    async def get_config_entries(self) -> tuple[ConfigEntry, ...]:
        """Return connection settings visible only to the MA host."""
        return (ConfigEntry(key="guest_ai", type=ConfigEntryType.BOOLEAN, default_value=True),)

    async def loaded_in_mass(self) -> None:
        """Register authenticated commands; there is deliberately no enqueue endpoint."""
        for name, handler in (
            ("config", self.dj_config),
            ("suggest", self.suggest),
            ("job", self.job),
        ):
            self._unregister.append(
                self.mass.register_api_command(
                    "ai_dj/" + name, handler, required_scope=Scope.LIBRARY_READ
                )
            )

    async def unload(self, is_removed: bool = False) -> None:
        """Remove the bridge commands."""
        for remove in self._unregister:
            remove()
        await super().unload(is_removed)

    async def dj_config(self) -> dict[str, bool]:
        """Report whether this session may use AI, without exposing credentials."""
        try:
            await self._session()
        except InvalidDataError:
            return {"enabled": False}
        return {"enabled": True}

    async def suggest(self, prompt: str, count: int = 8) -> dict[str, Any]:
        """Create an AI request from the current authenticated Party session."""
        owner, queue = await self._session()
        try:
            return await self._bridge.suggest(owner, queue, prompt, count)
        except ValueError as error:
            raise InvalidDataError(str(error)) from error

    async def job(self, job_id: str) -> dict[str, Any]:
        """Read suggestions, checking the caller's current music-source access."""
        owner, queue = await self._session()
        try:
            result = await self._bridge.job(owner, queue, job_id)
        except ValueError as error:
            raise InvalidDataError(str(error)) from error
        if result.get("state") != "ready":
            return result
        visible = visible_playback_sources(self.mass, get_current_user())
        tracks = []
        for raw in result.get("tracks", [])[:12]:
            try:
                track = await self.mass.music.get_item_by_uri(
                    raw["uri"], allow_update_metadata=False
                )
                if not isinstance(track, Track) or not track.available:
                    continue
                if visible is not None and not any(
                    mapping.provider_instance in visible and mapping.available
                    for mapping in track.provider_mappings
                ):
                    continue
                tracks.append(track.to_dict())
            except KeyError, TypeError, MusicAssistantError:
                continue
        result["tracks"] = tracks
        return result

    async def _session(self) -> tuple[str, str]:
        user = get_current_user()
        party = cast("PartyPlugin | None", self.mass.get_provider("party"))
        if user is None or party is None or not party.available:
            raise InvalidDataError("Open AI DJ from an authenticated Party session")
        if user.role == UserRole.GUEST and (
            user.username != "party_guest"
            or not party.config.get_value("enable_guest_access")
            or not self.get_config_value("guest_ai", True)
        ):
            raise InvalidDataError("AI guest access is disabled")
        queue = await party.get_party_player()
        if not queue:
            raise InvalidDataError("Choose the Party player first")
        capability = get_current_token() or get_current_client_id() or user.user_id
        owner = hashlib.sha256((user.user_id + ":" + capability).encode()).hexdigest()
        return owner, queue

    async def _request(self, path: str, data: dict[str, Any] | None) -> dict[str, Any]:
        try:
            async with self.mass.http_session.request(
                "POST" if data is not None else "GET",
                self._base + path,
                json=data,
                headers={"Authorization": "Bearer " + self._token},
                timeout=ClientTimeout(total=10),
                allow_redirects=False,
            ) as response:
                if response.status not in {200, 202}:
                    raise InvalidDataError(
                        "AI DJ addon refused the request; check the connection or try later"
                    )
                if response.content_length and response.content_length > 512_000:
                    raise InvalidDataError("AI response too large")
                payload = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    payload.extend(chunk)
                    if len(payload) > 512_000:
                        raise InvalidDataError("AI response too large")
                value = json.loads(payload)
                if not isinstance(value, dict):
                    raise InvalidDataError("Invalid AI response")
                return value
        except (ClientError, TimeoutError, ValueError) as error:
            raise InvalidDataError("Could not connect to the AI DJ addon") from error
