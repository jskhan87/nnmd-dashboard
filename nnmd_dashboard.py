# -*- coding: utf-8 -*-
"""
NNMD 프로젝트 대시보드 생성기
  '_NNMD 운영 (통합).xlsx'의 [프로젝트] 시트를 읽어
  Obsidian vault에 모바일용 대시보드 노트(.md)를 생성한다.

사용법
  python nnmd_dashboard.py            # 1회 생성
  python nnmd_dashboard.py --watch    # 엑셀 저장 감지 시 자동 갱신 (PC 상주용)
  python nnmd_dashboard.py --xlsx <엑셀> --out <md>   # 경로 지정 (GitHub Actions용)

의존성: pip install openpyxl
"""
import datetime as dt
import hashlib
import os
import shutil
import sys
import tempfile
import time
import unicodedata
import warnings

import openpyxl

# 엑셀 드롭다운(데이터 유효성 검사 확장) 미지원 경고 숨김 — 읽기 전용이라 원본에 영향 없음
warnings.filterwarnings("ignore", message="Data Validation extension")

# ============================== 설정 ==============================
XLSX_PATH = r"C:\Users\jskha\OneDrive\_NNMD 운영 (통합).xlsx"
SHEET = "프로젝트"
OUT_PATH = r"C:\Users\jskha\OneDrive\문서\ObsidianLocal\ObsidianLocal\00_Inbox\__DASHBOARD__.md"

STAGES = ["아이디어/문헌", "실험조건확보", "초기데이터확보", "데이터확장",
          "협업추진", "논문작업", "섭밋/리비전", "게재"]
HIDE_STATUS = ["게재", "보류"]                # Status에 이 단어가 들어가면 대시보드에서 제외
GROUP_ORDER = ["소자", "소재", "기타", "장비"]   # 구분 값에 이 단어가 들어가면 이 순서로 (그 외는 맨 뒤)

# 열 이름 후보 (첫 15행 안에서 헤더 행 자동 탐지; 공백·대소문자 무시)
COLS = {
    "name":     ["프로젝트", "프로젝트명", "과제명", "project"],
    "group":    ["구분", "분류", "카테고리", "category"],
    "priority": ["우선", "우선순위", "priority"],
    "status":   ["status", "단계", "상태"],
    "next":     ["다음액션", "nextstep", "next", "nextaction", "다음단계", "다음할일"],
    "ball":     ["ball"],
    "owner":    ["담당", "담당자", "학생", "owner"],
    "updated":  ["업데이트", "최종업데이트", "updated", "수정일", "최종수정"],
    "due":      ["마감", "목표일", "due", "deadline"],
    "link":     ["링크", "link", "데이터", "ppt"],
}
POLL_SEC = 30      # --watch 모드 확인 주기
SETTLE_SEC = 10    # 저장 직후 OneDrive 동기화 안정화 대기
# ==================================================================

WD = "월화수목금토일"
KST = dt.timezone(dt.timedelta(hours=9))   # 실행 위치(클라우드=UTC)와 무관하게 한국 시각으로 표기


def norm(s):
    return "".join(str(s).split()).lower() if s is not None else ""


def find_header(ws):
    for r in range(1, 16):
        row = {norm(c.value): c.column for c in ws[r] if c.value is not None}
        idx = {}
        for key, cands in COLS.items():
            for cand in cands:
                if cand in row:
                    idx[key] = row[cand]
                    break
        if "name" in idx and ("ball" in idx or "next" in idx):
            return r, idx
    raise RuntimeError(f"[{SHEET}] 시트에서 '프로젝트'/'다음 액션' 헤더를 찾지 못함 — COLS 설정 확인")


def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%m/%d")
    return " ".join(str(v).split())


def http_link(cell):
    if cell.hyperlink is not None and cell.hyperlink.target and cell.hyperlink.target.startswith("http"):
        return cell.hyperlink.target
    if isinstance(cell.value, str) and cell.value.strip().startswith("http"):
        return cell.value.strip()
    return ""


