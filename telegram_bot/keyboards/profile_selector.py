from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_profile_selection_keyboard(users: list, current_email: str = None, mode: str = "select"):
    """
    Generate inline buttons for multiple profile selection.
    mode: 'select' (for switching) or 'view' (for 👤 Profil details)
    """
    keyboard = []
    for user in users:
        is_current = (user.get('email') == current_email)
        indicator = "✅ " if is_current else ""
        
        # e.g. "👤 Ali (O'quvchi)"
        btn_text = f"{indicator}👤 {user.get('ism')} ({user.get('role_display')})"
        
        callback_prefix = "select_profile" if mode == "select" else "view_profile_details"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"{callback_prefix}:{user.get('email')}")])
    
    if mode == "select":
        keyboard.append([InlineKeyboardButton(text="➕ Yangi profil qo'shish", callback_data="add_profile")])
        keyboard.append([InlineKeyboardButton(text="❌ Hammasini uzish", callback_data="confirm_unlink_all")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_profile_management_keyboard(email: str):
    """Buttons for a specific profile (inside details view)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Faol qilish", callback_data=f"select_profile:{email}"),
            InlineKeyboardButton(text="🗑️ Uzib tashlash", callback_data=f"prompt_unlink_single:{email}")
        ],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_profiles")]
    ])

def get_confirmation_keyboard(action: str, data: str = ""):
    """Standard Yes/No keyboard for confirmation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ishonchim komil", callback_data=f"confirm:{action}:{data}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")
        ]
    ])
