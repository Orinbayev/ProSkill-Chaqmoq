from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_admin_main_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🏢 Markazlar"), KeyboardButton(text="💰 Moliyaviy"))
    builder.row(KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📱 Ilova statistikasi"))
    builder.row(KeyboardButton(text="👥 Ulangan profillar"), KeyboardButton(text="📢 Reklama yuborish"))
    builder.row(KeyboardButton(text="📁 Excel yuklab olish"), KeyboardButton(text="👨💼 Adminlar"))
    builder.row(KeyboardButton(text="👨👩👧 Ota-onalar paneli"), KeyboardButton(text="⚙️ Sozlamalar"))
    builder.row(KeyboardButton(text="🏠 Asosiy menyu"))

    return builder.as_markup(resize_keyboard=True)

def get_role_filter_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Barchaga"), KeyboardButton(text="Ota-onalar"))
    builder.row(KeyboardButton(text="Studentlar"), KeyboardButton(text="Teacherlar"))
    builder.row(KeyboardButton(text="Managerlar"), KeyboardButton(text="Directorlar"))
    builder.row(KeyboardButton(text="Superadminlar"), KeyboardButton(text="❌ Bekor qilish"))
    
    return builder.as_markup(resize_keyboard=True)
