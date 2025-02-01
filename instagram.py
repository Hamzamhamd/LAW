import os
import logging
from datetime import datetime
import yt_dlp
import sys
import re
import shutil
import locale

# تعيين ترميز النظام
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# إعداد التسجيل المفصل
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('instagram_downloader.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def check_ffmpeg():
    """التحقق من وجود ffmpeg"""
    ffmpeg_path = get_ffmpeg_path()
    return os.path.exists(ffmpeg_path)

def get_ffmpeg_path():
    """الحصول على المسار الكامل لـ ffmpeg"""
    return "C:\\ffmpeg\\ffmpeg.exe"

def is_valid_instagram_url(url: str) -> bool:
    """التحقق من صحة رابط إنستغرام"""
    patterns = [
        r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[\w-]+/?',
        r'https?://(?:www\.)?instagram\.com/stories/[\w\.]+/\d+/?'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

async def download_instagram(url: str, download_dir: str) -> tuple:
    """تحميل الفيديو من إنستغرام باستخدام yt-dlp"""
    try:
        # التحقق من وجود ffmpeg
        if not check_ffmpeg():
            print("⚠️ يرجى تثبيت ffmpeg على نظامك أولاً")
            print("1. قم بتحميل ffmpeg من: https://ffmpeg.org/download.html")
            print("2. قم بفك ضغط الملف")
            print("3. انسخ المجلد إلى C:\\Program Files\\ffmpeg")
            print("4. أضف مسار C:\\Program Files\\ffmpeg\\bin إلى متغير البيئة PATH")
            raise Exception("يرجى تثبيت ffmpeg")
            
        # التحقق من صحة الرابط
        if not is_valid_instagram_url(url):
            raise Exception("هذا ليس رابط إنستغرام صحيح")
            
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        os.makedirs(download_dir, exist_ok=True)
            
        print(f"بدء تحميل فيديو إنستغرام: {url}")
        
        # تنظيف الرابط
        url = url.split('?')[0].rstrip('/')
        
        # تكوين خيارات yt-dlp
        ydl_opts = {
            'format': 'best[ext=mp4]/best',  # تحميل أفضل جودة متاحة بصيغة MP4
            'outtmpl': os.path.join(download_dir, f"instagram_{datetime.now().strftime('%Y%m%d%H%M%S')}_%(id)s.%(ext)s"),
            'quiet': False,
            'verbose': True,  # إضافة المزيد من التفاصيل للتصحيح
            'no_warnings': False,
            'extract_flat': False,
            'ffmpeg_location': get_ffmpeg_path(),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
                'Referer': 'https://www.instagram.com/',
            },
            'socket_timeout': 30,
            'retries': 5,
            'ignoreerrors': False,
            'logtostderr': True,
            'no_color': True,
            'extractor_args': {
                'instagram': {
                    'username': [''],  # يمكنك إضافة اسم المستخدم هنا
                    'password': [''],  # يمكنك إضافة كلمة المرور هنا
                }
            }
        }
        
        # إضافة ملف الكوكيز إذا كان موجوداً
        cookies_file = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookies_file):
            print("تم العثور على ملف الكوكيز")
            ydl_opts['cookiefile'] = cookies_file
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # استخراج معلومات الفيديو
                print("جاري استخراج معلومات الفيديو...")
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise Exception("لم يتم العثور على الفيديو")
                    
                # التحقق من نوع المحتوى
                if info.get('_type') == 'playlist':
                    if not info.get('entries'):
                        raise Exception("لم يتم العثور على فيديو في هذا الرابط")
                    info = info['entries'][0]
                
                # التحقق من أن المحتوى فيديو
                if not info.get('is_video', True):
                    raise Exception("هذا المنشور ليس فيديو")
                
                # التحقق من حجم الفيديو
                filesize = info.get('filesize', 0)
                if filesize and filesize > 50 * 1024 * 1024:  # 50MB
                    print("الفيديو كبير جداً، جاري محاولة تحميله بجودة أقل...")
                    ydl_opts['format'] = 'worst[ext=mp4]/worst'
                    info = ydl.extract_info(url, download=False)
                
                # تحميل الفيديو
                print("جاري تحميل الفيديو...")
                ydl.download([url])
                
                # الحصول على اسم الملف
                filename = ydl.prepare_filename(info)
                if not filename.endswith('.mp4'):
                    new_filename = filename.rsplit('.', 1)[0] + '.mp4'
                    if os.path.exists(filename):
                        os.rename(filename, new_filename)
                    filename = new_filename
                
                if not os.path.exists(filename):
                    raise Exception("فشل تحميل الفيديو")
                
                # التحقق من حجم الملف النهائي
                if os.path.getsize(filename) > 50 * 1024 * 1024:  # 50MB
                    os.remove(filename)
                    raise Exception("حجم الفيديو كبير جداً")
                
                # استخراج العنوان
                title = info.get('title', '')
                if not title:
                    title = info.get('description', '')
                    if not title:
                        title = os.path.splitext(os.path.basename(filename))[0]
                    elif len(title) > 100:  # تقصير الوصف إذا كان طويلاً
                        title = title[:97] + '...'
                
                print(f"تم تحميل الفيديو بنجاح: {filename}")
                return filename, title
                
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e).lower()
                print(f"خطأ في تحميل الفيديو: {error_msg}")
                
                if 'private' in error_msg:
                    raise Exception("هذا المحتوى خاص")
                elif 'login' in error_msg:
                    raise Exception("يجب تسجيل الدخول لمشاهدة هذا المحتوى")
                elif 'not found' in error_msg or '404' in error_msg:
                    raise Exception("المنشور غير موجود")
                elif 'video' in error_msg:
                    raise Exception("هذا المنشور ليس فيديو")
                elif 'ffmpeg' in error_msg:
                    raise Exception("يرجى تثبيت ffmpeg على نظامك")
                else:
                    raise Exception(f"خطأ في التحميل: {str(e)}")
                    
    except Exception as e:
        print(f"خطأ في تحميل فيديو إنستغرام: {str(e)}")
        # تنظيف الملفات المؤقتة في حالة الفشل
        try:
            temp_file = os.path.join(download_dir, f"instagram_{datetime.now().strftime('%Y%m%d')}")
            for f in os.listdir(download_dir):
                if f.startswith(temp_file):
                    os.remove(os.path.join(download_dir, f))
        except:
            pass
        raise

# اختبار الكود إذا تم تشغيله مباشرة
if __name__ == "__main__":
    import asyncio
    
    async def main():
        url = "https://www.instagram.com/reel/DFQVGvpNfza"  # تم تحديث الرابط وإزالة المعلمات الإضافية
        download_dir = "downloads"
        try:
            filepath, title = await download_instagram(url, download_dir)
            print(f"تم التحميل بنجاح: {filepath}")
            print(f"العنوان: {title}")
        except Exception as e:
            print(f"فشل التحميل: {str(e)}")
    
    # تعيين ترميز وحدة التحكم
    if sys.platform.startswith('win'):
        os.system('chcp 65001')
    asyncio.run(main())
