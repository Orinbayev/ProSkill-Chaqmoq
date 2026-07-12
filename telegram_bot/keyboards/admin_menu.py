from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_admin_main_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📊 Statistika"), KeyboardButton(text="👥 Ulangan profillar"))
    builder.row(KeyboardButton(text="📱 Ilova statistikasi"))
    builder.row(KeyboardButton(text="📢 Reklama yuborish"), KeyboardButton(text="📁 Excel yuklab olish"))
    builder.row(KeyboardButton(text="👨💼 Adminlar"), KeyboardButton(text="👨👩👧 Ota-onalar paneli"))
    builder.row(KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="🏠 Asosiy menyu"))
    
    return builder.as_markup(resize_keyboard=True)

def get_role_filter_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Barchaga"), KeyboardButton(text="Ota-onalar"))
    builder.row(KeyboardButton(text="Studentlar"), KeyboardButton(text="Teacherlar"))
    builder.row(KeyboardButton(text="Managerlar"), KeyboardButton(text="Directorlar"))
    builder.row(KeyboardButton(text="Superadminlar"), KeyboardButton(text="❌ Bekor qilish"))
    
    return builder.as_markup(resize_keyboard=True)
