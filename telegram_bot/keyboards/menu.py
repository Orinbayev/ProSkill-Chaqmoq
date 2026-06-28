from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from keyboards.student_menu import get_student_main_menu
from keyboards.parent_menu import get_parent_main_menu
from keyboards.teacher_menu import get_teacher_main_menu
from keyboards.manager_menu import get_manager_main_menu

def get_main_menu(role: str | None = None):
    if role == "student":
        return get_student_main_menu()
    if role == "parent":
        return get_parent_main_menu()
    if role == "teacher":
        return get_teacher_main_menu()
    if role in {"manager", "director"}:
        return get_manager_main_menu()

    kb = [
        [
            KeyboardButton(text="👤 Profil"),
            KeyboardButton(text="📜 Faoliyat tarixi")
        ],
        [
            KeyboardButton(text="🔐 Xavfsizlik"),
            KeyboardButton(text="ℹ️ Yordam")
        ],
        [
            KeyboardButton(text="🔄 Profilni almashtirish"),
            KeyboardButton(text="🚪 Chiqish")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
