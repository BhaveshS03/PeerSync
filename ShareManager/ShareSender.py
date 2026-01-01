import requests

BASE_URL = "http://127.0.0.1:8000"

# GET request
resp = requests.get(f"{BASE_URL}/")
print("Health:", resp.json())

# POST request
payload = {
    "text": "Hello from Python client"
}

resp = requests.post(f"{BASE_URL}/send", json=payload)
print("Response:", resp.json())
