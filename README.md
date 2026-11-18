# NNMD 대시보드 — GitHub Actions 자동 갱신

OneDrive의 `_NNMD 운영 (통합).xlsx`를 5분마다 확인 → 바뀌었으면 `__DASHBOARD__.md`를 만들어 Obsidian Sync에 직접 올림.
연구실 PC가 꺼져 있어도 동작.

```
GitHub Actions (5분마다)
 ├ Microsoft Graph: 엑셀 변경 확인(cTag) → 바뀐 경우만 다운로드
 ├ nnmd_dashboard.py: md 생성
 └ obsidian-headless(ob): Obsidian Sync로 업로드 → 휴대폰 위젯
```

| 파일 | 역할 |
|---|---|
| `nnmd_dashboard.py` | 엑셀 → md 변환 (PC에서도 그대로 사용 가능) |
| `cloud_fetch.py` | OneDrive 엑셀 변경 확인·다운로드 |
| `get_token.py` | (1회) Microsoft 로그인 → refresh token 발급 |
| `.github/workflows/dashboard.yml` | 5분 주기 실행 |
| `.github/workflows/keepalive.yml` | 공개 저장소 60일 비활동 시 예약 실행 중지 방지 |

---

## 설정 (최초 1회)

### 1. GitHub 저장소
1. github.com → **New repository** → 이름 예: `nnmd-dashboard`
   - **Public**: Actions 무료 → 5분 주기 가능. 코드만 공개되고 엑셀·노트·토큰은 공개되지 않음(로그에도 남기지 않도록 처리).
   - **Private**: 무료 한도(월 $12 상당) 때문에 `dashboard.yml`의 cron을 `"*/30 * * * *"` 이상으로 늘려야 함.
2. 이 폴더의 파일을 모두 업로드 (`.github/workflows/` 포함).
   웹에서 폴더째 끌어다 놓기가 안 되면 **Add file → Create new file**에 경로 `.github/workflows/dashboard.yml`을 입력하고 내용 붙여넣기.

### 2. Microsoft 앱 등록 (OneDrive·To Do 읽기 권한)
1. https://entra.microsoft.com → **앱 등록(App registrations) → 새 등록**
   - 이름: `nnmd-dashboard`
   - 지원되는 계정 유형: **개인 Microsoft 계정만(Personal Microsoft accounts only)**
   - 리디렉션 URI: 비워 둠
2. 등록 후 **인증(Authentication) → 공용 클라이언트 흐름 허용(Allow public client flows) = 예** → 저장
3. **개요**의 **애플리케이션(클라이언트) ID** 복사
> 개인 계정으로 포털 진입이 막히면 무료 Azure 계정을 만들면 디렉터리가 생겨 등록 가능.

### 3. Microsoft refresh token (PC, Anaconda Prompt)
```
python get_token.py <클라이언트 ID>
```
안내된 주소에서 코드 입력 → **OneDrive가 있는 개인 계정**으로 로그인·동의 → 출력된 긴 문자열 복사.

### 4. Obsidian 토큰 (PC, CMD)
```
winget install OpenJS.NodeJS.LTS
```
CMD를 새로 열고:
```
npx -y -p obsidian-headless@0.0.14 ob login
npx -y -p obsidian-headless@0.0.14 ob sync-list-remote
type %USERPROFILE%\.obsidian-headless\auth_token
```
- 두 번째 줄에서 vault 이름 확인, 세 번째 줄 출력이 토큰.
- **PC에서 `ob sync-setup`·`ob sync`는 실행하지 말 것** (데스크톱 앱과 동시 동기화 금지). `ob logout`도 하지 말 것(토큰 무효화).

### 5. GitHub 토큰 (refresh token 자동 교체용)
github.com → Settings → Developer settings → **Fine-grained tokens → Generate**
- Repository access: `nnmd-dashboard`만
- Permissions → Repository → **Secrets: Read and write**
- 만료일 최대(1년) — 만료 전 재발급 필요

### 6. Secrets 등록
저장소 → Settings → Secrets and variables → Actions → **New repository secret**

| 이름 | 값 |
|---|---|
| `MS_CLIENT_ID` | 2번 클라이언트 ID |
| `MS_REFRESH_TOKEN` | 3번 출력값 |
| `OBSIDIAN_AUTH_TOKEN` | 4번 토큰 |
| `OB_VAULT` | 4번 vault 이름 |
| `OB_VAULT_PASSWORD` | vault가 종단간 암호화(E2E)일 때만 |
| `GH_PAT` | 5번 토큰 |

### 7. 시험 실행
Actions → **NNMD dashboard → Run workflow** (force 체크) → 초록색이면 휴대폰 Obsidian에서 확인.

### 8. PC 상주 스크립트 정리
클라우드와 PC가 같은 파일을 동시에 쓰면 충돌하므로:
- `Win + R` → `shell:startup` → `NNMD Dashboard` 바로가기 삭제
- 작업 관리자 → `pythonw.exe` 작업 끝내기

---

## 운영 메모
- 지연: GitHub 예약 실행은 부하에 따라 수 분~20분 밀리거나 가끔 건너뜀.
- vault에 최상위 폴더를 새로 만들면 `dashboard.yml`의 `OB_EXCLUDE`에 추가 (안 하면 실행 때마다 그 폴더도 내려받음).
- 실패 시 GitHub이 메일로 알림. 대표 원인: Microsoft 토큰 만료(3번 재실행), Obsidian 토큰 무효(4번 재실행), obsidian-headless 베타 변경.
- 잘못 올라간 경우 Obsidian Sync 버전 기록에서 복구 가능.
