# 导入工具
import feedparser
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import html
import re

# 环境变量读取
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS", "")

# 自定义发件人昵称
CUSTOM_NICKNAME = "aa快讯"

# 数据源配置
RSS_SOURCES = [
    ("https://reutersnew.buzzing.cc/feed.xml", "路透社"),
    ("https://bloombergnew.buzzing.cc/feed.xml", "彭博社")
]

# 邮件颜色配置
COLORS = {
    "time": "#F97316",
    "reuters": "#E63946",
    "bloomberg": "#1D4ED8",
    "link": "#E63946",
    "title": "#2E4057"
}

# 防重复推送
def get_pushed_ids():
    if not os.path.exists("pushed_ids.txt"):
        return set()
    with open("pushed_ids.txt", "r", encoding="utf-8") as f:
        return set(f.read().splitlines())

def save_pushed_id(id):
    with open("pushed_ids.txt", "a", encoding="utf-8") as f:
        f.write(f"{id}\n")

# 发送邮件（单独发送，收件人仅见自己）
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
    receiver_list = [email.strip() for email in RECEIVER_EMAILS.split(",") if email.strip()]
    if not receiver_list:
        print("❌ 无有效收件人邮箱")
        return

    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        print(f"✅ 连接Gmail成功，向{len(receiver_list)}个收件人发送")

        for receiver in receiver_list:
            msg = MIMEText(html_content, "html", "utf-8")
            msg["From"] = f"{CUSTOM_NICKNAME} <{GMAIL_EMAIL}>"
            msg["To"] = receiver
            msg["Subject"] = subject
            smtp.sendmail(GMAIL_EMAIL, [receiver], msg.as_string())
            print(f"✅ 已发送给：{receiver}")

        smtp.quit()
        print("✅ 所有邮件发送完成！")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail登录失败，检查邮箱/密码和环境变量")
    except Exception as e:
        print(f"❌ 发送失败：{e}")

# 🔴 核心修正：1.优先提原生时分 2.无时分时先将UTC转北京时间再提取月日
def get_source_time_and_timestamp(entry, content):
    try:
        # 步骤1：提取content中<time>标签里的原始时分（如02:19）
        content = html.unescape(content).replace("\n", "").replace("\r", "").replace("\t", "").strip()
        time_patterns = [
            r'>\s*(\d{2}:\d{2})\s*</time>',  # 匹配<time>02:19</time>
            r'datetime="[^"]*T(\d{2}:\d{2}):\d{2}[^"]*"\s*>\s*(\d{2}:\d{2})\s*</time>'  # 匹配带datetime的time标签
        ]
        show_time = None
        for pattern in time_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # 取分组里的时分（兼容两种正则的分组位置）
                show_time = match.group(1).strip() if match.group(1) else match.group(2).strip()
                break
        
        if show_time:
            # 有原生时分：生成「当日+时分」的时间戳（保证时分排序优先级）
            current_date = datetime.now().strftime("%Y-%m-%d")
            full_time = datetime.strptime(f"{current_date} {show_time}", "%Y-%m-%d %H:%M")
            return show_time, full_time.timestamp()
        else:
            # 步骤2：无原生时分 → 先将UTC时间转北京时间，再提取月日
            entry_time = entry.get("updated", entry.get("published", ""))
            if entry_time:
                # 解析UTC时间（带Z的ISO格式）
                utc_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                # UTC+8转换为北京时间
                bj_time = utc_time + timedelta(hours=8)
                # 提取北京时间的月日作为展示时间
                show_time = bj_time.strftime("%m-%d")
                # 生成北京时间的月日时间戳（用于排序）
                month_day_timestamp = datetime(bj_time.year, bj_time.month, bj_time.day).timestamp()
                return show_time, month_day_timestamp
            # 终极兜底：用当前北京时间的月日
            current_bj = datetime.now()
            show_time = current_bj.strftime("%m-%d")
            month_day_timestamp = datetime(current_bj.year, current_bj.month, current_bj.day).timestamp()
            return show_time, month_day_timestamp
    except Exception as e:
        # 异常兜底：用当前北京时间的月日
        current_bj = datetime.now()
        show_time = current_bj.strftime("%m-%d")
        month_day_timestamp = datetime(current_bj.year, current_bj.month, current_bj.day).timestamp()
        return show_time, month_day_timestamp

# 提取资讯的完整北京时间（年-月-日）用于邮件标题
def get_news_bj_date(entry):
    try:
        entry_time = entry.get("updated", entry.get("published", ""))
        if entry_time:
            utc_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
            bj_time = utc_time + timedelta(hours=8)
            return bj_time.strftime("%Y-%m-%d")
        return datetime.now().strftime("%Y-%m-%d")
    except:
        return datetime.now().strftime("%Y-%m-%d")

# 核心逻辑：按信息源原生时间排序
def fetch_rss():
    pushed_ids = get_pushed_ids()
    all_news = []  # 存储：(原生时间戳, 来源, 展示时间, 标题, 链接, 资讯ID, 完整日期)
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
                    news_bj_date = get_news_bj_date(entry)
                    # 获取信息源原生的展示时间和排序时间戳
                    show_time, source_timestamp = get_source_time_and_timestamp(entry, content)
                    all_news.append((source_timestamp, source, show_time, title, link, entry_id, news_bj_date))
                    save_pushed_id(entry_id)
        except Exception as e:
            print(f"⚠️ {source}抓取出错：{e}")

    # 按信息源原生时间戳倒序排序（有时分按时分，无时分按北京时间月日）
    all_news.sort(key=lambda x: -x[0])
    news_html_list = []

    if all_news:
        display_bj_date = all_news[0][6]
    else:
        display_bj_date = datetime.now().strftime("%Y-%m-%d")

    for news in all_news:
        source_timestamp, source, show_time, title, link, _, _ = news
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
        print("ℹ️  暂无新资讯，本次不推送")

if __name__ == "__main__":
    fetch_rss()

