# Usar una imagen base de Python ligera
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para Playwright
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
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root PRIMERO
RUN useradd -m -s /bin/bash myuser && \
    mkdir -p /home/myuser/.cache && \
    chown -R myuser:myuser /home/myuser

# Establecer el directorio de trabajo
WORKDIR /app

# Cambiar al usuario no root ANTES de instalar dependencias
USER myuser

# Establecer variables de entorno para Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/home/myuser/.cache/ms-playwright
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copiar archivo de dependencias y instalar
COPY --chown=myuser:myuser requirements.txt .
RUN pip install --user --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright como usuario no-root
RUN /home/myuser/.local/bin/playwright install chromium

# Copiar el resto del código
COPY --chown=myuser:myuser core/ ./core/
COPY --chown=myuser:myuser scrapers/ ./scrapers/
COPY --chown=myuser:myuser test/ ./test/
COPY --chown=myuser:myuser entrypoint.sh .

# Dar permisos de ejecución al entrypoint
RUN chmod +x entrypoint.sh

# Agregar el directorio local de pip al PATH
ENV PATH="/home/myuser/.local/bin:${PATH}"

# Definir punto de entrada
ENTRYPOINT ["./entrypoint.sh"]