# -*- coding: utf-8 -*-
"""
GitHub Actions용: OneDrive의 엑셀이 바뀌었는지 확인하고, 바뀌었으면 내려받는다.

환경변수 (GitHub Secrets/Variables)
  MS_CLIENT_ID      Entra 앱 등록의 Application (client) ID
  MS_REFRESH_TOKEN  get_token.py로 받은 refresh token
  XLSX_ONEDRIVE_PATH  OneDrive 루트 기준 엑셀 경로 (예: "_NNMD 운영 (통합).xlsx")
  GH_PAT, GITHUB_REPOSITORY  (선택) refresh token 자동 교체용

출력 ($GITHUB_OUTPUT)
  changed=true|false
  xlsx=<내려받은 파일 경로>

로그에는 파일 내용·이름을 남기지 않는다 (공개 저장소 대비).
"""
import datetime as dt
import os
import subprocess
import sys
import urllib.parse

import requests

TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
SCOPE = "Files.Read Tasks.Read offline_access"
GRAPH = "https://graph.microsoft.com/v1.0"
STATE_DIR = ".state"
ETAG_FILE = os.path.join(STATE_DIR, "etag")
ROTATED_FILE = os.path.join(STATE_DIR, "rotated")


def out(key, val):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={val}\n")


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def get_access_token():
    r = requests.post(TOKEN_URL, data={
        "client_id": os.environ["MS_CLIENT_ID"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["MS_REFRESH_TOKEN"],
        "scope": SCOPE,
    }, timeout=30)
    if r.status_code != 200:
        err = r.json().get("error", r.status_code)
        sys.exit(f"[토큰 갱신 실패] {err} — get_token.py로 refresh token을 다시 받아 MS_REFRESH_TOKEN을 갱신하세요.")
    j = r.json()
    new_rt = j.get("refresh_token")
    if new_rt:
        print(f"::add-mask::{new_rt}")
    print(f"::add-mask::{j['access_token']}")
    return j["access_token"], new_rt


def rotate_refresh_token(new_rt):
    """refresh token은 쓸 때마다 새것이 발급되고 각자 만료(약 90일)가 있으므로 하루 한 번 Secret을 교체."""
    today = dt.date.today().isoformat()
    if not new_rt or read(ROTATED_FILE) == today:
        return
    pat, repo = os.environ.get("GH_PAT"), os.environ.get("GITHUB_REPOSITORY")
    if not pat or not repo:
        print("::warning::GH_PAT 없음 — refresh token 자동 교체 생략 (약 90일 후 수동 갱신 필요)")
        return
    r = subprocess.run(["gh", "secret", "set", "MS_REFRESH_TOKEN", "--repo", repo],
                       input=new_rt, text=True, env={**os.environ, "GH_TOKEN": pat},
                       capture_output=True)
    if r.returncode == 0:
        write(ROTATED_FILE, today)
        out("state_changed", "true")
        print("refresh token 교체 완료")
    else:
        print("::warning::refresh token 교체 실패 (다음 실행에서 재시도)")


def main():
    force = "--force" in sys.argv
    token, new_rt = get_access_token()
    h = {"Authorization": f"Bearer {token}"}
    path = urllib.parse.quote(os.environ["XLSX_ONEDRIVE_PATH"].strip("/"))

    meta = requests.get(f"{GRAPH}/me/drive/root:/{path}", headers=h,
                        params={"$select": "id,eTag,cTag,lastModifiedDateTime"}, timeout=30)
    if meta.status_code != 200:
        sys.exit(f"[엑셀 조회 실패] HTTP {meta.status_code} — XLSX_ONEDRIVE_PATH 확인")
    m = meta.json()
    tag = m.get("cTag") or m.get("eTag")   # cTag: 내용이 바뀔 때만 변경

    rotate_refresh_token(new_rt)

    if not force and tag == read(ETAG_FILE):
        print("엑셀 변경 없음")
        out("changed", "false")
        return

    data = requests.get(f"{GRAPH}/me/drive/items/{m['id']}/content", headers=h, timeout=120)
    if data.status_code != 200:
        sys.exit(f"[엑셀 다운로드 실패] HTTP {data.status_code}")
    dst = os.path.abspath("work.xlsx")
    with open(dst, "wb") as f:
        f.write(data.content)
    write(ETAG_FILE, tag)     # 이후 단계가 실패하면 캐시가 저장되지 않으므로 다음 실행에서 재시도됨
    out("state_changed", "true")
    print("엑셀 변경 감지 → 내려받음")
    out("changed", "true")
    out("xlsx", dst)


if __name__ == "__main__":
    main()
