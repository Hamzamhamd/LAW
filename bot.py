# -*- coding: utf-8 -*-
import os
import sys
import logging
import sqlite3
from datetime import datetime
import pytz
import asyncio
import yt_dlp
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    CallbackContext
)
import subprocess
import instaloader
from instagram_private_api import Client, ClientCompatPatch
import aiohttp
import json
from instascrape import Reel, Post
from downloaders import (
    download_youtube, download_instagram, TikTokDownloader,
    download_facebook, LikeeDownloader
)
import urllib.parse
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()

# إعداد الترميز
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# التوكن الخاص بالبوت
TOKEN = os.getenv("BOT_TOKEN")

# إنشاء مجلد للتنزيلات إذا لم يكن موجوداً
DOWNLOAD_DIR = os.path.abspath("downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# تعيين المنطقة الزمنية
TIMEZONE = pytz.timezone('Asia/Riyadh')

# المشرفين
ADMIN_IDS = []  # أضف معرفات المشرفين هنا

# النقاط لكل تحميل
POINTS_PER_DOWNLOAD = 10

# النقاط والمستويات
LEVELS = {
    0: "🌱 مبتدئ",
    100: "⭐ نشط",
    500: "🌟 محترف",
    1000: "💎 خبير",
    5000: "👑 أسطوري"
}

# تكوين خيارات التحميل الأساسية
BASE_OPTS = {
    'format': 'best',
    'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True
}

# إعدادات تحميل الفيديو
VIDEO_OPTS = BASE_OPTS.copy()

# إعدادات تحميل الصوت
AUDIO_OPTS = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True
}

# تكوين خيارات تحميل كل منصة
YOUTUBE_OPTS = BASE_OPTS.copy()
TIKTOK_OPTS = BASE_OPTS.copy()
INSTAGRAM_OPTS = BASE_OPTS.copy()
FACEBOOK_OPTS = BASE_OPTS.copy()

def get_user_level(points: int) -> str:
    """حساب مستوى المستخدم بناءً على عدد النقاط"""
    if points < 10:
        return "🥉 مبتدئ"
    elif points < 50:
        return "🥈 نشط"
    elif points < 100:
        return "🥇 محترف"
    elif points < 500:
        return "💎 خبير"
    else:
        return "👑 أسطوري"

def update_user_points(user_id, points_to_add):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_to_add, user_id))
    c.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    total_points = c.fetchone()[0]
    new_level = get_user_level(total_points)
    c.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user_id))
    conn.commit()
    conn.close()
    return total_points, new_level

def send_monthly_stats():
    """إرسال إحصائيات شهرية للمشرفين"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        # الحصول على الشهر الحالي مع المنطقة الزمنية
        current_month = datetime.now(TIMEZONE).strftime("%Y-%m")
        
        # الحصول على إحصائيات الشهر لكل مستخدم
        c.execute("""
            SELECT user_id, COUNT(*) as downloads, SUM(points) as points 
            FROM downloads 
            WHERE strftime('%Y-%m', date) = ? 
            GROUP BY user_id
        """, (current_month,))
        
        stats = c.fetchall()
        
        for user_id, downloads, points in stats:
            stats_message = f"""📊 *إحصائيات الشهر*
            
📅 شهر: {current_month}
📥 عدد التحميلات: {downloads}
✨ النقاط المكتسبة: {points}

تابع استخدام البوت للحصول على المزيد من النقاط والمميزات! 🚀"""
            
            try:
                # إرسال الإحصائيات للمستخدم
                application.bot.send_message(chat_id=user_id, text=stats_message, parse_mode='Markdown')
            except Exception as e:
                print(f"Error sending monthly stats to user {user_id}: {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error in send_monthly_stats: {e}")

def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ عذراً، هذا الأمر متاح للمشرفين فقط.")
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # إحصائيات عامة
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM downloads")
    total_downloads = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM downloads WHERE date >= datetime('now', '-24 hours')")
    downloads_24h = c.fetchone()[0]
    
    # المستخدمين الأكثر نشاطاً
    c.execute("""
        SELECT username, downloads, points, level 
        FROM users 
        ORDER BY downloads DESC 
        LIMIT 5
    """)
    top_users = c.fetchall()
    
    dashboard_text = f"""📊 *لوحة التحكم*

📈 *إحصائيات عامة*:
👥 إجمالي المستخدمين: {total_users}
📥 إجمالي التحميلات: {total_downloads}
⚡ تحميلات آخر 24 ساعة: {downloads_24h}

