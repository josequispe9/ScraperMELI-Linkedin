# Usar una imagen base de Python ligera
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para Playwright + dos2unix
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libu2f-udev \
    libvulkan1 \
    libxss1 \
    xdg-utils \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root
RUN useradd -m -s /bin/bash myuser && \
    mkdir -p /home/myuser/.cache && \
    chown -R myuser:myuser /home/myuser

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar TODOS los archivos como root para poder modificar permisos
COPY requirements.txt ./
COPY core/ ./core/
COPY scrapers/ ./scrapers/
COPY test/ ./test/
COPY entrypoint.sh ./

# CRÍTICO: Convertir terminadores de línea y dar permisos ANTES de cambiar usuario
RUN dos2unix entrypoint.sh && \
    chmod +x entrypoint.sh && \
    chown -R myuser:myuser /app

# Cambiar al usuario no root
USER myuser

# Establecer variables de entorno para Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/home/myuser/.cache/ms-playwright
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/home/myuser/.local/bin:${PATH}"

# Instalar dependencias de Python
RUN pip install --user --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright
RUN playwright install chromium

# Definir punto de entrada
ENTRYPOINT ["./entrypoint.sh"]