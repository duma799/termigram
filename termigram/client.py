from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import User, Chat, Channel

load_dotenv()

API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_PATH = str(Path.home() / ".termigram_session")


class TGClient:
    _instance: TGClient | None = None

    def __new__(cls) -> TGClient:
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._client: TelegramClient | None = None
            inst._loop: asyncio.AbstractEventLoop | None = None
            inst._thread: threading.Thread | None = None
            inst._on_new_message = None
            inst._started = False
            inst._ready = threading.Event()
            cls._instance = inst
        return cls._instance

    def _ensure_loop(self) -> None:
        if self._started:
            self._ready.wait()
            return
        self._started = True

        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
            self._client.add_event_handler(
                self._handle_new_message, events.NewMessage
            )
            self._ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        self._ready.wait()

    def _call(self, coro):
        if not asyncio.iscoroutine(coro):
            async def _wrap():
                return await coro
            coro = _wrap()
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=60)

    async def connect(self) -> None:
        self._ensure_loop()
        await asyncio.to_thread(self._call, self._client.connect())

    async def is_authorized(self) -> bool:
        return await asyncio.to_thread(self._call, self._client.is_user_authorized())

    async def send_code(self, phone: str):
        return await asyncio.to_thread(self._call, self._client.send_code_request(phone))

    async def sign_in_code(self, phone: str, code: str, phone_code_hash: str):
        return await asyncio.to_thread(
            self._call,
            self._client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash),
        )

    async def sign_in_2fa(self, password: str):
        return await asyncio.to_thread(self._call, self._client.sign_in(password=password))

    async def get_dialogs(self, limit: int = 40):
        return await asyncio.to_thread(self._call, self._client.get_dialogs(limit=limit))

    async def get_messages(self, chat, limit: int = 50, offset_id: int = 0):
        kwargs: dict = {"limit": limit}
        if offset_id:
            kwargs["offset_id"] = offset_id
        return await asyncio.to_thread(self._call, self._client.get_messages(chat, **kwargs))

    async def send_message(self, chat, text: str):
        return await asyncio.to_thread(self._call, self._client.send_message(chat, text))

    async def get_me(self):
        return await asyncio.to_thread(self._call, self._client.get_me())

    async def qr_login(self):
        async def _do():
            qr = await self._client.qr_login()
            return qr.url, qr
        return await asyncio.to_thread(self._call, _do())

    async def qr_login_wait(self, qr_obj, timeout: float = 30):
        async def _do():
            return await qr_obj.wait(timeout=timeout)
        return await asyncio.to_thread(self._call, _do())

    async def qr_login_recreate(self, qr_obj):
        async def _do():
            await qr_obj.recreate()
            return qr_obj.url
        return await asyncio.to_thread(self._call, _do())

    def set_new_message_handler(self, callback) -> None:
        self._on_new_message = callback

    async def _handle_new_message(self, event: events.NewMessage.Event) -> None:
        if self._on_new_message:
            await self._on_new_message(event)

    @staticmethod
    def display_name(entity) -> str:
        if isinstance(entity, User):
            parts = [entity.first_name or "", entity.last_name or ""]
            name = " ".join(p for p in parts if p)
            return name or "Deleted Account"
        if isinstance(entity, (Chat, Channel)):
            return entity.title or "Unnamed"
        return str(getattr(entity, "title", getattr(entity, "first_name", "?")))

    async def disconnect(self) -> None:
        if self._client and self._loop:
            async def _do_disconnect():
                await self._client.disconnect()
            future = asyncio.run_coroutine_threadsafe(_do_disconnect(), self._loop)
            try:
                await asyncio.to_thread(future.result, 10)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
