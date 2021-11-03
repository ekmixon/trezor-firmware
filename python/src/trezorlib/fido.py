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

from typing import List

from . import messages
from .client import TrezorClient
from .tools import expect


@expect(messages.WebAuthnCredentials, field="credentials")
def list_credentials(client: TrezorClient) -> List[messages.WebAuthnCredential]:
    return client.call(messages.WebAuthnListResidentCredentials())


@expect(messages.Success, field="message")
def add_credential(client: TrezorClient, credential_id: bytes) -> str:
    return client.call(
        messages.WebAuthnAddResidentCredential(credential_id=credential_id)
    )


@expect(messages.Success, field="message")
def remove_credential(client: TrezorClient, index: int) -> str:
    return client.call(messages.WebAuthnRemoveResidentCredential(index=index))


@expect(messages.Success, field="message")
def set_counter(client: TrezorClient, u2f_counter: int) -> str:
    return client.call(messages.SetU2FCounter(u2f_counter=u2f_counter))


@expect(messages.NextU2FCounter, field="u2f_counter")
def get_next_counter(client: TrezorClient) -> int:
    return client.call(messages.GetNextU2FCounter())
