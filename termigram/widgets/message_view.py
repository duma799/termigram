from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from termigram.client import TGClient


class MessageBubble(Static):
    def __init__(self, msg, my_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._msg = msg
        self._my_id = my_id

    def compose(self) -> ComposeResult:
        msg = self._msg
        is_outgoing = getattr(msg, "out", False) or (
            msg.sender_id == self._my_id if msg.sender_id else False
        )

        sender = ""
        if not is_outgoing:
            if msg.sender:
                sender = TGClient.display_name(msg.sender)
            else:
                sender = "Unknown"

        text = msg.message or "[media]"
        ts = ""
        if msg.date:
            ts = msg.date.strftime("%H:%M")

        cls = "msg-out" if is_outgoing else "msg-in"
        self.add_class(cls)

        if sender:
            yield Label(sender, classes="msg-sender")
        yield Label(text, classes="msg-text")
        yield Label(ts, classes="msg-time")


class MessageView(Widget):
    current_chat: reactive[object | None] = reactive(None)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._my_id: int = 0
        self._oldest_id: int = 0

    def compose(self) -> ComposeResult:
        yield Static("Select a chat to start messaging", id="msg-placeholder")
        yield VerticalScroll(id="msg-scroll")

    def on_mount(self) -> None:
        self.query_one("#msg-scroll").display = False

    async def load_chat(self, dialog) -> None:
        self.current_chat = dialog
        tg = TGClient()

        if not self._my_id:
            me = await tg.get_me()
            self._my_id = me.id

        scroll = self.query_one("#msg-scroll", VerticalScroll)
        placeholder = self.query_one("#msg-placeholder", Static)
        placeholder.display = False
        scroll.display = True

        await scroll.remove_children()
        messages = await tg.get_messages(dialog.entity, limit=50)
        messages = list(reversed(messages))

        if messages:
            self._oldest_id = messages[0].id

        for msg in messages:
            await scroll.mount(MessageBubble(msg, self._my_id))

        scroll.scroll_end(animate=False)

    async def append_message(self, msg) -> None:
        scroll = self.query_one("#msg-scroll", VerticalScroll)
        await scroll.mount(MessageBubble(msg, self._my_id))
        scroll.scroll_end(animate=False)

    async def load_older(self) -> None:
        if not self.current_chat or not self._oldest_id:
            return
        tg = TGClient()
        messages = await tg.get_messages(
            self.current_chat.entity, limit=30, offset_id=self._oldest_id
        )
        if not messages:
            return
        scroll = self.query_one("#msg-scroll", VerticalScroll)
        messages = list(reversed(messages))
        self._oldest_id = messages[0].id
        for i, msg in enumerate(messages):
            bubble = MessageBubble(msg, self._my_id)
            await scroll.mount(bubble, before=i)
