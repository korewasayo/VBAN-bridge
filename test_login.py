import requests

try:
    response = requests.get('http://127.0.0.01:8000/login?token=test_token')
    print(response.status_code)
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
