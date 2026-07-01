import os
import requests
import feedparser
import schedule
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
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
CHAT_ID = os.getenv('CHAT_ID')  # معرف القناة أو المجموعة

bot = Bot(token=TOKEN)

# ==================== مصادر الأخبار المجانية ====================

def get_news_from_rss():
    """جلب الأخبار من مواقع RSS"""
    rss_sources = [
        {
            'url': 'https://www.filgoal.com/rss/rss.xml',  # في الجول - مصر
            'source': 'FilGoal'
        },
        {
            'url': 'https://www.kooora.com/rss/rss.xml',   # كورة - عربي
            'source': 'Kooora'
        },
        {
            'url': 'https://www.espn.com/espn/rss/news',   # ESPN - إنجليزي
            'source': 'ESPN'
        },
        {
            'url': 'https://www.bbc.co.uk/sport/rss.xml',  # BBC Sport
            'source': 'BBC Sport'
        }
    ]
    
    news_items = []
    
    for source in rss_sources:
        try:
            feed = feedparser.parse(source['url'])
            for entry in feed.entries[:3]:  # آخر 3 أخبار من كل مصدر
                news_item = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', ''),
                    'published': entry.get('published', ''),
                    'source': source['source']
                }
                
                # محاولة استخراج الصورة
                if 'media_content' in entry:
                    news_item['image'] = entry.media_content[0]['url']
                elif 'enclosures' in entry and entry.enclosures:
                    news_item['image'] = entry.enclosures[0].get('url', '')
                else:
                    news_item['image'] = None
                    
                news_items.append(news_item)
                
        except Exception as e:
            logger.error(f"خطأ في جلب RSS من {source['source']}: {e}")
    
    return news_items

def scrape_news_with_images():
    """سحب الأخبار مع الصور من مواقع الويب"""
    # مثال: سحب من موقع Goal.com
    url = "https://www.goal.com/ar"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        articles = []
        
        # البحث عن المقالات (قد تحتاج تعديل السيليكتور حسب الموقع)
        for article in soup.find_all('article', limit=5):
            try:
                title = article.find('h3').text.strip() if article.find('h3') else "عنوان غير متوفر"
                link = article.find('a')['href'] if article.find('a') else ""
                if link and not link.startswith('http'):
                    link = 'https://www.goal.com' + link
                
                # استخراج الصورة
                img_tag = article.find('img')
                image_url = None
                if img_tag:
                    image_url = img_tag.get('data-src') or img_tag.get('src')
                
                summary = article.find('p').text.strip() if article.find('p') else ""
                
                articles.append({
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'image': image_url,
                    'source': 'Goal.com'
                })
                
            except Exception as e:
                continue
                
        return articles
        
    except Exception as e:
        logger.error(f"خطأ في سحب الأخبار: {e}")
        return []

def get_image_from_url(image_url):
    """تحميل الصورة من الرابط"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'}
        response = requests.get(image_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.error(f"خطأ في تحميل الصورة: {e}")
    return None

# ==================== إرسال الأخبار ====================

def format_message(news):
    """تنسيق رسالة الخبر"""
    emoji = "⚽" if "كرة" in news['title'] or "football" in news['title'].lower() else "🏆"
    
    message = f"""
{emoji} *{news['title']}*

📝 {news.get('summary', 'لا يوجد ملخص')[:200]}...

📰 المصدر: {news['source']}
🔗 [قراءة المزيد]({news['link']})
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
    """
    return message

async def send_news():
    """إرسال الأخبار للقناة"""
    logger.info("بدء جلب الأخبار...")
    
    # جمع الأخبار من جميع المصادر
    all_news = []
    all_news.extend(get_news_from_rss())
    all_news.extend(scrape_news_with_images())
    
    # إزالة التكرارات
    seen = set()
    unique_news = []
    for news in all_news:
        if news['title'] not in seen:
            seen.add(news['title'])
            unique_news.append(news)
    
    # إرسال الأخبار
    for news in unique_news[:10]:  # إرسال آخر 10 أخبار
        try:
            message = format_message(news)
            
            if news.get('image'):
                # تحميل وإرسال الصورة مع النص
                image_data = get_image_from_url(news['image'])
                if image_data:
                    await bot.send_photo(
                        chat_id=CHAT_ID,
                        photo=image_data,
                        caption=message,
                        parse_mode='Markdown'
                    )
                else:
                    # إرسال نص فقط إذا فشل تحميل الصورة
                    await bot.send_message(
                        chat_id=CHAT_ID,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=False
                    )
            else:
                # إرسال نص بدون صورة
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            
            logger.info(f"تم إرسال خبر: {news['title'][:50]}...")
            time.sleep(2)  # تأخير بين كل رسالة
            
        except Exception as e:
            logger.error(f"خطأ في إرسال الخبر: {e}")
    
    # تشغيل مرة عند البدء
    import asyncio
    asyncio.run(send_news())
    
    # الحلقة الدائمة
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    main()
