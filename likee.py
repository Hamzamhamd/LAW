import os
import logging
import asyncio
import yt_dlp
import re
import requests
from urllib.parse import urlparse, urljoin, unquote

logger = logging.getLogger(__name__)

class LikeeDownloader:
    def __init__(self, download_dir: str):
        self.download_dir = download_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://likee.video/',
            'Origin': 'https://likee.video'
        }

    @staticmethod
    def normalize_url(url: str) -> str:
        """تنظيف وتوحيد شكل الرابط"""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # تحويل I إلى l في الروابط
        url = re.sub(r'https?://I\.', 'https://l.', url, flags=re.IGNORECASE)
        return url

    @staticmethod
    def is_valid_likee_url(url: str) -> bool:
        """التحقق من صحة رابط لايكي"""
        if not url:
            return False
            
        url = LikeeDownloader.normalize_url(url)
        logger.info(f"Checking URL validity: {url}")
        
        patterns = [
            r'https?://(?:www\.)?likee\.video/(?:v|video)/[\w\.-]+',
            r'https?://(?:www\.)?l\.likee\.video/v/[\w\.-]+',
            r'https?://(?:www\.)?like\.video/(?:v|video)/[\w\.-]+',
            r'https?://(?:www\.)?likee\.video/v/[\w\.-]+',
            r'https?://l\.likee\.video/[\w\.-]+',
            r'https?://l\.likeevideo/v/[\w\.-]+',
            r'https?://(?:www\.)?likeevideo/v/[\w\.-]+',
            r'https?://(?:www\.)?likee\.video/[\w\.-]+',
            r'https?://(?:www\.)?like\.video/[\w\.-]+'
        ]
        
        for pattern in patterns:
            if re.match(pattern, url, re.IGNORECASE):
                logger.info(f"URL matches pattern: {pattern}")
                return True
                
        logger.warning(f"URL does not match any pattern: {url}")
        return False

    @staticmethod
    def extract_video_id(url: str) -> str:
        """استخراج معرف الفيديو من الرابط"""
        try:
            # تنظيف الرابط
            url = url.strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # أنماط مختلفة من روابط لايكي
            patterns = [
                r'likee\.video/(?:v/)?(\w+)',  # likee.video/v/abc123 or likee.video/abc123
                r'l\.likee\.video/(?:v/)?(\w+)',  # l.likee.video/v/abc123
                r'like\.video/(?:v/)?(\w+)',  # like.video/v/abc123
                r'likeevideo/(?:v/)?(\w+)'  # likeevideo/v/abc123
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting video ID: {str(e)}")
            return None

    async def get_final_url(self, url: str) -> str:
        """الحصول على الرابط النهائي بعد تتبع التحويلات"""
        try:
            url = self.normalize_url(url)
            logger.info(f"Getting final URL for: {url}")
            
            # استخراج معرف الفيديو
            video_id = self.extract_video_id(url)
            logger.info(f"Extracted video ID: {video_id}")
            
            if video_id:
                # محاولة تكوين الرابط المباشر
                direct_urls = [
                    f"https://likee.video/@user/video/{video_id}",
                    f"https://likee.video/v/{video_id}",
                    f"https://l.likee.video/v/{video_id}",
                    f"https://like.video/v/{video_id}",
                    f"https://likee.video/{video_id}",
                    f"https://like.video/{video_id}"
                ]
                
                # تجربة كل رابط مباشر
                for direct_url in direct_urls:
                    try:
                        logger.info(f"Trying direct URL: {direct_url}")
                        response = requests.head(direct_url, headers=self.headers, allow_redirects=True, timeout=10)
                        if response.status_code == 200:
                            logger.info(f"Found working direct URL: {direct_url}")
                            return direct_url
                    except Exception as e:
                        logger.warning(f"Failed to access direct URL {direct_url}: {str(e)}")
                        continue
            
            return url
            
        except Exception as e:
            logger.error(f"Error getting final URL: {str(e)}")
            return url

    async def download(self, url: str) -> tuple:
        """تحميل الفيديو من لايكي"""
        try:
            logger.info(f"Starting Likee video download for URL: {url}")
            
            # التحقق من صحة الرابط
            if not self.is_valid_likee_url(url):
                error_msg = "❌ عذراً، هذا الرابط غير مدعوم"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # إنشاء مجلد التحميلات إذا لم يكن موجوداً
            if not os.path.exists(self.download_dir):
                os.makedirs(self.download_dir)
                logger.info(f"Created download directory: {self.download_dir}")
            
            # استخراج معرف الفيديو
            video_id = self.extract_video_id(url)
            if not video_id:
                raise Exception("❌ لم نتمكن من استخراج معرف الفيديو")
            
            # الحصول على رابط الفيديو المباشر
            api_url = f"https://likee.video/api/video/info?video_id={video_id}"
            response = requests.get(api_url, headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"❌ فشل الاتصال بخادم لايكي: {response.status_code}")
            
            data = response.json()
            if 'data' not in data or 'video_url' not in data['data']:
                raise Exception("❌ لم نتمكن من العثور على رابط الفيديو")
            
            video_url = data['data']['video_url']
            video_title = data['data'].get('title', f'likee_video_{video_id}')
            video_path = os.path.join(self.download_dir, f"{video_title}.mp4")
            
            # تحميل الفيديو
            logger.info(f"Downloading video from: {video_url}")
            video_response = requests.get(video_url, headers=self.headers, stream=True)
            if video_response.status_code != 200:
                raise Exception(f"❌ فشل تحميل الفيديو: {video_response.status_code}")
            
            with open(video_path, 'wb') as f:
                for chunk in video_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if not os.path.exists(video_path):
                raise Exception("❌ فشل تحميل الفيديو")
            
            logger.info(f"Successfully downloaded video: {video_title}")
            return video_path, video_title
            
        except Exception as e:
            error_msg = str(e) if str(e) != "" else "❌ حدث خطأ أثناء تحميل الفيديو"
            logger.error(f"Error in LikeeDownloader: {error_msg}")
            raise Exception(error_msg)

async def download_likee(url: str, download_dir: str) -> tuple[str, str]:
    """تحميل فيديو من لايكي"""
    downloader = LikeeDownloader(download_dir=download_dir)
    return await downloader.download(url)
