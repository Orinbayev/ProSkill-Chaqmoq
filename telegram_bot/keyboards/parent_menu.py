from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def _common_rows():
    return [
        [KeyboardButton(text="👤 Profil"), KeyboardButton(text="📜 Faoliyat tarixi")],
        [KeyboardButton(text="🔐 Xavfsizlik"), KeyboardButton(text="🔄 Profilni almashtirish")],
        [KeyboardButton(text="ℹ️ Yordam")],
    ]


def get_parent_main_menu():
    keyboard = [
        [KeyboardButton(text="👶 Bolalarim"), KeyboardButton(text="📊 Davomat")],
        [KeyboardButton(text="💰 To'lov Holati"), KeyboardButton(text="⚡ Chaqmoq Ballari")],
        [KeyboardButton(text="📞 O'qituvchi")],
    ]
    keyboard.extend(_common_rows())
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_children_selector_keyboard(children: list[dict], selected_child_id: int | None = None):
    buttons = []
    for child in children:
        prefix = "✅ " if selected_child_id == child.get("id") else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{child['full_name']}",
                    callback_data=f"parent:child:{child['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
