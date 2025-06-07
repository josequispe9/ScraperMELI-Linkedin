#!/bin/bash

# Verificar que los navegadores estén instalados
if [ ! -d "$PLAYWRIGHT_BROWSERS_PATH" ] || [ -z "$(ls -A $PLAYWRIGHT_BROWSERS_PATH 2>/dev/null)" ]; then
    echo "🚀 Instalando navegadores de Playwright..."
    playwright install chromium
    echo "✅ Navegadores instalados correctamente"
fi

if [ -z "$1" ]; then
    # Modo desarrollo: contenedor activo esperando comandos
    echo "🔧 Modo desarrollo: contenedor activo esperando comandos"
    echo "📁 Directorio de trabajo: $(pwd)"
    echo "👤 Usuario actual: $(whoami)"
    echo "🌐 Navegadores Playwright: $PLAYWRIGHT_BROWSERS_PATH"
    echo ""
    echo "Comandos disponibles:"
    echo "  python -m scrapers.linkedin.main"
    echo "  python -m scrapers.mercadolibre.main"
    echo ""
    echo "🎯 Usa 'Attach to Running Container' en VSCode para conectarte"
    tail -f /dev/null
elif [ "$1" = "linkedin" ]; then
    echo "🚀 Ejecutando scraper de LinkedIn..."
    exec python -m scrapers.linkedin.main
elif [ "$1" = "mercadolibre" ]; then
    echo "🚀 Ejecutando scraper de MercadoLibre..."
    exec python -m scrapers.mercadolibre.main
else
    echo "❌ Uso: Especifique 'linkedin' o 'mercadolibre' como argumento"
    echo "   O ejecute sin argumentos para modo desarrollo"
    exit 1
fi