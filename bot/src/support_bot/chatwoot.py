from typing import Protocol

import httpx


class Inbox(Protocol):
    async def conversation(self, account_id: int, conversation_id: int) -> dict: ...
    async def reply(self, account_id: int, conversation_id: int, text: str) -> None: ...
    async def private_note(self, account_id: int, conversation_id: int, text: str) -> None: ...
    async def hand_off(self, account_id: int, conversation_id: int) -> None: ...


class ChatwootClient:
    """Chatwoot Application API, authenticated as the agent bot."""

    def __init__(self, base_url: str, bot_token: str, team_id: int | None = None, timeout: float = 15):
        self.team_id = team_id
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout, headers={"api_access_token": bot_token})

    def _conv(self, account_id: int, conversation_id: int) -> str:
        return f"/api/v1/accounts/{account_id}/conversations/{conversation_id}"

    async def _post(self, path: str, body: dict) -> None:
        r = await self.client.post(path, json=body)
        r.raise_for_status()

    async def conversation(self, account_id: int, conversation_id: int) -> dict:
        r = await self.client.get(self._conv(account_id, conversation_id))
        r.raise_for_status()
        return r.json()

    async def reply(self, account_id: int, conversation_id: int, text: str) -> None:
        await self._post(f"{self._conv(account_id, conversation_id)}/messages", {"content": text, "message_type": "outgoing"})

    async def private_note(self, account_id: int, conversation_id: int, text: str) -> None:
        await self._post(
            f"{self._conv(account_id, conversation_id)}/messages",
            {"content": text, "message_type": "outgoing", "private": True},
        )

    async def hand_off(self, account_id: int, conversation_id: int) -> None:
        if self.team_id:
            await self._post(f"{self._conv(account_id, conversation_id)}/assignments", {"team_id": self.team_id})
        await self._post(f"{self._conv(account_id, conversation_id)}/toggle_status", {"status": "open"})
