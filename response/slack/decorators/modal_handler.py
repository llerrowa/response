import logging

logger = logging.getLogger(__name__)

MODAL_HANDLERS = {}


def modal_handler(callback_id, func=None):
    def _wrapper(fn):
        MODAL_HANDLERS[callback_id] = fn

    if func:
        return _wrapper(func)
    return _wrapper


def remove_modal_handler(callback_id):
    MODAL_HANDLERS.pop(callback_id, None)


def handle_modal(payload, callback_id):
    if callback_id not in MODAL_HANDLERS:
        logger.error(f"Can't find handler for modal id {callback_id}")
        return

    callback = MODAL_HANDLERS[callback_id]

    user_id = payload["user"]["id"]
    state = payload["view"]["state"]["values"]
    metadata = payload["view"]["private_metadata"]
    trigger_id = payload["trigger_id"]

    callback(user_id, state, metadata, trigger_id)
