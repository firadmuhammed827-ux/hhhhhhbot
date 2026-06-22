# 🚀 نشر بوت تقسيم الصور (Story Splitter) على Render (مجاني، بلا بطاقة)

البوت يقسّم الصورة إلى 3 أو 6 أجزاء (ستوريات). يعمل بنظام **polling** على Python عادي،
ويحتاج فقط `python-telegram-bot` و`Pillow`. أُضيف خادم صحة صغير ليبقى مستيقظاً على الخطة المجانية.

---

## 1) ارفع الكود إلى GitHub
المستودع: `https://github.com/firadmuhammed827-ux/hhhhhhbot`

```powershell
cd C:\Users\STRIX\Desktop\hhhhhhbot
git add .
git commit -m "update"
git push
```
> ملف `.env` **لن يُرفع** (محمي بـ `.gitignore`). التوكن لم يعد داخل الكود.

## 2) أنشئ الخدمة على Render
- ادخل **render.com** → Sign up **with GitHub** (بلا بطاقة).
- **New → Blueprint** → اختر مستودع `hhhhhhbot` → يقرأ `render.yaml` تلقائياً → **Apply**.
  - (أو يدوياً: New → Web Service → اختر المستودع → Runtime: **Python**،
    Build: `pip install -r requirements.txt`، Start: `python bot.py`، Plan: **Free**.)

## 3) ضع السر (Environment)
عند Apply سيطلب Render قيمة `BOT_TOKEN` (لأنها `sync: false`):

| Key | القيمة |
|---|---|
| `BOT_TOKEN` | توكن البوت من BotFather |

(`PYTHON_VERSION` موجود في `render.yaml` تلقائياً.)

## 4) انشر → تحقق
- بعد البناء، افتح رابط الخدمة (مثل `https://story-splitter-bot.onrender.com`) → يجب أن ترى **"Story splitter bot is alive"**.
- في **Logs** يجب أن تجد: `البوت يعمل...`

## 5) ⏰ اجعله لا ينام (UptimeRobot)
Render المجاني ينام بعد ~15 دقيقة خمول. لإبقائه 24/7:
- ادخل **uptimerobot.com** (مجاني) → **Add New Monitor**:
  - **Type:** HTTP(s)
  - **URL:** رابط خدمتك على Render
  - **Interval:** 5 دقائق
- احفظ. (بديل: cron-job.org)

## 6) أوقف النسخة المحلية
لا تُشغّل البوت على جهازك بنفس التوكن بعد النشر (تفادي خطأ 409 Conflict).

---

## تحديث الكود لاحقاً
عدّل الملفات ثم:
```powershell
git add . ; git commit -m "update" ; git push
```
Render ينشر تلقائياً (`autoDeploy: true`).
