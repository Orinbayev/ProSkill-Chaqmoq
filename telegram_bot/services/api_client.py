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

async def get_user_details_api(telegram_id: str):
    url = f"{BACKEND_URL}/hisob/login/bot-user-details/"
    params = {"telegram_id": telegram_id}
    headers = {"X-API-SECRET": API_SECRET}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            return response.status_code, response.json()
        except Exception as e:
            return 500, {"error": str(e)}
