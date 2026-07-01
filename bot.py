import os
import asyncio
import aiohttp
import feedparser
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تحميل المتغيرات
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = Bot(token=TOKEN)

# ==================== جلب الأخبار بشكل متواصل ====================

async def fetch_all_news():
    """جلب الأخبار من جميع المصادر بشكل متوازي"""
    tasks = [
        fetch_rss_news(),
        fetch_goal_news(),
        fetch_espn_news()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_news = []
    for result in results:
        if isinstance(result, list):
            all_news.extend(result)
    return all_news

async def fetch_rss_news():
    """جلب من RSS بشكل غير متزامن"""
    sources = [
        'https://www.filgoal.com/rss/rss.xml',
        'https://www.kooora.com/rss/rss.xml',
        'https://www.espn.com/espn/rss/news'
    ]
    
    news_items = []
    async with aiohttp.ClientSession() as session:
        for url in sources:
            try:
                async with session.get(url, timeout=10) as response:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries[:5]:
                        news_items.append({
                            'title': entry.get('title', ''),
                            'link': entry.get('link', ''),
                            'summary': entry.get('summary', '')[:150],
                            'source': 'RSS',
                            'image': entry.get('media_content', [{}])[0].get('url') if 'media_content' in entry else None
                        })
            except Exception as e:
                logger.error(f"RSS Error: {e}")
    
    return news_items

async def fetch_goal_news():
    """سحب Goal.com بشكل سريع"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.goal.com/ar', timeout=10) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                articles = []
                for article in soup.find_all('article', limit=5):
                    try:
                        title = article.find('h3').text.strip()
                        link = article.find('a')['href']
                        img = article.find('img')
                        image_url = img.get('data-src') or img.get('src') if img else None
                        
                        articles.append({
                            'title': title,
                            'link': f"https://www.goal.com{link}" if not link.startswith('http') else link,
                            'summary': '',
                            'source': 'Goal.com',
                            'image': image_url
                        })
                    except:
                        continue
                return articles
    except Exception as e:
        logger.error(f"Goal Error: {e}")
        return []

async def fetch_espn_news():
    """سحب ESPN"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.espn.com/espn/rss/news', timeout=10) as response:
                content = await response.text()
                feed = feedparser.parse(content)
                
                return [{
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', '')[:150],
                    'source': 'ESPN',
                    'image': None
                } for entry in feed.entries[:5]]
    except:
        return []

# ==================== إرسال سريع ====================

async def send_news_fast(chat_id, news_list):
    """إرسال جميع الأخبار بشكل متوازي بدون انتظار"""
    send_tasks = []
    
    for news in news_list:
        task = send_single_news(chat_id, news)
        send_tasks.append(task)
    
    # إرسال كل الأخبار في نفس الوقت
    await asyncio.gather(*send_tasks, return_exceptions=True)

async def send_single_news(chat_id, news):
    """إرسال خبر واحد"""
    try:
        emoji = "⚽" if any(word in news['title'] for word in ['كرة', 'football', 'soccer']) else "🏆"
        
        message = f"""
{emoji} *{news['title']}*

{news.get('summary', '')[:200]}

📰 {news['source']}
🔗 [المصدر]({news['link']})
        """
        
        if news.get('image'):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(news['image'], timeout=10) as img_response:
                        if img_response.status == 200:
                            image_data = await img_response.read()
                            await bot.send_photo(
                                chat_id=chat_id,
                                photo=image_data,
                                caption=message,
                                parse_mode='Markdown'
                            )
                            return
            except:
                pass
        
        # إرسال نص إذا فشلت الصورة
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
        
    except Exception as e:
        logger.error(f"Send Error: {e}")

# ==================== أوامر البوت ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء"""
    await update.message.reply_text(
        "🤖 بوت الأخبار الرياضية\n\n"
        "الأوامر المتاحة:\n"
        "/news - جلب أخبار فورية\n"
        "/live - وضع الأخبار المباشرة (كل دقيقة)\n"
        "/stop - إيقاف الأخبار المباشرة"
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPES):
    """جلب أخبار فورية"""
    await update.message.reply_text("⏳ جاري جلب الأخبار...")
    
    news = await fetch_all_news()
    
    if news:
        await update.message.reply_text(f"📨 تم العثور على {len(news)} خبر، جاري الإرسال...")
        await send_news_fast(update.effective_chat.id, news)
    else:
        await update.message.reply_text("❌ لم يتم العثور على أخبار")

# ==================== الوضع المباشر (بدون توقف) ====================

is_live_mode = False

async def live_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشغيل وضع الأخبار المباشرة"""
    global is_live_mode
    is_live_mode = True
    
    await update.message.reply_text("🔴 بدأ وضع الأخبار المباشرة - سيتم إرسال الأخبار كل دقيقة")
    
    while is_live_mode:
        try:
            news = await fetch_all_news()
            if news:
                # إرسال الأخبار الجديدة فقط
                await send_news_fast(CHAT_ID, news[:3])  # آخر 3 أخبار
            
            await asyncio.sleep(60)  # انتظار دقيقة فقط
            
        except Exception as e:
            logger.error(f"Live Error: {e}")
            await asyncio.sleep(30)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إيقاف الوضع المباشر"""
    global is_live_mode
    is_live_mode = False
    await update.message.reply_text("⏹️ تم إيقاف الأخبار المباشرة")

# ==================== التشغيل ====================

def main():
    """الدالة الرئيسية"""
    logger.info("🚀 تشغيل البوت...")
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة الأوامر
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("live", live_command))
    application.add_handler(CommandHandler("stop", stop_command))
    
    # تشغيل البوت
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
