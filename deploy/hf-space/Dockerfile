# Hugging Face Spaces (Docker SDK)용 이미지
# 봇 코드는 빌드 시점에 GitHub 레포 main 브랜치에서 가져온다.
# 레포 코드가 바뀌면 Space 설정에서 "Factory rebuild"를 눌러 다시 빌드하면 된다.
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir python-telegram-bot requests beautifulsoup4

ADD https://raw.githubusercontent.com/imsuviiix/zipsy-app/main/pdf_parser.py pdf_parser.py
ADD https://raw.githubusercontent.com/imsuviiix/zipsy-app/main/telegram_bot.py telegram_bot.py
COPY space_app.py .
RUN chmod 644 *.py

ENV PYTHONUNBUFFERED=1
EXPOSE 7860

CMD ["python", "space_app.py"]
