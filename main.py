import telebot
import re
import collections
import math
import os
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime

TOKEN = '_'
bot = telebot.TeleBot(TOKEN)
db = {}

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

def create_visuals(n1, n2, scores, times1, times2):
    # 1. График сходства стилей
    plt.figure(figsize=(6, 4))
    plt.bar(['Лексика', 'Знаки', 'Эмодзи'], [scores['sw']*100, scores['sp']*100, scores['se']*100], color=['#4CAF50', '#2196F3', '#FFC107'])
    plt.ylim(0, 100)
    plt.title('Сравнение стилей (%)')
    p1 = f"main_{n1}.png"
    plt.savefig(p1)
    plt.close()

    # 2. Линейный график времени (Кардиограмма)
    plt.figure(figsize=(7, 4))
    h1 = collections.Counter(times1)
    h2 = collections.Counter(times2)
    x = list(range(24))
    y1 = [h1.get(i, 0) for i in x]
    y2 = [h2.get(i, 0) for i in x]
    
    plt.plot(x, y1, label=n1, marker='o', linewidth=2, color='green')
    plt.plot(x, y2, label=n2, marker='o', linewidth=2, color='blue')
    plt.fill_between(x, y1, alpha=0.1, color='green')
    plt.fill_between(x, y2, alpha=0.1, color='blue')
    plt.xticks(x)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.title('Хронологический след (GMT)')
    p2 = f"time_{n1}.png"
    plt.savefig(p2)
    plt.close()
    
    # Считаем коэффициент совпадения времени для уведомления
    time_sim = get_cosine(h1, h2)
    return p1, p2, time_sim

@bot.message_handler(commands=['add'])
def add_target(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return bot.reply_to(message, "Введите имя цели!")
    uid, name = message.chat.id, args[1]
    if uid not in db: db[uid] = {}
    db[uid][name] = {'msgs': [], 'times': [], 'info': {}}
    db[uid]['active_target'] = name
    bot.reply_to(message, f"🎯 Цель **{name}** выбрана. Теперь пересылай её сообщения.")

@bot.message_handler(commands=['compare'])
def compare(message):
    args = message.text.split()
    if len(args) < 3: return bot.reply_to(message, "Используй: /compare Имя1 Имя2")
    uid, n1, n2 = message.chat.id, args[1], args[2]
    
    if n1 not in db[uid] or n2 not in db[uid]: return bot.reply_to(message, "Цель не найдена.")

    t1, t2 = db[uid][n1], db[uid][n2]
    w1, p1, e1 = analyze_text(t1['msgs'])
    w2, p2, e2 = analyze_text(t2['msgs'])
    
    sw, sp, se = get_cosine(w1, w2), get_cosine(p1, p2), get_cosine(e1, e2)
    total = (sw*0.5 + sp*0.3 + se*0.2)*100
    
    img1, img2, time_sim = create_visuals(n1, n2, {'sw':sw, 'sp':sp, 'se':se}, t1['times'], t2['times'])
    
    # Текстовый результат
    alert = ""
    if time_sim > 0.85:
        alert = "\n\n⚠️ **ВНИМАНИЕ:** Обнаружено критическое совпадение биоритмов (часов активности)!"
    
    res_text = (f"🧬 **Анализ завершен!**\n"
                f"🔥 Сходство: **{total:.1f}%**\n"
                f"⏰ Совпадение графиков: **{time_sim:.1%}**" + alert)

    # Генерация PDF
    pdf_name = f"Report_{n1}_{n2}.pdf"
    c = canvas.Canvas(pdf_name, pagesize=A4)
    c.setFont("Helvetica-Bold", 16); c.drawString(50, 800, f"OSINT REPORT: {n1} vs {n2}")
    c.setFont("Helvetica", 12); c.drawString(50, 780, f"Similiarity: {total:.1f}% | Time Match: {time_sim:.1%}")
    c.drawImage(img1, 50, 480, width=450, height=280)
    c.drawImage(img2, 50, 180, width=450, height=280)
    c.save()

    # Отправка
    with open(pdf_name, 'rb') as f:
        bot.send_document(uid, f, caption=res_text, parse_mode="Markdown")
    
    os.remove(pdf_name); os.remove(img1); os.remove(img2)

@bot.message_handler(content_types=['text'])
def collect(message):
    uid = message.chat.id
    if uid in db and 'active_target' in db[uid]:
        target = db[uid]['active_target']
        if message.forward_date:
            db[uid][target]['times'].append(datetime.fromtimestamp(message.forward_date).hour)
        db[uid][target]['msgs'].append(message.text)

bot.polling()
