# NNMD 대시보드 — GitHub Actions 자동 갱신

OneDrive 공유 링크로 `_NNMD 운영 (통합).xlsx`를 5분마다 내려받아, 대시보드 내용이 바뀌었으면
`00_Inbox/__DASHBOARD__.md`를 만들어 Obsidian Sync에 직접 올림. 연구실 PC가 꺼져 있어도 동작.

```
GitHub Actions (5분마다)
 ├ 공유 링크로 엑셀 다운로드 → 대시보드 내용 비교
 ├ 바뀐 경우만: nnmd_dashboard.py로 md 생성
 └ obsidian-headless(ob)로 Obsidian Sync 업로드 → 휴대폰 위젯
```

| 파일 | 역할 |
|---|---|
| `nnmd_dashboard.py` | 엑셀 → md 변환 (PC에서도 그대로 사용 가능) |
| `cloud_fetch.py` | 공유 링크로 엑셀 다운로드·변경 확인 |
| `.github/workflows/dashboard.yml` | 5분 주기 실행 |
| `.github/workflows/keepalive.yml` | 공개 저장소 60일 비활동 시 예약 실행 중지 방지 |

---

## 설정 (최초 1회)

### 1. 엑셀 공유 링크
1. onedrive.live.com에서 `_NNMD 운영 (통합).xlsx` 선택 → **공유**
2. 링크 설정: **링크가 있는 모든 사용자**, 권한 **보기 가능** (편집 허용 끔)
3. **링크 복사** (`https://1drv.ms/x/c/...` 형태)

> 이 링크를 가진 사람은 누구나 엑셀을 볼 수 있음. GitHub Secret에만 넣고 다른 곳에 붙이지 말 것.
> 노출이 의심되면 OneDrive 공유 관리에서 링크 삭제 → 새 링크로 Secret 교체.

### 2. Obsidian 토큰 (PC, CMD)
```
winget install OpenJS.NodeJS.LTS
```
CMD를 새로 열고:
```
npx -y -p obsidian-headless@0.0.14 ob login
npx -y -p obsidian-headless@0.0.14 ob sync-list-remote
type %USERPROFILE%\.obsidian-headless\auth_token
```
- 두 번째 줄 출력에서 vault 이름 확인, 세 번째 줄 출력이 토큰.
- **PC에서 `ob sync-setup`·`ob sync`는 실행하지 말 것** (데스크톱 앱과 동시 동기화 금지). `ob logout`도 하지 말 것(토큰 무효화).

### 3. GitHub 저장소
1. github.com → **New repository** → 이름 예: `nnmd-dashboard`, **Public**
   - Public: Actions 무료 → 5분 주기 가능. 공개되는 것은 코드뿐(엑셀·링크·토큰·노트는 비공개, 로그에도 남기지 않음).
   - Private로 하려면 무료 한도 때문에 `dashboard.yml`의 cron을 `"*/30 * * * *"` 이상으로 늘릴 것.
2. 이 폴더의 파일을 모두 업로드 (`.github/workflows/` 포함).
   웹에서 폴더째 끌어다 놓기가 안 되면 **Add file → Create new file**에 경로 `.github/workflows/dashboard.yml`을 입력하고 내용 붙여넣기.

### 4. Secrets 등록
저장소 → Settings → Secrets and variables → Actions → **New repository secret**

| 이름 | 값 |
|---|---|
| `XLSX_SHARE_URL` | 1번 공유 링크 |
| `OBSIDIAN_AUTH_TOKEN` | 2번 토큰 |
| `OB_VAULT` | 2번 vault 이름 |
| `OB_VAULT_PASSWORD` | vault가 종단간 암호화(E2E)일 때만 |

### 5. 시험 실행
Actions → **NNMD dashboard → Run workflow** (force 체크) → 초록색이면 휴대폰 Obsidian에서 확인.

### 6. PC 상주 스크립트 정리
클라우드와 PC가 같은 파일을 동시에 쓰면 충돌하므로:
- `Win + R` → `shell:startup` → `NNMD Dashboard` 바로가기 삭제
- 작업 관리자 → `pythonw.exe` 작업 끝내기

---

## 운영 메모
- 지연: GitHub 예약 실행은 부하에 따라 수 분~20분 밀리거나 가끔 건너뜀.
- 엑셀을 고쳐도 대시보드에 보이는 내용(구분·프로젝트·Status 이모지·다음 액션)이 그대로면 갱신하지 않음.
- vault에 최상위 폴더를 새로 만들면 `dashboard.yml`의 `OB_EXCLUDE`에 추가 (안 하면 실행 때마다 그 폴더도 내려받음).
- 실패 시 GitHub이 메일로 알림. 대표 원인: 공유 링크 해제·변경(1번), Obsidian 토큰 무효(2번), OneDrive 다운로드 방식 변경, obsidian-headless 베타 변경.
- 잘못 올라간 경우 Obsidian Sync 버전 기록에서 복구 가능.
