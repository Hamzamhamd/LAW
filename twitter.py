import os
import logging
import asyncio
import yt_dlp

logger = logging.getLogger(__name__)

async def download_twitter(url: str, download_dir: str) -> tuple:
    """تحميل الفيديو من تويتر"""
    try:
        # التحقق من صحة الرابط
        if not ('twitter.com' in url or 'x.com' in url):
            raise Exception("❌ هذا ليس رابط تويتر صحيح")
            
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        logger.info(f"بدء تحميل فيديو تويتر: {url}")
        
        # تكوين خيارات التحميل
        ydl_opts = {
            'format': 'best',  # أفضل جودة متاحة
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cookiefile': 'cookies.txt',  # ملف الكوكيز للتغلب على قيود تويتر
        }
        
        # تحميل الفيديو
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, ydl.extract_info, url, False)
            video_title = info.get('title', 'twitter_video')
            video_path = os.path.join(download_dir, f"{video_title}.{info['ext']}")
            await loop.run_in_executor(None, ydl.download, [url])
            
        if not os.path.exists(video_path):
            raise Exception("❌ فشل تحميل الفيديو")
            
        logger.info(f"تم تحميل فيديو تويتر بنجاح: {video_title}")
        return video_path, "تم التحميل بنجاح ✅"
        
    except Exception as e:
        error_msg = str(e) if str(e) != "" else "❌ حدث خطأ أثناء تحميل الفيديو"
        logger.error(f"خطأ في تحميل فيديو تويتر: {error_msg}")
        return None, error_msg
