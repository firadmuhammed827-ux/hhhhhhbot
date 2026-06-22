FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# مكتبات النظام:
#   - WeasyPrint يحتاج Pango/Cairo/GDK-Pixbuf لإنشاء PDF
#   - pdf2image يحتاج poppler-utils
#   - خطوط Noto للعربية + Liberation/DejaVu للاتيني
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        poppler-utils \
        fonts-noto-core \
        fonts-dejavu-core \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Render يحقن متغيّر PORT؛ خادم الصحة يستمع عليه
EXPOSE 10000

CMD ["python", "bot.py"]
