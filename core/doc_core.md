# Documentación del Módulo Core

El módulo `core/` contiene los componentes fundamentales y reutilizables para el sistema de web scraping. Proporciona funcionalidades esenciales como configuración, logging avanzado, gestión de navegadores y utilidades comunes.

## Estructura del Módulo

```
core/
├── __init__.py          # Inicialización del módulo
├── config.py            # Configuraciones centralizadas
├── logger.py            # Sistema de logging avanzado
├── utils.py             # Utilidades y decoradores
└── browser.py           # Gestión de navegadores con Playwright
```

## Componentes Principales

### 1. config.py - Configuración Centralizada

Maneja todas las configuraciones del sistema usando dataclasses y variables de entorno.

#### Clases de Configuración

##### `BrowserConfig`
Configuración para el navegador y comportamiento de scraping.

```python
from core.config import BROWSER_CONFIG

# Propiedades principales
BROWSER_CONFIG.headless           # Modo headless (True/False)
BROWSER_CONFIG.timeout           # Timeout en ms (30000)
BROWSER_CONFIG.viewport_width    # Ancho de viewport (1920)
BROWSER_CONFIG.viewport_height   # Alto de viewport (1080)
BROWSER_CONFIG.slow_mo          # Delay entre acciones en ms (100)

# Métodos
user_agent = BROWSER_CONFIG.get_random_user_agent()  # User agent aleatorio
```

##### `ScrapingConfig`
Configuración general para el proceso de scraping.

```python
from core.config import SCRAPING_CONFIG

SCRAPING_CONFIG.max_retries        # Reintentos máximos (3)
SCRAPING_CONFIG.delay_range        # Rango de delays (2, 5) segundos
SCRAPING_CONFIG.concurrent_pages   # Páginas concurrentes (3)
SCRAPING_CONFIG.batch_size        # Tamaño de lote (50)
```

##### `LinkedInConfig`
Configuración específica para LinkedIn (requiere variables de entorno).

```python
from core.config import LINKEDIN_CONFIG

# Variables de entorno requeridas:
# LINKEDIN_EMAIL=tu_email@example.com
# LINKEDIN_PASSWORD=tu_password
```

##### `MercadoLibreConfig`
Configuración para MercadoLibre Argentina.

```python
from core.config import MERCADOLIBRE_CONFIG

MERCADOLIBRE_CONFIG.base_url              # URL base
MERCADOLIBRE_CONFIG.search_terms          # Términos de búsqueda
MERCADOLIBRE_CONFIG.max_products_per_term # Productos máximos por término
```

### 2. logger.py - Sistema de Logging Avanzado

Sistema de logging especializado para web scraping con soporte para JSON, contexto y métricas de performance.

#### Clases Principales

##### `LogConfig`
Configuración del sistema de logging.

```python
from core.logger import LogConfig

config = LogConfig(
    level="INFO",              # Nivel de logging
    console_enabled=True,      # Habilitar salida a consola
    file_enabled=True,         # Habilitar archivo de log
    json_format=False,         # Formato JSON (True) o coloreado (False)
    log_dir="logs",           # Directorio de logs
    max_file_size=10*1024*1024, # Tamaño máximo de archivo (10MB)
    backup_count=5            # Archivos de respaldo
)
```

##### `ScrapingLogger`
Logger principal con contexto y métricas.

```python
from core.logger import get_logger

logger = get_logger("mi_scraper")

# Logging básico
logger.debug("Mensaje de debug")
logger.info("Información general")
logger.warning("Advertencia")
logger.error("Error", exc_info=True)
logger.critical("Error crítico")

# Establecer contexto global
logger.set_context(scraper_name="linkedin", session_id="12345")

# Limpiar contexto
logger.clear_context()
```

##### `PerformanceLogger`
Logger especializado para métricas de rendimiento.

```python
from core.logger import get_performance_logger

perf_logger = get_performance_logger()

# Medir operación
perf_logger.start("scraping_productos")
# ... operación ...
perf_logger.end(success=True, items_scraped=150)
```

##### `LogContext`
Context manager para contexto temporal.

```python
from core.logger import LogContext, get_logger

logger = get_logger()

with LogContext(logger, url="example.com", page=1) as ctx_logger:
    ctx_logger.info("Scrapeando página")  # Incluirá contexto automáticamente
```

#### Características del Sistema de Logging

- **Formato JSON**: Para integración con sistemas de monitoreo
- **Colores en consola**: Para desarrollo y debugging
- **Rotación de archivos**: Gestión automática de tamaño de logs
- **Contexto dinámico**: Información contextual en cada log
- **Métricas de performance**: Duración y éxito de operaciones
- **Stack traces**: Información detallada de errores

### 3. utils.py - Utilidades y Decoradores

Contiene funciones de utilidad y decoradores para operaciones comunes de scraping.

#### Funciones Principales

##### `random_delay()`
Introduce delays aleatorios para simular comportamiento humano.

```python
from core.utils import random_delay

await random_delay(min_delay=1, max_delay=3)  # Delay entre 1-3 segundos
```

##### `retry_async()` - Decorador
Decorador para reintentos automáticos con backoff exponencial.

```python
from core.utils import retry_async

@retry_async(max_retries=3, delay=1, backoff=2)
async def scrape_page(url):
    # Función que puede fallar
    response = await fetch_page(url)
    return response

# La función se reintentará automáticamente en caso de error
result = await scrape_page("https://example.com")
```

##### `safe_extract_text()`
Extracción segura de texto desde elementos de Playwright.

