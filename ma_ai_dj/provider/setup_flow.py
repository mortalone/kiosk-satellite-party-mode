"""Collect the existing addon connection in Music Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.enums import ConfigEntryType

if TYPE_CHECKING:
    from music_assistant.models.setup_flow import SetupSession


async def run_setup(session: SetupSession) -> None:
    """Configure the bridge without passing its token to the guest browser."""
    values = await session.form(
        [
            ConfigEntry(
                key="addon_url",
                type=ConfigEntryType.STRING,
                required=True,
                value=session.context.setup_data.get("addon_url"),
            ),
            ConfigEntry(key="addon_token", type=ConfigEntryType.SECURE_STRING, required=True),
        ],
        step_id="connection",
        last_step=True,
    )
    await session.finish(values)
