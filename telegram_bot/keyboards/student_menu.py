from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def _common_rows():
    # Family botда faqat 🚪 Chiqish ishlaydi; qolgan umumiy tugmalar (Profil,
    # Faoliyat, Xavfsizlik, Profilni almashtirish, Yordam) handlersiz edi — olib tashlandi.
    return [
        [KeyboardButton(text="🚪 Chiqish")],
    ]


def get_student_main_menu():
    keyboard = [
        [KeyboardButton(text="📊 Mening holatim"), KeyboardButton(text="⚡ Chaqmoq Balans")],
        [KeyboardButton(text="📅 Dars Jadvali"), KeyboardButton(text="💰 To'lov Holati")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="🛍 Do'kon")],
        [KeyboardButton(text="🔔 Sozlamalar"), KeyboardButton(text="🔑 Saytga login")],
    ]
    keyboard.extend(_common_rows())
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


def get_student_settings_keyboard(enabled: bool):
    toggle_text = "🔕 Bildirishnomani o'chirish" if enabled else "🔔 Bildirishnomani yoqish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"student:notifications:{int(not enabled)}")]
        ]
    )
