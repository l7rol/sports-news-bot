import os
import requests
import feedparser
import logging
import json
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# تخزين المصادر في الذاكرة (سيتم حذفها عند إعادة التشغيل)
# للحفظ الدائم، استخدم قاعدة بيانات أو ملف
RSS_SOURCES = {
    'filgoal': 'https://www.filgoal.com/rss/rss.xml'
}

def save_sources():
    """حفظ المصادر في ملف (اختياري)"""
    try:
        with open('sources.json', 'w', encoding='utf-8') as f:
            json.dump(RSS_SOURCES, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving sources: {e}")

def load_sources():
    """تحميل المصادر من الملف"""
    global RSS_SOURCES
    try:
        if os.path.exists('sources.json'):
            with open('sources.json', 'r', encoding='utf-8') as f:
                RSS_SOURCES.update(json.load(f))
    except Exception as e:
        logger.error(f"Error loading sources: {e}")

# تحميل المصادر عند البدء
load_sources()

def get_news_from_source(name, url):
    """جلب الأخبار من مصدر واحد"""
    news = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            news.append({
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'source': name,
                'image': entry.get('media_content', [{}])[0].get('url') if 'media_content' in entry else 
                         entry.get('enclosures', [{}])[0].get('href') if 'enclosures' in entry else None
            })
    except Exception as e:
        logger.error(f"RSS error for {name}: {e}")
    return news

def get_all_news():
    """جلب الأخبار من جميع المصادر"""
    all_news = []
    for name, url in RSS_SOURCES.items():
        news = get_news_from_source(name, url)
        all_news.extend(news)
    return all_news

async def send_news_item(context: ContextTypes.DEFAULT_TYPE, chat_id, news: dict):
    try:
        msg = f"⚽ *{news['title']}*\n\n📰 المصدر: {news['source']}\n🔗 [اقرأ المزيد]({news['link']})"
        if news.get('image'):
            r = requests.get(news['image'], timeout=10)
            await context.bot.send_photo(chat_id=chat_id, photo=r.content, caption=msg, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Send error: {e}")

async def live_news_job(context: ContextTypes.DEFAULT_TYPE):
    all_news = get_all_news()
    for n in all_news[:3]:
        await send_news_item(context, CHAT_ID, n)

# ============ أوامر البوت ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🤖 *بوت أخبار RSS*

الأوامر المتاحة:
📰 `/news` - جلب أخبار من جميع المصادر
📡 `/live` - تفعيل الوضع المباشر (كل دقيقة)
🛑 `/stop_live` - إيقاف الوضع المباشر

⚙️ إدارة المصادر:
➕ `/add_source` - إضافة مصدر جديد
📋 `/list_sources` - عرض المصادر الحالية
❌ `/remove_source` - حذف مصدر

مثال لإضافة مصدر:
`/add_source bbc https://feeds.bbci.co.uk/news/rss.xml`"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري جلب الأخبار من جميع المصادر...")
    
    if not RSS_SOURCES:
        await update.message.reply_text("❌ لا توجد مصادر مضافة. استخدم /add_source لإضافة مصدر")
        return
    
    all_news = get_all_news()
    if not all_news:
        await update.message.reply_text("❌ لم يتم العثور على أخبار حالياً.")
        return
    
    await update.message.reply_text(f"📰 تم العثور على {len(all_news)} خبر من {len(RSS_SOURCES)} مصدر:")
    
    for n in all_news[:5]:  # إرسال 5 أخبار فقط
        await send_news_item(context, update.effective_chat.id, n)

# ============ أوامر إدارة المصادر ============

async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة مصدر RSS جديد"""
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ الاستخدام الصحيح:\n"
            "`/add_source <الاسم> <الرابط>`\n\n"
            "مثال:\n"
            "`/add_source bbc https://feeds.bbci.co.uk/news/rss.xml`",
            parse_mode='Markdown'
        )
        return
    
    name = args[0]
    url = args[1]
    
    # التحقق من صحة الرابط
    if not url.startswith('http'):
        await update.message.reply_text("❌ الرابط يجب أن يبدأ بـ http:// أو https://")
        return
    
    # إضافة المصدر
    RSS_SOURCES[name] = url
    save_sources()  # حفظ في الملف
    
    await update.message.reply_text(f"✅ تم إضافة المصدر *{name}* بنجاح!\n🔗 {url}", parse_mode='Markdown')

async def list_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جميع المصادر"""
    if not RSS_SOURCES:
        await update.message.reply_text("📭 لا توجد مصادر مضافة.")
        return
    
    msg = "📋 *قائمة المصادر:*\n\n"
    for i, (name, url) in enumerate(RSS_SOURCES.items(), 1):
        msg += f"{i}. *{name}*\n🔗 `{url[:50]}...`\n\n"
    
    msg += f"\n📊 الإجمالي: {len(RSS_SOURCES)} مصدر"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف مصدر"""
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "⚠️ الاستخدام: `/remove_source <الاسم>`\n"
            "لمعرفة الأسماء: `/list_sources`",
            parse_mode='Markdown'
        )
        return
    
    name = args[0]
    
    if name not in RSS_SOURCES:
        await update.message.reply_text(f"❌ المصدر *{name}* غير موجود!")
        return
    
    del RSS_SOURCES[name]
    save_sources()
    
    await update.message.reply_text(f"✅ تم حذف المصدر *{name}* بنجاح!")

# ============ أوامر الوضع المباشر ============

async def start_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job_name = f"live_{update.effective_chat.id}"
    
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if current_jobs:
        await update.message.reply_text("🔄 الوضع المباشر يعمل بالفعل!")
        return
    
    context.job_queue.run_repeating(
        live_news_job, 
        interval=300,  # كل 5 دقائق (بدلاً من كل دقيقة)
        first=10, 
        name=job_name,
        chat_id=update.effective_chat.id
    )
    await update.message.reply_text("✅ تم تفعيل الوضع المباشر! سيتم إرسال الأخبار كل 5 دقائق.")

async def stop_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job_name = f"live_{update.effective_chat.id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    
    if not current_jobs:
        await update.message.reply_text("⚠️ الوضع المباشر متوقف.")
        return
    
    for job in current_jobs:
        job.schedule_removal()
    
    await update.message.reply_text("🛑 تم إيقاف الوضع المباشر.")

# ============ التشغيل ============

def main():
    if not TOKEN:
        logger.error("No BOT_TOKEN found!")
        return

    app = Application.builder().token(TOKEN).build()

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("live", start_live))
    app.add_handler(CommandHandler("stop_live", stop_live))
    
    # أوامر إدارة المصادر
    app.add_handler(CommandHandler("add_source", add_source))
    app.add_handler(CommandHandler("list_sources", list_sources))
    app.add_handler(CommandHandler("remove_source", remove_source))

    logger.info("Bot started!")
    app.run_polling()

if __name__ == '__main__':
    main()
