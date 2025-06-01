#!/bin/bash

# Instalar los navegadores si no están disponibles
playwright install --with-deps chromium

# Lógica para elegir el scraper
if [ "$1" = "linkedin" ]; then
    exec python scrapers/linkedin/main.py
elif [ "$1" = "mercadolibre" ]; then
    exec python scrapers/mercadolibre/main.py
else
    echo "Uso: Especifique 'linkedin' o 'mercadolibre' como argumento"
    exit 1
fi
