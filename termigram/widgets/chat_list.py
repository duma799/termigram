from __future__ import annotations

from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static

from termigram.client import TGClient


class ChatItem(ListItem):
    def __init__(self, dialog, **kwargs) -> None:
        super().__init__(**kwargs)
        self.dialog = dialog

    def compose(self) -> ComposeResult:
        d = self.dialog
        name = TGClient.display_name(d.entity)
        last_msg = ""
        if d.message and d.message.message:
            last_msg = d.message.message[:40]
            if len(d.message.message) > 40:
                last_msg += "..."

        ts = ""
        if d.message and d.message.date:
            dt = d.message.date
            now = datetime.now(dt.tzinfo)
            if dt.date() == now.date():
                ts = dt.strftime("%H:%M")
            else:
                ts = dt.strftime("%b %d")

        unread = d.unread_count or 0

        with Vertical(classes="chat-item-inner"):
            yield Static(
                self._top_line(name, ts, unread),
                classes="chat-item-top",
            )
            yield Label(last_msg, classes="chat-item-preview")

    @staticmethod
    def _top_line(name: str, ts: str, unread: int) -> str:
        badge = f" ({unread})" if unread else ""
        right = f"{ts}{badge}"
        return f"{name}  [dim]{right}[/dim]"


class ChatList(Widget):
    class ChatSelected(Message):
        def __init__(self, dialog) -> None:
            super().__init__()
            self.dialog = dialog

    selected_index: reactive[int] = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._dialogs: list = []

    def compose(self) -> ComposeResult:
        yield Static("  Termigram", id="chat-list-header")
        yield ListView(id="chat-listview")

    async def load_dialogs(self) -> None:
        tg = TGClient()
        self._dialogs = await tg.get_dialogs(limit=40)
        listview = self.query_one("#chat-listview", ListView)
        await listview.clear()
        for d in self._dialogs:
            await listview.append(ChatItem(d))

    @on(ListView.Selected, "#chat-listview")
    def on_chat_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, ChatItem):
            self.post_message(self.ChatSelected(item.dialog))

    def get_dialog_by_id(self, chat_id: int):
        for d in self._dialogs:
            if d.entity.id == chat_id:
                return d
        return None
