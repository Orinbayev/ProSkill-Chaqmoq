from django.test import Client
from django.contrib.auth import get_user_model
import traceback

User = get_user_model()
client = Client()
user = User.objects.filter(role='director').first()

if user:
    client.force_login(user)
    print(f"Logged in as: {user}")
    
    try:
        response = client.get('/')
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print("ERROR OCCURRED!")
    except Exception as e:
        print(f"Exception: {e}")
        traceback.print_exc()
else:
    print("No director user found")
