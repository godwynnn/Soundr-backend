import requests

# Test data
url = "http://127.0.0.1:8000/auth/convert-token"
data = {
    "grant_type": "convert_token",
    "client_id": "N77chEVa9JKhYjYogK83UC42dYXaThGJErTC62iJ",
    # "client_secret": "...", # Trying without secret for public app
    "backend": "google-oauth2",
    "token": "dummy-token"
}

response = requests.post(url, data=data)
print(f"Status: {response.status_code}")
print(f"JSON: {response.json()}")
