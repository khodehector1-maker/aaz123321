import asyncio
import os
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import DeleteHistoryRequest
from telethon.errors import FloodWaitError, RPCError

# ==================== خواندن از Environment ====================
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
TG_SESSION = os.environ["TG_SESSION"]  # StringSession

DAYS_OLD = int(os.getenv("DAYS_OLD", "30"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
SEND_REPORT = os.getenv("SEND_REPORT", "true").lower() == "true"

# آیدی‌های لیست سفید را با کاما جدا کن: "123456789,@my_family"
_wl = os.getenv("WHITELIST_CHATS", "")
WHITELIST_CHATS = []
for item in _wl.split(","):
    item = item.strip()
    if not item:
        continue
    WHITELIST_CHATS.append(int(item) if item.lstrip("-").isdigit() else item)

REPORT_PREFIX = os.getenv("REPORT_PREFIX", "🧹 گزارش پاک‌سازی چت‌های مرده")
# ==============================================================


async def send_report_to_saved(client, lines: list[str], header: str):
    MAX_LEN = 4000
    chunks, current = [], header + "\n\n"
    for line in lines:
        if len(current) + len(line) + 1 > MAX_LEN:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current)

    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        title = f"({i}/{total})\n" if total > 1 else ""
        await client.send_message("me", title + chunk, parse_mode="html")
        await asyncio.sleep(0.5)


async def main():
    client = TelegramClient(
        StringSession(TG_SESSION), API_ID, API_HASH
    )
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Session نامعتبر است. TG_SESSION را بررسی کن.")
        return

    print("✅ وارد شدید.\n")

    cutoff_date = datetime.now() - timedelta(days=DAYS_OLD)
    stats = {
        "deleted": 0,
        "skipped_pinned": 0,
        "skipped_active": 0,
        "skipped_onesided": 0,
        "skipped_whitelist": 0,
        "errors": 0,
    }
    deleted_reports = []

    async for dialog in client.iter_dialogs():
        if not dialog.is_user:
            continue

        if dialog.pinned:
            print(f"📌 سنجاق‌شده → رد: {dialog.name}")
            stats["skipped_pinned"] += 1
            continue

        entity_id = dialog.id
        entity_username = getattr(dialog.entity, "username", None)
        if entity_id in WHITELIST_CHATS or (
            entity_username and entity_username in WHITELIST_CHATS
        ):
            print(f"⭐ لیست سفید → رد: {dialog.name}")
            stats["skipped_whitelist"] += 1
            continue

        try:
            last_msgs = await client.get_messages(dialog.id, limit=1)
            if not last_msgs:
                continue
            last_date = last_msgs[0].date.replace(tzinfo=None)
            if last_date >= cutoff_date:
                print(f"💬 هنوز فعال → رد: {dialog.name}")
                stats["skipped_active"] += 1
                continue

            has_incoming = bool(
                await client.get_messages(dialog.id, incoming=True, limit=1)
            )
            has_outgoing = bool(
                await client.get_messages(dialog.id, outgoing=True, limit=1)
            )
            if not (has_incoming and has_outgoing):
                print(f"⏭️ یک‌طرفه → رد: {dialog.name}")
                stats["skipped_onesided"] += 1
                continue

            if DRY_RUN:
                print(
                    f"🧪 [DRY_RUN] می‌خواستم پاک کنم: {dialog.name} "
                    f"(آخرین: {last_date.date()})"
                )
            else:
                print(
                    f"🗑️ حذف دوطرفه: {dialog.name} "
                    f"(آخرین: {last_date.date()})"
                )
                await client(
                    DeleteHistoryRequest(
                        peer=dialog.entity,
                        max_id=0,
                        just_clear=True,
                        revoke=True,
                    )
                )
                await asyncio.sleep(2)

            stats["deleted"] += 1

            username_str = f"@{entity_username}" if entity_username else "—"
            dry_tag = " [DRY_RUN]" if DRY_RUN else ""
            deleted_reports.append(
                f"• <b>{dialog.name or 'بدون نام'}</b>{dry_tag}\n"
                f"  🆔 <code>{entity_id}</code>\n"
                f"  🔗 {username_str}\n"
                f"  📅 آخرین پیام: {last_date.date()}"
            )

        except FloodWaitError as e:
            print(f"⏳ FloodWait: {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
            stats["errors"] += 1
        except RPCError as e:
            print(f"❌ خطای تلگرام روی {dialog.name}: {e}")
            stats["errors"] += 1
        except Exception as e:
            print(f"❌ خطای غیرمنتظره روی {dialog.name}: {e}")
            stats["errors"] += 1

    print("\n📊 خلاصه:")
    print(f"   🗑️ حذف‌شده         : {stats['deleted']}")
    print(f"   📌 سنجاق           : {stats['skipped_pinned']}")
    print(f"   💬 فعال             : {stats['skipped_active']}")
    print(f"   ⏭️ یک‌طرفه          : {stats['skipped_onesided']}")
    print(f"   ⭐ لیست سفید        : {stats['skipped_whitelist']}")
    print(f"   ❌ خطاها            : {stats['errors']}")

    if SEND_REPORT:
        header = (
            f"{REPORT_PREFIX}\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"⚙️ آستانه مرده‌بودن: {DAYS_OLD} روز\n"
            f"{'🧪 DRY_RUN — چیزی حذف نشد' if DRY_RUN else '✅ حذف واقعی انجام شد'}\n"
            f"───────────────"
        )
        if deleted_reports:
            await send_report_to_saved(client, deleted_reports, header)
            print(f"\n📨 گزارش {len(deleted_reports)} چت ارسال شد.")
        else:
            await client.send_message(
                "me", header + "\n\nهیچ چتی واجد شرایط نبود.",
                parse_mode="html",
            )

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
