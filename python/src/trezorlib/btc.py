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

import warnings
from copy import copy
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from . import exceptions, messages
from .client import TrezorClient
from .tools import Address, expect, normalize_nfc, session


def from_json(json_dict: dict) -> messages.TransactionType:
    def make_input(vin: dict) -> messages.TxInputType:
        if "coinbase" in vin:
            return messages.TxInputType(
                prev_hash=b"\0" * 32,
                prev_index=0xFFFFFFFF,  # signed int -1
                script_sig=bytes.fromhex(vin["coinbase"]),
                sequence=vin["sequence"],
            )

        else:
            return messages.TxInputType(
                prev_hash=bytes.fromhex(vin["txid"]),
                prev_index=vin["vout"],
                script_sig=bytes.fromhex(vin["scriptSig"]["hex"]),
                sequence=vin["sequence"],
            )

    def make_bin_output(vout: dict) -> messages.TxOutputBinType:
        return messages.TxOutputBinType(
            amount=int(Decimal(vout["value"]) * (10 ** 8)),
            script_pubkey=bytes.fromhex(vout["scriptPubKey"]["hex"]),
        )

    return messages.TransactionType(
        version=json_dict["version"],
        lock_time=json_dict.get("locktime", 0),
        inputs=[make_input(vin) for vin in json_dict["vin"]],
        bin_outputs=[make_bin_output(vout) for vout in json_dict["vout"]],
    )


@expect(messages.PublicKey)
def get_public_node(
    client: TrezorClient,
    n: Address,
    ecdsa_curve_name: Optional[str] = None,
    show_display: bool = False,
    coin_name: Optional[str] = None,
    script_type: messages.InputScriptType = messages.InputScriptType.SPENDADDRESS,
    ignore_xpub_magic: bool = False,
) -> messages.PublicKey:
    return client.call(
        messages.GetPublicKey(
            address_n=n,
            ecdsa_curve_name=ecdsa_curve_name,
            show_display=show_display,
            coin_name=coin_name,
            script_type=script_type,
            ignore_xpub_magic=ignore_xpub_magic,
        )
    )


@expect(messages.Address, field="address")
def get_address(
    client: TrezorClient,
    coin_name: str,
    n: Address,
    show_display: bool = False,
    multisig: Optional[messages.MultisigRedeemScriptType] = None,
    script_type: messages.InputScriptType = messages.InputScriptType.SPENDADDRESS,
    ignore_xpub_magic: bool = False,
) -> str:
    return client.call(
        messages.GetAddress(
            address_n=n,
            coin_name=coin_name,
            show_display=show_display,
            multisig=multisig,
            script_type=script_type,
            ignore_xpub_magic=ignore_xpub_magic,
        )
    )


@expect(messages.OwnershipId, field="ownership_id")
def get_ownership_id(
    client: TrezorClient,
    coin_name: str,
    n: Address,
    multisig: Optional[messages.MultisigRedeemScriptType] = None,
    script_type: messages.InputScriptType = messages.InputScriptType.SPENDADDRESS,
) -> bytes:
    return client.call(
        messages.GetOwnershipId(
            address_n=n,
            coin_name=coin_name,
            multisig=multisig,
            script_type=script_type,
        )
    )


def get_ownership_proof(
    client: TrezorClient,
    coin_name: str,
    n: Address,
    multisig: Optional[messages.MultisigRedeemScriptType] = None,
    script_type: messages.InputScriptType = messages.InputScriptType.SPENDADDRESS,
    user_confirmation: bool = False,
    ownership_ids: Optional[List[bytes]] = None,
    commitment_data: Optional[bytes] = None,
    preauthorized: bool = False,
) -> Tuple[bytes, bytes]:
    if preauthorized:
        res = client.call(messages.DoPreauthorized())
        if not isinstance(res, messages.PreauthorizedRequest):
            raise exceptions.TrezorException("Unexpected message")

    res = client.call(
        messages.GetOwnershipProof(
            address_n=n,
            coin_name=coin_name,
            script_type=script_type,
            multisig=multisig,
            user_confirmation=user_confirmation,
            ownership_ids=ownership_ids,
            commitment_data=commitment_data,
        )
    )

    if not isinstance(res, messages.OwnershipProof):
        raise exceptions.TrezorException("Unexpected message")

    return res.ownership_proof, res.signature


@expect(messages.MessageSignature)
def sign_message(
    client: TrezorClient,
    coin_name: str,
    n: Address,
    message: bytes,
    script_type: messages.InputScriptType = messages.InputScriptType.SPENDADDRESS,
    no_script_type: bool = False,
) -> messages.MessageSignature:
    message = normalize_nfc(message)
    return client.call(
        messages.SignMessage(
            coin_name=coin_name,
            address_n=n,
            message=message,
            script_type=script_type,
            no_script_type=no_script_type,
        )
    )


def verify_message(
    client: TrezorClient,
    coin_name: str,
    address: str,
    signature: bytes,
    message: Union[str, bytes],
) -> bool:
    message = normalize_nfc(message)
    try:
        resp = client.call(
            messages.VerifyMessage(
                address=address,
                signature=signature,
                message=message,
                coin_name=coin_name,
            )
        )
    except exceptions.TrezorFailure:
        return False
    return isinstance(resp, messages.Success)