```python
from core.utils import safe_extract_text

# Con selector
text = await safe_extract_text(page, "h1.title", default="Sin título")

# Con elemento directo
element = await page.query_selector("h1")
text = await safe_extract_text(element, default="Sin título")
```

##### `safe_extract_attribute()`
Extracción segura de atributos.

```python
from core.utils import safe_extract_attribute

# Extraer href de un enlace
href = await safe_extract_attribute(page, "href", "a.link", default="#")

# Con elemento directo
link = await page.query_selector("a")
href = await safe_extract_attribute(link, "href", default="#")
```

### 4. browser.py - Gestión de Navegadores

Gestión avanzada de navegadores usando Playwright con funcionalidades de stealth mode, pool de páginas y manejo de sesiones.

#### Clases Principales

##### `BrowserManager`
Gestor principal del navegador y contextos.

```python
from core.browser import BrowserManager

manager = BrowserManager()
await manager.start()  # Inicializar navegador

# Crear contexto con sesión
context = await manager.create_context(storage_state="session.json")

# Guardar sesión actual
await manager.save_session(context, "nueva_session.json")

# Cerrar todo
await manager.close()
```

##### Context Manager `managed_browser()`
Manejo automático del ciclo de vida del navegador.

```python
from core.browser import managed_browser

async with managed_browser() as manager:
    context = await manager.create_context()
    page = await context.new_page()
    
    await page.goto("https://example.com")
    # ... scraping ...
    
# El navegador se cierra automáticamente
```

##### `PagePool`
Pool de páginas para scraping paralelo.

```python
from core.browser import PagePool

context = await manager.create_context()
pool = PagePool(context, size=5)  # 5 páginas en el pool
await pool.initialize()

# Usar página del pool
page = await pool.get_page()
await page.goto("https://example.com")
# ... scraping ...
await pool.return_page(page)  # Devolver al pool

await pool.close_all()  # Cerrar todas las páginas
```

#### Características del Navegador

- **Modo Stealth**: Evita detección de automatización
- **User Agents rotativos**: Diferentes user agents para cada contexto
- **Gestión de sesiones**: Guardar y cargar estados de login
- **Pool de páginas**: Scraping paralelo eficiente
- **Configuración anti-detección**: Headers y propiedades optimizadas

## Uso Integrado

### Ejemplo Básico

```python
import asyncio
from core.browser import managed_browser
from core.logger import get_logger
from core.utils import retry_async, random_delay

# Configurar logger
logger = get_logger("mi_scraper")

@retry_async(max_retries=3)
async def scrape_website():
    async with managed_browser() as manager:
        context = await manager.create_context()
        page = await context.new_page()
        
        logger.info("Iniciando scraping")
        await page.goto("https://example.com")
        
        # Delay humano
        await random_delay(2, 4)
        
        # Extraer datos
        title = await page.title()
        logger.info(f"Título extraído: {title}")
        
        return {"title": title}

# Ejecutar
asyncio.run(scrape_website())
```

### Ejemplo Avanzado con Contexto y Métricas

```python
from core.logger import get_logger, get_performance_logger, LogContext
from core.browser import managed_browser, PagePool

logger = get_logger("advanced_scraper")
perf_logger = get_performance_logger()

async def advanced_scraping():
    with LogContext(logger, scraper_type="advanced", session_id="abc123"):
        perf_logger.start("scraping_completo")
        
        async with managed_browser() as manager:
            context = await manager.create_context()
            pool = PagePool(context, size=3)
            await pool.initialize()
            
            # Scraping paralelo
            tasks = []
            urls = ["https://site1.com", "https://site2.com", "https://site3.com"]
            
            for url in urls:
                task = scrape_single_url(pool, url)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            await pool.close_all()
            
        perf_logger.end(success=True, urls_scraped=len(urls))
        return results

async def scrape_single_url(pool: PagePool, url: str):
    page = await pool.get_page()
    try:
        await page.goto(url)
        title = await page.title()
        return {"url": url, "title": title}
    finally:
        await pool.return_page(page)
```

## Variables de Entorno Requeridas

Crear un archivo `.env` en la raíz del proyecto:

```env
# LinkedIn (opcional, solo si usas LinkedInConfig)
LINKEDIN_EMAIL=tu_email@example.com
LINKEDIN_PASSWORD=tu_password_seguro
```

## Instalación de Dependencias

```bash
pip install playwright python-json-logger python-dotenv asyncio
playwright install chromium
```

## Mejores Prácticas

1. **Usar context managers**: Siempre usar `managed_browser()` para gestión automática
2. **Configurar logging apropiado**: Usar `json_format=True` en producción, `False` en desarrollo
3. **Establecer contexto**: Usar `LogContext` o `set_context()` para trazabilidad
4. **Delays humanos**: Siempre usar `random_delay()` entre operaciones
5. **Manejo de errores**: Usar `@retry_async` para operaciones que pueden fallar
6. **Pool de páginas**: Para scraping masivo, usar `PagePool` para mejor rendimiento
7. **Guardar sesiones**: Reutilizar sesiones de login cuando sea posible

## Logging y Monitoreo

Los logs se guardan en:
- **Consola**: Formato coloreado para desarrollo
- **Archivos**: `logs/scraper_YYYYMMDD.log` con rotación automática
- **Formato JSON**: Para integración con sistemas de monitoreo

Ejemplo de log JSON:
```json
{
  "timestamp": "2024-06-04T15:30:45.123Z",
  "name": "scraper",
  "levelname": "INFO",
  "message": "Scraping completado",
  "context": {
    "url": "https://example.com",
    "session_id": "abc123"
  },
  "duration_ms": 1250
}
```