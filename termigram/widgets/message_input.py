from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input


class MessageInput(Widget):
    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Type a message...", id="msg-input")

    @on(Input.Submitted, "#msg-input")
    def on_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        inp = self.query_one("#msg-input", Input)
        inp.value = ""
        self.post_message(self.Submitted(text))
