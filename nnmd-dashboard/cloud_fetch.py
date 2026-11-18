# -*- coding: utf-8 -*-
"""
GitHub Actions용: OneDrive 공유 링크로 엑셀을 내려받아, 대시보드 내용이 바뀌었는지 확인한다.

환경변수 (GitHub Secret)
  XLSX_SHARE_URL   엑셀의 "링크가 있는 모든 사용자 - 보기" 공유 링크 (https://1drv.ms/x/c/...)

출력 ($GITHUB_OUTPUT)
  changed=true|false        대시보드에 표시될 내용이 바뀌었는지
  state_changed=true        상태(.state) 캐시 저장 필요 여부
  xlsx=<내려받은 파일 경로>

로그에는 링크·파일 내용을 남기지 않는다 (공개 저장소 대비).
"""
import hashlib
import os
import sys

import requests

import nnmd_dashboard as nd

STATE_FILE = os.path.join(".state", "digest")
# OneDrive는 브라우저가 아닌 요청(기본 User-Agent)을 차단하므로 브라우저처럼 요청
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def out(key, val):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={val}\n")


def download(url, dst):
    url = url.strip()
    print(f"::add-mask::{url}")
    url += ("&" if "?" in url else "?") + "download=1"
    s = requests.Session()
    s.headers["User-Agent"] = UA
    r = s.get(url, allow_redirects=True, timeout=120)
    if r.status_code != 200 or not r.content.startswith(b"PK"):
        sys.exit(f"[엑셀 다운로드 실패] HTTP {r.status_code}, 형식 {r.headers.get('content-type', '?')} "
                 "— 공유 링크가 '링크가 있는 모든 사용자'로 되어 있는지, 만료·삭제되지 않았는지 확인")
    with open(dst, "wb") as f:
        f.write(r.content)


def main():
    force = "--force" in sys.argv
    dst = os.path.abspath("work.xlsx")
    download(os.environ["XLSX_SHARE_URL"], dst)

    # 파일 자체가 아니라 '대시보드에 보일 내용'으로 비교 → 엑셀 서식만 바뀐 경우 등은 건너뜀
    nd.XLSX_PATH = dst
    body, _, _ = nd.build_body(nd.load_projects())
    digest = hashlib.sha1(body.encode("utf-8")).hexdigest()

    try:
        prev = open(STATE_FILE, encoding="utf-8").read().strip()
    except FileNotFoundError:
        prev = ""

    if not force and digest == prev:
        print("대시보드 내용 변경 없음")
        out("changed", "false")
        return

    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(digest)   # 이후 단계가 실패하면 캐시가 저장되지 않으므로 다음 실행에서 재시도됨
    print("대시보드 내용 변경 감지")
    out("changed", "true")
    out("state_changed", "true")
    out("xlsx", dst)


if __name__ == "__main__":
    main()
