from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def _common_rows():
    # Soddalashtirildi: 📜 Faoliyat tarixi → 🔐 Xavfsizlik ichiga; 🔄 Profilni
    # almashtirish → 👤 Profil ichida (ko'p profil bo'lsa u yerдан almashtiriladi).
    return [
        [KeyboardButton(text="👤 Profil"), KeyboardButton(text="🔐 Xavfsizlik")],
        [KeyboardButton(text="ℹ️ Yordam"), KeyboardButton(text="🚪 Chiqish")],
    ]


def get_teacher_main_menu():
    # Soddalashtirildi: "Davomat belgilash" + "O'quvchilarim" → "📚 Guruhlarim" ichига
    # (guruhni tanlab, o'quvchilarni ko'rasiz yoki davomat belgilaysiz).
    # "📊 Statistika" olib tashlandi (u superadmin/bot admin statistikasi edi).
    keyboard = [
        [KeyboardButton(text="📚 Guruhlarim"), KeyboardButton(text="💵 Oylik Daromadim")],
        [KeyboardButton(text="📅 Dars Jadvalim")],
    ]
    keyboard.extend(_common_rows())
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_teacher_groups_keyboard(groups: list[dict], action: str = "group"):
    """Har guruh — bosiladigan tugma (default: guruh detali)."""
    buttons = []
    for group in groups:
        cnt = group.get("student_count", 0)
        buttons.append([
            InlineKeyboardButton(
                text=f"📚 {group['name']} · {cnt}👤",
                callback_data=f"teacher:{action}:{group['id']}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_teacher_group_detail_kb(group_id: int):
    """Bitta guruh: davomat belgilash / o'quvchilar / orqaga."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Davomat belgilash", callback_data=f"teacher:attendance:{group_id}")],
        [InlineKeyboardButton(text="👥 O'quvchilar ro'yxati", callback_data=f"teacher:students:{group_id}")],
        [InlineKeyboardButton(text="⬅️ Guruhlarga qaytish", callback_data="teacher:grouplist")],
    ])


def get_teacher_attendance_keyboard(group_id: int, students: list[dict]):
    rows = []
    for student in students[:25]:
        rows.append([
            InlineKeyboardButton(
                text=f"✅ {student['full_name']}",
                callback_data=f"teacher:mark:{group_id}:{student['id']}:present",
            ),
            InlineKeyboardButton(
                text="❌ Kelmadi",
                callback_data=f"teacher:mark:{group_id}:{student['id']}:absent",
            ),
        ])
    rows.append([
        InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"teacher:attendance:{group_id}"),
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"teacher:group:{group_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
