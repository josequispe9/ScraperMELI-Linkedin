# 🕷️ Sistema de Web Scraping Avanzado

Un sistema robusto y escalable para extracción automatizada de datos de LinkedIn Jobs y MercadoLibre Argentina, con análisis inteligente y exportación de reportes.

## 📋 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso Rápido](#-uso-rápido)
- [Documentación Detallada](#-documentación-detallada)

## ✨ Características Principales

### 🚀 **Scraping Avanzado**
- **Anti-detección**: Técnicas stealth para evitar bloqueos
- **Scraping asíncrono**: Procesamiento paralelo de alta velocidad
- **Reintentos inteligentes**: Recuperación automática de errores
- **Gestión de sesiones**: Login automático y persistencia de cookies

### 🎯 **Sitios Soportados**
- **LinkedIn Jobs Argentina**: Ofertas laborales, empresas, requisitos
- **MercadoLibre Argentina**: Productos, precios, vendedores, disponibilidad

### 📊 **Análisis Inteligente**
- **Procesamiento de datos**: Limpieza y normalización automática
- **Reportes CSV**: Análisis estadísticos listos para Excel/BI
- **Métricas de rendimiento**: Monitoreo completo del proceso
- **Visualización de datos**: Reportes categorizados y rankeados

### 🛡️ **Robustez y Confiabilidad**
- **Logging avanzado**: Trazabilidad completa con contexto
- **Manejo de errores**: Recuperación automática y alertas
- **Configuración flexible**: Adaptable a diferentes necesidades
- **Pool de navegadores**: Optimización de recursos

## 🏗️ Arquitectura del Sistema

```
web-scraping-system/
├── 📁 core/                    # Núcleo del sistema
│   ├── browser.py             # Gestión de navegadores Playwright
│   ├── config.py              # Configuraciones centralizadas
│   ├── logger.py              # Sistema de logging avanzado
│   └── utils.py               # Utilidades y decoradores
├── 📁 scrapers/               # Módulos de extracción
│   ├── linkedin/              # Scraper de LinkedIn Jobs
│   └── mercadolibre/          # Scraper de MercadoLibre
├── 📁 processor/              # Análisis y procesamiento
│   └── data_processor.py      # Limpieza y análisis de datos
├── 📁 data/                   # Datos extraídos (CSV)
├── 📁 logs/                   # Archivos de log
```

## 🚀 Instalación

### Instalación Automática

```bash
# 1. Clonar repositorio
git clone https://github.com/josequispe9/ScraperMELI-Linkedin.git
cd ScraperMELI-Linkedin

# 2. Levantar los servicios con Docker Compose
docker-compose up --build


## ⚙️ Configuración

### Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# LinkedIn
LINKEDIN_EMAIL=tu_email@example.com
LINKEDIN_PASSWORD=tu_password_seguro

```

### Configuración Básica

```python
# core/config.py - Personalizar según necesidades
BROWSER_CONFIG = BrowserConfig(
    headless=True,           # Modo sin ventana gráfica
    timeout=30000,           # 30 segundos timeout
    slow_mo=100             # Delay entre acciones (ms)
)

SCRAPING_CONFIG = ScrapingConfig(
    max_retries=3,          # Reintentos por error
    delay_range=(2, 5),     # Delay aleatorio entre páginas
    concurrent_pages=3,     # Páginas simultáneas
    batch_size=50          # Elementos por lote
)
```

## 🎯 Uso Rápido

### Scraping de LinkedIn Jobs

```bash
# Términos por defecto
python -m scrapers.linkedin.main

# Términos específicos
python -m scrapers.linkedin.main --terms "python developer" "data scientist"

# Limitar resultados
python -m scrapers.linkedin.main --max-jobs 10

# Modo de prueba (rápido)
python -m scrapers.linkedin.main --test
```

### Scraping de MercadoLibre

```bash
# Productos por defecto
python -m scrapers.mercadolibre.main

# Términos específicos
python -m scrapers.mercadolibre.main --terms "notebook" "smartphone"

# Limitar productos
python -m scrapers.mercadolibre.main --max-products 30

# Modo de prueba
python -m scrapers.mercadolibre.main --test
```

### Análisis de Datos

```bash
# Analizar datos extraídos
python processor/data_processor.py
```


## 📚 Documentación Detallada

### Documentación por Módulo

| Módulo | Documentación | Descripción |
|--------|---------------|-------------|
| **Core** | [📖 doc_core.md](core/doc_core.md) | Sistema base, configuración, logging y navegadores |
| **LinkedIn** | [📖 doc_linkedin.md](scrapers/linkedin/doc_linkedin.md) | Scraper de empleos, API reference y troubleshooting |
| **MercadoLibre** | [📖 doc_mercadolibre.md](scrapers/mercadolibre/doc_mercadolibre.md) | Scraper de productos y análisis de precios |
| **Processor** | [📖 doc_processor.md](processor/doc_processor.md) | Procesamiento de datos y generación de reportes |


## 📈 Resultados y Reportes

### Reportes de LinkedIn
- **empleos_por_fecha_publicacion.csv**: Empleos por antigüedad
- **empleos_por_nivel_experiencia.csv**: Distribución por seniority
- **empleos_por_modalidad.csv**: Remoto vs Presencial vs Híbrido

### Reportes de MercadoLibre
- **productos_por_rango_precio.csv**: Análisis de precios por categoría
- **productos_por_vendedor.csv**: Estadísticas de vendedores
- **productos_por_factor_personalizado.csv**: Ranking de valor

### Reporte Resumen
- **reporte_resumen.csv**: Estadísticas generales consolidadas
