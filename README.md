# zipsy-app
zipsy app for reporters

PDF에서 집회/시위 정보를 추출해 관할별(마영관/강광/중종)로 분류합니다.

## 구성

| 파일 | 설명 |
|---|---|
| `app.py` | Streamlit 웹 앱 |
| `telegram_bot.py` | 텔레그램 봇 |
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

### 실행

```bash
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="123456:ABC-xxxx"
export UPSTAGE_API_KEY="up_xxxx"

python telegram_bot.py
```

봇은 polling 방식으로 동작하므로 별도 서버 주소(웹훅) 설정 없이 아무 서버/PC에서나 실행하면 됩니다.

> 참고: 마지막으로 처리한 PDF 결과는 메모리에만 저장되므로, 봇을 재시작하면 키워드 조회를 위해 PDF를 다시 보내야 합니다.

## Streamlit 앱

```bash
pip install -r requirements.txt
export UPSTAGE_API_KEY="up_xxxx"   # 또는 Streamlit Secrets의 API_KEY
streamlit run app.py
```
