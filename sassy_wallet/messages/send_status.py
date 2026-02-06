import secrets


BAKED_MESSAGES_WITH_BAKER = [
    "Baker {baker} has baked your operation! Oven's clear.",
    "Crispy golden bread on the shelves - baked by {baker}.",
    "Fresh loaf delivered to the shelves - baked by {baker}.",
    "Oven log updated: baked by {baker}.",
    "Golden crust achieved - baked by {baker}.",
    "Steam is gone, glory remains - baked by {baker}.",
    "Hot tray out of the oven - baked by {baker}.",
    "Batch sealed and shelved - baked by {baker}.",
    "Bread ready for pickup - baked by {baker}.",
    "Oven door closed, loaf delivered - baked by {baker}.",
    "Proofed, baked, shelved - baked by {baker}.",
    "Fresh batch on the rack - baked by {baker}.",
]

BAKED_MESSAGES_GENERIC = [
    "Baker has baked your operation! Oven's clear.",
    "Crispy golden bread on the shelves.",
    "Fresh loaf delivered to the shelves.",
    "Oven log updated. Bread is ready.",
    "Golden crust achieved. Enjoy.",
    "Steam is gone, glory remains.",
    "Hot tray out of the oven.",
    "Batch sealed and shelved.",
    "Bread ready for pickup.",
    "Oven door closed, loaf delivered.",
    "Proofed, baked, shelved.",
    "Fresh batch on the rack.",
]


def get_send_baked_message(baker_label: str | None) -> str:
    if baker_label:
        return secrets.choice(BAKED_MESSAGES_WITH_BAKER).format(baker=baker_label)
    return secrets.choice(BAKED_MESSAGES_GENERIC)
