from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    kb = [
        [
            KeyboardButton(text="👤 Profil"),
            KeyboardButton(text="📜 Faoliyat tarixi")
        ],
        [
            KeyboardButton(text="🔐 Xavfsizlik"),
            KeyboardButton(text="ℹ️ Yordam")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
