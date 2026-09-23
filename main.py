import telebot
from telebot import types
import json, os, datetime, threading
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7994545750
app = Flask(__name__)
@app.route('/')
def home(): return "TaskFox Running 24/7"

bot = telebot.TeleBot(BOT_TOKEN)
DB = "users.json"
if not os.path.exists(DB):
    with open(DB, 'w') as f:
        json.dump({"users":{}, "task_counts":{}, "tasks":[], "pending_withdraws":{}}, f)

def load():
    with open(DB, encoding='utf-8') as f: return json.load(f)
def save(d):
    with open(DB, 'w', encoding='utf-8') as f: json.dump(d, f, ensure_ascii=False, indent=2)

@bot.message_handler(commands=['stats'])
def stats(m):
    if m.from_user.id!= ADMIN_ID: return
    data=load()
    total_users=len(data["users"])
    total_paid=sum([u.get("total_earned",0) for u in data["users"].values()])
    pending_wd=len(data["pending_withdraws"])
    pending_proofs=sum([len(u.get("pending",[])) for u in data["users"].values()])
    active_tasks=len([t for t in data["tasks"] if data["task_counts"].get(str(t["id"]),0) < t["limit"]])
    txt=f"📊 TaskFox لوحة الادمن\n\n👥 المستخدمين: {total_users}\n💰 اجمالي الارباح: {total_paid:.2f}$\n📋 مهام نشطة: {active_tasks}\n⏳ اثباتات معلقة: {pending_proofs}\n💸 سحوبات معلقة: {pending_wd}\n\nالاوامر:\n/addtask - اضافة مهمة جديدة"
    bot.send_message(m.chat.id, txt)

@bot.message_handler(commands=['addtask'])
def add_task_start(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "📝 عنوان المهمة؟")
    bot.register_next_step_handler(m, step_title)

def step_title(m):
    bot.send_message(m.chat.id, "🔗 رابط المهمة؟")
    bot.register_next_step_handler(m, lambda msg: step_link(msg, m.text))
def step_link(m, title):
    bot.send_message(m.chat.id, "💰 المكافأة بالدولار؟ مثال: 0.10")
    bot.register_next_step_handler(m, lambda msg: step_reward(msg, title, m.text))
def step_reward(m, title, link):
    try: reward=float(m.text)
    except: return bot.send_message(m.chat.id, "❌ ارسل رقم فقط")
    bot.send_message(m.chat.id, "👥 عدد الاشخاص المطلوب؟ مثال: 100")
    bot.register_next_step_handler(m, lambda msg: step_limit(msg, title, link, reward))
def step_limit(m, title, link, reward):
    try: limit=int(m.text)
    except: return
    data=load()
    new_id=max([t["id"] for t in data["tasks"]], default=0)+1
    data["tasks"].append({"id":new_id, "title":title, "link":link, "reward":reward, "limit":limit})
    save(data)
    bot.send_message(m.chat.id, f"✅ تم نشر المهمة #{new_id}\n📌 {title}")

@bot.message_handler(commands=['start'])
def start(m):
    data=load(); uid=str(m.from_user.id)
    args=m.text.split(); referrer=None
    if len(args)>1 and args[1].startswith("ref_"):
        referrer=args[1].replace("ref_","")
        if referrer==uid: referrer=None
    if uid not in data["users"]:
        data["users"][uid]={"balance":0.0, "total_earned":0.0, "tasks_done":[], "pending":[], "completed_log":[], "withdraw_log":[], "referred_by":referrer, "referral_paid":False}
        save(data)
    mk=types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add("📋 المهام المتاحة", "💰 رصيدي")
    mk.add("📜 سجل المهام", "📜 سجل السحب")
    mk.add("💸 سحب USDT (BSC)", "👥 رابط الاحالة")
    mk.add("📒 سجل الأصدقاء المدعوين")
    bot.send_message(m.chat.id, f"🦊 مرحبا في TaskFox!\n💰 رصيدك: {data['users'][uid]['balance']:.2f}$", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text=="📋 المهام المتاحة")
def tasks_list(m):
    data=load(); uid=str(m.from_user.id)
    user=data["users"].get(uid, {"tasks_done":[], "pending":[]})
    found=False
    for t in data["tasks"]:
        if data["task_counts"].get(str(t["id"]),0) >= t["limit"]: continue
        if t["id"] in user["tasks_done"] or t["id"] in user.get("pending",[]): continue
        left=t["limit"]-data["task_counts"].get(str(t["id"]),0)
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ تنفيذ المهمة", url=t["link"]))
        kb.add(types.InlineKeyboardButton("📸 أرسلت الدليل", callback_data=f"proof_{t['id']}"))
        bot.send_message(m.chat.id, f"📌 {t['title']}\n💰 {t['reward']}$ | متبقي {left} شخص", reply_markup=kb)
        found=True
        return
    if not found: bot.send_message(m.chat.id, "🎉 مافي مهام حاليا، ارجع لاحقا")

@bot.callback_query_handler(func=lambda c: c.data.startswith("proof_"))
def ask_proof(c):
    tid=int(c.data.split("_")[1])
    bot.send_message(c.message.chat.id, "📸 أرسل صورة الدليل (سكرين شوت):")
    bot.register_next_step_handler(c.message, lambda m: receive_proof(m, tid))

def receive_proof(m, tid):
    if not m.photo: return bot.send_message(m.chat.id, "❌ ارسل صورة فقط")
    data=load(); uid=str(m.from_user.id)
    if tid in data["users"][uid]["pending"]: return bot.send_message(m.chat.id, "⏳ ارسلت هذه المهمة من قبل")
    data["users"][uid]["pending"].append(tid)
    save(data)
    bot.send_message(m.chat.id, "⏳ تم الإرسال للمراجعة، انتظر موافقة الادمن")
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ تأكيد", callback_data=f"approve_{uid}_{tid}"))
    kb.add(types.InlineKeyboardButton("❌ رفض", callback_data=f"show_reject_task_{uid}_{tid}"))
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"📸 دليل جديد\n👤 المستخدم: {uid}\n📌 مهمة رقم: {tid}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_"))
def approve_task(c):
    _,uid,tid=c.data.split("_"); tid=int(tid)
    data=load()
    task=next((x for x in data["tasks"] if x["id"]==tid),None)
    if not task: return
    if tid in data["users"][uid]["pending"]: data["users"][uid]["pending"].remove(tid)
    if tid not in data["users"][uid]["tasks_done"]:
        data["users"][uid]["tasks_done"].append(tid)
        data["users"][uid]["completed_log"].append({"title":task["title"], "reward":task["reward"], "date":str(datetime.datetime.now())[:19]})
        data["users"][uid]["balance"]+=task["reward"]
        data["users"][uid]["total_earned"]+=task["reward"]
        data["task_counts"][str(tid)]=data["task_counts"].get(str(tid),0)+1
    save(data)
    bot.send_message(int(uid), f"✅ تم قبول مهمتك +{task['reward']}$\n📌 {task['title']}")
    try: bot.edit_message_caption(f"✅ تمت الموافقة للمستخدم {uid} مهمة {tid}", chat_id=c.message.chat.id, message_id=c.message.message_id)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("show_reject_task_"))
def show_reject_task(c):
    _,_,_,uid,tid=c.data.split("_")
    kb=types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📸 صورة غير واضحة", callback_data=f"rej_task_{uid}_{tid}_صورة غير واضحة"))
    kb.add(types.InlineKeyboardButton("
