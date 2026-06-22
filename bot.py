#!/usr/bin/env python3
# Combined Telegram Study Bot - Single File Version

from PIL import Image
from gtts import gTTS
from openai import OpenAI
from pdf2image import convert_from_path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, TimedOut, RetryAfter
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.request import HTTPXRequest
from weasyprint import HTML
import PyPDF2
import asyncio
import base64
import json
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
معالجات الملفات والذكاء الاصطناعي - النسخة المطورة بالكامل
يستخدم WeasyPrint لإنشاء PDF مع دعم كامل للعربية والمعادلات الرياضية
"""


# تهيئة عميل OpenAI
# يقرأ المفتاح من OPENAI_API_KEY و(إن وُجد) العنوان من OPENAI_BASE_URL تلقائياً
client = OpenAI()


# مجلد التحميلات المؤقتة (قابل للتهيئة عبر متغيّر بيئة، يعمل على Render)
DOWNLOAD_DIR = os.environ.get(
    "DOWNLOAD_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads"),
)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _start_health_server():
    """خادم HTTP بسيط ليبقى الخدمة حيّة على Render ويسمح لـ UptimeRobot بالـ ping."""
    port = int(os.environ.get("PORT", "10000"))

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Study bot is alive".encode("utf-8"))

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    HTTPServer(("0.0.0.0", port), _Handler).serve_forever()


# ===== دوال مساعدة =====

def detect_language(text):
    """كشف لغة النص - عربي أو إنجليزي"""
    arabic_chars = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    return 'ar' if arabic_chars > english_chars else 'en'


def safe_parse_json(text):
    """محاولة تحليل JSON مع عدة استراتيجيات احتياطية"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    json_start = text.find('{')
    json_end = text.rfind('}') + 1
    if json_start == -1 or json_end == 0:
        json_start = text.find('[')
        json_end = text.rfind(']') + 1
    if json_start == -1 or json_end == 0:
        raise ValueError("No JSON found in response")
    
    raw_json = text[json_start:json_end]
    
    # المحاولة 1: تحليل مباشر
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        pass
    
    # المحاولة 2: تنظيف $ و backslashes غير صحيحة
    try:
        cleaned = raw_json.replace('$', '')
        cleaned = cleaned.replace('\\\\', '\u0000DBLBACK\u0000')
        cleaned = cleaned.replace('\\"', '\u0000ESCQUOTE\u0000')
        cleaned = cleaned.replace('\\n', '\u0000NL\u0000')
        cleaned = cleaned.replace('\\t', '\u0000TAB\u0000')
        cleaned = cleaned.replace('\\r', '\u0000CR\u0000')
        cleaned = cleaned.replace('\\/', '\u0000SL\u0000')
        cleaned = cleaned.replace('\\b', '\u0000BS\u0000')
        cleaned = cleaned.replace('\\f', '\u0000FF\u0000')
        cleaned = cleaned.replace('\\', '')
        cleaned = cleaned.replace('\u0000DBLBACK\u0000', '\\\\')
        cleaned = cleaned.replace('\u0000ESCQUOTE\u0000', '\\"')
        cleaned = cleaned.replace('\u0000NL\u0000', '\\n')
        cleaned = cleaned.replace('\u0000TAB\u0000', '\\t')
        cleaned = cleaned.replace('\u0000CR\u0000', '\\r')
        cleaned = cleaned.replace('\u0000SL\u0000', '\\/')
        cleaned = cleaned.replace('\u0000BS\u0000', '\\b')
        cleaned = cleaned.replace('\u0000FF\u0000', '\\f')
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # المحاولة 3: إزالة كل backslashes ما عدا الصحيحة
    try:
        cleaned = raw_json.replace('$', '')
        cleaned = re.sub(r'\\(?!["\\/bfnrt])', '', cleaned)
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # المحاولة 4: إزالة كل backslashes ما عدا \"
    try:
        cleaned = raw_json.replace('$', '')
        cleaned = re.sub(r'\\(?!")', '', cleaned)
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # المحاولة 5: قص عند آخر JSON صالح
    try:
        cleaned = raw_json.replace('$', '')
        cleaned = re.sub(r'\\(?!["\\/bfnrt])', '', cleaned)
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        cleaned = re.sub(r'[\x00-\x1f]', ' ', cleaned)
        for end_pos in range(len(cleaned), max(0, len(cleaned) - 2000), -1):
            substr = cleaned[:end_pos]
            if substr.rstrip().endswith('}') or substr.rstrip().endswith(']'):
                try:
                    return json.loads(substr)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    # المحاولة 6: استخدام AI لإصلاح JSON
    try:
        fix_response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": "Fix this broken JSON. Return ONLY valid JSON, nothing else."},
                {"role": "user", "content": raw_json[:3000]}
            ],
            temperature=0,
            max_tokens=4000
        )
        fixed = fix_response.choices[0].message.content.strip()
        fixed = re.sub(r'```json\s*', '', fixed)
        fixed = re.sub(r'```\s*', '', fixed)
        return json.loads(fixed)
    except Exception:
        pass
    
    raise ValueError(f"Failed to parse JSON after all attempts")


def escape_html(text):
    """تنظيف النص من رموز HTML الخطيرة"""
    if not text:
        return ''
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


# ثابت LRM للتحكم بالاتجاه ثنائي الاتجاه
LRM = '\u200E'  # Left-to-Right Mark


def _insert_lrm_around_arabic(text):
    """إدراج علامات LRM حول الكلمات العربية داخل سياق رياضي LTR"""
    return re.sub(
        r'([\u0600-\u06FF][\u0600-\u06FF\u0640-\u065F\s/\.،]*[\u0600-\u06FF]|[\u0600-\u06FF])',
        lambda m: f'{LRM}{m.group(0)}{LRM}',
        text
    )


def format_math_text(text):
    """
    تحويل النص إلى HTML آمن مع دعم المعادلات الرياضية.
    يعالج مشكلة الاتجاه ثنائي الاتجاه (bidi) عند خلط النص العربي مع المعادلات.
    الخطوات: 1) escape HTML  2) تحويل الرموز  3) معالجة الرياضيات  4) إصلاح bidi
    """
    if not text:
        return ''
    
    # الخطوة 1: escape HTML أولاً لحماية من injection
    t = escape_html(text)
    
    # الخطوة 2: تحويل الرموز اليونانية والرياضية إلى Unicode
    greek = {
        'Delta': 'Δ', 'delta': 'δ', 'alpha': 'α', 'beta': 'β',
        'gamma': 'γ', 'Gamma': 'Γ', 'theta': 'θ', 'Theta': 'Θ',
        'lambda': 'λ', 'Lambda': 'Λ', 'mu': 'μ', 'pi': 'π',
        'Pi': 'Π', 'sigma': 'σ', 'Sigma': 'Σ', 'omega': 'ω',
        'Omega': 'Ω', 'phi': 'φ', 'Phi': 'Φ', 'psi': 'ψ',
        'epsilon': 'ε', 'rho': 'ρ', 'tau': 'τ', 'nu': 'ν',
        'eta': 'η', 'zeta': 'ζ', 'xi': 'ξ', 'kappa': 'κ',
        'infty': '∞', 'infinity': '∞',
        'approx': '≈', 'neq': '≠', 'leq': '≤', 'geq': '≥',
        'times': '×', 'cdot': '·', 'div': '÷', 'pm': '±',
        'sqrt': '√', 'sum': '∑', 'prod': '∏',
        'partial': '∂', 'nabla': '∇', 'forall': '∀', 'exists': '∃',
        'rightarrow': '→', 'leftarrow': '←', 'Rightarrow': '⇒',
    }
    for name, symbol in sorted(greek.items(), key=lambda x: -len(x[0])):
        t = t.replace(name, symbol)
    
    # الخطوة 3: تحويل FRAC(بسط,مقام) إلى HTML كسور
    def replace_frac(match):
        num = match.group(1).strip()
        den = match.group(2).strip()
        return (f'<span style="direction:ltr;display:inline-block;text-align:center;vertical-align:middle;">'
                f'<span style="display:block;border-bottom:1.5px solid #333;padding:0 5px 2px;">{num}</span>'
                f'<span style="display:block;padding:2px 5px 0;">{den}</span>'
                f'</span>')
    t = re.sub(r'FRAC\(([^,]+),([^)]+)\)', replace_frac, t)
    
    # الخطوة 4: تحويل الأسس ^{exp} و ^exp
    def replace_sup(match):
        base = match.group(1) if match.group(1) else ''
        exp = match.group(2)
        return f'{base}<sup style="font-size:0.7em;">{exp}</sup>'
    t = re.sub(r'(\w*)\^{([^}]+)}', replace_sup, t)
    t = re.sub(r'(\w+)\^([-]?\d+)', replace_sup, t)
    
    # الخطوة 5: تحويل subscripts _{sub} و _sub
    def replace_sub(match):
        base = match.group(1) if match.group(1) else ''
        sub = match.group(2)
        return f'{base}<sub style="font-size:0.7em;">{sub}</sub>'
    t = re.sub(r'(\w*)_{([^}]+)}', replace_sub, t)
    t = re.sub(r'([A-Za-z])_(\d+)', replace_sub, t)
    
    # الخطوة 6: إصلاح الاتجاه ثنائي الاتجاه (bidi) للنص المختلط
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', t))
    has_math = bool(re.search(r'[=+\-×÷].*\d|^\s*[A-Za-z_].*=', t))
    
    if has_arabic and has_math:
        # محاولة فصل النص العربي عن المعادلة عند النقطتين
        colon_split = re.match(r'^([\u0600-\u06FF\u0640-\u065F\s,،\.\(\)]+[:\s])\s*(.+)$', t)
        
        if colon_split:
            arabic_part = colon_split.group(1)
            math_part = colon_split.group(2)
            math_part = _insert_lrm_around_arabic(math_part)
            t = f'{arabic_part}<span class="math-expr">{math_part}</span>'
        else:
            # حساب نسبة الأحرف الرياضية مقابل العربية
            arabic_count = len(re.findall(r'[\u0600-\u06FF]', t))
            math_count = len(re.findall(r'[a-zA-Z0-9=+\-×÷\.\(\)<>/]', t))
            
            if math_count >= arabic_count:
                # معادلة رياضية مع وحدات عربية - لف الكل في LTR
                t = _insert_lrm_around_arabic(t)
                t = f'<span class="math-expr">{t}</span>'
            # وإلا: نص عربي بشكل أساسي، نتركه كما هو
    
    return t


