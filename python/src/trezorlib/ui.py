# This file is part of the Trezor project.
#
# Copyright (C) 2012-2019 SatoshiLabs and contributors
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the License along with this library.
# If not, see <https://www.gnu.org/licenses/lgpl-3.0.html>.

import os
from typing import Union

import click
from mnemonic import Mnemonic
from typing_extensions import Protocol

from . import device, messages
from .client import MAX_PIN_LENGTH, PASSPHRASE_ON_DEVICE
from .exceptions import Cancelled
from .messages import PinMatrixRequestType, WordRequestType

PIN_MATRIX_DESCRIPTION = """
Use the numeric keypad or lowercase letters to describe number positions.

The layout is:

    7 8 9        e r t
    4 5 6  -or-  d f g
    1 2 3        c v b
""".strip()

RECOVERY_MATRIX_DESCRIPTION = """
Use the numeric keypad to describe positions.
For the word list use only left and right keys.
Use backspace to correct an entry.

The keypad layout is:
    7 8 9     7 | 9
    4 5 6     4 | 6
    1 2 3     1 | 3
""".strip()

PIN_GENERIC = None
PIN_CURRENT = PinMatrixRequestType.Current
PIN_NEW = PinMatrixRequestType.NewFirst
PIN_CONFIRM = PinMatrixRequestType.NewSecond
WIPE_CODE_NEW = PinMatrixRequestType.WipeCodeFirst
WIPE_CODE_CONFIRM = PinMatrixRequestType.WipeCodeSecond


class TrezorClientUI(Protocol):
    def button_request(self, br: messages.ButtonRequest) -> None:
        ...

    def get_pin(self, code: PinMatrixRequestType) -> str:
        ...

    def get_passphrase(self, available_on_device: bool) -> Union[str, object]:
        ...


def echo(*args, **kwargs):
    return click.echo(*args, err=True, **kwargs)


def prompt(*args, **kwargs):
    return click.prompt(*args, err=True, **kwargs)


class ClickUI:
    def __init__(self, always_prompt=False, passphrase_on_host=False):
        self.pinmatrix_shown = False
        self.prompt_shown = False
        self.always_prompt = always_prompt
        self.passphrase_on_host = passphrase_on_host

    def button_request(self, _br):
        if not self.prompt_shown:
            echo("Please confirm action on your Trezor device.")
        if not self.always_prompt:
            self.prompt_shown = True

    def get_pin(self, code=None):
        if code == PIN_CURRENT:
            desc = "current PIN"
        elif code == PIN_NEW:
            desc = "new PIN"
        elif code == PIN_CONFIRM:
            desc = "new PIN again"
        elif code == WIPE_CODE_NEW:
            desc = "new wipe code"
        elif code == WIPE_CODE_CONFIRM:
            desc = "new wipe code again"
        else:
            desc = "PIN"

        if not self.pinmatrix_shown:
            echo(PIN_MATRIX_DESCRIPTION)
            if not self.always_prompt:
                self.pinmatrix_shown = True

        while True:
            try:
                pin = prompt(f"Please enter {desc}", hide_input=True)
            except click.Abort:
                raise Cancelled from None

            # translate letters to numbers if letters were used
            if all(d in "cvbdfgert" for d in pin):
                pin = pin.translate(str.maketrans("cvbdfgert", "123456789"))

            if any(d not in "123456789" for d in pin):
                echo(
                    "The value may only consist of digits 1 to 9 or letters cvbdfgert."
                )
            elif len(pin) > MAX_PIN_LENGTH:
                echo(f"The value must be at most {MAX_PIN_LENGTH} digits in length.")
            else:
                return pin

    def get_passphrase(self, available_on_device):
        if available_on_device and not self.passphrase_on_host:
            return PASSPHRASE_ON_DEVICE

        if os.getenv("PASSPHRASE") is not None:
            echo("Passphrase required. Using PASSPHRASE environment variable.")
            return os.getenv("PASSPHRASE")

        while True:
            try:
                passphrase = prompt(
                    "Passphrase required",
                    hide_input=True,
                    default="",
                    show_default=False,
                )
                second = prompt(
                    "Confirm your passphrase",
                    hide_input=True,
                    default="",
                    show_default=False,
                )
                if passphrase == second:
                    return passphrase
                else:
                    echo("Passphrase did not match. Please try again.")
            except click.Abort:
                raise Cancelled from None


def mnemonic_words(expand=False, language="english"):
    if expand:
        wordlist = Mnemonic(language).wordlist
    else:
        wordlist = set()

    def expand_word(word):
        if not expand:
            return word
        if word in wordlist:
            return word
        matches = [w for w in wordlist if w.startswith(word)]
        if len(matches) == 1:
            return matches[0]
        echo("Choose one of: " + ", ".join(matches))
        raise KeyError(word)

    def get_word(type):
        assert type == WordRequestType.Plain
        while True:
            try:
                word = prompt("Enter one word of mnemonic")
                return expand_word(word)
            except KeyError:
                pass
            except click.Abort:
                raise Cancelled from None

    return get_word


def matrix_words(type):
    while True:
        try:
            ch = click.getchar()
        except (KeyboardInterrupt, EOFError):
            raise Cancelled from None

        if ch in "\x04\x1b":
            # Ctrl+D, Esc
            raise Cancelled
        if ch in "\x08\x7f":
            # Backspace, Del
            return device.RECOVERY_BACK
        if type == WordRequestType.Matrix6 and ch in "147369":
            return ch
        if type == WordRequestType.Matrix9 and ch in "123456789":
            return ch
