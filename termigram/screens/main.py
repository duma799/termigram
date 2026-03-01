from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import Screen

from termigram.client import TGClient
from termigram.widgets.chat_list import ChatList
from termigram.widgets.message_input import MessageInput
from termigram.widgets.message_view import MessageView


class MainScreen(Screen):
    CSS = """
    MainScreen {
        layout: horizontal;
    }
    """

    BINDINGS = [
        ("escape", "focus_chatlist", "Focus chat list"),
    ]

    class NewTelegramMessage(Message):
        def __init__(self, event) -> None:
            super().__init__()
            self.event = event

    def __init__(self) -> None:
        super().__init__()
        self._current_dialog = None
        self._tg = TGClient()

    def compose(self) -> ComposeResult:
        yield ChatList(id="sidebar")
        with Vertical(id="main-pane"):
            yield MessageView(id="message-view")
            yield MessageInput(id="message-input")

    def on_mount(self) -> None:
        self._load_chats()
        self._tg.set_new_message_handler(self._on_new_message)

    @work(exclusive=True)
    async def _load_chats(self) -> None:
        chat_list = self.query_one("#sidebar", ChatList)
        await chat_list.load_dialogs()

    @on(ChatList.ChatSelected)
    def on_chat_selected(self, event: ChatList.ChatSelected) -> None:
        self._current_dialog = event.dialog
        self._load_messages(event.dialog)

    @work(exclusive=True)
    async def _load_messages(self, dialog) -> None:
        view = self.query_one("#message-view", MessageView)
        await view.load_chat(dialog)
        self.query_one("#msg-input").focus()

    @on(MessageInput.Submitted)
    def on_message_submitted(self, event: MessageInput.Submitted) -> None:
        if self._current_dialog:
            self._send_message(event.text)

    @work(exclusive=True)
    async def _send_message(self, text: str) -> None:
        if not self._current_dialog:
            return
        msg = await self._tg.send_message(self._current_dialog.entity, text)
        view = self.query_one("#message-view", MessageView)
        await view.append_message(msg)

    async def _on_new_message(self, event) -> None:
        self.post_message(self.NewTelegramMessage(event))

    @on(NewTelegramMessage)
    def handle_new_telegram_message(self, message: NewTelegramMessage) -> None:
        msg = message.event.message
        chat_id = msg.chat_id
        if self._current_dialog and self._current_dialog.entity.id == chat_id:
            self._append_incoming(msg)

    @work(exclusive=True)
    async def _append_incoming(self, msg) -> None:
        view = self.query_one("#message-view", MessageView)
        await view.append_message(msg)

    def action_focus_chatlist(self) -> None:
        self.query_one("#chat-listview").focus()
