import os
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = "db.json"

if not os.path.exists(DB):
    with open(DB, 'w', encoding='utf-8') as f:
        json.dump({"users": []}, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        with open(DB, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if user_id not in data.get("users", []):
            data["users"].append(user_id)
            with open(DB, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
    except:
        pass
    await update.message.reply_text("🦊 اهلا بك في تاسك فوكس بوت!\n\nالبوت شغال تمام على Railway ✅\nارسل /stats لو انت الادمن")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الامر للادمن فقط")
        return
    try:
        with open(DB, 'r', encoding='utf-8') as f:
            data = json.load(f)
        count = len(data.get("users", []))
    except:
        count = 0
    await update.message.reply_text(f"📊 احصائيات البوت:\n👥 المستخدمين: {count}\n🆔 ايدي الادمن: {ADMIN_ID}\n✅ الحالة: شغال")

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set")
        exit(1)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    print("Bot started...")
    app.run_polling()
