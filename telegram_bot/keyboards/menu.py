from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from keyboards.student_menu import get_student_main_menu
from keyboards.parent_menu import get_parent_main_menu
from keyboards.teacher_menu import get_teacher_main_menu
from keyboards.manager_menu import get_manager_main_menu


def get_main_menu(role: str | None = None):
    """ASOSIY bot menyusi — xodimlar + profil boshqaruvi.

    Ota-ona/o'quvchi panellari FAMILY botда (get_family_menu). Asosiy botда
    ular faqat profil/xavfsizlik/tiklash menyusini oladi — Family panel EMAS
    (aks holda tugmalar ishlamaydi, chunki asosiy bot student/parent routerlarni
    ro'yxatga olmaydi)."""
    if role == "teacher":
        return get_teacher_main_menu()
    if role in {"manager", "director"}:
        return get_manager_main_menu()

    # student / parent / boshqa / None → profil boshqaruv menyusi
    kb = [
        [KeyboardButton(text="👤 Profil"), KeyboardButton(text="🔐 Xavfsizlik")],
        [KeyboardButton(text="ℹ️ Yordam"), KeyboardButton(text="🚪 Chiqish")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_family_menu(role: str | None = None, lang: str = "uz"):
    """FAMILY bot menyusi — ota-ona/o'quvchi panellari (3 tilli)."""
    if role == "parent":
        return get_parent_main_menu(lang)
    return get_student_main_menu(lang)
