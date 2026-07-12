import httpx
import logging
from app_config import BACKEND_URL, API_SECRET

logger = logging.getLogger(__name__)

def _get_headers() -> dict:
    return {
        "X-API-SECRET": API_SECRET,
        "X-Forwarded-Proto": "https"
    }

async def link_account_api(phone: str, code: str, telegram_id: str, telegram_username: str = None):
    url = f"{BACKEND_URL}/api/v1/auth/link-telegram/"
    data = {
        "phone": phone,
        "code": code,
        "telegram_id": telegram_id,
        "telegram_username": telegram_username
    }
    headers = _get_headers()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_user_status_api(telegram_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-user-status/"
    params = {"telegram_id": telegram_id}
    headers = _get_headers()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_user_details_api(telegram_id: str, email: str = None):
    url = f"{BACKEND_URL}/hisob/login/bot-user-details/"
    params = {"telegram_id": telegram_id}
    if email:
        params["email"] = email
    headers = _get_headers()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}
async def unlink_account_api(telegram_id: str, email: str = None):
    url = f"{BACKEND_URL}/hisob/login/bot-unlink-telegram/"
    data = {"telegram_id": telegram_id}
    if email:
        data["email"] = email
    headers = _get_headers()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

# --- Admin APIs ---

async def get_admin_dashboard_api(admin_tg_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-admin-dashboard/"
    params = {"admin_tg_id": admin_tg_id}
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_app_adoption_api(admin_tg_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-app-adoption/"
    params = {"admin_tg_id": admin_tg_id}
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_linked_users_api(admin_tg_id: str, role: str = "all", offset: int = 0, limit: int = 20):
    url = f"{BACKEND_URL}/hisob/login/bot-linked-users/"
    params = {"admin_tg_id": admin_tg_id, "role": role, "offset": offset, "limit": limit}
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_broadcast_list_api(admin_tg_id: str, role: str = "all"):
    url = f"{BACKEND_URL}/hisob/login/bot-broadcast-list/"
    params = {"admin_tg_id": admin_tg_id, "role": role}
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def download_excel_api(admin_tg_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-excel-export/"
    params = {"admin_tg_id": admin_tg_id}
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.content
        except Exception as e:
            return 500, None

async def manage_admins_api(admin_tg_id: str, action: str = "list", target_tg_id: str = None, target_username: str = None):
    url = f"{BACKEND_URL}/hisob/login/bot-manage-admins/"
    params = {"admin_tg_id": admin_tg_id, "action": action}
    if target_tg_id: params["target_tg_id"] = target_tg_id
    if target_username: params["target_username"] = target_username
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_settings_api(admin_tg_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-settings/"
    params = {"admin_tg_id": admin_tg_id}
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def update_settings_api(admin_tg_id: str, data: dict):
    url = f"{BACKEND_URL}/hisob/login/bot-settings/"
    params = {"admin_tg_id": admin_tg_id}
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_parent_reports_api():
    url = f"{BACKEND_URL}/hisob/login/bot-parent-reports-data/"
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}


async def _bot_json_request(method: str, path: str, *, params: dict | None = None, data: dict | None = None):
    url = f"{BACKEND_URL}/hisob/login/{path.lstrip('/')}"
    headers = _get_headers()
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(method.upper(), url, params=params, json=data, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            logger.exception("Bot API request failed: %s %s", method, url)
            return 500, {"error": str(e)}


async def connect_parent_link_api(
    *,
    token: str,
    telegram_id: str,
    telegram_username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
):
    return await _bot_json_request(
        "POST",
        "bot-parent-connect/",
        data={
            "token": token,
            "telegram_id": telegram_id,
            "telegram_username": telegram_username or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
        },
    )


async def get_bot_dashboard_api(telegram_id: str, email: str, child_id: int | None = None, group_id: int | None = None):
    params = {"telegram_id": telegram_id, "email": email}
    if child_id:
        params["child_id"] = child_id
    if group_id:
        params["group_id"] = group_id
    return await _bot_json_request("GET", "bot-dashboard/", params=params)


async def update_notification_settings_api(telegram_id: str, email: str, enabled: bool):
    return await _bot_json_request(
        "POST",
        "bot-notification-settings/",
        data={"telegram_id": telegram_id, "email": email, "enabled": enabled},
    )


async def create_purchase_request_api(telegram_id: str, email: str, product_id: int, qty: int = 1):
    return await _bot_json_request(
        "POST",
        "bot-store-purchase-request/",
        data={"telegram_id": telegram_id, "email": email, "product_id": product_id, "qty": qty},
    )


async def get_group_attendance_sheet_api(telegram_id: str, email: str, group_id: int):
    return await _bot_json_request(
        "GET",
        "bot-group-attendance-sheet/",
        params={"telegram_id": telegram_id, "email": email, "group_id": group_id},
    )


async def mark_group_attendance_api(telegram_id: str, email: str, group_id: int, student_id: int, status: str):
    return await _bot_json_request(
        "POST",
        "bot-group-attendance-mark/",
        data={
            "telegram_id": telegram_id,
            "email": email,
            "group_id": group_id,
            "student_id": student_id,
            "status": status,
        },
    )


async def get_broadcast_audience_api(telegram_id: str, email: str, audience: str):
    return await _bot_json_request(
        "GET",
        "bot-broadcast-audience/",
        params={"telegram_id": telegram_id, "email": email, "audience": audience},
    )


async def search_inline_students_api(telegram_id: str, q: str):
    return await _bot_json_request(
        "GET",
        "bot-inline-student-search/",
        params={"telegram_id": telegram_id, "q": q},
    )


async def resolve_deep_link_api(telegram_id: str, email: str, param: str):
    return await _bot_json_request(
        "GET",
        "bot-deep-link/",
        params={"telegram_id": telegram_id, "email": email, "param": param},
    )


async def get_scheduler_payment_reminders_api():
    return await _bot_json_request("GET", "bot-scheduler-payment-reminders/")


async def get_scheduler_parent_attendance_api():
    return await _bot_json_request("GET", "bot-scheduler-parent-attendance/")


async def get_scheduler_weekly_reports_api():
    return await _bot_json_request("GET", "bot-scheduler-weekly-reports/")


async def get_scheduler_month_end_reminders_api():
    return await _bot_json_request("GET", "bot-scheduler-month-end-reminders/")


# ─── Family bot — telefon orqali ulanish ─────────────────────────────────
async def family_find_by_phone_api(
    *,
    phone: str,
    role: str,
    telegram_id: str,
    telegram_username: str | None = None,
):
    """Telefon raqami orqali ota-ona/o'quvchi yozuvini topish."""
    return await _bot_json_request(
        "POST",
        "bot-family-find-by-phone/",
        data={
            "phone": phone,
            "role": role,
            "telegram_id": telegram_id,
            "telegram_username": telegram_username,
        },
    )


async def family_issue_credentials_api(
    *,
    user_id: int,
    role: str,
    telegram_id: str | None = None,
):
    """Tanlangan o'quvchi/ota-ona uchun yangi parol yaratib qaytarish."""
    return await _bot_json_request(
        "POST",
        "bot-family-issue-credentials/",
        data={
            "user_id": user_id,
            "role": role,
            "telegram_id": telegram_id,
        },
    )


async def family_search_child_api(
    *,
    parent_user_id: int,
    name_query: str,
    telegram_id: str | None = None,
):
    """Ota-ona uchun farzand qidirish (parent markazi ichida)."""
    return await _bot_json_request(
        "POST",
        "bot-family-search-child/",
        data={
            "parent_user_id": parent_user_id,
            "name_query": name_query,
            "telegram_id": telegram_id,
        },
    )


async def family_add_child_api(
    *,
    parent_user_id: int,
    child_id: int,
    birth_date: str,
    telegram_id: str | None = None,
):
    """Ota-ona o'ziga farzandni biriktirish (tug'ilgan sana orqali tasdiqlash)."""
    return await _bot_json_request(
        "POST",
        "bot-family-add-child/",
        data={
            "parent_user_id": parent_user_id,
            "child_id": child_id,
            "birth_date": birth_date,
            "telegram_id": telegram_id,
        },
    )


async def family_student_by_name_api(
    *,
    name_query: str,
    birth_date: str,
    telegram_id: str | None = None,
):
    """O'quvchini ism + tug'ilgan sana orqali topish."""
    return await _bot_json_request(
        "POST",
        "bot-family-student-by-name/",
        data={
            "name_query": name_query,
            "birth_date": birth_date,
            "telegram_id": telegram_id,
        },
    )


async def family_confirm_link_api(
    *,
    user_id: int,
    role: str,
    telegram_id: str,
    telegram_username: str | None = None,
):
    """Profil tasdiqlash — User.telegram_id ni saqlash."""
    return await _bot_json_request(
        "POST",
        "bot-family-confirm-link/",
        data={
            "user_id": user_id,
            "role": role,
            "telegram_id": telegram_id,
            "telegram_username": telegram_username,
        },
    )
