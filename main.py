import telebot
import re
import collections
import math
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

TOKEN = 'Your_TOKEN'
ADMIN_ID = ID  # Твой ID

bot = telebot.TeleBot(TOKEN)
db = {}

# Если пишем цели на русском, рекомендую на en.
#FONT_PATH = '/usr/share/fonts/truetype/freefont/FreeSans.ttf'
#if os.path.exists(FONT_PATH):
#    pdfmetrics.registerFont(TTFont('FreeSans', FONT_PATH))
#    MAIN_FONT = 'FreeSans'
#else:
#    MAIN_FONT = 'Helvetica'

# --- [ЛОГИКА АНАЛИЗА] ---
def get_cosine(vec1, vec2):
    intersection = set(vec1.keys()) & set(vec2.keys())
    num = sum([vec1[x] * vec2[x] for x in intersection])
    sum1 = sum([v**2 for v in vec1.values()])
    sum2 = sum([v**2 for v in vec2.values()])
    den = math.sqrt(sum1) * math.sqrt(sum2)
    return float(num) / den if den else 0.0

def analyze_text(text_list):
    full_text = " ".join(text_list).lower()
    words = collections.Counter(re.findall(r'\b\w{4,}\b', full_text))
    punct = collections.Counter(re.findall(r'[!?.)(]{1,}', full_text))
    emojis = collections.Counter(re.findall(r'[^\w\s,.]', full_text))
    return words, punct, emojis


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if message.from_user.id != ADMIN_ID: return
    
    welcome_text = (
        "🕵️‍♂️ **TraceDNA OSINT Lab v2.3 (Kali Edition)**\n\n"
        "Привет! Я твой автономный комбайн для лингвистической экспертизы. "
        "Я помогу определить, принадлежат ли разные аккаунты одному человеку по их 'цифровому почерку'.\n\n"
        "**Как работать с ботом:**\n"
        "1️⃣ `/add [Имя]` — создай слот для цели (например, `/add Target_1`).\n"
        "2️⃣ **Перешли сообщения** этой цели мне в чат. Я соберу текст и время отправки.\n"
        "3️⃣ `/add [Имя]` — создай слот для второй цели и также перешли сообщения.\n"
        "4️⃣ `/compare [Имя1] [Имя2]` — получи итоговый процент сходства и подробный PDF-отчет.\n\n"
        "**Дополнительно:**\n"
        "• `/list` — список созданных целей и количество сообщений.\n"
        "• `/reset` — полная очистка текущей базы (в памяти).\n\n"
        "💡 *Совет: для точности пересылай не менее 5-10 сообщений для каждой цели.*"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=['add'])
def add(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return bot.reply_to(message, "⚠️ Ошибка! Введи имя: `/add Suspect`")
    
    name = args[1].replace(" ", "_") # Заменяем пробелы для корректности команд
    uid = message.chat.id
    
    if uid not in db: db[uid] = {}
    db[uid][name] = {'msgs': [], 'times': [], 'info': {}}
    db[uid]['active_target'] = name
    
    bot.reply_to(message, f"🎯 Цель **{name}** выбрана. Пересылай сообщения!")

@bot.message_handler(commands=['list'])
def list_targets(message):
    if message.from_user.id != ADMIN_ID: return
    uid = message.chat.id
    if uid not in db or len(db[uid]) <= 1:
        return bot.reply_to(message, "📭 База пуста.")
    
    targets = [f"• `{k}` ({len(v['msgs'])} сообщений)" for k, v in db[uid].items() if k != 'active_target']
    bot.reply_to(message, "📋 **Список целей:**\n" + "\n".join(targets), parse_mode="Markdown")

@bot.message_handler(commands=['compare'])
def compare(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        return bot.reply_to(message, "⚠️ Формат: `/compare Имя1 Имя2`")
    
    uid = message.chat.id
    n1, n2 = args[1], args[2]
    
    if n1 not in db[uid] or n2 not in db[uid]:
        return bot.reply_to(message, "❌ Одна из целей не найдена в /list")

    t1, t2 = db[uid][n1], db[uid][n2]
    w1, p1, e1 = analyze_text(t1['msgs'])
    w2, p2, e2 = analyze_text(t2['msgs'])
    
    sw, sp, se = get_cosine(w1, w2), get_cosine(p1, p2), get_cosine(e1, e2)
    h1, h2 = collections.Counter(t1['times']), collections.Counter(t2['times'])
    st = get_cosine(h1, h2)
    
    total = (sw*0.4 + sp*0.2 + se*0.15 + st*0.25)*100

    # Генерация графиков
    plt.figure(figsize=(6, 4))
    plt.bar(['Лексика', 'Стиль', 'Эмодзи'], [sw*100, sp*100, se*100], color=['green', 'blue', 'orange'])
    plt.title('Сравнение стилей (%)')
    p1_path = f"styles_{n1}.png"; plt.savefig(p1_path); plt.close()

    plt.figure(figsize=(7, 4))
    x = list(range(24))
    plt.plot(x, [h1.get(i, 0) for i in x], label=n1, color='green', marker='o')
    plt.plot(x, [h2.get(i, 0) for i in x], label=n2, color='blue', marker='o')
    plt.title('Хронологический след'); plt.legend(); plt.grid(True)
    p2_path = f"time_{n1}.png"; plt.savefig(p2_path); plt.close()

    # Сборка PDF
    pdf_file = f"Result_{n1}_{n2}.pdf"
    c = canvas.Canvas(pdf_file, pagesize=A4)
    c.setFont(MAIN_FONT, 18); c.drawString(50, 800, f"OSINT Report: {n1} vs {n2}")
    c.setFont(MAIN_FONT, 14); c.drawString(50, 770, f"Total Similarity Score: {total:.1f}%")
    c.drawImage(p1_path, 50, 480, width=450, height=250)
    c.drawImage(p2_path, 50, 200, width=450, height=250)
    c.save()

    with open(pdf_file, 'rb') as f:
        bot.send_document(uid, f, caption=f"🧬 Анализ завершен.\nСходство: **{total:.1f}%**", parse_mode="Markdown")
    
    os.remove(pdf_file); os.remove(p1_path); os.remove(p2_path)

@bot.message_handler(content_types=['text'])
def collect(message):
    if message.from_user.id != ADMIN_ID: return
    uid = message.chat.id
    if uid in db and 'active_target' in db[uid]:
        target = db[uid]['active_target']
        if message.forward_date:
            db[uid][target]['times'].append(datetime.fromtimestamp(message.forward_date).hour)
        db[uid][target]['msgs'].append(message.text)

@bot.message_handler(commands=['reset'])
def reset(message):
    if message.from_user.id != ADMIN_ID: return
    db[message.chat.id] = {}
    bot.reply_to(message, "🗑 Все цели и сообщения удалены.")

bot.polling(none_stop=True)