🏆 *أفضل 5 مستخدمين*:
"""
    
    for user in top_users:
        username, downloads, points, level = user
        dashboard_text += f"\n@{username or 'Unknown'}: {downloads} تحميل | {points} نقطة | {level}"
    
    conn.close()
    
    update.message.reply_text(dashboard_text, parse_mode='Markdown')

def get_platform(url):
    """تحديد نوع المنصة من الرابط"""
    try:
        # تنظيف الرابط من الفراغات
        url = url.strip()
        
        # التحقق من أن الرابط يبدأ ببروتوكول
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # فحص المنصات المدعومة
        if any(x in domain for x in ['youtube.com', 'youtu.be']):
            return 'youtube'
        elif any(x in domain for x in ['instagram.com', 'instagr.am']) or '/reel/' in path or '/p/' in path:
            return 'instagram'
        elif any(x in domain for x in ['tiktok.com', 'douyin.com', 'vm.tiktok.com', 'vt.tiktok.com']):
            return 'tiktok'
        elif any(x in domain for x in ['facebook.com', 'fb.watch', 'fb.com']):
            return 'facebook'
        elif any(x in domain for x in ['likee.com', 'l.likee.video', 'likee.video']):
            return 'likee'
        else:
            return 'unknown'
    except Exception as e:
        logger.error(f"Error parsing URL: {str(e)}")
        return 'unknown'

def get_platform_options(platform):
    options = {
        'format': 'best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': False,
        'no_warnings': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.instagram.com/',
            'X-IG-App-ID': '936619743392459'
        },
        'cookiefile': 'cookies.txt',
        'force_generic_extractor': True,
        'extractor_args': {
            'instagram': ['--original-url', '--ignore-config']
        },
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'
        }]
    }
    
    if platform == 'instagram':
        options.update({
            'headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
                'X-IG-App-ID': '936619743392459'
            },
            'extractor_args': {'instagram': ['--original-url']}
        })
    elif platform == 'tiktok':
        options['http_headers'] = {
            'Referer': 'https://www.tiktok.com/',
            'User-Agent': 'com.zhiliaoapp.musically/2023100030 (Linux; U; Android 10; en_US; Pixel 4; Build/QQ3A.200805.001; Cronet/58.0.2991.0)'
        }
    elif platform == 'facebook':
        options['force_generic_extractor'] = True
    elif platform == 'twitter':
        options['cookiefile'] = 'twitter_cookies.txt'
    
    return options

def ensure_downloads_directory():
    """التأكد من وجود مجلد التنزيلات"""
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        print("Created downloads directory")
    return os.path.abspath('downloads')

def clean_filename(filename):
    """تنظيف اسم الملف من الأحرف غير المسموح بها"""
    return "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()

def get_video_info(url, platform):
    """الحصول على معلومات الفيديو قبل التحميل"""
    try:
        options = get_platform_options(platform)
        options['extract_info'] = True
        options['download'] = False
        
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"Error getting video info: {str(e)}")
        return None

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الروابط المرسلة"""
    try:
        url = update.message.text.strip()
        
        # إضافة https:// إذا لم يكن موجوداً
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # إرسال رسالة جاري التحميل
        processing_message = await update.message.reply_text(
            "جاري معالجة الرابط... ⏳",
            reply_to_message_id=update.message.message_id
        )
        
        try:
            # تحديد نوع الرابط وتحميل الفيديو
            platform = get_platform(url)
            
            if platform == 'unknown':
                raise Exception("❌ عذراً، هذا الرابط غير مدعوم")
            
            logger.info(f"Downloading from platform: {platform}")
            logger.info(f"URL: {url}")
            
            if platform == 'instagram':
                filename, title = await download_instagram(url, DOWNLOAD_DIR)
            elif platform == 'youtube':
                filename, title = await download_youtube(url, DOWNLOAD_DIR)
            elif platform == 'tiktok':
                filename, title = await download_tiktok(url, DOWNLOAD_DIR)
            elif platform == 'facebook':
                filename, title = await download_facebook(url, DOWNLOAD_DIR)
            elif platform == 'likee':
                filename, title = await download_likee(url, DOWNLOAD_DIR)
            else:
                raise Exception("❌ عذراً، هذا الرابط غير مدعوم")
            
            # إرسال الفيديو
            if os.path.exists(filename):
                with open(filename, 'rb') as video:
                    await update.message.reply_video(
                        video=video,
                        caption=f"✅ {title}",
                        reply_to_message_id=update.message.message_id
                    )
                
                # حذف الملف بعد الإرسال
                os.remove(filename)
            else:
                raise Exception("❌ فشل تحميل الفيديو")
            
            # حذف رسالة جاري المعالجة
            await processing_message.delete()
            
        except Exception as e:
            # حذف رسالة جاري المعالجة
            await processing_message.delete()
            # إرسال رسالة الخطأ
            await update.message.reply_text(
                str(e),
                reply_to_message_id=update.message.message_id
            )
            
    except Exception as e:
        logger.error(f"Error handling URL: {str(e)}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء معالجة الرابط",
            reply_to_message_id=update.message.message_id
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية التفاعل مع البوت"""
    user = update.effective_user
    register_user(user.id, user.username)
    
    welcome_message = (
        f"👋 مرحباً {user.first_name}!\n\n"
        "🎥 أنا بوت تحميل الفيديوهات والصوت من مواقع التواصل الاجتماعي\n\n"
        "📱 المواقع المدعومة:\n"
        "▫️ يوتيوب\n"
        "▫️ تيك توك\n"
        "▫️ تويتر\n"
        "▫️ انستجرام\n"
        "▫️ فيسبوك\n"
        "▫️ لايكي\n\n"
        "🚀 فقط أرسل لي رابط الفيديو وسأقوم بتحميله لك!\n\n"
        "💡 للمساعدة اضغط على زر المساعدة أدناه"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("❓ مساعدة", callback_data="help"),
            InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")
        ],
        [InlineKeyboardButton("📢 قناة البوت", url="https://t.me/your_channel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رسالة المساعدة"""
    help_text = (
        "🔍 *كيفية استخدام البوت:*\n\n"
        "*1️⃣ التحميل من يوتيوب:*\n"
        "• انسخ رابط الفيديو من يوتيوب\n"
        "• الصق الرابط هنا في المحادثة\n"
        "• اختر نوع التحميل (فيديو/صوت)\n\n"
        "*2️⃣ التحميل من المنصات الأخرى:*\n"
        "• انسخ رابط الفيديو من التطبيق\n"
        "• الصق الرابط هنا مباشرة\n"
        "• انتظر قليلاً... ✨\n\n"
        "*⚠️ ملاحظات مهمة:*\n"
        "• تأكد أن الفيديو عام وليس خاص\n"
        "• بعض الفيديوهات قد تكون محمية\n"
        "• الحد الأقصى لحجم الملف: 50MB\n\n"
        "*🆘 للدعم والمساعدة:*\n"
        "• تواصل معنا: @hamzabot\n"
        "• قناة البوت: @your_channel"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: CallbackContext):
    """معالجة النقر على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        help_text = (
            "🔍 *كيفية استخدام البوت:*\n\n"
            "*1️⃣ التحميل من يوتيوب:*\n"
            "• انسخ رابط الفيديو من يوتيوب\n"
            "• الصق الرابط هنا في المحادثة\n"
            "• اختر نوع التحميل (فيديو/صوت)\n\n"
            "*2️⃣ التحميل من المنصات الأخرى:*\n"
            "• انسخ رابط الفيديو من التطبيق\n"
            "• الصق الرابط هنا مباشرة\n"
            "• انتظر قليلاً... ✨\n\n"
            "*⚠️ ملاحظات مهمة:*\n"
            "• تأكد أن الفيديو عام وليس خاص\n"
            "• بعض الفيديوهات قد تكون محمية\n"
            "• الحد الأقصى لحجم الملف: 50MB\n\n"
            "*🆘 للدعم والمساعدة:*\n"
            "• تواصل معنا: @hamzabot\n"
            "• قناة البوت: @your_channel"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif query.data == "back_to_start":
        welcome_message = (
            f"👋 مرحباً!\n\n"
            "🎥 أنا بوت تحميل الفيديوهات والصوت من مواقع التواصل الاجتماعي\n\n"
            "📱 المواقع المدعومة:\n"
            "▫️ يوتيوب\n"
            "▫️ تيك توك\n"
            "▫️ تويتر\n"
            "▫️ انستجرام\n"
            "▫️ فيسبوك\n"
            "▫️ لايكي\n\n"
            "🚀 فقط أرسل لي رابط الفيديو وسأقوم بتحميله لك!\n\n"
            "💡 للمساعدة اضغط على زر المساعدة أدناه"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("❓ مساعدة", callback_data="help"),
                InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")
            ],
            [InlineKeyboardButton("📢 قناة البوت", url="https://t.me/your_channel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(welcome_message, reply_markup=reply_markup)
        
    elif query.data == "stats":
        # عرض إحصائيات المستخدم
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute('SELECT * FROM user_stats WHERE user_id = ?', (query.from_user.id,))
        stats = c.fetchone()
        conn.close()
        
        if stats:
            text = (
                "📊 *إحصائياتك:*\n\n"
                f"📥 عدد التحميلات: {stats[1]}\n"
                f"📹 يوتيوب: {stats[2]}\n"
                f"📸 انستجرام: {stats[3]}\n"
                f"🎵 تيك توك: {stats[4]}\n"
                f"🐦 تويتر: {stats[5]}\n"
                f"👥 فيسبوك: {stats[6]}\n"
                f"📹 لايكي: {stats[7]}\n\n"
                "🏆 *مستواك:* {level}\n"
                "⭐️ *نقاطك:* {points}"
            )
            
            points = sum([stats[1], stats[2], stats[3], stats[4], stats[5], stats[6], stats[7]])
            level = get_user_level(points)
            
            text = text.format(level=level, points=points)
        else:
            text = "لم تقم بأي تحميل بعد!"
            
        await query.message.edit_text(text, parse_mode='Markdown')
        
    elif query.data == "rate":
        keyboard = [
            [
                InlineKeyboardButton("⭐️", callback_data='rate_1'),
                InlineKeyboardButton("⭐️⭐️", callback_data='rate_2'),
                InlineKeyboardButton("⭐️⭐️⭐️", callback_data='rate_3'),
                InlineKeyboardButton("⭐️⭐️⭐️⭐️", callback_data='rate_4'),
                InlineKeyboardButton("⭐️⭐️⭐️⭐️⭐️", callback_data='rate_5')
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "🌟 *قيم البوت من 5 نجوم:*"
        
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif query.data.startswith('rate_'):
        rating = int(query.data.split('_')[1])
        
        # حفظ التقييم في قاعدة البيانات
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS ratings
                    (user_id INTEGER PRIMARY KEY, rating INTEGER, date TEXT)''')
        c.execute('INSERT OR REPLACE INTO ratings VALUES (?, ?, ?)',
                 (query.from_user.id, rating, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        
        text = f"شكراً لك! لقد قيمت البوت {rating} ⭐️"
        await query.message.edit_text(text)
        
    elif query.data == 'back':
        # العودة للقائمة الرئيسية
        await start(update, context)
        
    else:
        # استخراج نوع التحميل والرابط
        action, url = query.data.split('_', 1)
        
        # تحديث رسالة الحالة
        await query.edit_message_text("⏳ جاري التحميل...")
        
        try:
            if action == 'video':
                print("Starting video download...")
                file_path, file_type = await download_video(url)
            else:  # audio
                print("Starting audio download...")
                file_path, file_type = await download_audio(url)
            
            print(f"Download completed: {file_path}")
            
            # التحقق من وجود الملف
            if not os.path.exists(file_path):
                raise FileNotFoundError("الملف غير موجود بعد التحميل")
                
            # التحقق من حجم الملف
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # 50 MB
                os.remove(file_path)
                await query.edit_message_text("❌ عذراً، حجم الملف كبير جداً (أكبر من 50 ميجابايت)")
                return
            
            # إرسال الملف
            with open(file_path, 'rb') as file:
                if file_type == 'video':
                    await query.message.reply_video(
                        video=file,
                        caption="✅ تم التحميل بنجاح!"
                    )
                else:
                    await query.message.reply_audio(
                        audio=file,
                        caption="✅ تم التحميل بنجاح!"
                    )
            
            # حذف الملف بعد الإرسال
            os.remove(file_path)
            print("File sent and cleaned up successfully")
            
            # تحديث رسالة الحالة
            await query.edit_message_text("✅ تم التحميل بنجاح!")
            
        except FileNotFoundError as e:
            error_msg = f"File not found: {str(e)}"
            print(error_msg)
            await query.edit_message_text("❌ عذراً، حدث خطأ أثناء معالجة الملف")
            
        except Exception as e:
            error_msg = str(e)
            print(f"Download error: {error_msg}")
            if "too large" in error_msg.lower():
                await query.edit_message_text("❌ عذراً، حجم الملف كبير جداً")
            else:
                await query.edit_message_text(f"❌ حدث خطأ أثناء التحميل. الرجاء المحاولة مرة أخرى")
            
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المستخدم"""
    try:
        user_id = update.effective_user.id
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        # الحصول على عدد التحميلات
        c.execute('''
            SELECT COUNT(*) as downloads, platform, COUNT(*) as platform_downloads
            FROM downloads
            WHERE user_id = ?
            GROUP BY platform
        ''', (user_id,))
        
        stats_data = c.fetchall()
        total_downloads = sum(row[0] for row in stats_data)
        
        message = "📊 *إحصائياتك*\n\n"
        message += f"📥 مجموع التحميلات: {total_downloads}\n\n"
        
        if stats_data:
            message += "🔍 تفاصيل التحميلات:\n"
            for _, platform, platform_downloads in stats_data:
                message += f"• {platform}: {platform_downloads} تحميل\n"
        
        conn.close()
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Error in stats command: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ في عرض الإحصائيات")

async def monthly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات الشهر الحالي"""
    try:
        user_id = update.effective_user.id
        current_month = datetime.now(TIMEZONE).strftime("%Y-%m")
        
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        # الحصول على إحصائيات الشهر الحالي
        c.execute('''
            SELECT COUNT(*) as downloads, platform, COUNT(*) as platform_downloads
            FROM downloads
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            GROUP BY platform
        ''', (user_id, current_month))
        
        stats_data = c.fetchall()
        total_downloads = sum(row[0] for row in stats_data)
        
        message = f"📊 *إحصائيات شهر {current_month}*\n\n"
        message += f"📥 مجموع التحميلات: {total_downloads}\n\n"
        
        if stats_data:
            message += "🔍 تفاصيل التحميلات:\n"
            for _, platform, platform_downloads in stats_data:
                message += f"• {platform}: {platform_downloads} تحميل\n"
        
        conn.close()
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Error in monthly_stats command: {str(e)}")
        await update.message.reply_text("❌ حدث خطأ في عرض إحصائيات الشهر")

async def update_user_stats(user_id: int, platform: str):
    """تحديث إحصائيات المستخدم"""
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # التأكد من وجود سجل للمستخدم
        c.execute('INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)', (user_id,))
        
        # تحديث عدد التحميلات
        c.execute('UPDATE user_stats SET downloads = downloads + 1 WHERE user_id = ?', (user_id,))
        
        # تحديث إحصائيات المنصة
        platform_column = f"{platform}_downloads"
        if platform_column in ['youtube_downloads', 'instagram_downloads', 'tiktok_downloads', 'twitter_downloads', 'facebook_downloads', 'likee_downloads']:
            c.execute(f'UPDATE user_stats SET {platform_column} = {platform_column} + 1 WHERE user_id = ?', (user_id,))
        
        # تحديث إحصائيات البوت
        today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
        c.execute('INSERT OR IGNORE INTO bot_stats (date) VALUES (?)', (today,))
        c.execute('UPDATE bot_stats SET total_downloads = total_downloads + 1, active_users = active_users + 1 WHERE date = ?', (today,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated stats for user {user_id} - platform: {platform}")
        
    except Exception as e:
        logger.error(f"Error updating user stats: {str(e)}")
        raise

def register_user(user_id: int, username: str):
    """تسجيل مستخدم جديد في قاعدة البيانات"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        conn.commit()
    except Exception as e:
        print(f"Error registering user: {str(e)}")
    finally:
        conn.close()

def ensure_permissions():
    """التأكد من وجود الصلاحيات والملفات اللازمة"""
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    if not os.access('downloads', os.W_OK):
        os.chmod('downloads', 0o777)
    if not os.path.exists('cookies.txt'):
        open('cookies.txt', 'w').close()

def error_handler(update: Update, context: CallbackContext) -> None:
    """Log Errors caused by Updates."""
    logger.error('Exception while handling an update:', exc_info=context.error)
    if update and update.effective_message:
        text = "عذراً، حدث خطأ غير متوقع. سيتم إصلاحه قريباً."
        update.effective_message.reply_text(text)

def init_db():
    """تهيئة قاعدة البيانات"""
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # جدول المستخدمين
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (user_id INTEGER PRIMARY KEY,
                     username TEXT,
                     join_date TEXT)''')
        
        # جدول إحصائيات المستخدمين
        c.execute('''CREATE TABLE IF NOT EXISTS user_stats
                    (user_id INTEGER PRIMARY KEY,
                     downloads INTEGER DEFAULT 0,
                     youtube_downloads INTEGER DEFAULT 0,
                     instagram_downloads INTEGER DEFAULT 0,
                     tiktok_downloads INTEGER DEFAULT 0,
                     twitter_downloads INTEGER DEFAULT 0,
                     facebook_downloads INTEGER DEFAULT 0,
                     likee_downloads INTEGER DEFAULT 0)''')
        
        # جدول التقييمات
        c.execute('''CREATE TABLE IF NOT EXISTS ratings
                    (user_id INTEGER PRIMARY KEY,
                     rating INTEGER,
                     date TEXT)''')
        
        # جدول إحصائيات البوت
        c.execute('''CREATE TABLE IF NOT EXISTS bot_stats
                    (date TEXT PRIMARY KEY,
                     total_downloads INTEGER DEFAULT 0,
                     active_users INTEGER DEFAULT 0,
                     new_users INTEGER DEFAULT 0)''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def register_user(user_id: int, username: str):
    """تسجيل مستخدم جديد في قاعدة البيانات"""
    try:
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        
        # التحقق من وجود المستخدم
        c.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        existing_user = c.fetchone()
        
        if not existing_user:
            # تسجيل مستخدم جديد
            current_time = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
            c.execute('INSERT INTO users (user_id, username, join_date) VALUES (?, ?, ?)',
                     (user_id, username, current_time))
            
            # تحديث إحصائيات البوت
            today = datetime.now(TIMEZONE).strftime('%Y-%m-%d')
            c.execute('INSERT OR IGNORE INTO bot_stats (date) VALUES (?)', (today,))
            c.execute('UPDATE bot_stats SET new_users = new_users + 1 WHERE date = ?', (today,))
            
            logger.info(f"New user registered: {username} (ID: {user_id})")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        raise

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء العامة"""
    try:
        error_msg = str(context.error)
        logger.error(f"Update {update} caused error: {error_msg}")
        
        if update.effective_message:
            if "Message is too long" in error_msg:
                await update.effective_message.reply_text(
                    "⚠️ عذراً، الرسالة طويلة جداً"
                )
            elif "Message_id_invalid" in error_msg:
                await update.effective_message.reply_text(
                    "⚠️ حدث خطأ في معالجة الرسالة"
                )
            elif "Forbidden" in error_msg:
                await update.effective_message.reply_text(
                    "⚠️ ليس لدي صلاحية لإرسال الرسائل"
                )
            else:
                await update.effective_message.reply_text(
                    "❌ عذراً، حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى"
                )
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}")
        
async def download_tiktok_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تحميل فيديو من تيك توك"""
    try:
        url = update.message.text
        await update.message.reply_text("جاري تحميل الفيديو من تيك توك...")
        
        async with TikTokDownloader(download_dir=DOWNLOAD_DIR) as downloader:
            video_path, video_title = await downloader.download(url)
            
            if video_path and os.path.exists(video_path):
                await update.message.reply_video(
                    video=open(video_path, 'rb'),
                    caption=f"تم تحميل الفيديو: {video_title}",
                    supports_streaming=True
                )
                os.remove(video_path)  # تنظيف الملف بعد الإرسال
            else:
                await update.message.reply_text("عذراً، حدث خطأ أثناء تحميل الفيديو.")
                
    except Exception as e:
        await update.message.reply_text(f"عذراً، حدث خطأ: {str(e)}")

def run_bot():
    """تشغيل البوت"""
    try:
        # تهيئة قاعدة البيانات
        init_db()
        
        # التأكد من الصلاحيات
        ensure_permissions()
        
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()
        
        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("monthly", monthly_stats))
        
        # إضافة معالج الرسائل
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
        
        # إضافة معالج الأزرار
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # تشغيل البوت
        print("جاري تشغيل البوت...".encode('utf-8').decode(sys.stdout.encoding, errors='replace'))
        application.run_polling()
        
    except Exception as e:
        error_msg = f"خطأ في تشغيل البوت: {str(e)}"
        print(error_msg.encode('utf-8').decode(sys.stdout.encoding, errors='replace'))

def check_ffmpeg():
    """التحقق من وجود ffmpeg"""
    try:
        result = subprocess.run([os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg.exe'), '-version'], 
                             capture_output=True, 
                             text=True, 
                             encoding='utf-8')
        if result.returncode == 0:
            logger.info("ffmpeg موجود ويعمل بشكل صحيح")
            return True
        else:
            logger.error(f"خطأ في تشغيل ffmpeg: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"خطأ في التحقق من ffmpeg: {str(e)}")
        return False

if __name__ == '__main__':
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error in main program: {str(e)}")
