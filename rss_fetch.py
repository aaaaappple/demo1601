# 导入工具（小白不用动）
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timedelta
import os
import html
import re

# ---------------------- 方案一专用：读取GitHub环境变量（关键！） ----------------------
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS", "")
# 你的Gmail别名配置
ALIAS_EMAIL = "hellostudyking@gmail.com"
SENDER_DISPLAY_NAME = "路彭速递"
# ------------------------------------------------------------------

# 数据源配置（不变）
RSS_SOURCES = [
    ("https://reutersnew.buzzing.cc/feed.xml", "路透社"),
    ("https://bloombergnew.buzzing.cc/feed.xml", "彭博社")
]

# 邮件颜色配置（不变）
COLORS = {
    "time": "#F97316",
    "reuters": "#E63946",
    "bloomberg": "#1D4ED8",
    "link": "#E63946",
    "title": "#2E4057"
}

# 防重复推送（不变）
def get_pushed_ids():
    if not os.path.exists("pushed_ids.txt"):
        return set()
    with open("pushed_ids.txt", "r", encoding="utf-8") as f:
        return set(f.read().splitlines())

def save_pushed_id(id):
    with open("pushed_ids.txt", "a", encoding="utf-8") as f:
        f.write(f"{id}\n")

# 发送邮件（修复SMTP实例化错误）
def send_email(subject, content, news_bj_date):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 微软雅黑, Arial, sans-serif; line-height: 2.2; font-size: 15px; }}
            li {{ margin-bottom: 12px; list-style: none; padding-left: 1px; }}
            a {{ text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h2 style="color:{COLORS['title']}; font-size:18px; margin-bottom:25px;">📩 路彭速递（{news_bj_date}）</h2>
        <ul style="padding-left:5px; margin:0;">
            {content}
        </ul>
    </body>
    </html>
    """
    msg = MIMEText(html_content, "html", "utf-8")
    msg["From"] = Header(f"{SENDER_DISPLAY_NAME} <{ALIAS_EMAIL}>", "utf-8")
    msg["To"] = RECEIVER_EMAILS
    msg["Subject"] = subject

    try:
        # 修复点1：正确实例化SMTP_SSL对象（带括号和参数）
        smtp_conn = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp_conn.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        smtp_conn.sendmail(ALIAS_EMAIL, RECEIVER_EMAILS.split(","), msg.as_string())
        # 修复点2：调用实例的quit方法
        smtp_conn.quit()
        print(f"✅ 邮件推送成功！发件人：{SENDER_DISPLAY_NAME} <{ALIAS_EMAIL}>")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail登录失败！检查主账号/应用密码，或别名是否验证")
    except Exception as e:
        print(f"❌ 推送失败：{e}")

# 提取资讯时间（不变）
def get_show_time(entry, content):
    try:
        content = html.unescape(content).replace("\n", "").replace("\r", "").replace("\t", "").strip()
        time_patterns = [
            r'>\s*(\d{2}:\d{2})\s*<',
            r'<time[^>]*>\s*(\d{2}:\d{2})\s*</time>',
            r'datetime="[^"]*T(\d{2}:\d{2}):\d{2}[^"]*"'
        ]
        for pattern in time_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        entry_time = entry.get("updated", entry.get("published", ""))
        if entry_time:
            time_obj = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
            return time_obj.strftime("%m-%d")
        return datetime.now().strftime("%m-%d")
    except:
        return datetime.now().strftime("%m-%d")

def get_news_bj_info(entry):
    try:
        entry_time = entry.get("updated", entry.get("published", ""))
        if entry_time:
            utc_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
            bj_time = utc_time + timedelta(hours=8)
            return bj_time.timestamp(), bj_time.strftime("%Y-%m-%d")
        current_bj = datetime.now()
        return current_bj.timestamp(), current_bj.strftime("%Y-%m-%d")
    except:
        current_bj = datetime.now()
        return current_bj.timestamp(), current_bj.strftime("%Y-%m-%d")

# 核心逻辑（不变）
def fetch_rss():
    pushed_ids = get_pushed_ids()
    all_news = []
    source_counter = {"路透社": 0, "彭博社": 0}
    global_counter = 0

    for rss_url, source in RSS_SOURCES:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                entry_id = entry.get("id", "").strip()
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                content = entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""

                if entry_id not in pushed_ids and entry_id and title and link.startswith(("http", "https")):
                    show_time = get_show_time(entry, content)
                    bj_timestamp, news_bj_date = get_news_bj_info(entry)
                    all_news.append((bj_timestamp, source, show_time, title, link, entry_id, news_bj_date))
                    save_pushed_id(entry_id)
        except Exception as e:
            print(f"⚠️ {source}资讯抓取出错：{e}")

    all_news.sort(key=lambda x: -x[0])
    news_html_list = []

    if all_news:
        display_bj_date = all_news[0][6]
    else:
        display_bj_date = datetime.now().strftime("%Y-%m-%d")

    for news in all_news:
        bj_timestamp, source, show_time, title, link, _, _ = news
        global_counter += 1
        source_counter[source] += 1
        source_seq = source_counter[source]

        time_style = f"color:{COLORS['time']};font-weight:bold;"
        source_color = COLORS["reuters"] if source == "路透社" else COLORS["bloomberg"]
        source_style = f"color:{source_color};font-weight:bold;"
        link_style = f"color:{COLORS['link']};"

        news_html = f"""
        <li>
            {global_counter}. ［<span style="{time_style}">{show_time}</span> <span style="{source_style}">{source}({source_seq})</span>］
            {title} 👉 <a href="{link}" target="_blank" style="{link_style}">🔗</a>
        </li>
        """
        news_html_list.append(news_html)

    if news_html_list:
        final_content = "\n".join(news_html_list)
        email_title = f"快讯 | {display_bj_date}"
        send_email(email_title, final_content, display_bj_date)
    else:
        print("ℹ️  暂无新资讯，本次不推送邮件")

if __name__ == "__main__":
    fetch_rss()

