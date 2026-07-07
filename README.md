# zipsy-app
zipsy app for reporters

PDF에서 집회/시위 정보를 추출해 관할별(마영관/강광/중종)로 분류합니다.

## 구성

| 파일 | 설명 |
|---|---|
| `app.py` | Streamlit 웹 앱 |
| `telegram_bot.py` | 텔레그램 봇 (서버에 상시 실행하는 방식) |
| `bot_poll.py` | 텔레그램 봇 (GitHub Actions로 주기 실행하는 방식, 서버 불필요) |
| `.github/workflows/telegram-bot.yml` | 5분마다 `bot_poll.py`를 실행하는 워크플로 |
| `pdf_parser.py` | 공용 PDF 파싱/분류 로직 |

## 텔레그램 봇

### 사용법
1. 봇에게 PDF 파일을 보내면 정보를 추출해 마영관/강광/중종으로 분류해서 보내줍니다.
2. 이후 `마영관`, `강광`, `중종`, `전체` 를 텍스트로 보내면 해당 분류만 다시 보내줍니다.

### 필요한 환경변수

| 환경변수 | 설명 | 발급처 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 | 텔레그램에서 [@BotFather](https://t.me/BotFather)에게 `/newbot` 명령으로 발급 |
| `UPSTAGE_API_KEY` | Upstage Document Parse API 키 | https://console.upstage.ai (기존 Streamlit 앱과 동일한 키) |

### 실행 방법 1: GitHub Actions (서버 불필요, 권장)

서버 없이 GitHub Actions가 5분마다 깨어나 밀린 메시지를 처리합니다.
답장이 즉각적이지 않고 **몇 분 정도 늦게** 올 수 있습니다.

설정 순서:

1. GitHub 레포 → **Settings → Secrets and variables → Actions → New repository secret**에서 두 개 등록:
   - `TELEGRAM_BOT_TOKEN`
   - `UPSTAGE_API_KEY`
2. 이 브랜치를 `main`에 머지 (스케줄 워크플로는 기본 브랜치에서만 동작)
3. 끝. 이후 자동으로 5분마다 실행됩니다. **Actions 탭 → Telegram Bot → Run workflow**로 즉시 수동 실행도 가능합니다.

> - 마지막 PDF 분류 결과는 Actions 캐시에 저장되어 다음 실행에서도 키워드 조회가 가능합니다. 캐시는 7일간 미사용 시 삭제되므로, 오래돼서 결과가 없다고 나오면 PDF를 다시 보내면 됩니다.
> - 공개(public) 레포는 Actions 사용량이 무료입니다. 비공개 레포는 월 무료 사용량(2,000분)을 초과할 수 있으니 주의하세요.

### 실행 방법 2: 서버/PC에서 상시 실행

```bash
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="123456:ABC-xxxx"
export UPSTAGE_API_KEY="up_xxxx"

python telegram_bot.py
```

polling 방식이므로 별도 서버 주소(웹훅) 설정 없이 아무 서버/PC에서나 실행하면 되고, 답장이 즉시 옵니다.

> 참고: 이 방식에서는 마지막 PDF 결과가 메모리에만 저장되므로, 봇을 재시작하면 키워드 조회를 위해 PDF를 다시 보내야 합니다.

## Streamlit 앱

```bash
pip install -r requirements.txt
export UPSTAGE_API_KEY="up_xxxx"   # 또는 Streamlit Secrets의 API_KEY
streamlit run app.py
```
