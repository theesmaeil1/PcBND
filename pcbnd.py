import telebot
from telebot import types
import sqlite3
from datetime import datetime
import time
import threading
import logging

# تنظیمات لاگ برای دیباگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# تنظیمات ربات
BOT_TOKEN = "" # توکن ربات تلگرام
GROUP_CHAT_ID = -100 # آیدی گروه چت
ADMIN_ID = 1111111 # ایدی ادمین

bot = telebot.TeleBot(BOT_TOKEN)

# اتصال به دیتابیس SQLite
def init_db():
    try:
        conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone_number TEXT,
                join_date TEXT,
                is_verified INTEGER
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                professor TEXT,
                file_id TEXT,
                uploaded_by INTEGER,
                upload_date TEXT,
                is_approved INTEGER DEFAULT 0
            )"""
        )
        conn.commit()
        conn.close()
        logging.info("دیتابیس با موفقیت مقداردهی اولیه شد.")
    except Exception as e:
        logging.error(f"خطا در مقداردهی اولیه دیتابیس: {e}")

# منوی اصلی
def get_main_menu(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("📤 آپلود فایل"), types.KeyboardButton("📚 منابع آموزشی"))
    keyboard.add(types.KeyboardButton("📩 درخواست‌ها"), types.KeyboardButton("ℹ️ راهنما"))
    if user_id == ADMIN_ID:
        keyboard.add(types.KeyboardButton("🛠 پنل ادمین"))
    return keyboard

# منوی مدیریت
def get_admin_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("📊 آمار ربات"), types.KeyboardButton("📢 پیام همگانی"))
    keyboard.add(types.KeyboardButton("🔄 فوروارد پیام"), types.KeyboardButton("📚 آپلود منابع آموزشی"))
    keyboard.add(types.KeyboardButton("💬 پیام شخصی به کاربر"), types.KeyboardButton("👤 نمایش اطلاعات کاربران"))
    keyboard.add(types.KeyboardButton("✅ تأیید منابع"), types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    return keyboard

# ذخیره وضعیت کاربران
user_states = {}

# تابع حذف پیام پس از 30 ثانیه
def delete_message_after_delay(chat_id, message_id):
    time.sleep(30)
    try:
        bot.delete_message(chat_id, message_id)
        bot.send_message(chat_id, "فایل حذف شد. دوباره شروع کن!", reply_markup=get_main_menu(ADMIN_ID))
    except Exception as e:
        logging.error(f"خطا در حذف پیام: {e}")

# تابع شروع و احراز هویت
@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    try:
        conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT is_verified FROM users WHERE user_id = ?", (user.id,))
        result = c.fetchone()
        conn.close()

        welcome_message = (
            "👩‍💻 به جمع صمیمی دانشجوهای کامپیوتر بندرعباس خوش اومدی! 👨‍💻\n\n"
            "⚡️ اینجا جاییه که می‌تونی جزوه و پروژه‌هاتو به اشتراک بذاری، درخواست بدی و کلی با بچه‌های دیگه گپ بزنی! 😎\n\n"
            "از منوی زیر شروع کن:"
        )

        if result and result[0] == 1:
            bot.send_message(message.chat.id, welcome_message, reply_markup=get_main_menu(user.id))
            user_states[str(user.id)] = "MAIN_MENU"
            logging.info(f"کاربر {user.id} به منوی اصلی هدایت شد.")
        else:
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(types.KeyboardButton("📱 اشتراک شماره تلفن", request_contact=True))
            bot.send_message(
                message.chat.id,
                "لطفاً برای احراز هویت، شماره تلفن خودت رو با دکمه زیر به اشتراک بذار:",
                reply_markup=keyboard
            )
            user_states[str(user.id)] = "AUTH"
            logging.info(f"کاربر {user.id} در حالت احراز هویت.")
    except Exception as e:
        logging.error(f"خطا در دستور /start: {e}")
        bot.send_message(message.chat.id, "خطایی رخ داد. لطفاً دوباره امتحان کنید.")

# مدیریت شماره تلفن
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user = message.from_user
    contact = message.contact
    try:
        if contact.user_id != user.id:
            bot.send_message(message.chat.id, "لطفاً شماره تلفن خودت رو به اشتراک بذار!")
            logging.warning(f"کاربر {user.id} شماره تلفن غیرخود را ارسال کرد.")
            return

        phone_number = contact.phone_number
        conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, phone_number, join_date, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user.id, user.username, user.first_name, user.last_name, phone_number, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1)
        )
        conn.commit()
        conn.close()

        bot.send_message(
            GROUP_CHAT_ID,
            f"کاربر جدید:\nID: {user.id}\nUsername: @{user.username or 'نامشخص'}\nنام: {user.first_name} {user.last_name or ''}\nشماره: {phone_number}\nتاریخ عضویت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bot.send_message(
            message.chat.id,
            "✅ احراز هویت با موفقیت انجام شد! به جمع ما خوش اومدی! 😊",
            reply_markup=get_main_menu(user.id)
        )
        user_states[str(user.id)] = "MAIN_MENU"
        logging.info(f"کاربر {user.id} با موفقیت احراز هویت شد.")
    except Exception as e:
        logging.error(f"خطا در مدیریت شماره تلفن: {e}")
        bot.send_message(message.chat.id, "خطایی رخ داد. لطفاً دوباره امتحان کنید.")

# منوی اصلی
@bot.message_handler(content_types=['text'])
def main_menu(message):
    user = message.from_user
    text = message.text
    state = user_states.get(str(user.id), "MAIN_MENU")

    try:
        if state == "AUTH":
            return

        if text == "📤 آپلود فایل":
            bot.send_message(message.chat.id, "لطفاً عنوان درس رو وارد کن (مثال: هوش مصنوعی):", reply_markup=types.ReplyKeyboardRemove())
            user_states[str(user.id)] = "UPLOAD_TITLE"
            logging.info(f"کاربر {user.id} وارد مرحله آپلود فایل شد.")
            return

        elif text == "📚 منابع آموزشی":
            conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
            c = conn.cursor()
            c.execute("SELECT id, title, professor, file_id FROM resources WHERE is_approved = 1")
            resources = c.fetchall()
            conn.close()

            if not resources:
                bot.send_message(message.chat.id, "هنوز منبعی آپلود نشده! 😕", reply_markup=get_main_menu(user.id))
                logging.info(f"کاربر {user.id} لیست منابع را مشاهده کرد - خالی بود.")
                return

            keyboard = types.InlineKeyboardMarkup()
            for res in resources:
                keyboard.add(types.InlineKeyboardButton(f"{res[1]} ({res[2]})", callback_data=f"resource_{res[0]}"))
            keyboard.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main"))
            bot.send_message(
                message.chat.id,
                "📚 منابع آموزشی موجود:\nانتخاب کن تا فایل برات ارسال بشه:",
                reply_markup=keyboard
            )
            logging.info(f"کاربر {user.id} لیست منابع را مشاهده کرد.")
            return

        elif text == "📩 درخواست‌ها":
            bot.send_message(message.chat.id, "لطفاً درخواست خودت رو بنویس (مثال: پروژه درس پایگاه داده با پایتون):", reply_markup=types.ReplyKeyboardRemove())
            user_states[str(user.id)] = "REQUEST"
            logging.info(f"کاربر {user.id} وارد مرحله درخواست شد.")
            return

        elif text == "ℹ️ راهنما":
            help_text = (
                "🤖 راهنمای ربات PcBND:\n\n"
                "📤 آپلود فایل: جزوه یا پروژه خودت رو با اسم درس و استاد آپلود کن.\n"
                "📚 منابع آموزشی: جزوه‌ها و پروژه‌های آپلودشده رو ببین و دانلود کن.\n"
                "📩 درخواست‌ها: درخواست پروژه یا کمک به ادمین بفرست.\n"
                "ℹ️ راهنما: اطلاعات ربات و لینک‌های مهم.\n\n"
                "لینک‌های ما:"
            )
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("📢 کانال", url="https://t.me/PcBND"))
            keyboard.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main"))
            bot.send_message(message.chat.id, help_text, reply_markup=keyboard)
            logging.info(f"کاربر {user.id} راهنما را مشاهده کرد.")
            return

        elif text == "🛠 پنل ادمین" and user.id == ADMIN_ID:
            bot.send_message(message.chat.id, "🛠 پنل مدیریت: گزینه مورد نظر رو انتخاب کن", reply_markup=get_admin_menu())
            user_states[str(user.id)] = "ADMIN_PANEL"
            logging.info(f"ادمین {user.id} وارد پنل مدیریت شد.")
            return

        elif text == "🔙 بازگشت به منوی اصلی":
            bot.send_message(message.chat.id, "بازگشت به منوی اصلی", reply_markup=get_main_menu(user.id))
            user_states[str(user.id)] = "MAIN_MENU"
            logging.info(f"کاربر {user.id} به منوی اصلی بازگشت.")
            return

        # مدیریت آپلود فایل
        if state == "UPLOAD_TITLE":
            user_states[f"{user.id}_title"] = text
            bot.send_message(message.chat.id, "لطفاً نام استاد رو وارد کن (مثال: دکتر احمدی):")
            user_states[str(user.id)] = "UPLOAD_PROFESSOR"
            logging.info(f"کاربر {user.id} عنوان درس را وارد کرد: {text}")
            return

        elif state == "UPLOAD_PROFESSOR":
            user_states[f"{user.id}_professor"] = text
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
            bot.send_message(message.chat.id, "حالا فایل PDF رو آپلود کن:", reply_markup=keyboard)
            user_states[str(user.id)] = "UPLOAD_FILE"
            logging.info(f"کاربر {user.id} نام استاد را وارد کرد: {text}")
            return

        elif state == "REQUEST":
            bot.send_message(GROUP_CHAT_ID, f"درخواست جدید:\nاز: @{user.username or 'نامشخص'}\nدرخواست: {text}")
            bot.send_message(message.chat.id, "درخواستت برای ادمین ارسال شد! ✅", reply_markup=get_main_menu(user.id))
            user_states[str(user.id)] = "MAIN_MENU"
            logging.info(f"کاربر {user.id} درخواست ارسال کرد: {text}")
            return

        # مدیریت پنل ادمین
        elif state == "ADMIN_PANEL":
            if text == "🔙 بازگشت به منوی اصلی":
                bot.send_message(message.chat.id, "بازگشت به منوی اصلی", reply_markup=get_main_menu(user.id))
                user_states[str(user.id)] = "MAIN_MENU"
                logging.info(f"ادمین {user.id} به منوی اصلی بازگشت.")
                return

            elif text == "📊 آمار ربات":
                try:
                    conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM users")
                    user_count = c.fetchone()[0]
                    c.execute("SELECT COUNT(*) FROM resources WHERE is_approved = 1")
                    resource_count = c.fetchone()[0]
                    conn.close()
                    bot.send_message(
                        message.chat.id,
                        f"📊 آمار ربات:\nتعداد کاربران: {user_count}\nتعداد جزوه‌ها: {resource_count}",
                        reply_markup=get_admin_menu()
                    )
                    logging.info(f"ادمین {user.id} آمار ربات را مشاهده کرد.")
                except Exception as e:
                    logging.error(f"خطا در دریافت آمار ربات: {e}")
                    bot.send_message(message.chat.id, "خطا در دریافت آمار. لطفاً دوباره امتحان کنید.", reply_markup=get_admin_menu())
                user_states[str(user.id)] = "ADMIN_PANEL"
                return

            elif text == "📢 پیام همگانی":
                bot.send_message(message.chat.id, "لطفاً متن پیام همگانی رو وارد کن:", reply_markup=types.ReplyKeyboardRemove())
                user_states[str(user.id)] = "ADMIN_MESSAGE"
                logging.info(f"ادمین {user.id} وارد مرحله ارسال پیام همگانی شد.")
                return

            elif text == "🔄 فوروارد پیام":
                bot.send_message(message.chat.id, "لطفاً پیام مورد نظر رو فوروارد کن:", reply_markup=types.ReplyKeyboardRemove())
                user_states[str(user.id)] = "ADMIN_FORWARD"
                logging.info(f"ادمین {user.id} وارد مرحله فوروارد پیام شد.")
                return

            elif text == "📚 آپلود منابع آموزشی":
                bot.send_message(message.chat.id, "لطفاً عنوان درس رو وارد کن (مثال: هوش مصنوعی):", reply_markup=types.ReplyKeyboardRemove())
                user_states[str(user.id)] = "ADMIN_UPLOAD_TITLE"
                logging.info(f"ادمین {user.id} وارد مرحله آپلود منابع شد.")
                return

            elif text == "💬 پیام شخصی به کاربر":
                bot.send_message(message.chat.id, "لطفاً ID عددی کاربر رو وارد کن:", reply_markup=types.ReplyKeyboardRemove())
                user_states[str(user.id)] = "ADMIN_PERSONAL_MESSAGE"
                logging.info(f"ادمین {user.id} وارد مرحله ارسال پیام شخصی شد.")
                return

            elif text == "👤 نمایش اطلاعات کاربران":
                bot.send_message(message.chat.id, "لطفاً ID عددی کاربر رو وارد کن:", reply_markup=types.ReplyKeyboardRemove())
                user_states[str(user.id)] = "ADMIN_USER_INFO"
                logging.info(f"ادمین {user.id} وارد مرحله نمایش اطلاعات کاربران شد.")
                return

            elif text == "✅ تأیید منابع":
                try:
                    conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
                    c = conn.cursor()
                    c.execute("SELECT id, title, professor, uploaded_by FROM resources WHERE is_approved = 0")
                    resources = c.fetchall()
                    conn.close()

                    if not resources:
                        bot.send_message(message.chat.id, "هیچ منبعی برای تأیید وجود ندارد!", reply_markup=get_admin_menu())
                        user_states[str(user.id)] = "ADMIN_PANEL"
                        logging.info(f"ادمین {user.id} لیست منابع خالی را مشاهده کرد.")
                        return

                    response = "منابع در انتظار تأیید:\n"
                    for res in resources:
                        response += f"ID: {res[0]} - درس: {res[1]} - استاد: {res[2]} - آپلود توسط: {res[3]}\n"
                    response += "\nلطفاً ID منبع مورد نظر برای تأیید را وارد کنید:"
                    bot.send_message(message.chat.id, response, reply_markup=types.ReplyKeyboardRemove())
                    user_states[str(user.id)] = "APPROVE_RESOURCE"
                    logging.info(f"ادمین {user.id} لیست منابع در انتظار تأیید را مشاهده کرد.")
                except Exception as e:
                    logging.error(f"خطا در دریافت منابع برای تأیید: {e}")
                    bot.send_message(message.chat.id, "خطا در دریافت منابع. لطفاً دوباره امتحان کنید.", reply_markup=get_admin_menu())
                return

        # مدیریت حالت‌های ادمین
        elif state == "ADMIN_MESSAGE":
            try:
                conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
                c = conn.cursor()
                c.execute("SELECT user_id FROM users")
                users = c.fetchall()
                conn.close()

                for user_id in users:
                    try:
                        if user_id[0] is not None:
                            bot.send_message(user_id[0], text)
                    except Exception as e:
                        logging.error(f"خطا در ارسال پیام همگانی به کاربر {user_id[0]}: {e}")
                        continue

                bot.send_message(GROUP_CHAT_ID, f"پیام همگانی از ادمین @{user.username or 'نامشخص'}:\n{text}")
                bot.send_message(message.chat.id, "پیام همگانی با موفقیت ارسال شد! ✅", reply_markup=get_admin_menu())
                user_states[str(user.id)] = "ADMIN_PANEL"
                logging.info(f"ادمین {user.id} پیام همگانی ارسال کرد: {text}")
            except Exception as e:
                logging.error(f"خطا در ارسال پیام همگانی: {e}")
                bot.send_message(message.chat.id, "خطا در ارسال پیام همگانی. لطفاً دوباره امتحان کنید.", reply_markup=get_admin_menu())
            return

        elif state == "ADMIN_UPLOAD_TITLE":
            user_states[f"{user.id}_admin_title"] = text
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
            bot.send_message(message.chat.id, "حالا فایل PDF رو آپلود کن:", reply_markup=keyboard)
            user_states[str(user.id)] = "ADMIN_UPLOAD_FILE"
            logging.info(f"ادمین {user.id} عنوان درس را وارد کرد: {text}")
            return

        elif state == "ADMIN_PERSONAL_MESSAGE":
            try:
                user_id = int(text)
                conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
                c = conn.cursor()
                c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if not c.fetchone():
                    conn.close()
                    bot.send_message(message.chat.id, "کاربر یافت نشد!", reply_markup=get_admin_menu())
                    user_states[str(user.id)] = "ADMIN_PANEL"
                    logging.warning(f"ادمین {user.id} ID کاربر نامعتبر وارد کرد: {text}")
                    return
                conn.close()
                user_states[f"{user.id}_personal_user_id"] = user_id
                bot.send_message(message.chat.id, "لطفاً متن پیام رو وارد کن:")
                user_states[str(user.id)] = "SEND_PERSONAL_MESSAGE"
                logging.info(f"ادمین {user.id} ID کاربر را وارد کرد: {user_id}")
            except ValueError:
                bot.send_message(message.chat.id, "لطفاً یک ID عددی معتبر وارد کن!")
                logging.warning(f"ادمین {user.id} ID نامعتبر وارد کرد: {text}")
            return

        elif state == "SEND_PERSONAL_MESSAGE":
            user_id = user_states.get(f"{user.id}_personal_user_id")
            if user_id is not None:
                try:
                    bot.send_message(user_id, text)
                    bot.send_message(GROUP_CHAT_ID, f"ادمین @{user.username or 'نامشخص'} پیام شخصی به کاربر {user_id} ارسال کرد:\n{text}")
                    bot.send_message(message.chat.id, "پیام با موفقیت ارسال شد! ✅", reply_markup=get_admin_menu())
                    logging.info(f"ادمین {user.id} پیام شخصی به کاربر {user_id} ارسال کرد: {text}")
                except Exception as e:
                    bot.send_message(message.chat.id, "خطا در ارسال پیام!", reply_markup=get_admin_menu())
                    logging.error(f"خطا در ارسال پیام شخصی به کاربر {user_id}: {e}")
            else:
                bot.send_message(message.chat.id, "خطا: شناسه کاربر معتبر نیست!", reply_markup=get_admin_menu())
                logging.error(f"ادمین {user.id} شناسه کاربر نامعتبر برای پیام شخصی.")
            user_states[str(user.id)] = "ADMIN_PANEL"
            user_states.pop(f"{user.id}_personal_user_id", None)
            return

        elif state == "ADMIN_USER_INFO":
            try:
                user_id = int(text)
                conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
                c = conn.cursor()
                c.execute("SELECT user_id, username, first_name, last_name, phone_number, join_date FROM users WHERE user_id = ?", (user_id,))
                user_info = c.fetchone()
                conn.close()

                if user_info:
                    info_text = (
                        f"👤 اطلاعات کاربر:\n"
                        f"ID: {user_info[0]}\n"
                        f"Username: @{user_info[1] or 'نامشخص'}\n"
                        f"نام: {user_info[2] or 'نامشخص'}\n"
                        f"نام خانوادگی: {user_info[3] or 'نامشخص'}\n"
                        f"شماره تلفن: {user_info[4]}\n"
                        f"تاریخ عضویت: {user_info[5]}"
                    )
                    bot.send_message(message.chat.id, info_text, reply_markup=get_admin_menu())
                    logging.info(f"ادمین {user.id} اطلاعات کاربر {user_id} را مشاهده کرد.")
                else:
                    bot.send_message(message.chat.id, "کاربر یافت نشد!", reply_markup=get_admin_menu())
                    logging.warning(f"ادمین {user.id} کاربر با ID {user_id} را پیدا نکرد.")
                user_states[str(user.id)] = "ADMIN_PANEL"
                return
            except ValueError:
                bot.send_message(message.chat.id, "لطفاً یک ID عددی معتبر وارد کن!")
                logging.warning(f"ادمین {user.id} ID نامعتبر برای اطلاعات کاربر وارد کرد: {text}")
                return

        elif state == "APPROVE_RESOURCE":
            try:
                resource_id = int(text)
                conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
                c = conn.cursor()
                c.execute("SELECT id, title, professor, file_id, uploaded_by FROM resources WHERE id = ? AND is_approved = 0", (resource_id,))
                resource = c.fetchone()
                if resource:
                    c.execute("UPDATE resources SET is_approved = 1 WHERE id = ?", (resource_id,))
                    conn.commit()
                    caption = (
                        f"جزوه جدید:\n"
                        f"درس: {resource[1]}\n"
                        f"استاد: {resource[2]}\n"
                        f"آپلود توسط: @{user.username or 'نامشخص'}"
                    )
                    bot.send_document(GROUP_CHAT_ID, resource[3], caption=caption)
                    bot.send_message(message.chat.id, f"منبع با ID {resource_id} تأیید شد! ✅", reply_markup=get_admin_menu())
                    bot.send_message(resource[4], "فایل شما توسط ادمین تأیید شد و در گروه منتشر شد! ✅")
                    logging.info(f"ادمین {user.id} منبع با ID {resource_id} را تأیید کرد.")
                else:
                    bot.send_message(message.chat.id, "منبع یافت نشد یا قبلاً تأیید شده!", reply_markup=get_admin_menu())
                    logging.warning(f"ادمین {user.id} منبع با ID {resource_id} را پیدا نکرد.")
                conn.close()
                user_states[str(user.id)] = "ADMIN_PANEL"
                return
            except ValueError:
                bot.send_message(message.chat.id, "لطفاً یک ID عددی معتبر وارد کن!")
                logging.warning(f"ادمین {user.id} ID نامعتبر برای تأیید منبع وارد کرد: {text}")
                return

    except Exception as e:
        logging.error(f"خطا در مدیریت منوی اصلی: {e}")
        bot.send_message(message.chat.id, "خطایی رخ داد. لطفاً دوباره امتحان کنید.", reply_markup=get_main_menu(user.id))
        user_states[str(user.id)] = "MAIN_MENU"

# مدیریت فایل‌ها
@bot.message_handler(content_types=['document'])
def handle_files(message):
    user = message.from_user
    state = user_states.get(str(user.id))

    try:
        if state == "UPLOAD_FILE":
            if message.text == "🔙 بازگشت به منوی اصلی":
                user_states[str(user.id)] = "MAIN_MENU"
                user_states.pop(f"{user.id}_title", None)
                user_states.pop(f"{user.id}_professor", None)
                bot.send_message(message.chat.id, "بازگشت به منوی اصلی", reply_markup=get_main_menu(user.id))
                logging.info(f"کاربر {user.id} از آپلود فایل به منوی اصلی بازگشت.")
                return

            document = message.document
            if not document or document.mime_type != "application/pdf":
                bot.send_message(message.chat.id, "لطفاً فقط فایل PDF آپلود کن!")
                logging.warning(f"کاربر {user.id} فایل غیر PDF آپلود کرد.")
                return

            conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
            c = conn.cursor()
            c.execute(
                "INSERT INTO resources (title, professor, file_id, uploaded_by, upload_date, is_approved) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user_states.get(f"{user.id}_title", "بدون عنوان"),
                    user_states.get(f"{user.id}_professor", "نامشخص"),
                    document.file_id,
                    user.id,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    0
                ),
            )
            resource_id = c.lastrowid
            conn.commit()
            conn.close()

            caption = (
                f"درخواست تأیید جزوه جدید:\n"
                f"ID: {resource_id}\n"
                f"درس: {user_states.get(f'{user.id}_title')}\n"
                f"استاد: {user_states.get(f'{user.id}_professor')}\n"
                f"آپلود توسط: @{user.username or 'نامشخص'}"
            )
            bot.send_document(GROUP_CHAT_ID, document.file_id, caption=caption)

            bot.send_message(message.chat.id, "فایل شما برای تأیید به گروه ارسال شد! ✅", reply_markup=get_main_menu(user.id))
            user_states[str(user.id)] = "MAIN_MENU"
            user_states.pop(f"{user.id}_title", None)
            user_states.pop(f"{user.id}_professor", None)
            logging.info(f"کاربر {user.id} فایل منبع با ID {resource_id} آپلود کرد.")
            return

        elif state == "ADMIN_UPLOAD_FILE":
            if message.text == "🔙 بازگشت به منوی اصلی":
                user_states[str(user.id)] = "ADMIN_PANEL"
                user_states.pop(f"{user.id}_admin_title", None)
                bot.send_message(message.chat.id, "بازگشت به منوی اصلی", reply_markup=get_admin_menu())
                logging.info(f"ادمین {user.id} از آپلود منبع به پنل ادمین بازگشت.")
                return

            document = message.document
            if not document or document.mime_type != "application/pdf":
                bot.send_message(message.chat.id, "لطفاً فقط فایل PDF آپلود کن!")
                logging.warning(f"ادمین {user.id} فایل غیر PDF آپلود کرد.")
                return

            conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
            c = conn.cursor()
            c.execute(
                "INSERT INTO resources (title, professor, file_id, uploaded_by, upload_date, is_approved) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user_states.get(f"{user.id}_admin_title", "بدون عنوان"),
                    "ادمین",
                    document.file_id,
                    user.id,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    1
                ),
            )
            conn.commit()
            conn.close()

            caption = f"جزوه جدید (ادمین):\nدرس: {user_states.get(f'{user.id}_admin_title')}\nآپلود توسط: @{user.username or 'نامشخص'}"
            bot.send_document(GROUP_CHAT_ID, document.file_id, caption=caption)

            bot.send_message(message.chat.id, "فایل با موفقیت آپلود شد! ✅", reply_markup=get_admin_menu())
            user_states[str(user.id)] = "ADMIN_PANEL"
            user_states.pop(f"{user.id}_admin_title", None)
            logging.info(f"ادمین {user.id} منبع جدید آپلود کرد.")
            return

    except Exception as e:
        logging.error(f"خطا در مدیریت فایل‌ها: {e}")
        bot.send_message(message.chat.id, "خطایی رخ داد. لطفاً دوباره امتحان کنید.", reply_markup=get_main_menu(user.id))
        user_states[str(user.id)] = "MAIN_MENU"

# مدیریت دکمه‌های شیشه‌ای
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user = call.from_user
    try:
        if call.data == "back_to_main":
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            bot.send_message(call.message.chat.id, "بازگشت به منوی اصلی", reply_markup=get_main_menu(user.id))
            user_states[str(user.id)] = "MAIN_MENU"
            logging.info(f"کاربر {user.id} به منوی اصلی بازگشت (از callback).")
            return

        if call.data.startswith("resource_"):
            resource_id = int(call.data.split("_")[1])
            conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
            c = conn.cursor()
            c.execute("SELECT file_id, title, professor FROM resources WHERE id = ? AND is_approved = 1", (resource_id,))
            resource = c.fetchone()
            conn.close()

            if resource:
                message = bot.send_document(
                    call.message.chat.id,
                    document=resource[0],
                    caption=f"درس: {resource[1]}\nاستاد: {resource[2]}",
                    reply_markup=get_main_menu(user.id)
                )
                threading.Thread(target=delete_message_after_delay, args=(call.message.chat.id, message.message_id)).start()
                logging.info(f"کاربر {user.id} منبع با ID {resource_id} را دانلود کرد.")
            else:
                bot.send_message(call.message.chat.id, "خطا! فایل یافت نشد یا هنوز تأیید نشده.", reply_markup=get_main_menu(user.id))
                logging.warning(f"کاربر {user.id} منبع با ID {resource_id} را پیدا نکرد.")
            user_states[str(user.id)] = "MAIN_MENU"
            return

    except Exception as e:
        logging.error(f"خطا در مدیریت callback: {e}")
        bot.send_message(call.message.chat.id, "خطایی رخ داد. لطفاً دوباره امتحان کنید.", reply_markup=get_main_menu(user.id))

# فوروارد پیام
@bot.message_handler(content_types=['text', 'photo', 'document', 'video', 'audio'], func=lambda message: user_states.get(str(message.from_user.id)) == "ADMIN_FORWARD")
def admin_forward(message):
    user = message.from_user
    try:
        conn = sqlite3.connect("pc_bnd_bot.db", check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()

        success_count = 0
        for user_id in users:
            try:
                if user_id[0] is not None:
                    bot.forward_message(user_id[0], message.chat.id, message.message_id)
                    success_count += 1
            except Exception as e:
                logging.warning(f"خطا در فوروارد پیام به کاربر {user_id[0]}: {e}")
                continue

        bot.send_message(GROUP_CHAT_ID, f"ادمین @{user.username or 'نامشخص'} یک پیام فوروارد کرد به {success_count} کاربر.")
        bot.send_message(message.chat.id, f"پیام با موفقیت به {success_count} کاربر فوروارد شد! ✅", reply_markup=get_admin_menu())
        user_states[str(user.id)] = "ADMIN_PANEL"
        logging.info(f"ادمین {user.id} پیام را به {success_count} کاربر فوروارد کرد.")
    except Exception as e:
        logging.error(f"خطا در فوروارد پیام: {e}")
        bot.send_message(message.chat.id, "خطا در فوروارد پیام. لطفاً دوباره امتحان کنید.", reply_markup=get_admin_menu())
        user_states[str(user.id)] = "ADMIN_PANEL"

# شروع ربات
if __name__ == "__main__":
    init_db()
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"خطا در polling ربات: {e}")
        time.sleep(5)  # در صورت خطا، 5 ثانیه صبر کن و دوباره تلاش کن
        bot.polling(none_stop=True)
