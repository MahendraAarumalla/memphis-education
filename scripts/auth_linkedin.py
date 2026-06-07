"""
Run this ONCE locally to get your LinkedIn Access Token + Person URN.
Copy the output values into GitHub Secrets.

Usage:
  LINKEDIN_CLIENT_ID=xxx LINKEDIN_CLIENT_SECRET=yyy python scripts/auth_linkedin.py
"""
import os
import sys
import time
import threading
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

CLIENT_ID     = os.environ.get("LINKEDIN_CLIENT_ID")     or input("LinkedIn Client ID: ").strip()
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET") or input("LinkedIn Client Secret: ").strip()
REDIRECT_URI  = "http://localhost:8080/callback"
SCOPES        = "openid profile email w_member_social"

auth_url = (
    "https://www.linkedin.com/oauth/v2/authorization"
    f"?response_type=code"
    f"&client_id={urllib.parse.quote(CLIENT_ID)}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&state=memphis_education_automation"
)

_code = {}

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in qs:
            _code["value"] = qs["code"][0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Authorized. You can close this tab.</h2>")
    def log_message(self, *a):
        pass

server = HTTPServer(("localhost", 8080), _Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

print("\nOpening LinkedIn authorization page...")
webbrowser.open(auth_url)
print("Waiting for you to authorize the app...\n")

while "value" not in _code:
    time.sleep(0.2)
server.shutdown()

# Exchange code for access token
resp = requests.post(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data={
        "grant_type":    "authorization_code",
        "code":          _code["value"],
        "redirect_uri":  REDIRECT_URI,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
resp.raise_for_status()
token_data    = resp.json()
access_token  = token_data["access_token"]
expires_days  = token_data.get("expires_in", 0) // 86400

# Fetch person URN via OpenID userinfo
profile = requests.get(
    "https://api.linkedin.com/v2/userinfo",
    headers={"Authorization": f"Bearer {access_token}"},
).json()
person_urn = f"urn:li:person:{profile['sub']}"

print("=" * 60)
print("SUCCESS — add these as GitHub Secrets:")
print("=" * 60)
print(f"\nLINKEDIN_ACCESS_TOKEN={access_token}")
print(f"\nLINKEDIN_PERSON_URN={person_urn}")
print(f"\nToken expires in {expires_days} days.")
print("\nProfile:", profile.get("name", ""), "/", profile.get("email", ""))
