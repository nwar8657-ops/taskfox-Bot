import telebot
from telebot import types
import json, os
from flask import Flask
import threading

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6691257142

bot = telebot.TeleBot(BOT_TOKEN)
DB = "users.json"

if not os.path.exists(DB):
    with open(DB, 'w') as f: json.dump({"users":{}, "task_counts":{}, "tasks":[]}, f)

def load():
    with open(DB) as f: return json.load(f)
def save(d):
    with open(DB, 'w') as f: json.dump(d, f)

@bot.message_handler(commands=['addtask'])
def add_task_start(m):
    if m.from_user.id!= ADMIN_ID:
        bot.send_message(m.chat.id, "❌ هذا الأمر للادمن فقط")
        return
    bot.send_message(m.chat.id, "📝 أرسل عنوان المهمة:\nمثال: تقييم تطبيق على متجر بلاي")
    bot.register_next_step_handler(m, step_title)

def step_title(m):
    title = m.text
    bot.send_message(m.chat.id, f"✅ العنوان: {title}\n\nالآن أرسل رابط المهمة:\nمثال: https://t.me/xxx")
    bot.register_next_step_handler(m, lambda msg: step_link(msg, title))

def step_link(m, title):
    link = m.text
    bot.send_message(m.chat.id, f"🔗 الرابط: {link}\n\nكم المكافأة؟ أرسل رقم فقط\nمثال: 0.20")
    bot.register_next_step_handler(m, lambda msg: step_reward(msg, title, link))

def step_reward(m, title, link):
    try: reward = float(m.text)
    except:
        bot.send_message(m.chat.id, "❌ لازم رقم! مثال 0.20")
        return
    bot.send_message(m.chat.id, f"💰 المكافأة: {reward}$\n\nكم عدد الأشخاص المسموح لهم بتنفيذها؟\nأرسل رقم: مثال 10 أو 20")
    bot.register_next_step_handler(m, lambda msg: step_limit(msg, title, link, reward))

def step_limit(m, title, link, reward):
    try: limit = int(m.text)
    except:
        bot.send_message(m.chat.id, "❌ لازم رقم صحيح! مثال 10")
        return
    data=load()
    new_id = max([t["id"] for t in data["tasks"]], default=0) + 1
    data["tasks"].append({"id":new_id, "title":title, "link":link, "reward":reward, "limit":limit})
    save(data)
    bot.send_message(m.chat.id, f"✅ تم نشر المهمة!\n\n📌 {title}\n🔗 {link}\n💰 {reward}$\n👥 العدد: {limit} شخص\n\nالمهمة الآن ظهرت للمستخدمين وبتختفي تلقائياً لما يوصل {limit} شخص.")

@bot.message_handler(commands=['tasks_admin'])
def admin_tasks(m):
    if m.from_user.id!= ADMIN_ID: return
    data=load()
    if not data["tasks"]:
        bot.send_message(m.chat.id, "مافي مهام")
        return
    text="📋 المهام الحالية:\n\n"
    for t in data["tasks"]:
        count = data["task_counts"].get(str(t["id"]),0)
        text+=f"ID:{t['id']} - {t['title']}\n{t['reward']}$ - {count}/{t['limit']}\n\n"
    bot.send_message(m.chat.id, text)

@bot.message_handler(commands=['deltask'])
def del_task(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "أرسل ID المهمة اللي تبي تحذفها:")
    bot.register_next_step_handler(m, do_del)

def do_del(m):
    try: tid=int(m.text)
    except: return
    data=load()
    data["tasks"]=[t for t in data["tasks"] if t["id"]!=tid]
    save(data)
    bot.send_message(m.chat.id, f"✅ تم حذف مهمة {tid}")

@bot.message_handler(commands=['start'])
def start(m):
    data=load()
    uid=str(m.from_user.id)
    if uid not in data["users"]:
        data["users"][uid]={"balance":0.0, "tasks_done":[], "pending":[]}
        if len(m.text.split())>1:
            ref=m.text.split()[1]
            if ref in data["users"] and ref!=uid:
                data["users"][ref]["balance"]+=0.05
        save(data)
    mk=types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add("📋 المهام المتاحة", "💰 رصيدي")
    mk.add("💸 سحب USDT", "👥 رابط الاحالة")
    bot.send_message(m.chat.id, "🦊 TaskFox\n💵 اربح من المهام", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text=="📋 المهام المتاحة")
def tasks_list(m):
    data=load()
    uid=str(m.from_user.id)
    user=data["users"].get(uid, {"tasks_done":[], "pending":[]})
    for t in data["tasks"]:
        count=data["task_counts"].get(str(t["id"]),0)
        if count>=t["limit"]: continue
        if t["id"] in user["tasks_done"]: continue
        if t["id"] in user.get("pending",[]): continue
        left=t["limit"]-count
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ تنفيذ", url=t["link"]))
        kb.add(types.InlineKeyboardButton("📸 أرسلت الدليل", callback_data=f"proof_{t['id']}"))
        bot.send_message(m.chat.id, f"📌 {t['title']}\n💰 {t['reward']}$\n👥 متبقي: {left}/{t['limit']}", reply_markup=kb)
        return
    bot.send_message(m.chat.id, "🎉 مافي مهام متاحة حالياً!")

