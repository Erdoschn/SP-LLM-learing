
import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ========== 配置 ==========
TARGET_URL = "https://www.ttreducators.com/ttr-compendium-catalogue"
DOWNLOAD_DIR = "ttr_compendium_downloads"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DOWNLOAD_DELAY = 1          # 下载间隔（秒）
TIMEOUT = 30
MAX_RETRIES = 3

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_html(url):
    """获取页面HTML"""
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    return resp.text

def extract_all_links(html, base_url):
    """提取所有资源链接：.zip, .pdf, .docx, /s/ 路径, Google Drive 链接"""
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith('#') or href.startswith('javascript:'):
            continue
        full = urljoin(base_url, href)
        # 资源判断
        if any(full.lower().endswith(ext) for ext in ['.zip', '.pdf', '.docx', '.pptx', '.xlsx', '.rar']):
            links.add(full)
        elif '/s/' in full and '.' in full.split('/')[-1]:   # 如 /s/xxx.zip
            links.add(full)
        elif 'drive.google.com' in full or 'google.com/drive' in full or 'uc?export=download' in full:
            links.add(full)
    return list(links)

def download_file(url, folder):
    """下载文件，支持 Google Drive 直链"""
    # 处理 Google Drive 链接
    if 'drive.google.com' in url:
        # 尝试提取直接下载链接
        match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            print(f"🔄 转换为直链: {url}")
    
    # 生成文件名
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    if not filename or '.' not in filename:
        filename = f"resource_{abs(hash(url))}.bin"
    # 清理非法字符
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    filepath = os.path.join(folder, filename)
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        print(f"⏭️  已存在，跳过: {filename}")
        return True
    
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(1, MAX_RETRIES+1):
        try:
            print(f"⬇️  下载 {filename} (尝试 {attempt})")
            resp = requests.get(url, headers=headers, stream=True, timeout=TIMEOUT)
            resp.raise_for_status()
            # 避免 Google Drive 的警告页面
            if 'Google Drive' in resp.text and 'virus' in resp.text.lower():
                print("⚠️  Google Drive 需要手动确认，请复制链接到浏览器下载")
                return False
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"✅ 保存至: {filepath}")
            return True
        except Exception as e:
            print(f"❌ 失败: {e}")
            time.sleep(2)
    return False

def main():
    print(f"🔍 抓取: {TARGET_URL}")
    html = get_html(TARGET_URL)
    # 保存源码供调试
    with open(os.path.join(DOWNLOAD_DIR, "page_source.html"), "w", encoding="utf-8") as f:
        f.write(html)
    
    links = extract_all_links(html, TARGET_URL)
    print(f"📦 共找到 {len(links)} 个资源链接")
    with open(os.path.join(DOWNLOAD_DIR, "all_links.json"), "w") as f:
        json.dump(links, f, indent=2)
    
    success, failed = [], []
    for idx, link in enumerate(links, 1):
        print(f"\n[{idx}/{len(links)}] {link}")
        if download_file(link, DOWNLOAD_DIR):
            success.append(link)
        else:
            failed.append(link)
        time.sleep(DOWNLOAD_DELAY)
    
    print(f"\n🎉 完成！成功: {len(success)}, 失败: {len(failed)}")
    if failed:
        print("❌ 失败的链接:")
        for f in failed:
            print(f"  {f}")
        with open(os.path.join(DOWNLOAD_DIR, "failed_links.json"), "w") as f:
            json.dump(failed, f, indent=2)

if __name__ == "__main__":
    main()