"""
بوت تيليجرام لتقسيم الصورة إلى 3 أو 6 أجزاء (ستوريات)
"""

import logging
import os
import threading
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer
from PIL import Image
import asyncio
from telegram import Update, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# التوكن من متغيّر البيئة (يُضبط في Render → Environment)
BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
if not BOT_TOKEN:
    raise SystemExit(
        "Missing BOT_TOKEN environment variable — set BOT_TOKEN in Render → Environment"
    )


def _start_health_server():
    """خادم HTTP بسيط ليبقى الخدمة حيّة على Render ويسمح لـ UptimeRobot بالـ ping."""
    port = int(os.environ.get("PORT", "10000"))

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Story splitter bot is alive")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    HTTPServer(("0.0.0.0", port), _Handler).serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ارسل الصورة الان")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ارسل الصورة الان")


def split_image_3(image: Image.Image) -> list:
    """تقسيم الصورة إلى 3 أجزاء عمودية بنسبة 9:16"""
    original_width, original_height = image.size

    part_width = original_width // 3
    target_height = int(part_width * (16 / 9))

    if target_height > original_height:
        target_height = original_height
        part_width = int(target_height * (9 / 16))
        total_width = part_width * 3

        if total_width > original_width:
            total_width = original_width
            part_width = original_width // 3
            target_height = int(part_width * (16 / 9))
    else:
        total_width = original_width

    x_start = (original_width - total_width) // 2
    y_start = (original_height - target_height) // 2

    cropped = image.crop((x_start, y_start, x_start + total_width, y_start + target_height))

    parts = []
    for i in range(3):
        left = i * part_width
        right = left + part_width
        part = cropped.crop((left, 0, right, target_height))
        part_resized = part.resize((1080, 1920), Image.LANCZOS)
        parts.append(part_resized)

    return parts


def split_image_6(image: Image.Image) -> tuple:
    """
    تقسيم الصورة إلى 6 أجزاء (صفين × 3 أعمدة)
    يقسم الصورة بالضبط 3 أعمدة ونصين - بدون أي فجوة
    يضيف حواف فوق وتحت حتى لا يقص الستوري المحتوى
    """
    original_width, original_height = image.size

    # نقسم الصورة بالضبط: 3 أعمدة و صفين
    part_width = original_width // 3
    part_height = original_height // 2

    # حجم الستوري النهائي 1080x1920
    story_width = 1080
    story_height = 1920

    # 15% حافة فوق و 15% حافة تحت - الصورة بالوسط
    padding_top = int(story_height * 0.15)
    padding_bottom = int(story_height * 0.15)
    available_height = story_height - padding_top - padding_bottom

    # الصورة تملأ كامل المساحة المتاحة
    scaled_height = available_height
    scaled_width = story_width

    # الصف العلوي - من 0 إلى نص الارتفاع
    top_parts = []
    for i in range(3):
        left = i * part_width
        upper = 0
        right = left + part_width
        lower = part_height
        part = image.crop((left, upper, right, lower))
        part_resized = part.resize((scaled_width, scaled_height), Image.LANCZOS)
        bg_color = get_edge_color(part_resized)
        story_img = Image.new('RGB', (story_width, story_height), bg_color)
        story_img.paste(part_resized, (0, padding_top))
        top_parts.append(story_img)

    # الصف السفلي - مباشرة من نص الارتفاع إلى النهاية
    bottom_parts = []
    for i in range(3):
        left = i * part_width
        upper = part_height
        right = left + part_width
        lower = part_height * 2
        part = image.crop((left, upper, right, lower))
        part_resized = part.resize((scaled_width, scaled_height), Image.LANCZOS)
        bg_color = get_edge_color(part_resized)
        story_img = Image.new('RGB', (story_width, story_height), bg_color)
        story_img.paste(part_resized, (0, padding_top))
        bottom_parts.append(story_img)

    return top_parts, bottom_parts


def get_edge_color(image: Image.Image) -> tuple:
    """يأخذ اللون السائد من أطراف الصورة للحواف"""
    # نأخذ عينة من البكسلات على الأطراف
    width, height = image.size
    pixels = []
    for x in range(0, width, max(1, width // 10)):
        pixels.append(image.getpixel((x, 0)))
        pixels.append(image.getpixel((x, height - 1)))
    # نحسب المتوسط
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return (r, g, b)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ الصورة وعرض خيارات التقسيم"""
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    photo_bytes = BytesIO()
    await file.download_to_memory(photo_bytes)
    photo_bytes.seek(0)

    # حفظ الصورة في بيانات المستخدم
    context.user_data['image'] = photo_bytes.getvalue()

    keyboard = [
        [
            InlineKeyboardButton("3", callback_data="split_3"),
            InlineKeyboardButton("6", callback_data="split_6"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر عدد الاقسام", reply_markup=reply_markup)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور المرسلة كملفات"""
    document = update.message.document

    if document.mime_type and document.mime_type.startswith('image/'):
        file = await context.bot.get_file(document.file_id)

        photo_bytes = BytesIO()
        await file.download_to_memory(photo_bytes)
        photo_bytes.seek(0)

        context.user_data['image'] = photo_bytes.getvalue()

        keyboard = [
            [
                InlineKeyboardButton("3", callback_data="split_3"),
                InlineKeyboardButton("6", callback_data="split_6"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("اختر عدد الاقسام", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المستخدم"""
    query = update.callback_query
    await query.answer()

    if 'image' not in context.user_data:
        await query.edit_message_text("ارسل الصورة الان")
        return

    image_data = context.user_data['image']
    image = Image.open(BytesIO(image_data))

    if image.mode != 'RGB':
        image = image.convert('RGB')

    if query.data == "split_3":
        await query.edit_message_text("جاري تقسيم الصورة...")

        parts = split_image_3(image)

        media_group = []
        for i, part in enumerate(parts):
            bio = BytesIO()
            part.save(bio, format='JPEG', quality=95)
            bio.seek(0)
            bio.name = f'story_part_{i+1}.jpg'
            media_group.append(InputMediaPhoto(media=bio))

        await query.message.reply_media_group(media=media_group)

    elif query.data == "split_6":
        await query.edit_message_text("جاري تقسيم الصورة...")

        top_parts, bottom_parts = split_image_6(image)

        # تجهيز كل الصور أولا
        media_group_top = []
        for i, part in enumerate(top_parts):
            bio = BytesIO()
            part.save(bio, format='JPEG', quality=80)
            bio.seek(0)
            bio.name = f'top_{i+1}.jpg'
            media_group_top.append(InputMediaPhoto(media=bio))

        media_group_bottom = []
        for i, part in enumerate(bottom_parts):
            bio = BytesIO()
            part.save(bio, format='JPEG', quality=80)
            bio.seek(0)
            bio.name = f'bottom_{i+1}.jpg'
            media_group_bottom.append(InputMediaPhoto(media=bio))

        # إرسال الفوق
        await query.message.reply_media_group(media=media_group_top)
        await asyncio.sleep(2)
        # إرسال التحت
        await query.message.reply_media_group(media=media_group_bottom)


def main():
    # خادم الصحة في خيط منفصل (مطلوب لخدمة Render المجانية + UptimeRobot)
    threading.Thread(target=_start_health_server, daemon=True).start()

    request = HTTPXRequest(connect_timeout=60, read_timeout=120, write_timeout=120, pool_timeout=60)
    application = Application.builder().token(BOT_TOKEN).request(request).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("البوت يعمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
