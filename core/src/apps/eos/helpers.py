from trezor import wire
from trezor.crypto import base58
from trezor.messages import EosAsset


def base58_encode(prefix: str, sig_prefix: str, data: bytes) -> str:
    b58 = base58.encode(data + base58.ripemd160_32(data + sig_prefix.encode()))
    return prefix + sig_prefix + "_" + b58 if sig_prefix else prefix + b58


def eos_name_to_string(value: int) -> str:
    charmap = ".12345abcdefghijklmnopqrstuvwxyz"
    tmp = value
    string = ""
    for i in range(13):
        c = charmap[tmp & (0x0F if i == 0 else 0x1F)]
        string = c + string
        tmp >>= 4 if i == 0 else 5

    return string.rstrip(".")


def eos_asset_to_string(asset: EosAsset) -> str:
    symbol_bytes = int.to_bytes(asset.symbol, 8, "big")
    precision = symbol_bytes[7]
    symbol = bytes(reversed(symbol_bytes[:7])).rstrip(b"\x00").decode("ascii")

    amount_digits = f"{asset.amount:0{precision}d}"
    if precision <= 0:
        return f"{amount_digits} {symbol}"
    integer = amount_digits[:-precision]
    if integer == "":
        integer = "0"
    fraction = amount_digits[-precision:]

    return f"{integer}.{fraction} {symbol}"


def public_key_to_wif(pub_key: bytes) -> str:
    if pub_key[0] == 0x04 and len(pub_key) == 65:
        head = b"\x03" if pub_key[64] & 0x01 else b"\x02"
        compressed_pub_key = head + pub_key[1:33]
    elif pub_key[0] in [0x02, 0x03] and len(pub_key) == 33:
        compressed_pub_key = pub_key
    else:
        raise wire.DataError("invalid public key")
    return base58_encode("EOS", "", compressed_pub_key)
