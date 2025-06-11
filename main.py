# main.py
import os
import time
import hmac
import base64
import hashlib
import urllib.parse
import requests
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ---------------------- 环境变量加载 ----------------------
load_dotenv()  # GitHub 部署时自动读取 .env 文件

# 如果在 Colab 中使用，请取消以下三行注释并填写你的密钥：
#os.environ["NEWSAPI_KEY"] = ""
#os.environ["DINGTALK_WEBHOOK"] = ""
#os.environ["DINGTALK_SECRET"] = ""

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET")

if not all([NEWSAPI_KEY, DINGTALK_WEBHOOK, DINGTALK_SECRET]):
    raise ValueError("请确认 NEWSAPI_KEY、DINGTALK_WEBHOOK 和 DINGTALK_SECRET 已设置")

# ---------------------- 配置参数 ----------------------
KEYWORDS = ["sewing thread"]
DAYS_FILTER = 360
NEWS_LIMIT = 3

# ---------------------- 获取钉钉签名 ----------------------
def sign_url():
    timestamp = str(round(time.time() * 1000))
    secret_enc = DINGTALK_SECRET.encode("utf-8")
    string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
    hmac_code = hmac.new(secret_enc, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"

# ---------------------- 抓取新闻 ----------------------
def fetch_news():
    seen_links = set()
    all_news = []

    for keyword in KEYWORDS:
        print(f"📡 抓取中：{keyword} - 使用 everything 接口，不分国家")
        url = (
            f"https://newsapi.org/v2/everything?"
            f"q={urllib.parse.quote(keyword)}&"
            f"apiKey={NEWSAPI_KEY}&"
            f"pageSize=50&"
            f"sortBy=publishedAt"
        )
        response = requests.get(url)
        if response.status_code != 200:
            print(f"❌ 抓取失败：{response.text}")
            continue

        articles = response.json().get("articles", [])
        print(f"本次抓取到 {len(articles)} 条新闻，过滤周期：近 {DAYS_FILTER} 天")

        for article in articles:
            published_at = article.get("publishedAt")
            if not published_at:
                continue
            try:
                published = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                continue

            if published < datetime.utcnow() - timedelta(days=DAYS_FILTER):
                continue

            url_link = article.get("url")
            if not url_link or url_link in seen_links:
                continue

            seen_links.add(url_link)

            source_name = article.get("source", {}).get("name", "")
            image_url = article.get("urlToImage")
            image = image_url.strip() if isinstance(image_url, str) and image_url.strip() else ""

            # ❌ 跳过包含 webp 格式的图片
            if "webp" in image.lower():
                continue


            all_news.append({
                "title": article.get("title", ""),
                "description": article.get("description") or "",
                "url": url_link,
                "image": image,
                "published": published.strftime("%Y-%m-%d %H:%M"),
                "published_dt": published,  # 新增字段用于判断近3天
                "source": source_name,
                "region": ""
            })

    # 先筛选出近2天的新闻
    recent_news = [n for n in all_news if n["published_dt"] >= datetime.utcnow() - timedelta(days=2)]
    print(f"📅 近2天内可选新闻条数：{len(recent_news)}")

    # 随机打乱后选取最多 NEWS_LIMIT 条
    random.shuffle(recent_news)
    selected_news = recent_news[:NEWS_LIMIT]

    return selected_news


# ---------------------- 发送钉钉 ----------------------
def send_to_dingtalk(news):
    if not news:
        print("⚠️ 没有可推送的新闻")
        return
    # 调试：打印一下 news 列表和长度，确认传入无误
    print(f"🔍 传入的 news（共 {len(news)} 条）:", news)
    
    content_blocks = []
    for i, item in enumerate(news, start=1):
        block = f""" {i}. [{item['title']}]({item['url']})\n
🌐 来源：{item['source']}{' | 地区：' + item['region'] if item['region'] else ''}
🕘 时间：{item['published']}
{f'![图片]({item["image"]})' if item['image'] else ''}
"""
        content_blocks.append(block.strip())

    markdown_text = "\n\n---\n\n".join(content_blocks)

    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": "📢最新速览",
            "text": markdown_text
        }
    }

    webhook_url = sign_url()
    headers = {'Content-Type': 'application/json'}
    response = requests.post(webhook_url, headers=headers, json=data)
    print(f"🚀 钉钉推送状态: {response.status_code}, 返回: {response.text}")

# ---------------------- 主函数 ----------------------
if __name__ == "__main__":
    news = fetch_news()
    total_news_count = len(news)
    print(f"\n✅ 共选取到 {total_news_count} 条新闻")
    for i, item in enumerate(news, 1):
        print(f"{i}. [{item['title']}]({item['url']}) - {item['published']} {('('+item['region']+')') if item['region'] else ''}\n🎞️ 图片: {item['image'] or '无'}")
    send_to_dingtalk(news)