def get_base_css(lang):
    """إرجاع CSS الأساسي حسب اللغة"""
    direction = 'rtl' if lang == 'ar' else 'ltr'
    text_align = 'right' if lang == 'ar' else 'left'
    font_family = "'Noto Sans Arabic', 'Arial', sans-serif" if lang == 'ar' else "'Helvetica Neue', 'Arial', sans-serif"
    
    return f"""
    @page {{
        size: A4;
        margin: 2cm 2.5cm;
        @bottom-center {{
            content: counter(page);
            font-size: 10px;
            color: #95a5a6;
        }}
    }}
    body {{
        font-family: {font_family};
        direction: {direction};
        text-align: {text_align};
        line-height: 2;
        color: #1a1a2e;
        font-size: 15px;
    }}
    .main-title {{
        font-size: 28px;
        font-weight: bold;
        text-align: center;
        color: #1a1a2e;
        margin-bottom: 10px;
        padding-bottom: 15px;
    }}
    .title-line {{
        border: none;
        border-top: 2.5px solid #1a1a2e;
        margin-bottom: 30px;
    }}
    /* ===== التعاليل والتعاريف ===== */
    .question {{
        font-size: 17px;
        font-weight: bold;
        color: #0a3d62;
        margin-top: 25px;
        margin-bottom: 8px;
        line-height: 1.9;
    }}
    .answer {{
        font-size: 15px;
        color: #2c3e50;
        margin-bottom: 10px;
        line-height: 2;
    }}
    .term {{
        font-size: 17px;
        font-weight: bold;
        color: #16213e;
        margin-top: 25px;
        margin-bottom: 5px;
    }}
    .definition {{
        font-size: 15px;
        color: #2c3e50;
        margin-bottom: 10px;
        line-height: 2;
    }}
    .summary-point {{
        font-size: 15px;
        color: #2c3e50;
        margin-bottom: 12px;
        line-height: 2;
    }}
    .divider {{
        border: none;
        border-top: 1px solid #dcdde1;
        margin: 15px 0;
    }}
    .footer {{
        text-align: center;
        color: #95a5a6;
        font-size: 11px;
        margin-top: 40px;
    }}
    /* ===== تصميم الحلول الاحترافي ===== */
    .sol-card {{
        background: #f8f9fa;
        border-radius: 10px;
        padding: 20px 25px;
        margin-bottom: 25px;
    }}
    .sol-q-header {{
        background: #0a3d62;
        color: white;
        padding: 10px 18px;
        border-radius: 8px;
        font-size: 17px;
        font-weight: bold;
        line-height: 1.8;
        margin-bottom: 15px;
    }}
    .sol-steps-title {{
        font-size: 15px;
        font-weight: bold;
        color: #16213e;
        margin-bottom: 10px;
        padding-bottom: 5px;
        border-bottom: 1px solid #dcdde1;
    }}
    .sol-step {{
        font-size: 14px;
        color: #2d3436;
        margin-bottom: 8px;
        padding: 8px 12px;
        background: white;
        border-radius: 6px;
        line-height: 1.9;
        border-right: 3px solid #3498db;
    }}
    .sol-step-en {{
        font-size: 14px;
        color: #2d3436;
        margin-bottom: 8px;
        padding: 8px 12px;
        background: white;
        border-radius: 6px;
        line-height: 1.9;
        border-left: 3px solid #3498db;
    }}
    .sol-step-num {{
        display: inline-block;
        background: #3498db;
        color: white;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        text-align: center;
        font-size: 12px;
        line-height: 22px;
        margin-left: 8px;
        margin-right: 8px;
    }}
    .sol-final {{
        background: #006266;
        color: white;
        padding: 12px 18px;
        border-radius: 8px;
        font-size: 15px;
        font-weight: bold;
        margin-top: 12px;
        line-height: 1.9;
    }}
    .sol-divider {{
        border: none;
        border-top: 2px dashed #bdc3c7;
        margin: 20px 0;
    }}
    .sol-theory-answer {{
        font-size: 15px;
        color: #2d3436;
        padding: 15px 20px;
        background: white;
        border-radius: 8px;
        line-height: 2.0;
        margin-top: 10px;
    }}
    .sol-part {{
        margin: 12px 0;
        padding: 12px 18px;
        background: white;
        border-radius: 8px;
    }}
    .sol-part-label {{
        font-size: 16px;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 8px;
        padding-bottom: 5px;
        border-bottom: 1px solid #ecf0f1;
    }}
    .sol-sub-q {{
        margin: 10px 0;
        padding: 10px 15px;
        background: #fafafa;
        border-radius: 6px;
        line-height: 1.9;
    }}
    .sol-sub-num {{
        display: inline-block;
        background: #8e44ad;
        color: white;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        text-align: center;
        font-size: 11px;
        line-height: 20px;
        margin-left: 6px;
        margin-right: 6px;
    }}
    .sol-sub-text {{
        font-size: 14px;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 5px;
    }}
    .sol-sub-answer {{
        font-size: 14px;
        color: #2d3436;
        line-height: 1.9;
        padding: 5px 0;
    }}
    /* ===== تصميم الاختبار ===== */
    .exam-header {{
        text-align: center;
        margin-bottom: 25px;
        padding: 20px;
        border: 2px solid #1a1a2e;
        border-radius: 10px;
    }}
    .exam-header-title {{
        font-size: 24px;
        font-weight: bold;
        color: #1a1a2e;
        margin-bottom: 8px;
    }}
    .exam-header-info {{
        font-size: 13px;
        color: #636e72;
        line-height: 1.8;
    }}
    .exam-q-card {{
        margin-bottom: 25px;
        border: 1px solid #dcdde1;
        border-radius: 10px;
        overflow: hidden;
    }}
    .exam-q-header {{
        background: #0a3d62;
        color: white;
        padding: 10px 18px;
        font-size: 17px;
        font-weight: bold;
        line-height: 1.8;
    }}
    .exam-q-num {{
        display: inline-block;
        background: #e74c3c;
        color: white;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        text-align: center;
        font-size: 14px;
        line-height: 28px;
        margin-left: 8px;
        margin-right: 8px;
    }}
    .exam-part {{
        padding: 15px 20px;
        border-bottom: 1px solid #ecf0f1;
    }}
    .exam-part:last-child {{
        border-bottom: none;
    }}
    .exam-part-label {{
        display: inline-block;
        background: #1e6f9f;
        color: white;
        padding: 2px 12px;
        border-radius: 15px;
        font-size: 13px;
        font-weight: bold;
        margin-bottom: 8px;
        margin-left: 5px;
        margin-right: 5px;
    }}
    .exam-part-text {{
        font-size: 15px;
        color: #2c3e50;
        line-height: 2.0;
        padding: 5px 0;
    }}
    .exam-answer-line {{
        border-bottom: 1px dotted #bdc3c7;
        height: 30px;
        margin: 8px 0;
    }}
    /* ===== تصميم حلول الاختبار ===== */
    .exam-sol-card {{
        margin-bottom: 25px;
        background: #f8f9fa;
        border-radius: 10px;
        padding: 0;
        overflow: hidden;
    }}
    .exam-sol-header {{
        background: #006266;
        color: white;
        padding: 10px 18px;
        font-size: 17px;
        font-weight: bold;
        line-height: 1.8;
    }}
    .exam-sol-part {{
        padding: 15px 20px;
        border-bottom: 1px solid #ecf0f1;
    }}
    .exam-sol-part:last-child {{
        border-bottom: none;
    }}
    .exam-sol-part-label {{
        display: inline-block;
        background: #e74c3c;
        color: white;
        padding: 2px 12px;
        border-radius: 15px;
        font-size: 13px;
        font-weight: bold;
        margin-bottom: 8px;
        margin-left: 5px;
        margin-right: 5px;
    }}
    .exam-sol-q-text {{
        font-size: 14px;
        font-weight: bold;
        color: #0a3d62;
        line-height: 1.9;
        margin-bottom: 8px;
    }}
    .exam-sol-answer {{
        font-size: 14px;
        color: #2d3436;
        line-height: 2.0;
        padding: 10px 15px;
        background: white;
        border-radius: 8px;
        border-right: 3px solid #006266;
    }}
    .exam-sol-answer-en {{
        font-size: 14px;
        color: #2d3436;
        line-height: 2.0;
        padding: 10px 15px;
        background: white;
        border-radius: 8px;
        border-left: 3px solid #006266;
    }}
    /* ===== جداول المقارنات الاحترافية ===== */
    .comp-card {{
        margin-bottom: 30px;
        page-break-inside: avoid;
    }}
    .comp-title {{
        background: #0a3d62;
        color: white;
        padding: 12px 20px;
        border-radius: 10px 10px 0 0;
        font-size: 17px;
        font-weight: bold;
        line-height: 1.8;
        text-align: center;
    }}
    .comp-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 0;
        font-size: 13px;
    }}
    .comp-table thead th {{
        background: #1e6f9f;
        color: white;
        padding: 10px 14px;
        font-weight: bold;
        font-size: 14px;
        text-align: center;
        border: 1px solid #1a5f8a;
        line-height: 1.7;
    }}
    .comp-table thead th.aspect-header {{
        background: #16213e;
        width: 22%;
    }}
    .comp-table tbody td {{
        padding: 10px 14px;
        border: 1px solid #dcdde1;
        line-height: 1.8;
        vertical-align: top;
    }}
    .comp-table tbody tr:nth-child(even) {{
        background: #f8f9fa;
    }}
    .comp-table tbody tr:nth-child(odd) {{
        background: #ffffff;
    }}
    .comp-table tbody td.aspect-cell {{
        background: #eaf2f8;
        font-weight: bold;
        color: #0a3d62;
        text-align: center;
        font-size: 13px;
    }}
    .comp-table tbody td.value-cell {{
        color: #2d3436;
        font-size: 13px;
    }}
    .comp-number {{
        display: inline-block;
        background: #e74c3c;
        color: white;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        text-align: center;
        font-size: 13px;
        line-height: 26px;
        margin-left: 8px;
        margin-right: 8px;
    }}
    /* Math LTR isolation */
    .math-ltr {{
        direction: ltr;
        display: inline-block;
        unicode-bidi: embed;
        text-align: left;
    }}
    .math-expr {{
        direction: ltr;
        unicode-bidi: isolate;
        display: inline;
    }}
    sup {{
        font-size: 0.7em;
        vertical-align: super;
    }}
    sub {{
        font-size: 0.7em;
        vertical-align: sub;
    }}

    /* ===== الشرح المبسط ===== */
    .explain-main-title {{
        text-align: center;
        font-size: 26px;
        font-weight: bold;
        color: #1E3A5F;
        background: linear-gradient(135deg, #E8F4FD 0%, #D1ECFD 100%);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 8px;
        border-bottom: 4px solid #3B82F6;
    }}
    .explain-intro {{
        background: #F0F9FF;
        border-right: 4px solid #3B82F6;
        border-left: 4px solid #3B82F6;
        padding: 15px 20px;
        margin-bottom: 20px;
        border-radius: 8px;
        font-size: 14px;
        color: #334155;
        line-height: 1.8;
    }}
    .explain-section {{
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        margin-bottom: 18px;
        padding: 0;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}
    .explain-section-header {{
        background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
        color: white;
        padding: 12px 18px;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .explain-section-num {{
        background: #EF4444;
        color: white;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 14px;
        flex-shrink: 0;
    }}
    .explain-section-icon {{
        font-size: 20px;
        flex-shrink: 0;
    }}
    .explain-section-title {{
        font-size: 16px;
        font-weight: bold;
    }}
    .explain-text {{
        padding: 15px 20px;
        font-size: 13.5px;
        line-height: 2;
        color: #1E293B;
        border-bottom: 1px dashed #E2E8F0;
    }}
    .explain-formula-box {{
        background: #FFF7ED;
        border: 1px solid #FDBA74;
        border-radius: 8px;
        margin: 12px 18px;
        padding: 12px 15px;
    }}
    .explain-formula-label {{
        font-weight: bold;
        color: #C2410C;
        font-size: 13px;
        margin-bottom: 6px;
    }}
    .explain-formula {{
        font-family: 'Courier New', monospace;
        font-size: 15px;
        color: #1E293B;
        text-align: center;
        padding: 8px;
        background: white;
        border-radius: 6px;
        direction: ltr;
        unicode-bidi: isolate;
    }}
    .explain-formula-desc {{
        font-size: 12px;
        color: #78716C;
        margin-top: 6px;
        line-height: 1.6;
    }}
    .explain-example {{
        background: #F0FDF4;
        border: 1px solid #86EFAC;
        border-radius: 8px;
        margin: 12px 18px;
        padding: 12px 15px;
    }}
    .explain-example-label {{
        font-weight: bold;
        color: #15803D;
        font-size: 13px;
        margin-bottom: 6px;
    }}
    .explain-example-text {{
        font-size: 13px;
        color: #166534;
        line-height: 1.7;
    }}
    .explain-note {{
        background: #FEF3C7;
        border: 1px solid #FCD34D;
        border-radius: 8px;
        margin: 12px 18px 15px 18px;
        padding: 10px 15px;
        font-size: 12.5px;
        color: #92400E;
        line-height: 1.6;
    }}

    /* ===== المهم ===== */
    .imp-main-title {{
        text-align: center;
        font-size: 26px;
        font-weight: bold;
        color: #FFFFFF;
        background: linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%);
        padding: 20px;
        border-radius: 15px 15px 0 0;
        margin-bottom: 0;
    }}
    .imp-subtitle {{
        text-align: center;
        font-size: 14px;
        color: #6D28D9;
        background: #EDE9FE;
        padding: 8px;
        border-radius: 0 0 15px 15px;
        margin-bottom: 20px;
        font-weight: bold;
    }}
    .imp-category {{
        margin-bottom: 20px;
    }}
    .imp-cat-header {{
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        color: white;
        padding: 12px 18px;
        border-radius: 10px 10px 0 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .imp-cat-icon {{
        font-size: 22px;
    }}
    .imp-cat-name {{
        font-size: 16px;
        font-weight: bold;
        flex-grow: 1;
    }}
    .imp-cat-count {{
        background: rgba(255,255,255,0.25);
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }}
    .imp-point {{
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-top: none;
        padding: 12px 18px;
    }}
    .imp-point:last-child {{
        border-radius: 0 0 10px 10px;
    }}
    .imp-point-header {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 6px;
    }}
    .imp-point-num {{
        color: white;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 12px;
        flex-shrink: 0;
    }}
    .imp-point-title {{
        font-size: 14px;
        font-weight: bold;
        color: #1E293B;
        flex-grow: 1;
    }}
    .imp-badge {{
        color: white;
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 10px;
        font-weight: bold;
        flex-shrink: 0;
    }}
    .imp-point-content {{
        font-size: 13px;
        color: #475569;
        line-height: 1.8;
        padding-right: 36px;
        padding-left: 36px;
    }}
    .imp-tip {{
        background: #FFFBEB;
        border: 1px solid #FDE68A;
        border-radius: 6px;
        padding: 8px 12px;
        margin-top: 8px;
        font-size: 12px;
        color: #92400E;
        line-height: 1.5;
        margin-right: 36px;
        margin-left: 36px;
    }}
    """


