import logging

from aiogram.fsm.context import FSMContext

from keyboards.menu import get_main_menu
from services.api_client import get_user_details_api

logger = logging.getLogger(__name__)


def _sender(event):
    return event.message if hasattr(event, "message") and event.message else event


async def sync_profile_state(state: FSMContext, telegram_id: str, email: str):
    status_code, response = await get_user_details_api(telegram_id, email=email)
    if status_code != 200:
        return None

    profile = response.get("profile", {})
    await state.update_data(
        current_user_email=email,
        current_user_role=profile.get("role_key"),
        current_user_name=profile.get("full_name"),
        current_user_id=profile.get("id"),
    )
    return profile


async def get_active_profile(state: FSMContext):
    data = await state.get_data()
    return {
        "email": data.get("current_user_email"),
        "role": data.get("current_user_role"),
        "name": data.get("current_user_name"),
        "user_id": data.get("current_user_id"),
        "child_id": data.get("selected_child_id"),
    }


async def ensure_active_profile(event, state: FSMContext, allowed_roles: tuple[str, ...] | None = None):
    profile = await get_active_profile(state)
    sender = _sender(event)

    if not profile.get("email"):
        await sender.answer("❌ Faol profil topilmadi. /start buyrug'ini yuboring.")
        return None

    if allowed_roles and profile.get("role") not in allowed_roles:
        await sender.answer(
            "❌ Bu bo'lim sizning joriy profilingiz uchun mavjud emas.",
            reply_markup=get_main_menu(profile.get("role")),
        )
        return None

    return profile


async def set_selected_child(state: FSMContext, child_id: int):
    await state.update_data(selected_child_id=child_id)
