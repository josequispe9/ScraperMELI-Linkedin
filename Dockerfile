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
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar archivo de dependencias primero para cacheo eficiente
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Instalar los navegadores de Playwright
RUN playwright install --with-deps

# Copiar el código del proyecto
COPY core/ ./core/
COPY scrapers/ ./scrapers/
COPY test/ ./test/
COPY entrypoint.sh .

# Crear usuario no root
RUN useradd -m myuser

# Permisos de ejecución y entorno
RUN chmod +x entrypoint.sh
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Cambiar al usuario no root
USER myuser

# Instalar los navegadores al inicio del contenedor
ENTRYPOINT ["./entrypoint.sh"]
CMD ["sleep", "infinity"]
