import os
import requests
import feedparser
import logging
import time
import threading
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
bot = Bot(token=TOKEN)

is_live = False

def get_news():
    news = []
    try:
        feed = feedparser.parse('https://www.filgoal.com/rss/rss.xml')
        for entry in feed.entries[:5]:
            news.append({
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'source': 'FilGoal',
                'image': entry.get('media_content', [{}])[0].get('url') if 'media_content' in entry else None
            })
    except Exception as e:
        logger.error(f"RSS Error: {e}")
    return news

def send_news_item(chat_id, news):
    try:
        msg = f"⚽ *{news['title']}*\n\n📰 {news['source']}\n🔗 [المصدر]({news['link']})"
        if news.get('image'):
            r = requests.get(news['image'], timeout=10)
            bot.send_photo(chat_id=chat_id, photo=r.content, caption=msg, parse_mode='Markdown')
        else:
            bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Send Error: {e}")

def live_loop():
    global is_live
    while is_live:
        news = get_news()
        for n in news[:3]:
            send_news_item(CHAT_ID, n)
        time.sleep(60)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 بوت الأخبار جاهز!\n/news - أخبار فورية\n/live - وضع مباشر")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري جلب الأخبار...")
    news_list = get_news()
    for n in news_list:
        send_news_item(update.effective_chat.id, n)

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_live
    is_live = True
    threading.Thread(target=live_loop, daemon=True).start()
    await update.message.reply_text("🔴 بدأ الوضع المباشر")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_live
    is_live = False
    await update.message.reply_text("⏹️ تم الإيقاف")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("stop", stop))
    logger.info("🚀 البوت يعمل!")
    app.run_polling()

if __name__ == '__main__':
    main()
