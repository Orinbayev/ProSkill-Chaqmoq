from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def _common_rows():
    return [
        [KeyboardButton(text="👤 Profil"), KeyboardButton(text="📜 Faoliyat tarixi")],
        [KeyboardButton(text="🔐 Xavfsizlik"), KeyboardButton(text="🔄 Profilni almashtirish")],
        [KeyboardButton(text="ℹ️ Yordam")],
    ]


def get_manager_main_menu():
    keyboard = [
        [KeyboardButton(text="📊 Kunlik Hisobot"), KeyboardButton(text="⚠️ Xavfli O'quvchilar")],
        [KeyboardButton(text="👤 Yangi Lidlar"), KeyboardButton(text="📣 Xabar Yuborish")],
        [KeyboardButton(text="💰 Moliyaviy Holat"), KeyboardButton(text="👥 Xodimlar")],
    ]
    keyboard.extend(_common_rows())
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_manager_broadcast_audience_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎓 O'quvchilarga", callback_data="manager:broadcast:students"),
                InlineKeyboardButton(text="👨‍🏫 O'qituvchilarga", callback_data="manager:broadcast:teachers"),
            ]
        ]
    )
