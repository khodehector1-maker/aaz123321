from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.network.connection import ConnectionTcpFull

API_ID = 36999253  # عدد خودت
API_HASH = "93e8fa5e73be9af4717f1386dfaa7d6c"  # رشته خودت

# --- تنظیمات پروکسی Hiddify ---
proxy = {
    'proxy_type': 'socks5',  # برای Mixed port معمولاً socks5 بهتر جواب می‌ده
    'addr': '127.0.0.1',     
    'port': 12334,           # <--- پورت Mixed رو اینجا گذاشتیم
    'username': None,
    'password': None,
    'rdns': True
}
# ------------------------------

with TelegramClient(
    StringSession(), 
    API_ID, 
    API_HASH,
    proxy=proxy,
    connection=ConnectionTcpFull
) as client:
    print("\n" + "="*50)
    print("SESSION_STRING (این رشته را کپی و در جای امنی ذخیره کنید):")
    print(client.session.save())
    print("="*50 + "\n")
