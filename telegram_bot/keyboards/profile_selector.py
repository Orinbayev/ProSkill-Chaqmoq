from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_profile_selection_keyboard(users: list):
    """Generate inline buttons for multiple profile selection."""
    keyboard = []
    for user in users:
        # e.g. "👤 Ali (O'quvchi)"
        btn_text = f"👤 {user.get('ism')} ({user.get('role_display')})"
        # Callback data should include email or ID to unique identify
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"select_profile:{user.get('email')}")])
    
    # Optional: Logout / Add another button
    keyboard.append([InlineKeyboardButton(text="➕ Yangi profil qo'shish", callback_data="add_profile")])
    keyboard.append([InlineKeyboardButton(text="❌ Hammasini uzish", callback_data="confirm_unlink_all")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirmation_keyboard(action: str, data: str = ""):
    """Standard Yes/No keyboard for confirmation."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm:{action}:{data}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel")
        ]
    ])
