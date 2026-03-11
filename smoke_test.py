import os
import django
from django.test import Client
from django.urls import get_resolver, URLPattern, URLResolver

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def get_urls(url_patterns, prefix=''):
    urls = []
    for pattern in url_patterns:
        if isinstance(pattern, URLPattern):
            # Only test routes that don't have variables like <int:pk>
            if '<' not in str(pattern.pattern):
                urls.append(prefix + str(pattern.pattern))
        elif isinstance(pattern, URLResolver):
            urls.extend(get_urls(pattern.url_patterns, prefix + str(pattern.pattern)))
    return urls

urls = get_urls(get_resolver().url_patterns)
client = Client()

print(f"Testing {len(urls)} static URLs...")
for url in urls:
    if not url.startswith('/'):
        url = '/' + url
    try:
        response = client.get(url)
        if response.status_code >= 500:
            print(f"[{response.status_code}] {url}")
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
