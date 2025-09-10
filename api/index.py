import json
import os
import tempfile
import requests
from urllib.parse import urlparse
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота (установите в переменных окружения Vercel)
BOT_TOKEN = os.getenv('BOT_TOKEN')

class VideoDownloader:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    def download_video(self, url):
        """Скачивает видео и возвращает путь к файлу"""
        try:
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': f'{self.temp_dir}/%(title)s.%(ext)s',
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename, info.get('title', 'Video')
        except Exception as e:
            logger.error(f"Ошибка скачивания видео: {e}")
            return None, None
    
    def extract_audio(self, url):
        """Извлекает аудио из видео"""
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{self.temp_dir}/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Имя файла с расширением mp3
                filename = ydl.prepare_filename(info)
                audio_filename = filename.rsplit('.', 1)[0] + '.mp3'
                return audio_filename, info.get('title', 'Audio')
        except Exception as e:
            logger.error(f"Ошибка извлечения аудио: {e}")
            return None, None

downloader = VideoDownloader()

async def start(update: Update, context):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Отправь мне ссылку на видео (YouTube, TikTok, Instagram и др.), "
        "и я скачаю его для тебя!\n\n"
        "После скачивания видео ты сможешь также получить только аудио."
    )

async def handle_url(update: Update, context):
    """Обработчик URL-ссылок"""
    url = update.message.text.strip()
    
    # Проверяем, что это URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        await update.message.reply_text("❌ Пожалуйста, отправьте корректную ссылку на видео.")
        return
    
    # Отправляем сообщение о начале обработки
    processing_msg = await update.message.reply_text("⏳ Обрабатываю видео...")
    
    try:
        # Скачиваем видео
        video_path, title = downloader.download_video(url)
        
        if not video_path or not os.path.exists(video_path):
            await processing_msg.edit_text("❌ Не удалось скачать видео. Проверьте ссылку.")
            return
        
        # Проверяем размер файла (Telegram лимит ~50MB)
        file_size = os.path.getsize(video_path)
        if file_size > 50 * 1024 * 1024:  # 50MB
            await processing_msg.edit_text("❌ Видео слишком большое для отправки через Telegram.")
            os.remove(video_path)
            return
        
        # Создаем кнопку для скачивания аудио
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 Скачать только музыку", callback_data=f"audio:{url}")]
        ])
        
        # Отправляем видео
        await processing_msg.edit_text("📤 Отправляю видео...")
        
        with open(video_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=f"🎬 {title}",
                reply_markup=keyboard
            )
        
        await processing_msg.delete()
        
        # Удаляем временный файл
        os.remove(video_path)
        
    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        await processing_msg.edit_text("❌ Произошла ошибка при обработке видео.")

async def handle_audio_callback(update: Update, context):
    """Обработчик нажатия кнопки для скачивания аудио"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем URL из callback_data
    url = query.data.split(":", 1)[1]
    
    # Отправляем сообщение о начале обработки
    processing_msg = await query.message.reply_text("⏳ Извлекаю аудио...")
    
    try:
        # Извлекаем аудио
        audio_path, title = downloader.extract_audio(url)
        
        if not audio_path or not os.path.exists(audio_path):
            await processing_msg.edit_text("❌ Не удалось извлечь аудио из видео.")
            return
        
        # Отправляем аудио
        await processing_msg.edit_text("📤 Отправляю аудио...")
        
        with open(audio_path, 'rb') as audio_file:
            await query.message.reply_audio(
                audio=audio_file,
                title=title,
                caption=f"🎵 {title}"
            )
        
        await processing_msg.delete()
        
        # Удаляем временный файл
        os.remove(audio_path)
        
    except Exception as e:
        logger.error(f"Ошибка извлечения аудио: {e}")
        await processing_msg.edit_text("❌ Произошла ошибка при извлечении аудио.")

# Создаем приложение
application = Application.builder().token(BOT_TOKEN).build()

# Добавляем обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
application.add_handler(CallbackQueryHandler(handle_audio_callback, pattern="^audio:"))

async def webhook_handler(request_body):
    """Обработчик webhook запросов"""
    try:
        update = Update.de_json(json.loads(request_body), application.bot)
        await application.process_update(update)
        return {"statusCode": 200}
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return {"statusCode": 500}

from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(webhook_handler(post_data.decode('utf-8')))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            
        except Exception as e:
            logger.error(f"Handler error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        finally:
            if 'loop' in locals():
                loop.close()
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Telegram Bot is running!')