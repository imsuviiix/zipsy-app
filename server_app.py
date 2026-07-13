"""Render 등 웹서비스형 호스팅에서 텔레그램 봇을 상시 실행하는 진입점

호스팅 서비스가 요구하는 웹 포트(PORT 환경변수)에 상태 확인용 HTTP 서버를
백그라운드로 띄우고, 메인 스레드에서 폴링 봇을 실행한다.
"""
import http.server
import os
import threading


def _serve_health():
    port = int(os.getenv("PORT", "10000"))

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("📋 집회시위 정보 추출 봇이 실행 중입니다.".encode("utf-8"))

        def do_HEAD(self):
            # UptimeRobot 등 모니터링 서비스는 HEAD 요청을 보낸다
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()

        def log_message(self, *args):
            pass

    http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


threading.Thread(target=_serve_health, daemon=True).start()

import telegram_bot  # noqa: E402

telegram_bot.main()