def build_html_pdf(html_body, lang, output_path):
    """بناء PDF من HTML مع دعم كامل للعربية"""
    direction = 'rtl' if lang == 'ar' else 'ltr'
    lang_attr = 'ar' if lang == 'ar' else 'en'
    css = get_base_css(lang)
    
    full_html = f"""<!DOCTYPE html>
<html dir="{direction}" lang="{lang_attr}">
<head>
<meta charset="utf-8">
<style>{css}</style>
</head>
<body>
{html_body}
</body>
</html>"""
    
    HTML(string=full_html).write_pdf(output_path)


# ===== معالجة الملفات =====

async def process_image(image_path: str) -> str:
    """معالجة الصورة واستخراج النص"""
    try:
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this image accurately. Write all text found in the image whether in Arabic or English. Maintain the original formatting and order."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            }],
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error processing image: {e}")
        return None


async def process_pdf(pdf_path: str) -> str:
    """معالجة ملف PDF"""
    try:
        content = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text.strip():
                    content += text + "\n\n"
        
        if len(content.strip()) < 100:
            images = convert_from_path(pdf_path, dpi=200)
            for i, image in enumerate(images):
                temp_path = f"/tmp/page_{i}.jpg"
                image.save(temp_path, 'JPEG')
                page_content = await process_image(temp_path)
                if page_content:
                    content += page_content + "\n\n"
                os.remove(temp_path)
        
        return content.strip()
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return None


# ===== الـ Prompts الموحدة =====

MATH_INSTRUCTIONS = """
CRITICAL RULES FOR MATH AND SCIENTIFIC NOTATION:
- Write fractions as: FRAC(numerator,denominator) - example: FRAC(h,4pi)
- Write superscripts/exponents as: x^{exp} - example: 10^{-34} or x^{2}
- Write subscripts as: x_{sub} - example: H_{2}O or N_{2}
- Use these words for symbols: times for ×, approx for ≈, geq for ≥, leq for ≤
- Write Greek letters as words: Delta, pi, sigma, mu, alpha, beta, theta, lambda, omega
- NEVER use LaTeX commands like \\frac, \\times, \\Delta etc.
- NEVER use $ signs
- Keep equations on separate lines for clarity
"""

JSON_RULES = """
CRITICAL JSON RULES:
- Return ONLY valid JSON, no text before or after
- Do NOT use backslash (\\) in text values except for \\n or \\"
- Do NOT use LaTeX commands
- Use plain text and the FRAC() notation for math
- Ensure all strings are properly closed with "
- Ensure all arrays and objects are properly closed
"""


# ===== توليد المحتوى =====

async def generate_mcq_quiz(query, context, content: str, user_id: int):
    """توليد أسئلة MCQ"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""بناءً على المحتوى التالي، أنشئ 20-30 سؤال اختيار من متعدد (MCQ) يغطي كامل المادة.

المحتوى:
{content}

المتطلبات:
1. أنشئ 20-30 سؤال لتغطية كامل المحتوى
2. استخرج الأسئلة مباشرة من المحتوى فقط
3. كل سؤال له 4 خيارات
4. إجابة صحيحة واحدة فقط
5. أضف شرح مختصر للإجابة الصحيحة
6. اكتب كل شيء بالعربية
7. للرموز الرياضية استخدم نص عادي مثل: 10^2 و H2O
{JSON_RULES}

أرجع النتيجة بصيغة JSON:
{{"questions": [{{"question": "نص السؤال", "options": ["خيار 1", "خيار 2", "خيار 3", "خيار 4"], "correct": 0, "explanation": "شرح الإجابة"}}]}}"""
        else:
            prompt = f"""Based on the following content, create 20-30 MCQ questions covering ALL the material.

Content:
{content}

Requirements:
1. Generate 20-30 questions to cover the ENTIRE content
2. Extract questions DIRECTLY from the content only
3. Each question has 4 options
4. Only one correct answer
5. Add brief explanation
6. Write everything in English
7. For math symbols use plain text: 10^2 and H2O
{JSON_RULES}

Return in JSON:
{{"questions": [{{"question": "Question text", "options": ["A", "B", "C", "D"], "correct": 0, "explanation": "Explanation"}}]}}"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "Expert MCQ creator. Return ONLY valid JSON. NO LaTeX. NO backslash commands."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=8000
        )
        
        result = response.choices[0].message.content
        mcq_data = safe_parse_json(result)
        
        for i, q in enumerate(mcq_data['questions'], 1):
            q_text = q['question']
            if len(q_text) > 290:
                q_text = q_text[:290] + "..."
            options = q['options'][:4]
            options = [o[:100] for o in options]
            await query.message.reply_poll(
                question=q_text,
                options=options,
                type='quiz',
                correct_option_id=q['correct'],
                explanation=q.get('explanation', '')[:200],
                is_anonymous=False
            )
            await asyncio.sleep(1)
        
    except Exception as e:
        print(f"Error generating MCQ: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


async def generate_explanations(query, context, content: str, user_id: int):
    """توليد التعاليل"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""بناءً على المحتوى التالي، أنشئ 20-30 سؤال وجواب (تعاليل) تغطي كامل المادة.

المحتوى:
{content}

المتطلبات:
1. أنشئ 20-30 سؤال وجواب لتغطية كامل المحتوى
2. استخرج الأسئلة والأجوبة مباشرة من المحتوى فقط
3. الأسئلة تسأل "لماذا" و "كيف" و "اشرح" و "ما السبب"
4. الأجوبة تفصيلية وواضحة
5. اكتب كل شيء بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON:
{{"explanations": [{{"question": "السؤال", "answer": "الجواب التفصيلي"}}]}}"""
        else:
            prompt = f"""Based on the following content, create 20-30 Q&A pairs covering ALL the material.

Content:
{content}

