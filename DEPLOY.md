# 🚀 نشر بوت الدراسة على Render (مجاني، بلا بطاقة)

البوت يعمل بنظام **polling**، ويستخدم **Docker** لأنه يحتاج مكتبات نظام (WeasyPrint للـ PDF، poppler للصور، خطوط عربية).
أُضيف خادم صحة صغير ليبقى مستيقظاً على الخطة المجانية.

---

## 1) ارفع الكود إلى GitHub
المستودع جاهز: `https://github.com/firadmuhammed827-ux/hhhhhhbot`

```powershell
cd C:\Users\STRIX\Desktop\hhhhhhbot
git init
git add .
git commit -m "study bot - render deploy"
git branch -M main
git remote add origin https://github.com/firadmuhammed827-ux/hhhhhhbot.git
git push -u origin main
```
> ملف `.env` **لن يُرفع** (محمي بـ `.gitignore`). التوكن لم يعد داخل الكود.

## 2) أنشئ الخدمة على Render
- ادخل **render.com** → Sign up **with GitHub** (بلا بطاقة).
- **New → Blueprint** → اختر مستودع `hhhhhhbot` → يقرأ `render.yaml` تلقائياً → **Apply**.
- أول بناء بـ Docker يأخذ **5–10 دقائق** (يثبّت المكتبات والخطوط). الإعادات اللاحقة أسرع.

## 3) ضع الأسرار (Environment) — كلها مطلوبة
عند Apply سيطلب منك Render هذه القيم (لأنها `sync: false`):

| Key | القيمة |
|---|---|
| `TOKEN` | توكن البوت من BotFather |
| `OPENAI_API_KEY` | مفتاح بوابة الذكاء الاصطناعي |
| `OPENAI_BASE_URL` | عنوان البوابة التي تخدم `gemini-2.5-flash` و`gpt-4.1-nano` |

> ⚠️ **مهم:** البوت يستخدم نماذج `gemini-2.5-flash` و`gpt-4.1-nano` عبر SDK الخاص بـ OpenAI،
> وهي **ليست** نماذج OpenAI الرسمية. لذلك **يجب** ضبط `OPENAI_BASE_URL` على البوابة التي كنت تستخدمها محلياً.
> إن تركته فارغاً سيحاول البوت الاتصال بـ OpenAI الرسمي وستفشل كل ميزات الذكاء.

## 4) انشر → تحقق
- بعد البناء، افتح رابط الخدمة (مثل `https://study-bot.onrender.com`) → يجب أن ترى **"Study bot is alive"**.
- في **Logs** يجب أن تجد: `Bot started successfully! Waiting for messages...`

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

## ملاحظات
- **التخزين مؤقّت:** ملفات الـ PDF/الصوت تُنشأ مؤقتاً في `downloads/` وتُمسح بعد الإرسال — لا حاجة لتخزين دائم.
- **تحديث الكود لاحقاً:** عدّل الملفات ثم:
  ```powershell
  git add . ; git commit -m "update" ; git push
  ```
  Render ينشر تلقائياً (`autoDeploy: true`).
