

import os
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ========== 配置 ==========
START_URL = "https://virtualpatients.eu/referatory/"
OUTPUT_DIR = "evip_downloads"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_DELAY = 1          # 请求间隔（秒）
TIMEOUT = 15

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_html(url):
    """获取页面 HTML"""
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        return resp.text
    except Exception as e:
        print(f"❌ 获取失败 {url}: {e}")
        return None

def extract_vp_from_table(soup, base_url):
    """从页面中提取所有虚拟病人条目（支持多种表格结构）"""
    vp_list = []

    # 方法1：查找所有 <table> 标签，然后遍历其中的 <tr>
    tables = soup.find_all('table')
    if not tables:
        print("⚠️ 未找到任何 <table>，尝试查找 <div> 中的表格类内容...")
        # 方法2：有些网站用 <div> 模拟表格，但这里先假设存在标准表格
        return vp_list

    print(f"🔍 找到 {len(tables)} 个表格，开始解析...")
    for table_idx, table in enumerate(tables):
        rows = table.find_all('tr')
        if not rows:
            continue
        # 跳过表头（通常第一个 tr 是 th）
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 6:
                continue
            # 提取标题和链接
            title_cell = cols[0]
            link_tag = title_cell.find('a')
            if not link_tag:
                continue
            title = link_tag.get_text(strip=True)
            detail_url = urljoin(base_url, link_tag.get('href'))

            # 其他字段（根据实际列顺序调整）
            keywords = cols[1].get_text(strip=True) if len(cols) > 1 else ''
            language = cols[2].get_text(strip=True) if len(cols) > 2 else ''
            institution = cols[3].get_text(strip=True) if len(cols) > 3 else ''
            license_type = cols[4].get_text(strip=True) if len(cols) > 4 else ''

            # 资源链接列（可能包含多个链接）
            resource_url = None
            external_url = None
            if len(cols) > 5:
                link_cell = cols[5]
                for a in link_cell.find_all('a'):
                    href = a.get('href', '').strip()
                    if not href:
                        continue
                    full = urljoin(base_url, href)
                    if 'content-package' in href.lower() or href.endswith('.zip'):
                        resource_url = full
                    else:
                        external_url = full

            vp_list.append({
                "title": title,
                "detail_url": detail_url,
                "keywords": keywords,
                "language": language,
                "institution": institution,
                "license": license_type,
                "resource_url": resource_url,
                "external_player_url": external_url
            })
    return vp_list

def has_next_page(soup, base_url):
    """检查是否有下一页链接（常见分页样式）"""
    # 查找包含 'next' 或 '»' 的链接
    next_link = soup.find('a', string=lambda t: t and ('Next' in t or '»' in t or 'next' in t.lower()))
    if next_link and next_link.get('href'):
        return urljoin(base_url, next_link['href'])
    # 也尝试查找 class 包含 'pager-next' 或 'next' 的链接
    for a in soup.find_all('a', class_=lambda c: c and ('next' in c.lower() or 'pager-next' in c.lower())):
        if a.get('href'):
            return urljoin(base_url, a['href'])
    return None

def main():
    all_vp = []
    url = START_URL
    page_num = 1

    while url:
        print(f"\n📄 正在抓取第 {page_num} 页: {url}")
        html = get_html(url)
        if not html:
            break

        # 保存每页源码（便于调试）
        with open(os.path.join(OUTPUT_DIR, f"page_{page_num}.html"), "w", encoding="utf-8") as f:
            f.write(html)

        soup = BeautifulSoup(html, 'html.parser')
        vp_data = extract_vp_from_table(soup, url)
        print(f"   本页找到 {len(vp_data)} 个虚拟病人")
        all_vp.extend(vp_data)

        # 查找下一页
        next_url = has_next_page(soup, url)
        if next_url and next_url != url:
            url = next_url
            page_num += 1
            time.sleep(REQUEST_DELAY)
        else:
            break

    print(f"\n📦 总共抓取到 {len(all_vp)} 个虚拟病人条目")
    if not all_vp:
        print("⚠️ 未发现任何数据。请检查保存的 page_1.html 文件，确认页面结构是否与预期不符。")
        return

    # 保存最终结果
    output_file = os.path.join(OUTPUT_DIR, "evip_virtual_patients.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_vp, f, indent=2, ensure_ascii=False)

    # 统计信息
    institutions = set(vp.get("institution") for vp in all_vp if vp.get("institution"))
    languages = set(vp.get("language") for vp in all_vp if vp.get("language"))
    print(f"✅ 数据已保存至 {output_file}")
    print(f"   涉及机构: {len(institutions)} 个")
    print(f"   涉及语言: {len(languages)} 个")

if __name__ == "__main__":
    main()