"""GitHub Actions용 텔레그램 봇 폴러

서버 없이 GitHub Actions 스케줄로 주기적으로 실행되어,
밀린 텔레그램 메시지를 가져와 처리하고 종료합니다.

- PDF 문서 → 집회/시위 정보 추출 후 마영관/강광/중종 분류 결과 전송
- "마영관"/"강광"/"중종"/"전체" 텍스트 → 마지막 PDF 결과에서 해당 분류만 전송
  (분류 결과는 state/bot_state.json 에 저장되어 Actions 캐시로 다음 실행에 전달)

필요한 환경변수:
  TELEGRAM_BOT_TOKEN - BotFather에서 발급받은 봇 토큰
  UPSTAGE_API_KEY    - Upstage Document Parse API 키
선택 환경변수:
  BOT_RUN_SECONDS    - 한 번 실행 시 폴링을 유지할 시간(초), 기본 270
  BOT_STATE_FILE     - 상태 파일 경로, 기본 state/bot_state.json
"""
import io
import json
import logging
import os
import time

import requests

from pdf_parser import classify_entries, extract_entries, process_pdf

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
UPSTAGE_API_KEY = os.environ["UPSTAGE_API_KEY"]
API = f"https://api.telegram.org/bot{TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{TOKEN}"

STATE_FILE = os.getenv("BOT_STATE_FILE", "state/bot_state.json")
RUN_SECONDS = int(os.getenv("BOT_RUN_SECONDS", "270"))

MAX_MESSAGE_LENGTH = 4000

HELP_TEXT = (
    "📋 집회시위 정보 추출 봇\n\n"
    "1. PDF 파일을 보내주세요. 집회/시위 정보를 자동으로 추출해서 관할별로 분류해 드립니다.\n"
    "2. 그 다음 아래 키워드를 보내면 해당 분류만 다시 보내드립니다.\n"
    "   - 마영관\n"
    "   - 강광\n"
    "   - 중종\n"
    "   - 전체\n\n"
    "⏱ 봇은 몇 분 간격으로 메시지를 확인하므로 답장이 조금 늦을 수 있습니다."
)


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"offset": 0, "chats": {}}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def split_message(text):
    """4096자 제한에 맞춰 줄 단위로 메시지 분할"""
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        while len(line) > MAX_MESSAGE_LENGTH:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:MAX_MESSAGE_LENGTH])
            line = line[MAX_MESSAGE_LENGTH:]

        if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line

    if current:
        chunks.append(current)
    return chunks


def build_section(name, entries):
    header = f"=== {name} ===\n총 {len(entries)}건"
    if not entries:
        return header + "\n\n(해당 없음)"
    return header + "\n\n" + "\n".join(entries)


def send_message(chat_id, text):
    for chunk in split_message(text):
        r = requests.post(
            f"{API}/sendMessage",
            json={"chat_id": chat_id, "text": chunk},
            timeout=30,
        )
        if not r.ok:
            logger.error("sendMessage 실패: %s", r.text)


def download_document(document):
    r = requests.get(f"{API}/getFile", params={"file_id": document["file_id"]}, timeout=30)
    r.raise_for_status()
    file_path = r.json()["result"]["file_path"]
    r = requests.get(f"{FILE_API}/{file_path}", timeout=120)
    r.raise_for_status()
    return r.content


def handle_pdf(state, chat_id, document):
    file_name = document.get("file_name") or "document.pdf"
    is_pdf = "pdf" in (document.get("mime_type") or "").lower() or file_name.lower().endswith(".pdf")
    if not is_pdf:
        send_message(chat_id, "PDF 파일만 처리할 수 있습니다.")
        return

    send_message(chat_id, "📄 PDF 파일을 처리 중입니다. 잠시만 기다려주세요...")

    pdf_bytes = download_document(document)
    response_data = process_pdf((file_name, io.BytesIO(pdf_bytes)), UPSTAGE_API_KEY)

    if "elements" not in response_data:
        logger.error("Upstage API 오류 응답: %s", response_data)
        send_message(chat_id, "PDF 분석에 실패했습니다. API 키 설정을 확인하거나 잠시 후 다시 시도해주세요.")
        return

    formatted_entries = extract_entries(response_data)
    mayoung, ganggwang, jungjong = classify_entries(formatted_entries)

    state["chats"][str(chat_id)] = {
        "마영관": mayoung,
        "강광": ganggwang,
        "중종": jungjong,
        "전체": formatted_entries,
    }

    if not formatted_entries:
        send_message(chat_id, "추출된 집회/시위 정보가 없습니다.")
        return

    send_message(
        chat_id,
        f"✅ 처리 완료! 총 {len(formatted_entries)}건의 정보를 추출했습니다.\n"
        f"🔵 마영관: {len(mayoung)}건\n"
        f"🟢 강광: {len(ganggwang)}건\n"
        f"🟡 중종: {len(jungjong)}건",
    )
    for name, entries in (("마영관", mayoung), ("강광", ganggwang), ("중종", jungjong)):
        send_message(chat_id, build_section(name, entries))
    send_message(chat_id, "특정 분류만 다시 보려면 '마영관', '강광', '중종', '전체' 중 하나를 보내주세요.")


def handle_text(state, chat_id, text):
    keyword = text.strip()
    if keyword in ("/start", "/help"):
        send_message(chat_id, HELP_TEXT)
        return

    if keyword in ("마영관", "강광", "중종", "전체"):
        results = state["chats"].get(str(chat_id))
        if not results:
            send_message(chat_id, "먼저 PDF 파일을 보내주세요.")
            return
        send_message(chat_id, build_section(keyword, results[keyword]))
    else:
        send_message(chat_id, HELP_TEXT)


def handle_update(state, update):
    message = update.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]

    try:
        if "document" in message:
            handle_pdf(state, chat_id, message["document"])
        elif "text" in message:
            handle_text(state, chat_id, message["text"])
    except Exception:
        logger.exception("메시지 처리 중 오류 (chat_id=%s)", chat_id)
        try:
            send_message(chat_id, "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        except Exception:
            pass


def main():
    state = load_state()
    offset = int(state.get("offset", 0))
    deadline = time.time() + RUN_SECONDS
    processed = 0

    logger.info("폴링 시작 (최대 %d초, offset=%d)", RUN_SECONDS, offset)

    while time.time() < deadline:
        timeout = max(1, min(30, int(deadline - time.time())))
        try:
            r = requests.get(
                f"{API}/getUpdates",
                params={"offset": offset, "timeout": timeout},
                timeout=timeout + 15,
            )
            updates = r.json().get("result", [])
        except requests.RequestException as e:
            logger.warning("getUpdates 실패, 재시도: %s", e)
            time.sleep(3)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            handle_update(state, update)
            processed += 1
            state["offset"] = offset
            save_state(state)

    # 처리 완료한 업데이트를 텔레그램 서버에서 확정(삭제)
    try:
        requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 0}, timeout=15)
    except requests.RequestException:
        pass

    state["offset"] = offset
    save_state(state)
    logger.info("폴링 종료 (처리한 메시지 %d건)", processed)


if __name__ == "__main__":
    main()
