"""Landing page — public marketing surface."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/landing", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "landing/index.html",
        context={
            "features": [
                {
                    "icon": "☕",
                    "title": "Защита в публичных Wi-Fi",
                    "text": "Кафе, аэропорты, отели — шифруем ваше соединение от перехвата.",
                },
                {
                    "icon": "💳",
                    "title": "Безопасные онлайн-платежи",
                    "text": "Банковские операции под защитой современного шифрования.",
                },
                {
                    "icon": "🔒",
                    "title": "Приватность данных",
                    "text": "Ваши персональные данные не становятся товаром.",
                },
                {
                    "icon": "🌐",
                    "title": "Стабильное соединение",
                    "text": "Шифрование без потери скорости — современный протокол.",
                },
            ],
            "tech_facts": [
                {"big": "256-bit", "text": "Шифрование военного уровня (ChaCha20-Poly1305)"},
                {"big": "Reality", "text": "Современный протокол (Project XTLS)"},
                {"big": "NL", "text": "Сервера в Нидерландах — за пределами юрисдикции РФ"},
                {"big": "0", "text": "Логов персонального трафика"},
            ],
            "faq": [
                {
                    "q": "Это легально?",
                    "a": "Да. Сервис обеспечивает шифрование трафика. Использование подобных "
                         "решений для защиты персональных данных законом не ограничивается.",
                },
                {
                    "q": "Что вы сохраняете обо мне?",
                    "a": "Только email и факт регистрации. Содержимое и адресаты вашего "
                         "трафика мы не пишем — это архитектурный факт.",
                },
                {
                    "q": "Какие приложения поддерживаются?",
                    "a": "v2RayTun (iOS / Android), Hiddify (все платформы), NekoBox (Android). "
                         "Эти клиенты проверены — другие не гарантируем.",
                },
                {
                    "q": "Сколько устройств можно подключить?",
                    "a": "На стадии тестирования — до трёх устройств на одну подписку.",
                },
            ],
        },
    )
