import os
import logging
import re
from datetime import datetime
import yt_dlp
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json

logger = logging.getLogger(__name__)

# قائمة وكلاء مجانية - يمكنك تحديثها بوكلاء جديدة
FREE_PROXIES = [
    'http://51.159.115.233:3128',
    'http://13.95.173.197:80',
    'http://167.172.96.117:34913',
    'http://51.75.206.209:80',
]

def get_random_proxy():
    """الحصول على وكيل عشوائي من القائمة"""
    return random.choice(FREE_PROXIES) if FREE_PROXIES else None

def is_valid_tiktok_url(url: str) -> bool:
    """التحقق من صحة رابط تيك توك"""
    patterns = [
        r'https?://(?:www\.)?tiktok\.com/@[\w\.-]+/video/\d+',
        r'https?://(?:www\.)?tiktok\.com/[@\w\.-]+/\w+/\d+',
        r'https?://(?:www\.)?vm\.tiktok\.com/\w+',
        r'https?://(?:www\.)?vt\.tiktok\.com/\w+',
        r'https?://(?:www\.)?tiktok\.com/t/\w+',
        r'https?://(?:m\.)?tiktok\.com/v/\d+',
        r'https?://(?:www\.)?tiktok\.com/\w+',
        r'https?://(?:www\.)?douyin\.com/video/\d+'
    ]
    return any(re.match(pattern, url) for pattern in patterns)

def extract_video_id(url: str) -> str:
    """استخراج معرف الفيديو من الرابط"""
    # محاولة استخراج معرف الفيديو من الرابط المباشر
    video_id_match = re.search(r'/video/(\d+)', url)
    if video_id_match:
        return video_id_match.group(1)
    
    # إذا كان الرابط مختصر، نتبع إعادة التوجيه للحصول على الرابط الكامل
    try:
        proxy = get_random_proxy()
        proxies = {'http': proxy, 'https': proxy} if proxy else None
        response = requests.head(url, allow_redirects=True, timeout=30, proxies=proxies)
        final_url = response.url
        video_id_match = re.search(r'/video/(\d+)', final_url)
        if video_id_match:
            return video_id_match.group(1)
    except:
        pass
    
    return None

def get_video_info(url: str) -> dict:
    """الحصول على معلومات الفيديو باستخدام selenium"""
    options = uc.ChromeOptions()
    options.add_argument('--headless')  # تشغيل المتصفح بدون واجهة
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = uc.Chrome(options=options)
    try:
        driver.get(url)
        # انتظار حتى يتم تحميل الفيديو
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "video"))
        )
        
        # إعطاء وقت إضافي للتأكد من تحميل كل شيء
        time.sleep(3)
        
        # الحصول على عنصر الفيديو
        video_element = driver.find_element(By.TAG_NAME, "video")
        video_url = video_element.get_attribute('src')
        
        # الحصول على معلومات إضافية
        title = driver.title
        
        return {
            'url': video_url,
            'title': title
        }
    finally:
        driver.quit()

async def download_tiktok(url: str, download_dir: str) -> tuple:
    """تحميل الفيديو من تيك توك"""
    try:
        # التحقق من صحة الرابط
        if not is_valid_tiktok_url(url):
            raise Exception("هذا ليس رابط تيك توك صحيح")
            
        # إنشاء مجلد التحميلات إذا لم يكن موجوداً
        os.makedirs(download_dir, exist_ok=True)
            
        logger.info(f"بدء تحميل فيديو تيك توك: {url}")
        
        # استخراج معرف الفيديو
        video_id = extract_video_id(url)
        if not video_id:
            raise Exception("لم يتم العثور على معرف الفيديو")
        
        # الحصول على معلومات الفيديو
        video_info = get_video_info(url)
        if not video_info or not video_info.get('url'):
            raise Exception("لم يتم العثور على رابط الفيديو")
        
        # تحميل الفيديو
        video_url = video_info['url']
        title = video_info.get('title', f'tiktok_video_{video_id}')
        filename = f"tiktok_{datetime.now().strftime('%Y%m%d%H%M%S')}_{video_id}.mp4"
        filepath = os.path.join(download_dir, filename)
        
        # تحميل الفيديو باستخدام requests
        proxy = get_random_proxy()
        proxies = {'http': proxy, 'https': proxy} if proxy else None
        response = requests.get(video_url, stream=True, timeout=60, proxies=proxies)
        if response.status_code != 200:
            raise Exception("فشل في تحميل الفيديو")
        
        # حفظ الفيديو
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # التحقق من حجم الملف
        if os.path.getsize(filepath) > 50 * 1024 * 1024:  # 50MB
            os.remove(filepath)
            raise Exception("حجم الفيديو كبير جداً")
        
        logger.info(f"تم تحميل الفيديو بنجاح: {filepath}")
        return filepath, title
                
    except Exception as e:
        logger.error(f"خطأ في تحميل فيديو تيك توك: {str(e)}")
        # تنظيف الملفات المؤقتة في حالة الفشل
        try:
            temp_file = os.path.join(download_dir, f"tiktok_{datetime.now().strftime('%Y%m%d')}")
            for f in os.listdir(download_dir):
                if f.startswith(temp_file):
                    os.remove(os.path.join(download_dir, f))
        except:
            pass
        raise

# اختبار الكود إذا تم تشغيله مباشرة
if __name__ == "__main__":
    import asyncio
    import random
    
    async def main():
        url = "https://www.tiktok.com/@flight.controller/video/7458356827747552534"
        download_dir = "downloads"
        try:
            filepath, title = await download_tiktok(url, download_dir)
            print(f"تم التحميل بنجاح: {filepath}")
            print(f"العنوان: {title}")
        except Exception as e:
            print(f"فشل التحميل: {str(e)}")
    
    asyncio.run(main())