Requirements:
1. Generate 20-30 Q&A pairs to cover the ENTIRE content
2. Extract from the content only
3. Questions: "Why", "How", "Explain"
4. Answers: detailed and clear
5. Write everything in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON:
{{"explanations": [{{"question": "Question", "answer": "Detailed answer"}}]}}"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "Expert Q&A creator. Return ONLY valid JSON. NO LaTeX. NO backslash commands. Use FRAC() for fractions and ^{} for exponents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=10000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_explanations.pdf"
        create_explanations_pdf(data['explanations'], pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Explanations.pdf",
            caption="تم إنشاء ملف التعاليل بنجاح ✅" if lang == 'ar' else "Explanations file created successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating explanations: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


async def generate_definitions(query, context, content: str, user_id: int):
    """استخراج التعاريف"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""استخرج جميع المصطلحات والتعاريف المهمة من المحتوى التالي.

المحتوى:
{content}

المتطلبات:
1. استخرج 20-30 مصطلح وتعريف لتغطية كامل المحتوى
2. شمل أسماء العلماء والنظريات والقوانين والمفاهيم
3. استخرج التعاريف كما هي مكتوبة في المحتوى
4. لا تضف معلومات من خارج المحتوى
5. اكتب كل شيء بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON:
{{"definitions": [{{"term": "المصطلح", "definition": "التعريف الشامل"}}]}}"""
        else:
            prompt = f"""Extract ALL important terms and definitions from the following content.

Content:
{content}

Requirements:
1. Extract 20-30 terms and definitions
2. Include scientists, theories, laws, concepts
3. Extract as written in the content
4. Do NOT add external information
5. Write everything in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON:
{{"definitions": [{{"term": "Term", "definition": "Comprehensive definition"}}]}}"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "Expert definition extractor. Return ONLY valid JSON. NO LaTeX. NO backslash commands."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=10000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_definitions.pdf"
        create_definitions_pdf(data['definitions'], pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Definitions.pdf",
            caption="تم إنشاء ملف التعاريف بنجاح ✅" if lang == 'ar' else "Definitions file created successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating definitions: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


async def generate_summary(query, context, content: str, user_id: int):
    """تلخيص المحتوى"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""لخص المحتوى التالي بشكل شامل ومفصل.

المحتوى:
{content}

المتطلبات:
1. أنشئ 20-30 نقطة تلخيصية تغطي كامل المحتوى
2. شمل جميع المواضيع والمفاهيم والتعاريف والأمثلة
3. لا تتخطى أي قسم أو معلومة مهمة
4. كل نقطة جملة كاملة تغطي فكرة رئيسية
5. رتب النقاط بشكل منطقي
6. استخرج المعلومات مباشرة من المحتوى فقط
7. اكتب كل شيء بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON:
{{"summary": [{{"point": "نقطة التلخيص"}}]}}"""
        else:
            prompt = f"""Create a comprehensive summary of the following content.

Content:
{content}

Requirements:
1. Generate 20-30 summary points covering the ENTIRE content
2. Include ALL topics, concepts, definitions, examples
3. Do NOT skip any section
4. Each point is a complete sentence
5. Organize logically
6. Extract from the content only
7. Write everything in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON:
{{"summary": [{{"point": "Summary point"}}]}}"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "Expert summarizer. Return ONLY valid JSON. NO LaTeX. NO backslash commands."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=8000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_summary.pdf"
        create_summary_pdf(data['summary'], pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Summary.pdf",
            caption="تم إنشاء الملخص بنجاح ✅" if lang == 'ar' else "Summary created successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


async def generate_solutions(query, context, content: str, user_id: int):
    """حل جميع الأسئلة"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""أنت خبير أكاديمي متخصص في حل المسائل العلمية والرياضية. حل جميع الأسئلة والمسائل الموجودة في المحتوى التالي بدقة تامة.

المحتوى:
{content}

⚠️ قواعد صارمة جداً - يجب الالتزام بها:

1. **ترقيم الأسئلة (مهم جداً)**:
   - اقرأ المحتوى بعناية وحدد أرقام الأسئلة كما هي مكتوبة بالضبط
   - إذا كان السؤال الأول مرقماً بـ "1" أو "السؤال الأول" → اكتبه "س 1"
   - إذا كان السؤال الثاني مرقماً بـ "2" → اكتبه "س 2" وليس "س 4" أو أي رقم آخر
   - لا تخترع أرقاماً جديدة - استخدم الأرقام الموجودة في الورقة فقط
   - رتّب الأسئلة بنفس الترتيب الذي تظهر به في الورقة

2. **دقة الحلول (مهم جداً)**:
   - تحقق من كل حساب مرتين قبل كتابته
   - استخدم القوانين الصحيحة لكل مسألة
   - لا تخمّن - إذا كانت المعطيات ناقصة، اذكر ذلك
   - الإجابة النهائية يجب أن تكون نتيجة الحسابات الفعلية وليس رقماً عشوائياً
   - تأكد من وحدات القياس في كل خطوة

3. **هيكل الأسئلة**:
   - حافظ على هيكل الأسئلة كما هي في الورقة
   - إذا كان السؤال يحتوي على فروع (A, B) أو نقاط فرعية (1, 2, 3) فاحفظها كفروع داخل نفس السؤال

4. **نوع الأسئلة**:
   - أسئلة نظرية/شرح (ما المقصود، عرّف، علل، قارن): أجب مباشرة بدون خطوات
   - مسائل حسابية (تحتاج حسابات): قدم خطوات تفصيلية مع التحقق

5. اكتب كل شيء بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON بهذا الهيكل:
{{"solutions": [
  {{
    "question_num": "س 1",
    "parts": [
      {{
        "part_label": "A",
        "part_text": "نص الفرع",
        "type": "math",
        "steps": ["الخطوة 1: ..."],
        "final_answer": "الإجابة",
        "sub_questions": []
      }},
      {{
        "part_label": "B",
        "part_text": "أجب عن اثنين",
        "type": "theory",
        "steps": [],
        "final_answer": "",
        "sub_questions": [
          {{"sub_num": "1", "sub_text": "علل فشل...", "answer": "الجواب"}},
          {{"sub_num": "2", "sub_text": "ما التطبيقات...", "answer": "الجواب"}}
        ]
      }}
    ]
  }}
]}}

قواعد الهيكل:
- إذا السؤال بدون فروع (A/B): ضع فرع واحد فقط بدون part_label
- إذا الفرع فيه نقاط فرعية (1, 2, 3): ضعها في sub_questions
- إذا الفرع مسألة حسابية: type=math و steps تحتوي الخطوات
- إذا الفرع نظري: type=theory و الإجابة في final_answer أو sub_questions

قواعد تنسيق الخطوات (مهمة جداً):
- كل خطوة يجب أن تبدأ بوصف عربي قصير ثم نقطتين (:) ثم المعادلة الرياضية
- مثال صحيح: "حساب الطاقة: K = 2.832 × 10^{{-19}} جول"
- لا تضع أكثر من معادلة واحدة في نفس الخطوة
- المعطيات: ضع كل معطى في خطوة منفصلة
- مثال: بدلاً من "المعطيات: W = 7.195 جول، V = 1.77 فولت" اكتب خطوتين:
  خطوة 1: "دالة الشغل: W = 7.195 × 10^{{-19}} جول"
  خطوة 2: "جهد الإيقاف: V_{{s}} = 1.77 فولت"""
        else:
            prompt = f"""You are an expert academic solver specializing in scientific and mathematical problems. Solve ALL questions in the following content with complete accuracy.

Content:
{content}

⚠️ STRICT RULES - Must be followed:

1. **Question Numbering (CRITICAL)**:
   - Read the content carefully and identify question numbers EXACTLY as written
   - If the first question is numbered "1" or "Question 1" → write it as "Q1"
   - If the second question is numbered "2" → write it as "Q2" NOT "Q4" or any other number
   - Do NOT invent new numbers - use only the numbers found in the paper
   - Keep questions in the same order they appear in the paper

2. **Solution Accuracy (CRITICAL)**:
   - Verify every calculation twice before writing it
   - Use the correct laws/formulas for each problem
   - Do NOT guess - if data is missing, state that clearly
   - The final answer must be the result of actual calculations, not a random number
   - Verify units of measurement in every step

3. **Question Structure**:
   - Preserve the question structure as in the original
   - If a question has parts (A, B) or sub-questions (1, 2, 3), keep them as parts within the same question

4. **Question Types**:
   - Theory/explanation (define, explain, compare): Answer directly without steps
   - Math/calculation (needs calculations): Provide step-by-step solution with verification

5. Write everything in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON with this structure:
{{"solutions": [
  {{
    "question_num": "Q1",
    "parts": [
      {{
        "part_label": "A",
        "part_text": "Part text",
        "type": "math",
        "steps": ["Step 1: ..."],
        "final_answer": "Answer",
        "sub_questions": []
      }},
      {{
        "part_label": "B",
        "part_text": "Answer two",
        "type": "theory",
        "steps": [],
        "final_answer": "",
        "sub_questions": [
          {{"sub_num": "1", "sub_text": "Explain...", "answer": "Answer"}},
          {{"sub_num": "2", "sub_text": "What are...", "answer": "Answer"}}
        ]
      }}
    ]
  }}
]}}

Rules:
- If question has no parts (A/B): put one part without part_label
- If part has sub-questions (1, 2, 3): put them in sub_questions
- Math parts: type=math with steps
- Theory parts: type=theory with answer in final_answer or sub_questions

Step formatting rules (IMPORTANT):
- Each step should start with a short description then colon then the equation
- Example: "Calculate energy: K = 2.832 × 10^{{-19}} J"
- Do NOT put multiple equations in the same step
- For givens: put each given in a separate step
- Example: Instead of "Given: W = 7.195 J, V = 1.77 V" write two steps:
  Step 1: "Work function: W = 7.195 × 10^{{-19}} J"
  Step 2: "Stopping potential: V_s = 1.77 V"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a precise academic expert. CRITICAL: 1) Use question numbers EXACTLY as they appear in the source - never invent or change numbers. 2) Verify ALL calculations twice - accuracy is mandatory. 3) Return ONLY valid JSON. NO LaTeX. NO backslash commands. Use FRAC(num,den) for fractions and ^{exp} for exponents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=16000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_solutions.pdf"
        create_solutions_pdf(data['solutions'], pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Solutions.pdf",
            caption="تم إنشاء ملف الحلول بنجاح ✅" if lang == 'ar' else "Solutions file created successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating solutions: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


async def generate_differences(query, context, content: str, user_id: int):
    """إنشاء فروقات ومقارنات بين المفاهيم"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""أنت خبير أكاديمي. استخرج من المحتوى التالي الفروقات والمقارنات بين المفاهيم المتشابهة أو المترابطة.

المحتوى:
{content}

قواعد صارمة:
1. استخرج فقط المقارنات المنطقية من نفس الموضوع (لا تقارن مواضيع مختلفة تماماً)
2. كل مقارنة يجب أن تكون بين مفهومين أو أكثر مترابطين فعلاً
3. استخدم أوجه مقارنة واضحة ومحددة (مثل: التعريف، الخصائص، الاستخدام، المعادلة، الوحدة، النوع، الشروط)
4. المعلومات يجب أن تكون صحيحة 100% من المحتوى
5. استخرج أكبر عدد ممكن من المقارنات (10 على الأقل إن أمكن)
6. اكتب بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON بهذا الهيكل:
{{"comparisons": [
  {{
    "title": "الفرق بين المفهوم الأول والمفهوم الثاني",
    "items": ["المفهوم الأول", "المفهوم الثاني"],
    "criteria": [
      {{
        "aspect": "وجه المقارنة (مثل: التعريف)",
        "values": ["قيمة المفهوم الأول", "قيمة المفهوم الثاني"]
      }}
    ]
  }}
]}}

ملاحظات:
- items تحتوي أسماء المفاهيم المقارنة (2 أو 3 عناصر كحد أقصى)
- values يجب أن يكون عددها مساوياً لعدد items
- اجعل القيم مختصرة وواضحة (جملة واحدة أو عبارة قصيرة)
- كل مقارنة يجب أن تحتوي 3-6 أوجه مقارنة على الأقل"""
        else:
            prompt = f"""You are an academic expert. Extract from the following content the differences and comparisons between related concepts.

Content:
{content}

Strict rules:
1. Extract only logical comparisons from the same topic (do NOT compare completely different subjects)
2. Each comparison must be between 2 or 3 genuinely related concepts
3. Use clear and specific comparison aspects (e.g., definition, properties, usage, formula, unit, type, conditions)
4. Information must be 100% accurate from the content
5. Extract as many comparisons as possible (at least 10 if possible)
6. Write in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON with this structure:
{{"comparisons": [
  {{
    "title": "Difference between Concept A and Concept B",
    "items": ["Concept A", "Concept B"],
    "criteria": [
      {{
        "aspect": "Comparison aspect (e.g., Definition)",
        "values": ["Value for Concept A", "Value for Concept B"]
      }}
    ]
  }}
]}}

Notes:
- items contains the names of compared concepts (2 or 3 max)
- values count must equal items count
- Keep values concise and clear (one sentence or short phrase)
- Each comparison should have at least 3-6 comparison aspects"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a precise academic expert specializing in creating comparison tables. Return ONLY valid JSON. NO LaTeX. Use FRAC(num,den) for fractions and ^{exp} for exponents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=16000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_differences.pdf"
        create_differences_pdf(data['comparisons'], pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Comparisons.pdf",
            caption="تم إنشاء ملف الفروقات والمقارنات بنجاح ✅" if lang == 'ar' else "Comparisons file created successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating differences: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


# ===== إنشاء ملفات PDF باستخدام WeasyPrint =====

def create_explanations_pdf(explanations, output_path, lang):
    """إنشاء PDF للتعاليل"""
    title = "التعاليل والأجوبة" if lang == 'ar' else "Explanations and Answers"
    q_prefix = "س" if lang == 'ar' else "Q"
    a_label = "الجواب:" if lang == 'ar' else "Answer:"
    
    html_parts = []
    html_parts.append(f'<div class="main-title">{escape_html(title)}</div>')
    html_parts.append('<hr class="title-line">')
    
    for i, item in enumerate(explanations, 1):
        q_text = format_math_text(item.get('question', ''))
        a_text = format_math_text(item.get('answer', ''))
        
        html_parts.append(f'<div class="question">{q_prefix}{i}: {q_text}</div>')
        html_parts.append(f'<div class="answer"><b>{a_label}</b> {a_text}</div>')
        
        if i < len(explanations):
            html_parts.append('<hr class="divider">')
    
    html_parts.append('<div class="footer">Powered by: Firas APA</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_definitions_pdf(definitions, output_path, lang):
    """إنشاء PDF للتعاريف"""
    title = "المصطلحات والتعاريف" if lang == 'ar' else "Terms and Definitions"
    
    html_parts = []
    html_parts.append(f'<div class="main-title">{escape_html(title)}</div>')
    html_parts.append('<hr class="title-line">')
    
    for i, item in enumerate(definitions, 1):
        term = format_math_text(item.get('term', ''))
        definition = format_math_text(item.get('definition', ''))
        
        html_parts.append(f'<div class="term">{i}. {term}</div>')
        html_parts.append(f'<div class="definition">{definition}</div>')
        
        if i < len(definitions):
            html_parts.append('<hr class="divider">')
    
    html_parts.append('<div class="footer">Powered by: Firas APA</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_summary_pdf(summary, output_path, lang):
    """إنشاء PDF للملخص"""
    title = "الملخص الشامل" if lang == 'ar' else "Comprehensive Summary"
    
    html_parts = []
    html_parts.append(f'<div class="main-title">{escape_html(title)}</div>')
    html_parts.append('<hr class="title-line">')
    
    for i, item in enumerate(summary, 1):
        point = format_math_text(item.get('point', ''))
        html_parts.append(f'<div class="summary-point"><b>{i}.</b> {point}</div>')
    
    html_parts.append('<hr class="divider">')
    html_parts.append('<div class="footer">Powered by: Firas APA</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_solutions_pdf(solutions, output_path, lang):
    """إنشاء PDF احترافي للحلول - يدعم الهيكل الهرمي (سؤال ← فرع ← نقاط فرعية)"""
    title = "الحلول التفصيلية" if lang == 'ar' else "Detailed Solutions"
    steps_label = "خطوات الحل:" if lang == 'ar' else "Solution Steps:"
    ans_label = "الإجابة النهائية:" if lang == 'ar' else "Final Answer:"
    ans_direct = "الجواب:" if lang == 'ar' else "Answer:"
    step_class = "sol-step" if lang == 'ar' else "sol-step-en"
    
    html_parts = []
    html_parts.append(f'<div class="main-title">{escape_html(title)}</div>')
    html_parts.append('<hr class="title-line">')
    
    for i, item in enumerate(solutions, 1):
        # التحقق من نوع الهيكل: هرمي (parts) أو مسطح (question)
        has_parts = 'parts' in item and isinstance(item.get('parts'), list)
        
        html_parts.append('<div class="sol-card">')
        
        if has_parts:
            # === الهيكل الهرمي الجديد ===
            q_num = item.get('question_num', f'س {i}' if lang == 'ar' else f'Q{i}')
            html_parts.append(f'<div class="sol-q-header">{format_math_text(q_num)}</div>')
            
            for part in item['parts']:
                part_label = part.get('part_label', '')
                part_text = format_math_text(part.get('part_text', ''))
                p_type = part.get('type', 'theory').lower()
                steps = part.get('steps', [])
                final = format_math_text(part.get('final_answer', ''))
                sub_qs = part.get('sub_questions', [])
                
                html_parts.append('<div class="sol-part">')
                
                # عنوان الفرع
                if part_label:
                    html_parts.append(f'<div class="sol-part-label">{part_label}: {part_text}</div>')
                elif part_text:
                    html_parts.append(f'<div class="sol-part-label">{part_text}</div>')
                
                if sub_qs:
                    # فرع يحتوي نقاط فرعية (1, 2, 3)
                    for sq in sub_qs:
                        sq_num = sq.get('sub_num', '')
                        sq_text = format_math_text(sq.get('sub_text', ''))
                        sq_answer = format_math_text(sq.get('answer', ''))
                        
                        html_parts.append('<div class="sol-sub-q">')
                        html_parts.append(f'<div class="sol-sub-text"><span class="sol-sub-num">{sq_num}</span> {sq_text}</div>')
                        html_parts.append(f'<div class="sol-sub-answer"><strong>{ans_direct}</strong> {sq_answer}</div>')
                        html_parts.append('</div>')
                
                elif p_type == 'math' and steps:
                    # مسألة حسابية مع خطوات
                    html_parts.append(f'<div class="sol-steps-title">{steps_label}</div>')
                    for j, step in enumerate(steps, 1):
                        step_html = format_math_text(step)
                        html_parts.append(
                            f'<div class="{step_class}">'
                            f'<span class="sol-step-num">{j}</span>'
                            f'{step_html}'
                            f'</div>'
                        )
                    if final:
                        html_parts.append(f'<div class="sol-final">{ans_label} {final}</div>')
                
                else:
                    # سؤال نظري - جواب مباشر
                    if final:
                        html_parts.append(f'<div class="sol-theory-answer"><strong>{ans_direct}</strong> {final}</div>')
                
                html_parts.append('</div>')  # end sol-part
        
        else:
            # === الهيكل المسطح القديم (backward compatibility) ===
            q_text = format_math_text(item.get('question', ''))
            q_type = item.get('type', 'math').lower()
            steps = item.get('steps', [])
            
            if not steps:
                q_type = 'theory'
            
            q_label_text = "السؤال" if lang == 'ar' else "Question"
            html_parts.append(f'<div class="sol-q-header">{q_label_text} {i}: {q_text}</div>')
            
            if q_type == 'theory' or not steps:
                final = format_math_text(item.get('final_answer', ''))
                html_parts.append(f'<div class="sol-theory-answer"><strong>{ans_direct}</strong> {final}</div>')
            else:
                html_parts.append(f'<div class="sol-steps-title">{steps_label}</div>')
                for j, step in enumerate(steps, 1):
                    step_html = format_math_text(step)
                    html_parts.append(
                        f'<div class="{step_class}">'
                        f'<span class="sol-step-num">{j}</span>'
                        f'{step_html}'
                        f'</div>'
                    )
                final = format_math_text(item.get('final_answer', ''))
                html_parts.append(f'<div class="sol-final">{ans_label} {final}</div>')
        
        html_parts.append('</div>')  # end sol-card
        
        if i < len(solutions):
            html_parts.append('<hr class="sol-divider">')
    
    html_parts.append('<div class="footer">Powered by: Firas APA</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_differences_pdf(comparisons, output_path, lang):
    """إنشاء PDF للفروقات والمقارنات بجداول احترافية"""
    title = "الفروقات والمقارنات" if lang == 'ar' else "Differences & Comparisons"
    aspect_label = "وجه المقارنة" if lang == 'ar' else "Aspect"
    
    html_parts = []
    html_parts.append(f'<div class="main-title">{escape_html(title)}</div>')
    html_parts.append('<hr class="title-line">')
    
    for i, comp in enumerate(comparisons, 1):
        comp_title = format_math_text(comp.get('title', ''))
        items = comp.get('items', [])
        criteria = comp.get('criteria', [])
        
        if not items or not criteria:
            continue
        
        # بطاقة المقارنة
        html_parts.append('<div class="comp-card">')
        
        # عنوان المقارنة
        html_parts.append(f'<div class="comp-title"><span class="comp-number">{i}</span> {comp_title}</div>')
        
        # بداية الجدول
        html_parts.append('<table class="comp-table">')
        
        # رأس الجدول
        html_parts.append('<thead><tr>')
        html_parts.append(f'<th class="aspect-header">{escape_html(aspect_label)}</th>')
        for item_name in items:
            html_parts.append(f'<th>{format_math_text(item_name)}</th>')
        html_parts.append('</tr></thead>')
        
        # صفوف المقارنة
        html_parts.append('<tbody>')
        for criterion in criteria:
            aspect = format_math_text(criterion.get('aspect', ''))
            values = criterion.get('values', [])
            
            html_parts.append('<tr>')
            html_parts.append(f'<td class="aspect-cell">{aspect}</td>')
            
            for idx in range(len(items)):
                val = format_math_text(values[idx]) if idx < len(values) else '-'
                html_parts.append(f'<td class="value-cell">{val}</td>')
            
            html_parts.append('</tr>')
        
        html_parts.append('</tbody>')
        html_parts.append('</table>')
        html_parts.append('</div>')  # end comp-card
    
    # تذييل
    footer_text = f"إجمالي المقارنات: {len(comparisons)}" if lang == 'ar' else f"Total comparisons: {len(comparisons)}"
    html_parts.append(f'<div class="footer">{footer_text}</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_exam_pdf(questions, output_path, lang):
    """إنشاء PDF الاختبار (بدون إجابات)"""
    if lang == 'ar':
        title = "اختبار"
        q_label = "السؤال"
        num_q = f"عدد الأسئلة: {len(questions)}"
        note = "أجب عن جميع الأسئلة التالية"
    else:
        title = "Exam"
        q_label = "Question"
        num_q = f"Number of questions: {len(questions)}"
        note = "Answer all of the following questions"
    
    html_parts = []
    
    # رأس الاختبار
    html_parts.append('<div class="exam-header">')
    html_parts.append(f'<div class="exam-header-title">{escape_html(title)}</div>')
    html_parts.append(f'<div class="exam-header-info">{escape_html(num_q)}<br>{escape_html(note)}</div>')
    html_parts.append('</div>')
    
    # الأسئلة
    for q in questions:
        q_num = q.get('question_num', 0)
        q_title = format_math_text(q.get('question_title', ''))
        parts = q.get('parts', [])
        
        html_parts.append('<div class="exam-q-card">')
        
        # عنوان السؤال
        header_text = f'{q_label} <span class="exam-q-num">{q_num}</span>'
        if q_title:
            header_text += f' : {q_title}'
        html_parts.append(f'<div class="exam-q-header">{header_text}</div>')
        
        # الفروع
        for part in parts:
            p_label = part.get('part_label', '')
            p_text = format_math_text(part.get('question_text', ''))
            
            html_parts.append('<div class="exam-part">')
            html_parts.append(f'<span class="exam-part-label">{p_label}</span>')
            html_parts.append(f'<div class="exam-part-text">{p_text}</div>')
            # خطوط للإجابة
            for _ in range(3):
                html_parts.append('<div class="exam-answer-line"></div>')
            html_parts.append('</div>')
        
        html_parts.append('</div>')  # end exam-q-card
    
    # تذييل
    footer = "انتهت الأسئلة - بالتوفيق" if lang == 'ar' else "End of exam - Good luck"
    html_parts.append(f'<div class="footer">{footer}</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_exam_solutions_pdf(questions, output_path, lang):
    """إنشاء PDF حلول الاختبار"""
    if lang == 'ar':
        title = "حلول الاختبار"
        q_label = "السؤال"
        ans_label = "الجواب:"
        answer_class = "exam-sol-answer"
    else:
        title = "Exam Solutions"
        q_label = "Question"
        ans_label = "Answer:"
        answer_class = "exam-sol-answer-en"
    
    html_parts = []
    html_parts.append(f'<div class="main-title">{escape_html(title)}</div>')
    html_parts.append('<hr class="title-line">')
    
    for q in questions:
        q_num = q.get('question_num', 0)
        q_title = format_math_text(q.get('question_title', ''))
        parts = q.get('parts', [])
        
        html_parts.append('<div class="exam-sol-card">')
        
        # عنوان السؤال
        header_text = f'{q_label} <span class="exam-q-num">{q_num}</span>'
        if q_title:
            header_text += f' : {q_title}'
        html_parts.append(f'<div class="exam-sol-header">{header_text}</div>')
        
        # الفروع مع الإجابات
        for part in parts:
            p_label = part.get('part_label', '')
            p_text = format_math_text(part.get('question_text', ''))
            p_answer = format_math_text(part.get('answer', ''))
            
            html_parts.append('<div class="exam-sol-part">')
            html_parts.append(f'<span class="exam-sol-part-label">{p_label}</span>')
            html_parts.append(f'<div class="exam-sol-q-text">{p_text}</div>')
            html_parts.append(f'<div class="{answer_class}"><strong>{ans_label}</strong> {p_answer}</div>')
            html_parts.append('</div>')
        
        html_parts.append('</div>')  # end exam-sol-card
    
    # تذييل
    footer_text = f"إجمالي الأسئلة: {len(questions)}" if lang == 'ar' else f"Total questions: {len(questions)}"
    html_parts.append(f'<div class="footer">{footer_text}</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_simple_explanation_pdf(data, output_path, lang):
    """إنشاء PDF للشرح المبسط بتصميم احترافي"""
    title = data.get('title', 'شرح مبسط' if lang == 'ar' else 'Simple Explanation')
    intro = format_math_text(data.get('introduction', ''))
    sections = data.get('sections', [])
    
    html_parts = []
    
    # العنوان الرئيسي
    html_parts.append(f'<div class="explain-main-title">{escape_html(title)}</div>')
    
    # المقدمة
    if intro:
        html_parts.append(f'<div class="explain-intro">{intro}</div>')
    
    # الأقسام
    for i, section in enumerate(sections, 1):
        s_title = escape_html(section.get('section_title', ''))
        s_icon = section.get('icon', '💡')
        s_explanation = format_math_text(section.get('explanation', ''))
        s_formula = format_math_text(section.get('key_formula', ''))
        s_formula_exp = format_math_text(section.get('formula_explanation', ''))
        s_example = format_math_text(section.get('real_life_example', ''))
        s_note = format_math_text(section.get('important_note', ''))
        
        html_parts.append('<div class="explain-section">')
        
        # عنوان القسم
        html_parts.append(f'<div class="explain-section-header">')
        html_parts.append(f'<span class="explain-section-num">{i}</span>')
        html_parts.append(f'<span class="explain-section-icon">{s_icon}</span>')
        html_parts.append(f'<span class="explain-section-title">{s_title}</span>')
        html_parts.append('</div>')
        
        # الشرح
        html_parts.append(f'<div class="explain-text">{s_explanation}</div>')
        
        # المعادلة
        if s_formula:
            formula_label = 'القانون الرئيسي' if lang == 'ar' else 'Key Formula'
            html_parts.append(f'<div class="explain-formula-box">')
            html_parts.append(f'<div class="explain-formula-label">📐 {formula_label}</div>')
            html_parts.append(f'<div class="explain-formula">{s_formula}</div>')
            if s_formula_exp:
                html_parts.append(f'<div class="explain-formula-desc">{s_formula_exp}</div>')
            html_parts.append('</div>')
        
        # مثال من الحياة
        if s_example:
            example_label = 'مثال من الحياة' if lang == 'ar' else 'Real-Life Example'
            html_parts.append(f'<div class="explain-example">')
            html_parts.append(f'<div class="explain-example-label">🌟 {example_label}</div>')
            html_parts.append(f'<div class="explain-example-text">{s_example}</div>')
            html_parts.append('</div>')
        
        # ملاحظة مهمة
        if s_note:
            note_label = 'ملاحظة مهمة' if lang == 'ar' else 'Important Note'
            html_parts.append(f'<div class="explain-note">')
            html_parts.append(f'<strong>⚠️ {note_label}:</strong> {s_note}')
            html_parts.append('</div>')
        
        html_parts.append('</div>')  # end explain-section
    
    footer_text = f'إجمالي الأقسام: {len(sections)}' if lang == 'ar' else f'Total sections: {len(sections)}'
    html_parts.append(f'<div class="footer">{footer_text}</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


def create_important_points_pdf(data, output_path, lang):
    """إنشاء PDF لأهم النقاط بتصميم احترافي"""
    title = data.get('title', 'أهم النقاط' if lang == 'ar' else 'Important Points')
    categories = data.get('categories', [])
    total = data.get('total_points', 0)
    
    # حساب إجمالي النقاط الفعلي
    actual_total = sum(len(cat.get('points', [])) for cat in categories)
    if total == 0:
        total = actual_total
    
    # خريطة ألوان الأهمية
    importance_colors = {
        'حرج': '#DC2626',
        'critical': '#DC2626',
        'مهم جداً': '#EA580C',
        'مهم جدا': '#EA580C',
        'very important': '#EA580C',
        'مهم': '#2563EB',
        'important': '#2563EB'
    }
    importance_labels = {
        'حرج': 'حرج',
        'critical': 'Critical',
        'مهم جداً': 'مهم جداً',
        'مهم جدا': 'مهم جداً',
        'very important': 'Very Important',
        'مهم': 'مهم',
        'important': 'Important'
    }
    
    html_parts = []
    
    # العنوان الرئيسي
    subtitle = f'{total} نقطة أساسية' if lang == 'ar' else f'{total} Key Points'
    html_parts.append(f'<div class="imp-main-title">{escape_html(title)}</div>')
    html_parts.append(f'<div class="imp-subtitle">{subtitle}</div>')
    
    point_counter = 0
    
    for cat in categories:
        cat_name = escape_html(cat.get('category_name', ''))
        cat_icon = cat.get('category_icon', '📌')
        points = cat.get('points', [])
        
        # عنوان الفئة
        html_parts.append(f'<div class="imp-category">')
        html_parts.append(f'<div class="imp-cat-header">')
        html_parts.append(f'<span class="imp-cat-icon">{cat_icon}</span>')
        html_parts.append(f'<span class="imp-cat-name">{cat_name}</span>')
        html_parts.append(f'<span class="imp-cat-count">{len(points)}</span>')
        html_parts.append('</div>')
        
        # النقاط
        for pt in points:
            point_counter += 1
            pt_title = format_math_text(pt.get('title', ''))
            pt_content = format_math_text(pt.get('content', ''))
            pt_importance = pt.get('importance', 'مهم').lower().strip()
            pt_tip = format_math_text(pt.get('tip', ''))
            
            imp_color = importance_colors.get(pt_importance, '#2563EB')
            imp_label = importance_labels.get(pt_importance, pt_importance)
            
            html_parts.append(f'<div class="imp-point">')
            html_parts.append(f'<div class="imp-point-header">')
            html_parts.append(f'<span class="imp-point-num" style="background:{imp_color}">{point_counter}</span>')
            html_parts.append(f'<span class="imp-point-title">{pt_title}</span>')
            html_parts.append(f'<span class="imp-badge" style="background:{imp_color}">{imp_label}</span>')
            html_parts.append('</div>')
            html_parts.append(f'<div class="imp-point-content">{pt_content}</div>')
            
            if pt_tip:
                tip_label = '💡 نصيحة:' if lang == 'ar' else '💡 Tip:'
                html_parts.append(f'<div class="imp-tip"><strong>{tip_label}</strong> {pt_tip}</div>')
            
            html_parts.append('</div>')  # end imp-point
        
        html_parts.append('</div>')  # end imp-category
    
    footer_text = f'إجمالي النقاط: {point_counter}' if lang == 'ar' else f'Total points: {point_counter}'
    html_parts.append(f'<div class="footer">{footer_text}</div>')
    
    html_body = '\n'.join(html_parts)
    build_html_pdf(html_body, lang, output_path)


# ===== الاختبار الكامل =====

async def generate_exam(query, context, content: str, user_id: int):
    """إنشاء اختبار كامل من 5 أسئلة كل سؤال بفرعين"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""أنت معلم خبير في إعداد الاختبارات. أنشئ اختباراً كاملاً من المحتوى التالي.

المحتوى:
{content}

المطلوب:
1. أنشئ 5 أسئلة بالضبط
2. كل سؤال يحتوي على فرعين (A و B)
3. نوّع الأسئلة: تعريفات، تعليلات، حسابات، مقارنات، شرح مفاهيم
4. الأسئلة يجب أن تغطي أجزاء مختلفة من المحتوى
5. اجعل الأسئلة واقعية ومناسبة للاختبارات المدرسية/الجامعية
6. قدّم الجواب الصحيح لكل فرع (سيستخدم في ملف الحلول المنفصل)
7. اكتب بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON بهذا الهيكل:
{{"exam": [
  {{
    "question_num": 1,
    "question_title": "عنوان السؤال الرئيسي (اختياري - يمكن تركه فارغاً)",
    "parts": [
      {{
        "part_label": "A",
        "question_text": "نص السؤال الفرعي",
        "answer": "الجواب الكامل والصحيح",
        "type": "theory" 
      }},
      {{
        "part_label": "B",
        "question_text": "نص السؤال الفرعي",
        "answer": "الجواب الكامل والصحيح",
        "type": "math"
      }}
    ]
  }}
]}}

ملاحظات:
- type يكون "theory" للأسئلة النظرية أو "math" للحسابية
- الجواب يجب أن يكون كاملاً وصحيحاً 100%
- للأسئلة الحسابية: اكتب الجواب مع خطوات الحل كاملة
- للأسئلة النظرية: اكتب الجواب بشكل واضح ومفصل"""
        else:
            prompt = f"""You are an expert teacher in creating exams. Create a complete exam from the following content.

Content:
{content}

Requirements:
1. Create exactly 5 questions
2. Each question has 2 parts (A and B)
3. Mix question types: definitions, explanations, calculations, comparisons, concept analysis
4. Questions should cover different parts of the content
5. Make questions realistic and suitable for school/university exams
6. Provide the correct answer for each part (will be used in a separate solutions file)
7. Write in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON with this structure:
{{"exam": [
  {{
    "question_num": 1,
    "question_title": "Main question title (optional - can be empty)",
    "parts": [
      {{
        "part_label": "A",
        "question_text": "Sub-question text",
        "answer": "Complete and correct answer",
        "type": "theory"
      }},
      {{
        "part_label": "B",
        "question_text": "Sub-question text",
        "answer": "Complete and correct answer",
        "type": "math"
      }}
    ]
  }}
]}}

Notes:
- type is "theory" for theoretical or "math" for calculation questions
- Answer must be complete and 100% correct
- For math: include full solution steps
- For theory: write clear and detailed answer"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a precise academic exam creator. CRITICAL: Create exactly 5 questions, each with exactly 2 parts (A and B). Answers must be 100% accurate. Return ONLY valid JSON. NO LaTeX. Use FRAC(num,den) for fractions and ^{exp} for exponents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=16000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        exam_questions = data.get('exam', [])
        
        # حفظ بيانات الاختبار لاستخدامها لاحقاً في ملف الحلول
        context.user_data['exam_data'] = {'questions': exam_questions, 'lang': lang}
        
        # إنشاء PDF الاختبار (بدون إجابات)
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_exam.pdf"
        create_exam_pdf(exam_questions, pdf_path, lang)
        
        # إرسال الاختبار
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Exam.pdf",
            caption="تم إنشاء الاختبار بنجاح ✅" if lang == 'ar' else "Exam created successfully ✅"
        )
        
        # إرسال زر الحلول
        solutions_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 أعطني ملف الحلول" if lang == 'ar' else "📋 Give me the solutions file", callback_data='exam_solutions')]
        ])
        
        await query.message.reply_text(
            "هل تريد ملف الحلول؟" if lang == 'ar' else "Want the solutions file?",
            reply_markup=solutions_keyboard
        )
        
    except Exception as e:
        print(f"Error generating exam: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


async def generate_exam_solutions(query, context, exam_data: dict, user_id: int):
    """إنشاء ملف حلول الاختبار"""
    try:
        questions = exam_data.get('questions', [])
        lang = exam_data.get('lang', 'ar')
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_exam_solutions.pdf"
        create_exam_solutions_pdf(questions, pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Exam_Solutions.pdf",
            caption="تم إنشاء ملف الحلول بنجاح ✅" if lang == 'ar' else "Solutions file created successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating exam solutions: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


# ===== الشرح المبسط =====

async def generate_simple_explanation(query, context, content: str, user_id: int):
    """إنشاء شرح مبسط ومفهوم للمادة"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""أنت معلم خبير متخصص في تبسيط المفاهيم العلمية. قم بشرح المحتوى التالي بأسلوب مبسط جداً ومفهوم.

المحتوى:
{content}

قواعد صارمة وملزمة:
1. اشرح كل مفهوم بأسلوب بسيط جداً كأنك تشرح لطالب مبتدئ
2. لا تحذف أي معلومة مهمة من الشرح الأصلي - يجب تغطية كل شيء
3. استخدم أمثلة من الحياة اليومية لتوضيح المفاهيم الصعبة
4. قسّم الشرح إلى أقسام واضحة حسب المواضيع
5. كل قسم يحتوي عنوان واضح وشرح مفصل ومبسط
6. إذا كانت هناك معادلات رياضية، اشرح كل رمز فيها بالتفصيل
7. إذا كانت هناك قوانين، اشرح متى ولماذا نستخدمها
8. اكتب بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON بهذا الهيكل:
{{"title": "عنوان الموضوع الرئيسي",
"introduction": "مقدمة بسيطة عن الموضوع في 2-3 جمل",
"sections": [
  {{
    "section_title": "عنوان القسم",
    "icon": "رمز مناسب مثل: 💡 أو 🔬 أو ⚡ أو 📐 أو 🧪 أو 🌊 أو ☀️ أو 🔋",
    "explanation": "الشرح المبسط والمفصل لهذا القسم",
    "key_formula": "المعادلة أو القانون الرئيسي إن وجد (اتركه فارغاً إذا لا يوجد)",
    "formula_explanation": "شرح بسيط لكل رمز في المعادلة (اتركه فارغاً إذا لا يوجد)",
    "real_life_example": "مثال من الحياة اليومية لتوضيح المفهوم",
    "important_note": "ملاحظة مهمة يجب تذكرها (اتركه فارغاً إذا لا يوجد)"
  }}
]}}

ملاحظات:
- اجعل الشرح شاملاً لكل المحتوى بدون حذف أي شيء مهم
- استخدم لغة بسيطة وسهلة الفهم
- كل قسم يجب أن يكون مفهوماً بذاته
- أضف أمثلة واقعية قدر الإمكان"""
        else:
            prompt = f"""You are an expert teacher specializing in simplifying scientific concepts. Explain the following content in a very simple and understandable way.

Content:
{content}

Strict rules:
1. Explain each concept in very simple terms as if explaining to a beginner student
2. Do NOT omit any important information from the original content - cover everything
3. Use real-life examples to clarify difficult concepts
4. Divide the explanation into clear sections by topic
5. Each section should have a clear title and detailed simple explanation
6. If there are mathematical equations, explain each symbol in detail
7. If there are laws, explain when and why we use them
8. Write in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON with this structure:
{{"title": "Main topic title",
"introduction": "Simple introduction about the topic in 2-3 sentences",
"sections": [
  {{
    "section_title": "Section title",
    "icon": "Appropriate icon like: 💡 or 🔬 or ⚡ or 📐 or 🧪 or 🌊 or ☀️ or 🔋",
    "explanation": "Simplified and detailed explanation of this section",
    "key_formula": "Main equation or law if any (leave empty if none)",
    "formula_explanation": "Simple explanation of each symbol in the equation (leave empty if none)",
    "real_life_example": "Real-life example to illustrate the concept",
    "important_note": "Important note to remember (leave empty if none)"
  }}
]}}

Notes:
- Make the explanation comprehensive covering all content without omitting anything important
- Use simple and easy-to-understand language
- Each section should be understandable on its own
- Add real-life examples as much as possible"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a brilliant teacher who makes complex topics simple and fun. Return ONLY valid JSON. NO LaTeX. Use FRAC(num,den) for fractions and ^{exp} for exponents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=16000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_simple_explanation.pdf"
        create_simple_explanation_pdf(data, pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Simple_Explanation.pdf",
            caption="تم إنشاء الشرح المبسط بنجاح ✅" if lang == 'ar' else "Simple explanation created successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating simple explanation: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


# ===== المهم =====

async def generate_important_points(query, context, content: str, user_id: int):
    """استخراج أهم النقاط والمفاهيم الأساسية"""
    try:
        lang = detect_language(content)
        
        if lang == 'ar':
            prompt = f"""أنت خبير أكاديمي متخصص في استخراج المعلومات الجوهرية. استخرج أهم النقاط والمفاهيم من المحتوى التالي.

المحتوى:
{content}

قواعد صارمة وملزمة:
1. استخرج فقط المعلومات الأكثر أهمية التي يجب حفظها وفهمها
2. رتب النقاط حسب الأهمية (الأهم أولاً)
3. صنّف النقاط إلى فئات واضحة (تعريفات مهمة، قوانين أساسية، مفاهيم جوهرية، نقاط يجب تذكرها)
4. كل نقطة يجب أن تكون مختصرة لكن واضحة ومفهومة
5. أضف مستوى الأهمية لكل نقطة (حرج، مهم جداً، مهم)
6. لا تضف معلومات غير موجودة في المحتوى
7. اكتب بالعربية فقط
{MATH_INSTRUCTIONS}
{JSON_RULES}

أرجع بصيغة JSON بهذا الهيكل:
{{"title": "عنوان الموضوع",
"total_points": 0,
"categories": [
  {{
    "category_name": "اسم الفئة (مثل: تعريفات أساسية)",
    "category_icon": "رمز مناسب مثل: 📌 أو 🔑 أو ⚡ أو 📐 أو 🎯 أو 💎 أو 🏆",
    "points": [
      {{
        "title": "عنوان النقطة المختصر",
        "content": "شرح النقطة بوضوح واختصار",
        "importance": "حرج أو مهم جداً أو مهم",
        "tip": "نصيحة للحفظ أو الفهم (اتركه فارغاً إذا لا يوجد)"
      }}
    ]
  }}
]}}

ملاحظات:
- استخرج 15-30 نقطة مهمة على الأقل
- لا تكرر نفس المعلومة
- اجعل كل نقطة قابلة للمراجعة السريعة قبل الاختبار
- ركز على ما يُسأل عنه عادةً في الاختبارات"""
        else:
            prompt = f"""You are an academic expert specializing in extracting essential information. Extract the most important points and concepts from the following content.

Content:
{content}

Strict rules:
1. Extract only the most important information that must be memorized and understood
2. Rank points by importance (most important first)
3. Categorize points into clear categories (key definitions, fundamental laws, core concepts, must-remember points)
4. Each point should be concise but clear and understandable
5. Add importance level for each point (critical, very important, important)
6. Do NOT add information not present in the content
7. Write in English only
{MATH_INSTRUCTIONS}
{JSON_RULES}

Return in JSON with this structure:
{{"title": "Topic title",
"total_points": 0,
"categories": [
  {{
    "category_name": "Category name (e.g., Key Definitions)",
    "category_icon": "Appropriate icon like: 📌 or 🔑 or ⚡ or 📐 or 🎯 or 💎 or 🏆",
    "points": [
      {{
        "title": "Short point title",
        "content": "Clear and concise explanation of the point",
        "importance": "critical or very important or important",
        "tip": "Tip for memorization or understanding (leave empty if none)"
      }}
    ]
  }}
]}}

Notes:
- Extract at least 15-30 important points
- Do not repeat the same information
- Make each point suitable for quick review before exams
- Focus on what is typically asked in exams"""

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a precise academic expert who identifies the most critical information students need. Return ONLY valid JSON. NO LaTeX. Use FRAC(num,den) for fractions and ^{exp} for exponents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=16000
        )
        
        result = response.choices[0].message.content
        data = safe_parse_json(result)
        
        pdf_path = f"{DOWNLOAD_DIR}/{user_id}_important_points.pdf"
        create_important_points_pdf(data, pdf_path, lang)
        
        await query.message.reply_document(
            document=open(pdf_path, 'rb'),
            filename="Important_Points.pdf",
            caption="تم استخراج أهم النقاط بنجاح ✅" if lang == 'ar' else "Important points extracted successfully ✅"
        )
        
    except Exception as e:
        print(f"Error generating important points: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


# ===== الشرح الصوتي =====

async def generate_audio_explanation(query, context, content: str, user_id: int, language: str):
    """إنشاء شرح صوتي"""
    try:
        
        if language == 'en':
            prompt = f"""Create a comprehensive audio explanation of the following content in English.

Content:
{content}

Requirements:
1. Explain in a clear, educational manner suitable for audio
2. Use simple language easy to understand when listening
3. Organize the explanation logically
4. Include all important points
5. Aim for 2-3 minutes of speaking time

Provide ONLY the explanation text, no formatting."""
            
            response = client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": "You are an expert educational narrator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            explanation_text = response.choices[0].message.content.strip()
            tts_language = 'en'
            
        else:
            prompt = f"""قم بإنشاء شرح صوتي شامل ومفصل للمحتوى التالي بالعربية.

المحتوى:
{content}

المتطلبات:
1. اشرح بطريقة واضحة وتعليمية مناسبة للصوت
2. استخدم لغة بسيطة سهلة الفهم
3. نظم الشرح بشكل منطقي
4. ضمّن جميع النقاط المهمة
5. اهدف لمدة 2-3 دقائق من الكلام

قدم فقط نص الشرح، بدون تنسيق."""
            
            response = client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": "أنت خبير في الشرح التعليمي الصوتي."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            explanation_text = response.choices[0].message.content.strip()
            tts_language = 'ar'
        
        audio_path = f"{DOWNLOAD_DIR}/{user_id}_explanation_{language}.mp3"
        tts = gTTS(text=explanation_text, lang=tts_language, slow=False, tld='com')
        tts.save(audio_path)
        
        with open(audio_path, 'rb') as audio_file:
            caption = "الشرح الصوتي بالعربية 🔊" if language == 'ar' else "Audio Explanation in English 🔊"
            await query.message.reply_voice(voice=audio_file, caption=caption)
        
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
    except Exception as e:
        print(f"Error generating audio: {e}")
        await query.message.reply_text(f"حدث خطأ في الشرح الصوتي: {str(e)}")




# إعداد التوكن من متغيّر البيئة (يُضبط في Render → Environment)
TOKEN = os.environ.get("TOKEN") or os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise SystemExit(
        "Missing TOKEN environment variable — set TOKEN in Render → Environment"
    )

# إعداد التسجيل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تجاهل أخطاء الشبكة المتكررة في اللوج
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext._updater").setLevel(logging.WARNING)


def get_main_keyboard():
    """إرجاع لوحة الأزرار الرئيسية"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 أسئلة MCQ (20+)", callback_data='mcq')],
        [InlineKeyboardButton("🔍 استخراج التعاليل (20+)", callback_data='explanations')],
        [InlineKeyboardButton("📖 استخراج التعاريف (20+)", callback_data='definitions')],
        [InlineKeyboardButton("📋 تلخيص شامل (20+)", callback_data='summary')],
        [InlineKeyboardButton("💡 حل جميع الأسئلة", callback_data='solutions')],
        [InlineKeyboardButton("📊 فروقات ومقارنات", callback_data='differences')],
        [InlineKeyboardButton("📄 اختبار كامل", callback_data='exam')],
        [InlineKeyboardButton("📖 شرح مبسط", callback_data='simple_explain')],
        [InlineKeyboardButton("⭐ المهم", callback_data='important')],
        [InlineKeyboardButton("🔊 شرح صوتي (عربي)", callback_data='audio_ar'),
         InlineKeyboardButton("🔊 Audio (EN)", callback_data='audio_en')]
    ])


async def error_handler(update, context):
    """معالجة الأخطاء العامة - تجاهل أخطاء الشبكة المؤقتة"""
    error = context.error
    if isinstance(error, (NetworkError, TimedOut)):
        logger.warning(f"Network error (will retry): {type(error).__name__}")
        return  # تجاهل - البوت سيعيد المحاولة تلقائياً
    if isinstance(error, RetryAfter):
        logger.warning(f"Rate limited, retrying after {error.retry_after}s")
        await asyncio.sleep(error.retry_after)
        return
    logger.error(f"Unhandled error: {error}", exc_info=context.error)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة ترحيب عند بدء البوت"""
    await update.message.reply_text(
        "مرحباً بك في بوت الدراسة المطور! 📚✨\n\n"
        "أرسل لي صورة أو ملف PDF وسأقوم بمساعدتك في:\n"
        "✅ حل الأسئلة والمسائل بالتفصيل\n"
        "✅ إنشاء أسئلة MCQ (20+ سؤال)\n"
        "✅ استخراج التعاريف والتعاليل (20+ عنصر)\n"
        "✅ تلخيص المحتوى بشكل شامل\n"
        "✅ فروقات ومقارنات بين المفاهيم\n"
        "✅ اختبار كامل مع الحلول\n"
        "✅ شرح مبسط ومفهوم للمادة\n"
        "✅ استخراج أهم النقاط والمفاهيم\n"
        "✅ شرح صوتي للمادة\n\n"
        "أنا جاهز لمساعدتك الآن! 🚀"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع الرسائل النصية"""
    message = update.message
    user_id = update.effective_user.id
    text = message.text.strip()
    
    if not text:
        return
    
    # حفظ النص كمحتوى
    context.user_data['content'] = text
    
    await message.reply_text("تم استلام النص! ماذا تريد أن أفعل؟", reply_markup=get_main_keyboard())


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع الصور والملفات المرفوعة"""
    message = update.message
    user_id = update.effective_user.id
    
    # إنشاء مجلد التحميل إذا لم يكن موجوداً
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    status_msg = await message.reply_text("جاري معالجة الملف... انتظر قليلاً ⏳")
    
    file_path = None
    content = ""
    
    try:
        if message.photo:
            photo_file = await message.photo[-1].get_file()
            file_path = f"{DOWNLOAD_DIR}/{user_id}_image.jpg"
            await photo_file.download_to_drive(file_path)
            content = await process_image(file_path)
            
        elif message.document:
            doc_file = await message.document.get_file()
            file_path = f"{DOWNLOAD_DIR}/{user_id}_{message.document.file_name}"
            await doc_file.download_to_drive(file_path)
            
            if message.document.mime_type == 'application/pdf':
                content = await process_pdf(file_path)
            else:
                await status_msg.edit_text("عذراً، أدعم حالياً الصور وملفات PDF فقط.")
                return

        if not content:
            await status_msg.edit_text("لم أتمكن من استخراج نص من الملف. تأكد من وضوح الصورة.")
            return

        # حفظ المحتوى في context لاستخدامه لاحقاً
        context.user_data['content'] = content
        
        await status_msg.edit_text("تم استخراج النص بنجاح! ماذا تريد أن أفعل؟", reply_markup=get_main_keyboard())
        
    except Exception as e:
        logger.error(f"Error in handle_document: {e}")
        await status_msg.edit_text(f"حدث خطأ أثناء المعالجة: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع ضغطات الأزرار"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    action = query.data
    
    # زر حلول الاختبار - يستخدم البيانات المحفوظة
    if action == 'exam_solutions':
        exam_data = context.user_data.get('exam_data')
        if not exam_data:
            await query.message.reply_text("عذراً، لم يتم العثور على بيانات الاختبار. أنشئ اختباراً جديداً أولاً.")
            return
        
        await query.message.reply_text("جاري إنشاء ملف الحلول... ⏳")
        try:
            await generate_exam_solutions(query, context, exam_data, user_id)
        except Exception as e:
            logger.error(f"Error generating exam solutions: {e}")
            await query.message.reply_text(f"حدث خطأ: {str(e)}")
        return
    
    # باقي الأزرار تحتاج المحتوى
    content = context.user_data.get('content')
    
    if not content:
        await query.message.reply_text("عذراً، انتهت الجلسة. يرجى إرسال الملف مرة أخرى.")
        return
        
    await query.message.reply_text("جاري العمل على طلبك... قد يستغرق ذلك دقيقة نظراً لحجم المحتوى ⏳")
    
    try:
        if action == 'mcq':
            await generate_mcq_quiz(query, context, content, user_id)
        elif action == 'explanations':
            await generate_explanations(query, context, content, user_id)
        elif action == 'definitions':
            await generate_definitions(query, context, content, user_id)
        elif action == 'summary':
            await generate_summary(query, context, content, user_id)
        elif action == 'solutions':
            await generate_solutions(query, context, content, user_id)
        elif action == 'differences':
            await generate_differences(query, context, content, user_id)
        elif action == 'exam':
            await generate_exam(query, context, content, user_id)
        elif action == 'simple_explain':
            await generate_simple_explanation(query, context, content, user_id)
        elif action == 'important':
            await generate_important_points(query, context, content, user_id)
        elif action == 'audio_ar':
            await generate_audio_explanation(query, context, content, user_id, 'ar')
        elif action == 'audio_en':
            await generate_audio_explanation(query, context, content, user_id, 'en')
            
    except Exception as e:
        logger.error(f"Error in button_callback: {e}")
        await query.message.reply_text(f"حدث خطأ: {str(e)}")


def main():
    """تشغيل البوت مع إعدادات اتصال محسنة"""
    # خادم الصحة في خيط منفصل (مطلوب لخدمة Render المجانية + UptimeRobot)
    threading.Thread(target=_start_health_server, daemon=True).start()

    # إعدادات اتصال قوية مع timeout عالي وإعادة محاولة
    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0,
        connection_pool_size=20,
    )
    
    application = (
        Application.builder()
        .token(TOKEN)
        .request(request)
        .get_updates_request(HTTPXRequest(
            connect_timeout=60.0,
            read_timeout=60.0,
            write_timeout=60.0,
            pool_timeout=60.0,
        ))
        .build()
    )

    # إضافة معالج الأخطاء
    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot started successfully! Waiting for messages...")
    
    # تشغيل مع إعادة محاولة تلقائية عند أخطاء الشبكة
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        poll_interval=1.0,
        timeout=30,
    )


if __name__ == '__main__':
    main()