def load_projects():
    # 열려 있거나 동기화 중인 파일을 피하려고 임시 사본에서 읽음
    tmp = os.path.join(tempfile.gettempdir(), "nnmd_dash_copy.xlsx")
    shutil.copy2(XLSX_PATH, tmp)
    wb = openpyxl.load_workbook(tmp, data_only=True)
    ws = wb[SHEET]
    hr, idx = find_header(ws)
    projects = []
    for r in range(hr + 1, ws.max_row + 1):
        get = lambda k: ws.cell(r, idx[k]) if k in idx else None
        name_c = get("name")
        name = cell_text(name_c.value)
        if not name:
            continue
        p = {k: cell_text(get(k).value) if get(k) else "" for k in COLS}
        p["name"] = name
        p["priority"] = p["priority"].upper()[:1]
        upd = get("updated").value if get("updated") else None
        p["updated_dt"] = upd if isinstance(upd, (dt.datetime, dt.date)) else None
        p["url"] = http_link(name_c) or (http_link(get("link")) if get("link") else "")
        projects.append(p)
    wb.close()
    return projects


def status_emoji(status):
    """'2 🛠 실험조건확보' → '🛠' : Status 값에서 이모지만 추출"""
    keep = []
    for ch in status:
        cat = unicodedata.category(ch)
        if cat in ("So", "Sk") or ch in "\u200d\ufe0f":
            keep.append(ch)
    return "".join(keep).strip("\u200d\ufe0f")


def esc(t):
    return t.replace("|", "\\|") if t else "—"


def sort_key(p):
    pri = {"A": 0, "B": 1, "C": 2}.get(p["priority"], 3)
    return (pri, p["name"])


def build_body(projects):
    hidden = lambda p: any(w in p["status"] for w in HIDE_STATUS)
    active = [p for p in projects if not hidden(p)]
    done = [p for p in projects if hidden(p)]
    out = []
    def gkey(g):
        for i, w in enumerate(GROUP_ORDER):
            if w and w in g:
                return (i, g)
        return (len(GROUP_ORDER) + (1 if not g else 0), g)
    groups = sorted({p["group"] for p in active}, key=gkey)
    for g in groups:
        items = sorted([p for p in active if p["group"] == g], key=sort_key)
        if not items:
            continue
        # 표 대신 한 줄 목록: 모바일에서 셀 여백·줄바꿈이 적음 (제목은 목록을 끊어주는 작은 헤딩)
        out.append(f"#### {g or '미분류'}")
        for p in items:
            name = f"[{p['name']}]({p['url']})" if p["url"] else p["name"]
            emo = status_emoji(p["status"])
            nxt = f" — {p['next']}" if p["next"] else ""
            out.append(f"- {emo + ' ' if emo else ''}**{name}**{nxt}")
    return "\n".join(out), len(active), len(done)


def generate(force=False):
    projects = load_projects()
    body, n_act, n_done = build_body(projects)
    digest = hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]

    # 내용이 같으면 파일을 다시 쓰지 않음 (동기화 충돌·불필요한 churn 방지)
    if not force and os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            if f"%%hash: {digest}%%" in f.read():
                return False

    now = dt.datetime.now(KST)
    # 속성(frontmatter) 상자를 없애 상단 여백 제거; 비교용 hash는 화면에 안 보이는 %% 주석으로 맨 끝에
    head = f"갱신 {now:%m/%d} ({WD[now.weekday()]}) {now:%H:%M}\n"
    body = body + f"\n%%hash: {digest}%%\n"
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + body)
    os.replace(tmp, OUT_PATH)   # 원자적 교체: 동기화 도구가 반쯤 쓴 파일을 올리지 않게
    return True


def watch():
    last = None
    print(f"감시 중: {XLSX_PATH}")
    while True:
        try:
            m = os.path.getmtime(XLSX_PATH)
            if m != last:
                time.sleep(SETTLE_SEC)
                if os.path.getmtime(XLSX_PATH) == m:
                    changed = generate()
                    print(f"{dt.datetime.now(KST):%H:%M:%S} {'갱신' if changed else '변경 없음'}")
                    last = m
        except Exception as e:      # 동기화 중 잠금 등은 다음 주기에 재시도
            print(f"{dt.datetime.now(KST):%H:%M:%S} 대기: {e}")
        time.sleep(POLL_SEC)


def _arg(name):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


if __name__ == "__main__":
    XLSX_PATH = _arg("--xlsx") or XLSX_PATH
    OUT_PATH = _arg("--out") or OUT_PATH
    if "--watch" in sys.argv:
        watch()
    else:
        print("갱신" if generate(force="--force" in sys.argv) else "변경 없음")
