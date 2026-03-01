from __future__ import annotations

from textual.app import App

from termigram.client import TGClient
from termigram.screens.auth import AuthScreen


class TermigramApp(App):
    TITLE = "Termigram"
    CSS_PATH = "styles/app.tcss"

    def on_mount(self) -> None:
        self.push_screen(AuthScreen())

    async def on_unmount(self) -> None:
        tg = TGClient()
        await tg.disconnect()
