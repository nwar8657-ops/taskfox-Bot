import telebot
from telebot import types
import json, os, datetime

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
    txt=f"📊 TaskFox\n👥 {total_users}\n💰 {total_paid:.2f}$\n📋 {active_tasks}\n⏳ {pending_proofs}\n💸 {pending_wd}"
    bot.send_message(m.chat.id, txt)

@bot.message_handler(commands=['addtask'])
def add_task_start(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "📝 عنوان المهمة؟")
    bot.register_next_step_handler(m, step_title)

def step_title(m):
    bot.send_message(m.chat.id, "🔗 رابط؟")
    bot.register_next_step_handler(m, lambda msg: step_link(msg, m.text))

def step_link(m, title):
    bot.send_message(m.chat.id, "💰 المكافأة؟")
    bot.register_next_step_handler(m, lambda msg: step_reward(msg, title, m.text))

def step_reward(m, title, link):
    try: reward=float(m.text)
    except: return
    bot.send_message(m.chat.id, "👥 العدد؟")
    bot.register_next_step_handler(m, lambda msg: step_limit(msg, title, link, reward))

def step_limit(m, title, link, reward):
    limit=int(m.text)
    data=load()
    new_id=max([t["id"] for t in data["tasks"]], default=0)+1
    data["tasks"].append({"id":new_id, "title":title, "link":link, "reward":reward, "limit":limit})
    save(data)
    bot.send_message(m.chat.id, f"✅ تم نشر المهمة {new_id}")

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
    bot.send_message(m.chat.id, f"🦊 TaskFox جاهز!\nرصيدك: {data['users'][uid]['balance']:.2f}$", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text=="📋 المهام المتاحة")
def tasks_list(m):
    data=load(); uid=str(m.from_user.id)
    user=data["users"].get(uid, {"tasks_done":[], "pending":[]})
    for t in data["tasks"]:
        if data["task_counts"].get(str(t["id"]),0) >= t["limit"]: continue
        if t["id"] in user["tasks_done"] or t["id"] in user.get("pending",[]): continue
        left=t["limit"]-data["task_counts"].get(str(t["id"]),0)
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ تنفيذ", url=t["link"]))
        kb.add(types.InlineKeyboardButton("📸 أرسلت الدليل", callback_data=f"proof_{t['id']}"))
        bot.send_message(m.chat.id, f"📌 {t['title']}\n💰 {t['reward']}$ | متبقي {left}", reply_markup=kb)
        return
    bot.send_message(m.chat.id, "🎉 مافي مهام")

@bot.callback_query_handler(func=lambda c: c.data.startswith("proof_"))
def ask_proof(c):
    tid=int(c.data.split("_")[1])
    bot.send_message(c.message.chat.id, "📸 أرسل صورة الدليل:")
    bot.register_next_step_handler(c.message, lambda m: receive_proof(m, tid))

def receive_proof(m, tid):
    if not m.photo: return
    data=load(); uid=str(m.from_user.id)
    if tid in data["users"][uid]["pending"]: return
    data["users"][uid]["pending"].append(tid)
    save(data)
    bot.send_message(m.chat.id, "⏳ تم الإرسال للمراجعة")
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ تأكيد", callback_data=f"approve_{uid}_{tid}"))
    kb.add(types.InlineKeyboardButton("❌ رفض", callback_data=f"show_reject_task_{uid}_{tid}"))
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=f"دليل\n👤 {uid}\n📌 {tid}", reply_markup=kb)

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
    bot.send_message(int(uid), f"✅ قبول +{task['reward']}$")
    try: bot.edit_message_caption("✅ تم", chat_id=c.message.chat.id, message_id=c.message.message_id)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("show_reject_task_"))
