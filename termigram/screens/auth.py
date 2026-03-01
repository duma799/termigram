from __future__ import annotations

import asyncio

import qrcode
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, Static

from termigram.client import TGClient


def _qr_to_text(url: str) -> str:
    qr = qrcode.QRCode(box_size=1, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    lines = []
    for r in range(0, len(matrix), 2):
        line = ""
        for c in range(len(matrix[0])):
            top = matrix[r][c]
            bot = matrix[r + 1][c] if r + 1 < len(matrix) else False
            if top and bot:
                line += " "
            elif top and not bot:
                line += "\u2584"
            elif not top and bot:
                line += "\u2580"
            else:
                line += "\u2588"
        lines.append(line)
    return "\n".join(lines)


class AuthScreen(Screen):
    CSS = """
    AuthScreen {
        align: center middle;
        background: #0e1117;
    }
    #auth-box {
        width: 64;
        height: auto;
        padding: 2 4;
        border: round #58a6ff;
        background: #161b22;
    }
    #auth-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #58a6ff;
        margin-bottom: 1;
    }
    #auth-subtitle {
        width: 100%;
        text-align: center;
        color: #8b949e;
        margin-bottom: 1;
    }
    #qr-display {
        width: 100%;
        content-align: center middle;
        text-align: center;
        color: #e6edf3;
        margin: 1 4;
        display: none;
    }
    #qr-display.visible {
        display: block;
    }
    #auth-error {
        width: 100%;
        text-align: center;
        color: #f85149;
        margin-top: 1;
        display: none;
    }
    #auth-error.visible {
        display: block;
    }
    #auth-input {
        margin-bottom: 1;
        display: none;
    }
    #auth-input.visible {
        display: block;
    }
    #auth-hint {
        width: 100%;
        text-align: center;
        color: #484f58;
        margin-top: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._stage = "qr"
        self._phone = ""
        self._phone_code_hash = ""
        self._tg = TGClient()
        self._qr_obj = None

    def compose(self) -> ComposeResult:
        with Vertical(id="auth-box"):
            yield Label("Termigram", id="auth-title")
            yield Label("Connecting...", id="auth-subtitle")
            yield Static("", id="qr-display")
            yield Input(placeholder="+1234567890", id="auth-input")
            yield Label("", id="auth-error")
            yield Label("", id="auth-hint")

    def on_mount(self) -> None:
        self._connect_and_qr()

    @work(group="connect")
    async def _connect_and_qr(self) -> None:
        await self._tg.connect()
        if await self._tg.is_authorized():
            self._auth_complete()
            return
        self._start_qr_login()

    @work(group="auth")
    async def _start_qr_login(self) -> None:
        self._stage = "qr"
        subtitle = self.query_one("#auth-subtitle", Label)
        qr_display = self.query_one("#qr-display", Static)
        hint = self.query_one("#auth-hint", Label)
        self.query_one("#auth-input").remove_class("visible")

        subtitle.update("Scan QR code with Telegram on your phone")
        hint.update("Open Telegram > Settings > Devices > Link Desktop Device")

        try:
            url, self._qr_obj = await self._tg.qr_login()
            qr_text = _qr_to_text(url)
            qr_display.update(qr_text)
            qr_display.add_class("visible")

            while True:
                try:
                    user = await self._tg.qr_login_wait(self._qr_obj, timeout=30)
                    self._auth_complete()
                    return
                except asyncio.TimeoutError:
                    new_url = await self._tg.qr_login_recreate(self._qr_obj)
                    qr_text = _qr_to_text(new_url)
                    qr_display.update(qr_text)
                except Exception as e:
                    err_str = str(e)
                    if "2FA" in err_str or "password" in err_str.lower():
                        qr_display.remove_class("visible")
                        hint.update("")
                        self._set_input_stage(
                            "2fa",
                            "Enter your 2FA password",
                            "Password",
                            password=True,
                        )
                    else:
                        self._show_error(err_str)
                    return
        except Exception as e:
            self._show_error(str(e))

    def _set_input_stage(
        self, stage: str, subtitle: str, placeholder: str, password: bool = False
    ) -> None:
        self._stage = stage
        self.query_one("#auth-subtitle", Label).update(subtitle)
        self.query_one("#qr-display").remove_class("visible")
        inp = self.query_one("#auth-input", Input)
        inp.value = ""
        inp.placeholder = placeholder
        inp.password = password
        inp.add_class("visible")
        inp.focus()
        self._clear_error()

    def _show_error(self, message: str) -> None:
        err = self.query_one("#auth-error", Label)
        err.update(message)
        err.add_class("visible")

    def _clear_error(self) -> None:
        err = self.query_one("#auth-error", Label)
        err.update("")
        err.remove_class("visible")

    @on(Input.Submitted, "#auth-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        self._clear_error()
        if self._stage == "2fa":
            self._do_2fa(value)
        elif self._stage == "phone":
            self._do_phone(value)
        elif self._stage == "code":
            self._do_code(value)

    @work(group="auth")
    async def _do_2fa(self, password: str) -> None:
        try:
            self.query_one("#auth-subtitle", Label).update("Verifying...")
            await self._tg.sign_in_2fa(password)
            self._auth_complete()
        except Exception as e:
            self._show_error(str(e))
            self.query_one("#auth-subtitle", Label).update(
                "Enter your 2FA password"
            )

    @work(group="auth")
    async def _do_phone(self, phone: str) -> None:
        try:
            self._phone = phone
            self.query_one("#auth-subtitle", Label).update("Sending code...")
            result = await self._tg.send_code(phone)
            self._phone_code_hash = result.phone_code_hash
            self._set_input_stage("code", "Enter the verification code", "12345")
        except Exception as e:
            self._show_error(str(e))
            self.query_one("#auth-subtitle", Label).update(
                "Enter your phone number (with country code)"
            )

    @work(group="auth")
    async def _do_code(self, code: str) -> None:
        from telethon.errors import SessionPasswordNeededError

        try:
            self.query_one("#auth-subtitle", Label).update("Verifying...")
            await self._tg.sign_in_code(self._phone, code, self._phone_code_hash)
            self._auth_complete()
        except SessionPasswordNeededError:
            self._set_input_stage(
                "2fa", "Enter your 2FA password", "Password", password=True
            )
        except Exception as e:
            self._show_error(str(e))
            self.query_one("#auth-subtitle", Label).update(
                "Enter the verification code"
            )

    def _auth_complete(self) -> None:
        from termigram.screens.main import MainScreen

        self.app.switch_screen(MainScreen())
