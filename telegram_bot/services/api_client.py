import httpx
from config import BACKEND_URL, API_SECRET

async def link_account_api(phone: str, code: str, telegram_id: str, telegram_username: str = None):
    url = f"{BACKEND_URL}/hisob/login/bot-link-telegram/" # Changed to match typical URL pattern if needed, but let's check auth_urls.py
    # Re-checking auth_urls: path('bot-link-telegram/', api_auth.link_telegram_api, name='bot_link_telegram'), 
    # Wait, I saw link-telegram/ earlier. Let me check auth_urls.py again.
    
    url = f"{BACKEND_URL}/api/v1/auth/link-telegram/"
    data = {
        "phone": phone,
        "code": code,
        "telegram_id": telegram_id,
        "telegram_username": telegram_username
    }
    headers = {"X-API-SECRET": API_SECRET}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_user_status_api(telegram_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-user-status/"
    params = {"telegram_id": telegram_id}
    headers = {"X-API-SECRET": API_SECRET}
    
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
    headers = {"X-API-SECRET": API_SECRET}
    
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
    headers = {"X-API-SECRET": API_SECRET}
    
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
    headers = {"X-API-SECRET": API_SECRET}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_linked_users_api(admin_tg_id: str, role: str = "all", offset: int = 0):
    url = f"{BACKEND_URL}/hisob/login/bot-linked-users/"
    params = {"admin_tg_id": admin_tg_id, "role": role, "offset": offset}
    headers = {"X-API-SECRET": API_SECRET}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_broadcast_list_api(admin_tg_id: str, role: str = "all"):
    url = f"{BACKEND_URL}/hisob/login/bot-broadcast-list/"
    params = {"admin_tg_id": admin_tg_id, "role": role}
    headers = {"X-API-SECRET": API_SECRET}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def download_excel_api(admin_tg_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-excel-export/"
    params = {"admin_tg_id": admin_tg_id}
    headers = {"X-API-SECRET": API_SECRET}
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
    headers = {"X-API-SECRET": API_SECRET}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_settings_api(admin_tg_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-settings/"
    params = {"admin_tg_id": admin_tg_id}
    headers = {"X-API-SECRET": API_SECRET}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def update_settings_api(admin_tg_id: str, data: dict):
    url = f"{BACKEND_URL}/hisob/login/bot-settings/"
    params = {"admin_tg_id": admin_tg_id}
    headers = {"X-API-SECRET": API_SECRET}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}

async def get_parent_reports_api():
    url = f"{BACKEND_URL}/hisob/login/bot-parent-reports-data/"
    headers = {"X-API-SECRET": API_SECRET}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}
