from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from i18n import b


def get_parent_main_menu(lang: str = "uz"):
    keyboard = [
        [KeyboardButton(text=b("p_children", lang)), KeyboardButton(text=b("p_attendance", lang))],
        [KeyboardButton(text=b("p_payment", lang)), KeyboardButton(text=b("p_balance", lang))],
        [KeyboardButton(text=b("p_teacher", lang)), KeyboardButton(text=b("p_addchild", lang))],
        [KeyboardButton(text=b("c_sitelogin", lang)), KeyboardButton(text=b("c_logout", lang))],
    ]
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
