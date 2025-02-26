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

import pytest

from trezorlib import btc, messages as proto
from trezorlib.exceptions import TrezorFailure
from trezorlib.tools import parse_path

from ..tx_cache import TxCache
from .signtx import request_finished, request_input, request_meta, request_output

B = proto.ButtonRequestType
TX_API = TxCache("Bitcoin")

TXHASH_d5f65e = bytes.fromhex(
    "d5f65ee80147b4bcc70b75e4bbf2d7382021b871bd8867ef8fa525ef50864882"
)


class TestOpReturn:
    def test_opreturn(self, client):
        inp1 = proto.TxInputType(
            address_n=parse_path("44'/0'/0'/0/2"),
            amount=390000,
            prev_hash=TXHASH_d5f65e,
            prev_index=0,
        )

        out1 = proto.TxOutputType(
            address="1MJ2tj2ThBE62zXbBYA5ZaN3fdve5CPAz1",
            amount=390000 - 10000,
            script_type=proto.OutputScriptType.PAYTOADDRESS,
        )

        out2 = proto.TxOutputType(
            op_return_data=b"test of the op_return data",
            amount=0,
            script_type=proto.OutputScriptType.PAYTOOPRETURN,
        )

        with client:
            client.set_expected_responses(
                [
                    request_input(0),
                    request_output(0),
                    proto.ButtonRequest(code=B.ConfirmOutput),
                    request_output(1),
                    proto.ButtonRequest(code=B.ConfirmOutput),
                    proto.ButtonRequest(code=B.SignTx),
                    request_input(0),
                    request_meta(TXHASH_d5f65e),
                    request_input(0, TXHASH_d5f65e),
                    request_input(1, TXHASH_d5f65e),
                    request_output(0, TXHASH_d5f65e),
                    request_input(0),
                    request_output(0),
                    request_output(1),
                    request_output(0),
                    request_output(1),
                    request_finished(),
                ]
            )
            _, serialized_tx = btc.sign_tx(
                client, "Bitcoin", [inp1], [out1, out2], prev_txes=TX_API
            )

        assert (
            serialized_tx.hex()
            == "010000000182488650ef25a58fef6788bd71b8212038d7f2bbe4750bc7bcb44701e85ef6d5000000006b483045022100bc36e1227b334e856c532bbef86d30a96823a5f2461738f4dbf969dfbcf1b40b022078c5353ec9a4bce2bb05bd1ec466f2ab379c1aad926e208738407bba4e09784b012103330236b68aa6fdcaca0ea72e11b360c84ed19a338509aa527b678a7ec9076882ffffffff0260cc0500000000001976a914de9b2a8da088824e8fe51debea566617d851537888ac00000000000000001c6a1a74657374206f6620746865206f705f72657475726e206461746100000000"
        )

    def test_nonzero_opreturn(self, client):
        inp1 = proto.TxInputType(
            address_n=parse_path("44'/0'/10'/0/5"),
            amount=390000,
            prev_hash=TXHASH_d5f65e,
            prev_index=0,
        )

        out1 = proto.TxOutputType(
            op_return_data=b"test of the op_return data",
            amount=10000,
            script_type=proto.OutputScriptType.PAYTOOPRETURN,
        )

        with client:
            client.set_expected_responses(
                [request_input(0), request_output(0), proto.Failure()]
            )

            with pytest.raises(
                TrezorFailure, match="OP_RETURN output with non-zero amount"
            ):
                btc.sign_tx(client, "Bitcoin", [inp1], [out1], prev_txes=TX_API)

    def test_opreturn_address(self, client):
        inp1 = proto.TxInputType(
            address_n=parse_path("44'/0'/0'/0/2"),
            amount=390000,
            prev_hash=TXHASH_d5f65e,
            prev_index=0,
        )

        out1 = proto.TxOutputType(
            address_n=parse_path("44'/0'/0'/1/2"),
            amount=0,
            op_return_data=b"OMNI TRANSACTION GOES HERE",
            script_type=proto.OutputScriptType.PAYTOOPRETURN,
        )

        with client:
            client.set_expected_responses(
                [request_input(0), request_output(0), proto.Failure()]
            )
            with pytest.raises(
                TrezorFailure, match="Output's address_n provided but not expected."
            ):
                btc.sign_tx(client, "Bitcoin", [inp1], [out1], prev_txes=TX_API)
