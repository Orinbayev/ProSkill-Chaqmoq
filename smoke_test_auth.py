import os
import django
from django.test import Client
from django.urls import get_resolver, URLPattern, URLResolver

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
# Login as director
user = User.objects.get(phone_number='+998901112112')

def get_urls(url_patterns, prefix=''):
    urls = []
    for pattern in url_patterns:
        if isinstance(pattern, URLPattern):
            if '<' not in str(pattern.pattern):
                urls.append(prefix + str(pattern.pattern))
        elif isinstance(pattern, URLResolver):
            urls.extend(get_urls(pattern.url_patterns, prefix + str(pattern.pattern)))
    return urls

urls = get_urls(get_resolver().url_patterns)
client = Client()
client.force_login(user)

print(f"Testing {len(urls)} URLs as director...")
errors = 0
for url in urls:
    if not url.startswith('/'):
        url = '/' + url
    if url.startswith('/admin/'):
        continue # Skip admin views that are known to fail on Python 3.14
    try:
        response = client.get(url)
        if response.status_code >= 500:
            print(f"[{response.status_code}] {url}")
            errors += 1
    except Exception as e:
        print(f"[EXCEPTION] {url}: {e}")
        errors += 1

print(f"Found {errors} failing non-admin pages.")
