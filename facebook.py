import os
import logging
from datetime import datetime
import yt_dlp
import re

logger = logging.getLogger(__name__)

def is_valid_facebook_url(url: str) -> bool:
    """التحقق من صحة رابط فيسبوك"""
    patterns = [
        r'https?://(?:www\.)?facebook\.com/[^/]+/videos/\d+',
        r'https?://(?:www\.)?facebook\.com/watch/\?v=\d+',
        r'https?://(?:www\.)?facebook\.com/\w+/posts/\d+',
        r'https?://(?:www\.)?facebook\.com/share/[^/]+/\d+',
        r'https?://(?:www\.)?facebook\.com/share/[^/]+',
        r'https?://(?:www\.)?fb\.watch/[^/]+',
        r'https?://(?:www\.)?fb\.com/[^/]+'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

async def download_facebook(url: str, download_dir: str) -> tuple:
    """تحميل الفيديو من فيسبوك باستخدام yt-dlp"""
    try:
        # التحقق من صحة الرابط
        if not is_valid_facebook_url(url):
            raise Exception("هذا ليس رابط فيسبوك صحيح")
            
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        os.makedirs(download_dir, exist_ok=True)
            
        logger.info(f"بدء تحميل فيديو فيسبوك: {url}")
        
        # تكوين خيارات yt-dlp
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(download_dir, f"facebook_{datetime.now().strftime('%Y%m%d%H%M%S')}_%(id)s.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Mode': 'navigate'
            },
            'socket_timeout': 30,
            'retries': 20,
            'fragment_retries': 20,
            'ignoreerrors': False,
            'no_color': True,
            'extractor_args': {
                'facebook': {
                    'download_timeout': 60,
                    'extract_flat': True,
                    'allow_redirects': True
                }
            },
            'concurrent_fragment_downloads': 1,
            'buffersize': 1024,
            'external_downloader_args': ['-timeout', '30'],
            'force_generic_extractor': False,
            'sleep_interval': 3,
            'max_sleep_interval': 10,
            'sleep_interval_requests': 1
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # استخراج معلومات الفيديو
                logger.info("جاري استخراج معلومات الفيديو...")
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise Exception("لم يتم العثور على الفيديو")
                
                # التحقق من حجم الفيديو
                filesize = info.get('filesize', 0)
                if filesize and filesize > 50 * 1024 * 1024:  # 50MB
                    raise Exception("حجم الفيديو كبير جداً")
                
                # تحميل الفيديو
                logger.info("جاري تحميل الفيديو...")
                ydl.download([url])
                
                # الحصول على اسم الملف
                filename = ydl.prepare_filename(info)
                if not os.path.exists(filename):
                    raise Exception("فشل تحميل الفيديو")
                
                # استخراج العنوان
                title = info.get('title', '')
                if not title:
                    title = info.get('description', '')
                    if not title:
                        title = os.path.splitext(os.path.basename(filename))[0]
                    elif len(title) > 100:  # تقصير الوصف إذا كان طويلاً
                        title = title[:97] + '...'
                
                logger.info(f"تم تحميل الفيديو بنجاح: {filename}")
                return filename, title
                
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e).lower()
                logger.error(f"خطأ في تحميل الفيديو: {error_msg}")
                
                if 'private' in error_msg:
                    raise Exception("هذا الفيديو خاص")
                elif 'not found' in error_msg or '404' in error_msg:
                    raise Exception("الفيديو غير موجود")
                elif 'removed' in error_msg:
                    raise Exception("تم حذف الفيديو")
                elif 'login' in error_msg:
                    raise Exception("يجب تسجيل الدخول لمشاهدة هذا الفيديو")
                else:
                    raise Exception(f"خطأ في التحميل: {str(e)}")
                    
    except Exception as e:
        logger.error(f"خطأ في تحميل فيديو فيسبوك: {str(e)}")
        # تنظيف الملفات المؤقتة في حالة الفشل
        try:
            temp_file = os.path.join(download_dir, f"facebook_{datetime.now().strftime('%Y%m%d')}")
            for f in os.listdir(download_dir):
                if f.startswith(temp_file):
                    os.remove(os.path.join(download_dir, f))
        except:
            pass
        raise