@session
def sign_tx(
    client: TrezorClient,
    coin_name: str,
    inputs: Sequence[messages.TxInputType],
    outputs: Sequence[messages.TxOutputType],
    details: messages.SignTx = None,
    prev_txes: Dict[bytes, messages.TransactionType] = None,
    preauthorized: bool = False,
    **kwargs: Any,
) -> Tuple[Sequence[bytes], bytes]:
    """Sign a Bitcoin-like transaction.

    Returns a list of signatures (one for each provided input) and the
    network-serialized transaction.

    In addition to the required arguments, it is possible to specify additional
    transaction properties (version, lock time, expiry...). Each additional argument
    must correspond to a field in the `SignTx` data type. Note that some fields
    (`inputs_count`, `outputs_count`, `coin_name`) will be inferred from the arguments
    and cannot be overriden by kwargs.
    """
    if prev_txes is None:
        prev_txes = {}

    if details is not None:
        warnings.warn(
            "'details' argument is deprecated, use kwargs instead",
            DeprecationWarning,
            stacklevel=2,
        )
        signtx = details
        signtx.coin_name = coin_name
        signtx.inputs_count = len(inputs)
        signtx.outputs_count = len(outputs)

    else:
        signtx = messages.SignTx(
            coin_name=coin_name,
            inputs_count=len(inputs),
            outputs_count=len(outputs),
        )
        for name, value in kwargs.items():
            if hasattr(signtx, name):
                setattr(signtx, name, value)

    if preauthorized:
        res = client.call(messages.DoPreauthorized())
        if not isinstance(res, messages.PreauthorizedRequest):
            raise exceptions.TrezorException("Unexpected message")

    res = client.call(signtx)

    # Prepare structure for signatures
    signatures: List[Optional[bytes]] = [None] * len(inputs)
    serialized_tx = b""

    def copy_tx_meta(tx: messages.TransactionType) -> messages.TransactionType:
        tx_copy = copy(tx)
        # clear fields
        tx_copy.inputs_cnt = len(tx.inputs)
        tx_copy.inputs = []
        tx_copy.outputs_cnt = len(tx.bin_outputs or tx.outputs)
        tx_copy.outputs = []
        tx_copy.bin_outputs = []
        tx_copy.extra_data_len = len(tx.extra_data or b"")
        tx_copy.extra_data = None
        return tx_copy

    this_tx = messages.TransactionType(
        inputs=list(inputs),
        outputs=list(outputs),
        inputs_cnt=len(inputs),
        outputs_cnt=len(outputs),
        # pick either kw-provided or default value from the SignTx request
        version=signtx.version,
    )

    R = messages.RequestType
    while isinstance(res, messages.TxRequest):
        # If there's some part of signed transaction, let's add it
        if res.serialized:
            if res.serialized.serialized_tx:
                serialized_tx += res.serialized.serialized_tx

            if res.serialized.signature_index is not None:
                idx = res.serialized.signature_index
                sig = res.serialized.signature
                if signatures[idx] is not None:
                    raise ValueError(f"Signature for index {idx} already filled")
                signatures[idx] = sig

        if res.request_type == R.TXFINISHED:
            break

        # Device asked for one more information, let's process it.
        if res.details.tx_hash is not None:
            current_tx = prev_txes[res.details.tx_hash]
        else:
            current_tx = this_tx

        if res.request_type == R.TXMETA:
            msg = copy_tx_meta(current_tx)
            res = client.call(messages.TxAck(tx=msg))

        elif res.request_type in (R.TXINPUT, R.TXORIGINPUT):
            msg = messages.TransactionType()
            msg.inputs = [current_tx.inputs[res.details.request_index]]
            res = client.call(messages.TxAck(tx=msg))

        elif res.request_type == R.TXOUTPUT:
            msg = messages.TransactionType()
            if res.details.tx_hash:
                msg.bin_outputs = [current_tx.bin_outputs[res.details.request_index]]
            else:
                msg.outputs = [current_tx.outputs[res.details.request_index]]

            res = client.call(messages.TxAck(tx=msg))

        elif res.request_type == R.TXORIGOUTPUT:
            msg = messages.TransactionType()
            msg.outputs = [current_tx.outputs[res.details.request_index]]
            res = client.call(messages.TxAck(tx=msg))

        elif res.request_type == R.TXEXTRADATA:
            o, l = res.details.extra_data_offset, res.details.extra_data_len
            msg = messages.TransactionType()
            msg.extra_data = current_tx.extra_data[o : o + l]
            res = client.call(messages.TxAck(tx=msg))

    if not isinstance(res, messages.TxRequest):
        raise exceptions.TrezorException("Unexpected message")

    for i, sig in zip(inputs, signatures):
        if i.script_type != messages.InputScriptType.EXTERNAL and sig is None:
            raise exceptions.TrezorException("Some signatures are missing!")

    return signatures, serialized_tx


@expect(messages.Success, field="message")
def authorize_coinjoin(
    client: TrezorClient,
    coordinator: str,
    max_total_fee: int,
    n: Address,
    coin_name: str,
    fee_per_anonymity: Optional[int] = None,
    script_type: messages.InputScriptType = messages.InputScriptType.SPENDADDRESS,
) -> str:
    return client.call(
        messages.AuthorizeCoinJoin(
            coordinator=coordinator,
            max_total_fee=max_total_fee,
            address_n=n,
            coin_name=coin_name,
            fee_per_anonymity=fee_per_anonymity,
            script_type=script_type,
        )
    )