@bot.callback_query_handler(func=lambda c: c.data.startswith("proof_"))
def ask_proof(c):
    tid=int(c.data.split("_")[1])
    bot.send_message(c.message.chat.id, "📸 أرسل صورة الدليل الآن:")
    bot.register_next_step_handler(c.message, lambda m: receive_proof(m, tid))

def receive_proof(m, tid):
    if not m.photo:
        bot.send_message(m.chat.id, "❌ لازم صورة")
        return
    data=load()
    uid=str(m.from_user.id)
    if tid in data["users"][uid].get("pending",[]):
        bot.send_message(m.chat.id, "⏳ مهمتك قيد المراجعة بالفعل")
        return
    data["users"][uid]["pending"].append(tid)
    save(data)
    bot.send_message(m.chat.id, "⏳ جار التحقق... سيتم المراجعة خلال 24 ساعة")
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ تأكيد", callback_data=f"approve_{uid}_{tid}"),
            types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_{uid}_{tid}"))
    task=[x for x in data["tasks"] if x["id"]==tid][0]
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"🔔 دليل\n👤 {m.from_user.first_name}\n🆔 {uid}\n📌 {task['title']}\n💰 {task['reward']}$\n👥 {data['task_counts'].get(str(tid),0)}/{task['limit']}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_"))
def approve(c):
    _,uid,tid=c.data.split("_"); tid=int(tid)
    data=load()
    if tid in data["users"][uid]["pending"]:
        data["users"][uid]["pending"].remove(tid)
        data["users"][uid]["tasks_done"].append(tid)
        reward=[x for x in data["tasks"] if x["id"]==tid][0]["reward"]
        data["users"][uid]["balance"]+=reward
        data["task_counts"][str(tid)]=data["task_counts"].get(str(tid),0)+1
        save(data)
        bot.send_message(int(uid), f"✅ تم تأكيد مهمتك +{reward}$\nرصيدك: {data['users'][uid]['balance']:.2f}$")
        bot.edit_message_caption(f"✅ تم - {uid} - {tid} - {data['task_counts'][str(tid)]}/{[x for x in data['tasks'] if x['id']==tid][0]['limit']}", chat_id=c.message.chat.id, message_id=c.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("reject_"))
def reject(c):
    _,uid,tid=c.data.split("_"); tid=int(tid)
    data=load()
    if tid in data["users"][uid]["pending"]:
        data["users"][uid]["pending"].remove(tid)
        save(data)
        bot.send_message(int(uid), "❌ تم رفض الدليل، حاول بصورة أوضح")
        bot.edit_message_caption(f"❌ رفض - {uid} - {tid}", chat_id=c.message.chat.id, message_id=c.message.message_id)

@bot.message_handler(func=lambda m: m.text=="💰 رصيدي")
def bal(m):
    data=load(); b=data["users"].get(str(m.from_user.id),{}).get("balance",0)
    bot.send_message(m.chat.id, f"💰 رصيدك: {b:.2f} USDT (BSC)")

@bot.message_handler(func=lambda m: m.text=="👥 رابط الاحالة")
def ref(m):
    bot.send_message(m.chat.id, f"رابطك:\nhttps://t.me/TaskFoxYEbot?start={m.from_user.id}")

@bot.message_handler(func=lambda m: m.text=="💸 سحب USDT")
def withdraw(m):
    data=load(); b=data["users"].get(str(m.from_user.id),{}).get("balance",0)
    if b<2:
        bot.send_message(m.chat.id, f"❌ رصيدك {b:.2f}$ أقل من 2$"); return
    bot.send_message(m.chat.id, f"💰 رصيدك: {b:.2f}$\nأرسل عنوان BSC (0x...):")
    bot.register_next_step_handler(m, get_address)

def get_address(m):
    if not m.text.startswith("0x"):
        bot.send_message(m.chat.id, "❌ لازم يبدأ بـ 0x"); return
    data=load(); uid=str(m.from_user.id); amount=data["users"][uid]["balance"]
    bot.send_message(m.chat.id, f"✅ طلب سحب {amount:.2f}$\n⏳ خلال 24س")
    data["users"][uid]["balance"]=0; save(data)
    bot.send_message(ADMIN_ID, f"🔔 سحب BSC\n🆔 {uid}\n💰 {amount:.2f}$\n📬 `{m.text}`", parse_mode="Markdown")

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()
print("Bot ready with admin panel")
bot.infinity_polling()
