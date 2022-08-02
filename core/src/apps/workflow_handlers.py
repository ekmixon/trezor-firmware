from trezor import utils
from trezor.enums import MessageType

workflow_handlers: dict[int, Handler] = {}


def register(wire_type: int, handler: Handler) -> None:
    """Register `handler` to get scheduled after `wire_type` message is received."""
    workflow_handlers[wire_type] = handler


def find_message_handler_module(msg_type: int) -> str:
    """Statically find the appropriate workflow handler.

    For now, new messages must be registered by hand in the if-elif manner below.
    The reason for this is memory fragmentation optimization:
    - using a dict would mean that the whole thing stays in RAM, whereas an if-elif
      sequence is run from flash
    - collecting everything as strings instead of importing directly means that we don't
      need to load any of the modules into memory until we actually need them
    """
    raise ValueError


def find_registered_handler(iface: WireInterface, msg_type: int) -> Handler | None:
    if msg_type in workflow_handlers:
        # Message has a handler available, return it directly.
        return workflow_handlers[msg_type]

    try:
        modname = find_message_handler_module(msg_type)
        handler_name = modname[modname.rfind(".") + 1 :]
        module = __import__(modname, None, None, (handler_name,), 0)
        return getattr(module, handler_name)  # type: ignore
    except ValueError:
        return None
