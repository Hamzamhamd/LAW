import os
import logging
import asyncio
import yt_dlp

logger = logging.getLogger(__name__)

async def download_youtube(url: str, download_dir: str) -> tuple:
    """تحميل الفيديو من يوتيوب"""
    try:
        # التحقق من صحة الرابط
        if not ('youtube.com' in url or 'youtu.be' in url):
            raise Exception("❌ هذا ليس رابط يوتيوب صحيح")
            
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        logger.info(f"بدء تحميل فيديو يوتيوب: {url}")
        
        # تكوين خيارات التحميل
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # أفضل جودة متاحة بصيغة MP4
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        async with asyncio.Lock():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # استخراج معلومات الفيديو
                    info = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: ydl.extract_info(url, download=False)
                    )
                    
                    if not info:
                        raise Exception("❌ لم يتم العثور على الفيديو")
                        
                    # التحقق من حجم الفيديو (لا يتجاوز 50MB)
                    filesize = info.get('filesize', 0)
                    if filesize and filesize > 50 * 1024 * 1024:  # 50MB
                        logger.warning("الفيديو كبير جداً، جاري محاولة تحميله بجودة أقل...")
                        ydl_opts['format'] = 'best[height<=720][ext=mp4]/best[height<=720]'
                        info = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: ydl.extract_info(url, download=False)
                        )
                    
                    # تحميل الفيديو
                    logger.info("جاري تحميل الفيديو...")
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: ydl.download([url])
                    )
                    
                    # الحصول على اسم الملف
                    filename = ydl.prepare_filename(info)
                    if not filename.endswith('.mp4'):
                        filename = filename.rsplit('.', 1)[0] + '.mp4'
                    
                    logger.info(f"تم التحميل إلى: {filename}")
                    
                    if not os.path.exists(filename):
                        raise Exception("❌ فشل تحميل الفيديو")
                    
                    # التحقق من حجم الملف النهائي
                    if os.path.getsize(filename) > 50 * 1024 * 1024:  # 50MB
                        os.remove(filename)
                        raise Exception("⚠️ حجم الفيديو كبير جداً")
                    
                    return filename, info.get('title', 'فيديو يوتيوب')
                    
                except Exception as e:
                    logger.error(f"خطأ في تحميل فيديو يوتيوب: {str(e)}")
                    error_msg = str(e).lower()
                    
                    if 'private video' in error_msg:
                        raise Exception("🔒 هذا الفيديو خاص")
                    elif 'copyright' in error_msg:
                        raise Exception("⚠️ هذا الفيديو محمي بحقوق النشر")
                    elif 'not available' in error_msg:
                        raise Exception("❌ هذا الفيديو غير متاح")
                    elif 'sign in' in error_msg:
                        raise Exception("🔒 هذا الفيديو يتطلب تسجيل الدخول")
                    elif 'age restricted' in error_msg:
                        raise Exception("🔞 هذا الفيديو مقيد بالعمر")
                    else:
                        raise Exception(f"❌ خطأ في التحميل: {str(e)}")
                        
    except Exception as e:
        logger.error(f"خطأ في تحميل فيديو يوتيوب: {str(e)}")
        raise
