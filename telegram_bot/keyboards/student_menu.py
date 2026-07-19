from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from i18n import b


def get_student_main_menu(lang: str = "uz"):
    keyboard = [
        [KeyboardButton(text=b("s_status", lang)), KeyboardButton(text=b("s_balance", lang))],
        [KeyboardButton(text=b("s_schedule", lang)), KeyboardButton(text=b("s_payment", lang))],
        [KeyboardButton(text=b("s_ranking", lang)), KeyboardButton(text=b("s_store", lang))],
        [KeyboardButton(text=b("s_settings", lang)), KeyboardButton(text=b("c_sitelogin", lang))],
        [KeyboardButton(text=b("c_logout", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_store_products_keyboard(products: list[dict]):
    buttons = []
    for product in products[:20]:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🛍 {product['name']} · {product['price_chaqmoq']}⚡",
                    callback_data=f"student:buy:{product['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_student_settings_keyboard(enabled: bool, lang: str = "uz"):
    from i18n import ik
    toggle_text = ik("notif_off", lang) if enabled else ik("notif_on", lang)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"student:notifications:{int(not enabled)}")]
        ]
    )
