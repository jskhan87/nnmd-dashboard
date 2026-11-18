# -*- coding: utf-8 -*-
"""
1회용: Microsoft 개인 계정 로그인 → refresh token 출력 (PC의 Anaconda Prompt에서 실행)

  python get_token.py <Application (client) ID>

화면에 나오는 주소에서 코드를 입력하고 로그인하면 refresh token이 출력된다.
출력된 값을 GitHub 저장소 Secret `MS_REFRESH_TOKEN`에 붙여 넣는다.
"""
import sys
import time

import requests

BASE = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
SCOPE = "Files.Read Tasks.Read offline_access"

if len(sys.argv) < 2:
    sys.exit("사용법: python get_token.py <client_id>")
cid = sys.argv[1]

r = requests.post(f"{BASE}/devicecode", data={"client_id": cid, "scope": SCOPE}, timeout=30).json()
if "device_code" not in r:
    sys.exit(f"오류: {r.get('error_description', r)}")
print("\n" + r["message"] + "\n")

while True:
    time.sleep(r.get("interval", 5))
    t = requests.post(f"{BASE}/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": cid, "device_code": r["device_code"]}, timeout=30).json()
    if "refresh_token" in t:
        print("=== MS_REFRESH_TOKEN (아래 한 줄 전체를 복사) ===")
        print(t["refresh_token"])
        break
    if t.get("error") not in ("authorization_pending", "slow_down"):
        sys.exit(f"오류: {t.get('error_description', t)}")
