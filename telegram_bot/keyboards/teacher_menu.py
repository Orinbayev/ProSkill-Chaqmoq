from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def _common_rows():
    return [
        [KeyboardButton(text="👤 Profil"), KeyboardButton(text="📜 Faoliyat tarixi")],
        [KeyboardButton(text="🔐 Xavfsizlik"), KeyboardButton(text="🔄 Profilni almashtirish")],
        [KeyboardButton(text="ℹ️ Yordam"), KeyboardButton(text="🚪 Chiqish")],
    ]


def get_teacher_main_menu():
    keyboard = [
        [KeyboardButton(text="📚 Guruhlarim"), KeyboardButton(text="✅ Davomat Belgilash")],
        [KeyboardButton(text="👥 O'quvchilarim"), KeyboardButton(text="💵 Oylik Daromadim")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📅 Dars Jadvalim")],
    ]
    keyboard.extend(_common_rows())
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_teacher_groups_keyboard(groups: list[dict], action: str):
    buttons = []
    for group in groups:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📚 {group['name']}",
                    callback_data=f"teacher:{action}:{group['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_teacher_attendance_keyboard(group_id: int, students: list[dict]):
    rows = []
    for student in students[:25]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✅ {student['full_name']}",
                    callback_data=f"teacher:mark:{group_id}:{student['id']}:present",
                ),
                InlineKeyboardButton(
                    text="❌ Kelmadi",
                    callback_data=f"teacher:mark:{group_id}:{student['id']}:absent",
                ),
            ]
        )
    rows.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"teacher:attendance:{group_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