def show_reject_task(c):
    _,_,_,uid,tid=c.data.split("_")
    kb=types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📸 صورة غير واضحة", callback_data=f"rej_task_{uid}_{tid}_صورة غير واضحة"))
    kb.add(types.InlineKeyboardButton("🚫 لم تنفذ", callback_data=f"rej_task_{uid}_{tid}_لم تنفذ المهمة"))
    kb.add(types.InlineKeyboardButton("⚠️ مزور", callback_data=f"rej_task_{uid}_{tid}_دليل مزور"))
    kb.add(types.InlineKeyboardButton("✍️ مخصص", callback_data=f"custom_reject_task_{uid}_{tid}"))
    bot.edit_message_caption("❓ سبب الرفض:", chat_id=c.message.chat.id, message_id=c.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rej_task_"))
def do_reject_task_btn(c):
    _,_,uid,tid,reason=c.data.split("_",4)
    tid=int(tid); data=load()
    if tid in data["users"][uid]["pending"]: data["users"][uid]["pending"].remove(tid)
    save(data)
    bot.send_message(int(uid), f"❌ رفض {tid}\n📝 {reason}")
    bot.edit_message_caption(f"❌ {reason}", chat_id=c.message.chat.id, message_id=c.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("custom_reject_task_"))
def custom_reject_task(c):
    _,_,_,uid,tid=c.data.split("_")
    bot.send_message(c.message.chat.id, f"سبب رفض {tid} للمستخدم {uid}:")
    bot.register_next_step_handler(c.message, lambda m: custom_reject_do(m, uid, tid, c.message.message_id))

def custom_reject_do(m, uid, tid, mid):
    reason=m.text; tid=int(tid); data=load()
    if tid in data["users"][uid]["pending"]: data["users"][uid]["pending"].remove(tid)
    save(data)
    bot.send_message(int(uid), f"❌ رفض {tid}\n📝 {reason}")
    bot.edit_message_caption(f"❌ {reason}", chat_id=m.chat.id, message_id=mid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("wd_ok_"))
def wd_ok(c):
    uid=c.data.split("_")[2]
    data=load()
    wd=data["pending_withdraws"].pop(uid, None)
    if not wd: return
    data["users"][uid]["balance"]-=wd["amount"]
    data["users"][uid]["withdraw_log"].append({"amount":wd["amount"], "status":"تم", "date":wd["date"]})
    save(data)
    bot.send_message(int(uid), f"✅ تم إرسال {wd['amount']}$")
    bot.edit_message_text("✅ تم التحويل", chat_id=c.message.chat.id, message_id=c.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("show_wd_no_"))
def show_wd_no(c):
    uid=c.data.split("_")[3]
    bot.send_message(c.message.chat.id, f"سبب رفض سحب {uid}:")
    bot.register_next_step_handler(c.message, lambda m: do_wd_no(m, uid, c.message.message_id))

def do_wd_no(m, uid, mid):
    reason=m.text
    data=load()
    wd=data["pending_withdraws"].pop(uid, None)
    if wd:
        data["users"][uid]["withdraw_log"].append({"amount":wd["amount"], "status":f"مرفوض: {reason}", "date":wd["date"]})
    save(data)
    bot.send_message(int(uid), f"❌ رفض السحب\n📝 {reason}")
    bot.edit_message_text(f"❌ رفض: {reason}", chat_id=m.chat.id, message_id=mid)

@bot.message_handler(func=lambda m: True)
def others(m):
    if m.text.startswith("/"): return
    data=load(); uid=str(m.from_user.id); u=data["users"].get(uid, {})
    if m.text=="💰 رصيدي": bot.send_message(m.chat.id, f"💰 {u.get('balance',0):.2f}$")
    elif m.text=="📜 سجل المهام":
        txt="\n".join([f"✅ {x['title']} +{x['reward']}$" for x in u.get("completed_log",[])]) or "فاضي"
        bot.send_message(m.chat.id, txt)
    elif m.text=="📜 سجل السحب":
        txt="\n".join([f"💸 {x['amount']}$ {x['status']}" for x in u.get("withdraw_log",[])]) or "فاضي"
        bot.send_message(m.chat.id, txt)
    elif m.text=="👥 رابط الاحالة":
        bot.send_message(m.chat.id, f"https://t.me/{bot.get_me().username}?start=ref_{uid}")
    elif m.text=="📒 سجل الأصدقاء المدعوين":
        invited=[(k,v) for k,v in data["users"].items() if v.get("referred_by")==uid]
        if not invited: bot.send_message(m.chat.id, "📭 لم تدع أحد"); return
        txt=f"📒 دعوت {len(invited)}:\n" + "\n".join([f"👤 {fid} | {info.get('total_earned',0)}$" for fid,info in invited])
        bot.send_message(m.chat.id, txt)
    elif m.text=="💸 سحب USDT (BSC)":
    
