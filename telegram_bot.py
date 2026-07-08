"""집회시위 정보 추출 텔레그램 봇

사용법:
  1. PDF 파일을 봇에게 보내면 집회/시위 정보를 추출해 마영관/강광/중종으로 분류하여 보내줍니다.
  2. 이후 "마영관", "강광", "중종", "전체" 라고 보내면 해당 분류의 텍스트만 다시 보내줍니다.

필요한 환경변수:
  TELEGRAM_BOT_TOKEN - BotFather에서 발급받은 봇 토큰
  UPSTAGE_API_KEY    - Upstage Document Parse API 키
선택 환경변수:
  ALLOWED_CHAT_IDS   - 허용할 chat_id 목록(쉼표 구분). 비워두면 모두 허용
"""
import asyncio
import io
import logging
import os
import time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pdf_parser import classify_entries, extract_entries, process_pdf

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
ALLOWED_CHAT_IDS = {s.strip() for s in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if s.strip()}

# 텔레그램 메시지 최대 길이는 4096자 — 여유를 두고 분할
MAX_MESSAGE_LENGTH = 4000

HELP_TEXT = (
    "📋 집회시위 정보 추출 봇\n\n"
    "1. PDF 파일을 보내주세요. 집회/시위 정보를 자동으로 추출해서 관할별로 분류해 드립니다.\n"
    "2. 그 다음 아래 키워드를 보내면 해당 분류만 다시 보내드립니다.\n"
    "   - 마영관\n"
    "   - 강광\n"
    "   - 중종\n"
    "   - 전체\n\n"
    "분류 기준:\n"
    "- 마영관: 마포, 서대문, 은평, 서부, 영등포, 구로, 강서, 양천, 관악, 방배, 금천, 동작\n"
    "- 강광: 강남, 서초, 수서, 송파, 성동, 강동, 광진\n"
    "- 중종: 나머지 지역"
)


def split_message(text):
    """4096자 제한에 맞춰 줄 단위로 메시지 분할"""
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        # 한 줄 자체가 너무 길면 강제로 자름
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


async def send_long_message(update, text):
    for chunk in split_message(text):
        await update.message.reply_text(chunk)


def build_section(name, entries):
    header = f"=== {name} ===\n총 {len(entries)}건"
    if not entries:
        return header + "\n\n(해당 없음)"
    return header + "\n\n" + "\n".join(entries)


async def check_allowed(update):
    """ALLOWED_CHAT_IDS가 설정된 경우 허용된 채팅인지 확인"""
    chat_id = update.message.chat_id
    if ALLOWED_CHAT_IDS and str(chat_id) not in ALLOWED_CHAT_IDS:
        await update.message.reply_text(
            f"이 봇을 사용할 권한이 없습니다. (당신의 chat_id: {chat_id})"
        )
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_allowed(update):
        return
    await update.message.reply_text(HELP_TEXT)


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_allowed(update):
        return
    document = update.message.document
    if not (
        (document.mime_type and "pdf" in document.mime_type.lower())
        or (document.file_name and document.file_name.lower().endswith(".pdf"))
    ):
        await update.message.reply_text("PDF 파일만 처리할 수 있습니다.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("📄 PDF 파일을 처리 중입니다. 잠시만 기다려주세요...")

    try:
        tg_file = await document.get_file()
        pdf_bytes = await tg_file.download_as_bytearray()

        pdf_file = (document.file_name or "document.pdf", io.BytesIO(bytes(pdf_bytes)))
        response_data = process_pdf(pdf_file, UPSTAGE_API_KEY)

        if "elements" not in response_data:
            logger.error("Upstage API 오류 응답: %s", response_data)
            await update.message.reply_text(
                "PDF 분석에 실패했습니다. API 키 설정을 확인하거나 잠시 후 다시 시도해주세요."
            )
            return

        formatted_entries = extract_entries(response_data)
        mayoung, ganggwang, jungjong = classify_entries(formatted_entries)

        # 이후 키워드 조회를 위해 채팅별로 결과 저장
        context.chat_data["results"] = {
            "마영관": mayoung,
            "강광": ganggwang,
            "중종": jungjong,
            "전체": formatted_entries,
        }

        if not formatted_entries:
            await update.message.reply_text("추출된 집회/시위 정보가 없습니다.")
            return

        summary = (
            f"✅ 처리 완료! 총 {len(formatted_entries)}건의 정보를 추출했습니다.\n"
            f"🔵 마영관: {len(mayoung)}건\n"
            f"🟢 강광: {len(ganggwang)}건\n"
            f"🟡 중종: {len(jungjong)}건"
        )
        await update.message.reply_text(summary)

        for name, entries in (("마영관", mayoung), ("강광", ganggwang), ("중종", jungjong)):
            await send_long_message(update, build_section(name, entries))

        await update.message.reply_text(
            "특정 분류만 다시 보려면 '마영관', '강광', '중종', '전체' 중 하나를 보내주세요."
        )

    except Exception as e:
        logger.exception("PDF 처리 중 오류")
        await update.message.reply_text(f"처리 중 오류가 발생했습니다: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_allowed(update):
        return
    keyword = update.message.text.strip()

    results = context.chat_data.get("results")
    if keyword in ("마영관", "강광", "중종", "전체"):
        if not results:
            await update.message.reply_text("먼저 PDF 파일을 보내주세요.")
            return
        await send_long_message(update, build_section(keyword, results[keyword]))
    else:
        await update.message.reply_text(HELP_TEXT)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("환경변수 TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
    if not UPSTAGE_API_KEY:
        raise SystemExit("환경변수 UPSTAGE_API_KEY가 설정되지 않았습니다.")

    # 일시적 네트워크 오류(TimedOut 등)로 죽지 않도록 무한 재시작 루프
    while True:
        asyncio.set_event_loop(asyncio.new_event_loop())

        app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .pool_timeout(30)
            .get_updates_connect_timeout(30)
            .get_updates_read_timeout(60)
            .build()
        )

        app.add_handler(CommandHandler(["start", "help"], start))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        try:
            logger.info("텔레그램 봇을 시작합니다 (polling)...")
            app.run_polling(allowed_updates=Update.ALL_TYPES, bootstrap_retries=-1)
            break  # 정상 종료 (Ctrl+C 등)
        except Exception:
            logger.exception("봇이 오류로 중단되었습니다. 10초 후 재시작합니다.")
            time.sleep(10)


if __name__ == "__main__":
    main()
