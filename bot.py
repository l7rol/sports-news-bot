import os
import requests
import feedparser
import logging
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Setup Logging with proper capitalization
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('bot_token')
CHAT_ID = os.getenv('chat_id')

# Thread-safe global flag
is_live = False

def get_news():
    news = []
    try:
        feed = feedparser.parse('https://www.filgoal.com/rss/rss.xml')
        for entry in feed.entries[:5]:
            news.append({
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'source': 'filgoal',
                'image': entry.get('media_content', [{}])[0].get('url') if 'media_content' in entry else None
            })
    except Exception as e:
        logger.error(f"RSS error: {e}")
    return news

async def send_news_item(context: ContextTypes.DEFAULT_TYPE, chat_id: str, news: dict):
    try:
        msg = f"⚽ *{news['title']}*\n\n📰 {news['source']}\n🔗 [المصدر]({news['link']})"
        if news.get('image'):
            # Fetch image content asynchronously (or synchronously inside async context safely)
            r = requests.get(news['image'], timeout=10)
            await context.bot.send_photo(chat_id=chat_id, photo=r.content, caption=msg, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Send error: {e}")

# The background job function triggered periodically by JobQueue
async def live_news_job(context: ContextTypes.DEFAULT_TYPE):
    news_list = get_news()
    for n in news_list[:3]:
        await send_news_item(context, CHAT_ID, n)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 بوت الأخبار جاهز!\n/news - أخبار فورية\n/live - تفعيل الوضع المباشر\n/stop_live - إيقاف الوضع المباشر")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري جلب الأخبار...")
    news_list = get_news()
    if not news_list:
        await update.message.reply_text("❌ لم يتم العثور على أخبار حالياً.")
        return
    for n in news_list[:3]:
        await send_news_item(context, update.effective_chat.id, n)

async def start_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_live
    job_name = "live_news_broadcast"
    
    # Check if job is already active
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if current_jobs:
        await update.message.reply_text("🔄 الوضع المباشر يعمل بالفعل!")
        return

    is_live = True
    # Run the live loop every 60 seconds natively without multi-threading errors
    context.job_queue.run_repeating(live_news_job, interval=60, first=1, name=job_name)
    await update.message.reply_text("✅ تم تفعيل الوضع المباشر! سيتم إرسال الأخبار كل دقيقة.")

async def stop_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_live
    job_name = "live_news_broadcast"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    
    if not current_jobs:
        await update.message.reply_text("⚠️ الوضع المباشر متوقف بالفعل.")
        return

    for job in current_jobs:
        job.schedule_removal()
    is_live = False
    await update.message.reply_text("🛑 تم إيقاف الوضع المباشر بنجاح.")

def main():
    if not TOKEN:
        logger.error("No token found. Please set 'bot_token' in your environment variables.")
        return

    # Build application with native support for JobQueue
    app = Application.builder().token(TOKEN).build()

    # Register handlers with accurate capitalization
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("live", start_live))
    app.add_handler(CommandHandler("stop_live", stop_live))

    # Keep polling active until closed manually
    print("Bot is polling...")
    app.run_polling()

if __name__ == '__main__':
    main()
