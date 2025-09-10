#!/usr/bin/env python3
"""
Скрипт для настройки webhook для Telegram бота
Запустите после деплоя на Vercel
"""

import requests
import os

def setup_webhook():
    bot_token = input("Введите токен вашего бота: ")
    webhook_url = input("Введите URL вашего Vercel приложения (например: https://your-app.vercel.app/api/webhook): ")
    
    # URL для установки webhook
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    
    # Данные для запроса
    data = {
        "url": webhook_url
    }
    
    # Отправляем запрос
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print("✅ Webhook успешно установлен!")
            print(f"URL: {webhook_url}")
        else:
            print("❌ Ошибка при установке webhook:")
            print(result.get("description", "Неизвестная ошибка"))
    else:
        print(f"❌ HTTP ошибка: {response.status_code}")

if __name__ == "__main__":
    setup_webhook()