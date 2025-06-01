"""
Scraper para MercadoLibre Argentina
Extrae información de productos con manejo de paginación y detección anti-bot
Versión actualizada que utiliza los métodos robustos del parser mejorado
"""

import asyncio
import random
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
import re

from playwright.async_api import Page, Browser, BrowserContext
from core.browser import BrowserManager, PagePool
from core.config import MERCADOLIBRE_CONFIG, BROWSER_CONFIG, SCRAPING_CONFIG
from core.logger import get_logger, LogContext, PerformanceLogger, LogConfig
from core.utils import retry_async, random_delay, safe_extract_text, safe_extract_attribute
from .parser import MercadoLibreParser, ProductData

config = LogConfig(json_format=False)
logger = get_logger("scraper", config)
perf_logger = PerformanceLogger(logger)

class MercadoLibreScraper:
    def __init__(self):
        self.browser_manager = BrowserManager()
        self.parser = MercadoLibreParser()
        self.base_url = MERCADOLIBRE_CONFIG.base_url
        self.max_products = MERCADOLIBRE_CONFIG.max_products_per_term
        self.scraped_products = []
        
    async def scrape_products(self, search_terms: List[str] = None) -> List[ProductData]:
        """Scraper principal para extraer productos de MercadoLibre"""
        if not search_terms:
            search_terms = MERCADOLIBRE_CONFIG.search_terms
            
        perf_logger.start("MercadoLibre scraping session")
        
        try:
            await self.browser_manager.start()
            context = await self.browser_manager.create_context()
            
            # Configurar headers adicionales para evitar detección
            await self._setup_stealth_headers(context)
            
            all_products = []
            
            for i, term in enumerate(search_terms):
                with LogContext(logger, search_term=term):
                    logger.info(f"Iniciando scraping para término {i+1}/{len(search_terms)}: {term}")
                    products = await self._scrape_search_term(context, term)
                    all_products.extend(products)
                    
                    logger.info(f"Completado término '{term}': {len(products)} productos extraídos")
                    
                    # Delay entre términos de búsqueda para evitar rate limiting
                    if i < len(search_terms) - 1:  # No delay después del último término
                        await random_delay(5, 10)
            
            # Eliminar duplicados basados en URL
            unique_products = self._remove_duplicates(all_products)
            logger.info(f"Productos únicos después de eliminar duplicados: {len(unique_products)}")
            
            perf_logger.end(success=True, total_products=len(unique_products))
            return unique_products
            
        except Exception as e:
            logger.error(f"Error en sesión de scraping: {e}", exc_info=True)
            perf_logger.end(success=False)
            raise
        finally:
            await self.browser_manager.close()
    
    def _remove_duplicates(self, products: List[ProductData]) -> List[ProductData]:
        """Eliminar productos duplicados basados en URL"""
        seen_urls = set()
        unique_products = []
        
        for product in products:
            if product.url_producto != "N/A" and product.url_producto not in seen_urls:
                seen_urls.add(product.url_producto)
                unique_products.append(product)
            elif product.url_producto == "N/A":
                # Para productos sin URL, usar el título como identificador
                product_key = f"{product.producto}_{product.precio}_{product.vendedor}"
                if product_key not in seen_urls:
                    seen_urls.add(product_key)
                    unique_products.append(product)
        
        return unique_products
    
    async def _setup_stealth_headers(self, context: BrowserContext):
        """Configurar headers adicionales para evitar detección"""
        await context.add_init_script("""
            // Sobrescribir propiedades de detección de automatización
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Simular plugins del navegador
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Configurar idiomas
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-AR', 'es', 'en'],
            });
            
            // Simular canvas fingerprinting
            const getContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type) {
                if (type === '2d') {
                    const context = getContext.apply(this, arguments);
                    const originalFillText = context.fillText;
                    context.fillText = function() {
                        return originalFillText.apply(this, arguments);
                    };
                    return context;
                }
                return getContext.apply(this, arguments);
            };
        """)
    
    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _scrape_search_term(self, context: BrowserContext, search_term: str) -> List[ProductData]:
        """Scraper para un término de búsqueda específico con paginación mejorada"""
        page = await context.new_page()
        products = []
        
        try:
            # Construir URL de búsqueda con parámetros adicionales
            search_url = self._build_search_url(search_term)
            logger.info(f"Navegando a: {search_url}")
            
            await page.goto(search_url, wait_until='networkidle', timeout=30000)
            await self._handle_bot_detection(page)
            
            # Verificar que la página cargó correctamente
            if not await self._verify_search_page_loaded(page):
                logger.error("La página de búsqueda no cargó correctamente")
                return []
            
            page_number = 1
            products_scraped = 0
            consecutive_empty_pages = 0
            max_empty_pages = 2
            
            while products_scraped < self.max_products and consecutive_empty_pages < max_empty_pages:
                logger.info(f"Procesando página {page_number} para término '{search_term}'")
                
                # Esperar a que carguen los productos usando el parser mejorado
                await self._wait_for_products_to_load(page)
                
                # Extraer productos usando el método robusto del parser
                page_products = await self._extract_products_from_page_robust(page, search_term)
                
                if not page_products:
                    consecutive_empty_pages += 1
                    logger.warning(f"Página {page_number} sin productos (intento {consecutive_empty_pages}/{max_empty_pages})")
                    
                    if consecutive_empty_pages >= max_empty_pages:
                        logger.info("Alcanzado límite de páginas vacías consecutivas")
                        break
                else:
                    consecutive_empty_pages = 0  # Reset contador
                    products.extend(page_products)
                    products_scraped += len(page_products)
                    
                    logger.info(f"✅ Extraídos {len(page_products)} productos de página {page_number}")
                
                # Verificar si hemos alcanzado el límite
                if products_scraped >= self.max_products:
                    logger.info(f"Alcanzado límite máximo de productos: {self.max_products}")
                    break
                    
                # Buscar siguiente página
                next_page_url = await self._get_next_page_url(page)
                if not next_page_url:
                    logger.info("No hay más páginas disponibles")
                    break
                
                # Navegar a siguiente página con delay
                await random_delay(3, 6)
                logger.debug(f"Navegando a página {page_number + 1}: {next_page_url}")
                
                try:
                    await page.goto(next_page_url, wait_until='networkidle', timeout=30000)
                    await self._handle_bot_detection(page)
                    page_number += 1
                except Exception as e:
                    logger.error(f"Error navegando a siguiente página: {e}")
                    break
            
            logger.info(f"✅ Scraping completado para '{search_term}': {len(products)} productos en {page_number} páginas")
            return products[:self.max_products]
            
        except Exception as e:
            logger.error(f"❌ Error scrapeando término '{search_term}': {e}", exc_info=True)
            raise
        finally:
            await page.close()
    
    def _build_search_url(self, search_term: str) -> str:
        """Construir URL de búsqueda optimizada"""
        # Limpiar y formatear término de búsqueda
        clean_term = search_term.strip().replace(' ', '-')
        clean_term = re.sub(r'[^\w\-]', '', clean_term)
        
        # URL base con parámetros para mejorar resultados
        base_url = f"{self.base_url}/{clean_term}"
        
        # Agregar parámetros útiles
        params = [
            "_NoThanks=pagination",  # Evitar infinite scroll
            "sort=relevance",  # Ordenar por relevancia
        ]
        
        if params:
            base_url += "?" + "&".join(params)
        
        return base_url
    
    async def _verify_search_page_loaded(self, page: Page) -> bool:
        """Verificar que la página de búsqueda cargó correctamente"""
        try:
            # Verificar que no sea una página de error
            page_text = await page.text_content('body') or ""
            
            error_indicators = [
                'página no encontrada',
                'error 404',
                'no se encontró',
                'page not found'
            ]
            
            for indicator in error_indicators:
                if indicator.lower() in page_text.lower():
                    logger.error(f"Página de error detectada: {indicator}")
                    return False
            
            # Verificar presencia de elementos de búsqueda
            search_indicators = [
                '.ui-search-results',
                '.ui-search-result',
                '[data-testid="results"]'
            ]
            
            for selector in search_indicators:
                if await page.query_selector(selector):
                    return True
            
            logger.warning("No se encontraron indicadores de página de búsqueda válida")
            return False
            
        except Exception as e:
            logger.error(f"Error verificando página de búsqueda: {e}")
            return False
    
    async def _wait_for_products_to_load(self, page: Page):
        """Esperar a que los productos se carguen usando múltiples estrategias"""
        # Lista de selectores que indican que los productos han cargado
        product_indicators = [
            '.ui-search-results__item',
            '.ui-search-result',
            '[data-testid="result-item"]',
            'a[href*="MLA-"]'
        ]
        
        # Intentar cada selector con timeout progresivo
        for i, selector in enumerate(product_indicators):
            try:
                timeout = 5000 + (i * 2000)  # Timeout progresivo
                await page.wait_for_selector(selector, timeout=timeout)
                logger.debug(f"✅ Productos cargados detectados con selector: {selector}")
                
                # Esperar un poco más para asegurar carga completa
                await asyncio.sleep(1)
                return
                
            except Exception as e:
                logger.debug(f"❌ Selector {selector} no funcionó: {e}")
                continue
        
        # Si llegamos aquí, ningún selector funcionó
        logger.warning("⚠️ No se pudo confirmar carga de productos - continuando con extracción")
        await asyncio.sleep(3)  # Espera adicional por si acaso
    
    async def _extract_products_from_page_robust(self, page: Page, search_term: str) -> List[ProductData]:
        """Extraer productos usando el método robusto del parser"""
        products = []
        
        try:
            # Usar el método robusto del parser para encontrar elementos
            product_elements = await self.parser.find_product_elements_robust(page)
            
            if not product_elements:
                logger.warning("❌ No se encontraron elementos de producto con método robusto")
                return []
            
            logger.info(f"📦 Encontrados {len(product_elements)} elementos de producto")
            
            # Procesar cada elemento
            successful_extractions = 0
            for i, element in enumerate(product_elements):
                try:
                    product_data = await self.parser.parse_product_element(element, search_term)
                    
                    if product_data:
                        products.append(product_data)
                        successful_extractions += 1
                        logger.debug(f"✅ Producto {i+1} extraído: {product_data.producto[:50]}...")
                    else:
                        logger.debug(f"❌ Producto {i+1} no válido - descartado")
                        
                except Exception as e:
                    logger.debug(f"❌ Error parseando producto {i+1}: {e}")
                    continue
            
            logger.info(f"✅ Extracción exitosa: {successful_extractions}/{len(product_elements)} productos")
            return products
            
        except Exception as e:
            logger.error(f"❌ Error en extracción robusta de productos: {e}", exc_info=True)
            return []
    
    async def _handle_bot_detection(self, page: Page):
        """Manejar posible detección de bot con estrategias mejoradas"""
        try:
            # Verificar múltiples indicadores de detección
            detection_indicators = {
                'captcha': [
                    '[data-testid="captcha"]',
                    '.captcha-container',
                    'iframe[src*="captcha"]',
                    '.g-recaptcha',
                    '#captcha'
                ],
                'rate_limit': [
                    'demasiadas solicitudes',
                    'many requests',
                    'blocked',
                    'verificación',
                    'robot',
                    'automatizado'
                ],
                'access_denied': [
                    'acceso denegado',
                    'access denied',
                    'forbidden',
                    '403'
                ]
            }
            
            # Verificar CAPTCHA
            for selector in detection_indicators['captcha']:
                if await page.query_selector(selector):
                    logger.warning("🤖 CAPTCHA detectado - aplicando estrategia de espera")
                    await self._handle_captcha_detection(page)
                    return
            
            # Verificar rate limiting por contenido de texto
            page_text = await page.text_content('body') or ""
            page_text_lower = page_text.lower()
            
            for category, indicators in detection_indicators.items():
                if category == 'captcha':
                    continue  # Ya verificado arriba
                    
                for indicator in indicators:
                    if indicator.lower() in page_text_lower:
                        logger.warning(f"🚫 Detección de {category}: {indicator}")
                        await self._handle_detection_delay(category)
                        return
            
            # Verificar si la página parece estar bloqueada
            if len(page_text.strip()) < 100:
                logger.warning("⚠️ Página con contenido mínimo - posible bloqueo")
                await random_delay(5, 10)
                        
        except Exception as e:
            logger.debug(f"Error en detección de bot: {e}")
    
    async def _handle_captcha_detection(self, page: Page):
        """Manejar detección de CAPTCHA"""
        logger.warning("🤖 CAPTCHA detectado - implementando espera extendida")
        
        # Espera extendida con logging
        wait_time = random.randint(15, 30)
        logger.info(f"⏳ Esperando {wait_time} segundos para bypass de CAPTCHA...")
        
        for i in range(wait_time):
            if i % 5 == 0:
                logger.debug(f"⏳ Esperando... {wait_time - i} segundos restantes")
            await asyncio.sleep(1)
        
        # Intentar hacer scroll para simular actividad humana
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(2)
            await page.evaluate("window.scrollTo(0, 0)")
        except:
            pass
    
    async def _handle_detection_delay(self, detection_type: str):
        """Manejar diferentes tipos de detección con delays apropiados"""
        delay_configs = {
            'rate_limit': (10, 20),
            'access_denied': (15, 25),
            'default': (5, 10)
        }
        
        min_delay, max_delay = delay_configs.get(detection_type, delay_configs['default'])
        wait_time = random.randint(min_delay, max_delay)
        
        logger.warning(f"🚫 Detección tipo '{detection_type}' - esperando {wait_time} segundos")
        await asyncio.sleep(wait_time)
    
    async def _get_next_page_url(self, page: Page) -> Optional[str]:
        """Obtener URL de la siguiente página con selectores mejorados"""
        try:
            # Selectores mejorados para paginación
            next_selectors = [
                '.andes-pagination__button--next:not(.andes-pagination__button--disabled)',
                '.ui-search-pagination [title="Siguiente"]',
                'a[aria-label="Siguiente"]',
                '.ui-search-pagination .ui-search-pagination__button--next',
                '[data-testid="pagination-next"]',
                'a[href*="_Desde_"]:contains("Siguiente")',
                '.ui-search-pagination a[href*="_Desde_"]:last-child'
            ]
            
            for selector in next_selectors:
                try:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        # Verificar que el botón no esté deshabilitado
                        disabled = await next_button.get_attribute('disabled')
                        aria_disabled = await next_button.get_attribute('aria-disabled')
                        
                        if disabled or aria_disabled == 'true':
                            continue
                        
                        href = await next_button.get_attribute('href')
                        if href:
                            # Construir URL completa si es relativa
                            if href.startswith('/'):
                                full_url = f"https://listado.mercadolibre.com.ar{href}"
                            else:
                                full_url = href
                            
                            logger.debug(f"✅ Siguiente página encontrada: {full_url}")
                            return full_url
                            
                except Exception as e:
                    logger.debug(f"Error con selector de paginación {selector}: {e}")
                    continue
            
            # Método alternativo: buscar enlaces con patrón de paginación
            try:
                all_links = await page.query_selector_all('a[href*="_Desde_"]')
                for link in all_links:
                    href = await link.get_attribute('href')
                    if href and '_Desde_' in href:
                        # Extraer número de página actual y siguiente
                        current_url = page.url
                        if self._is_next_page(current_url, href):
                            if href.startswith('/'):
                                return f"https://listado.mercadolibre.com.ar{href}"
                            return href
            except Exception as e:
                logger.debug(f"Error en método alternativo de paginación: {e}")
            
            logger.debug("❌ No se encontró enlace a siguiente página")
            return None
            
        except Exception as e:
            logger.debug(f"Error obteniendo URL de siguiente página: {e}")
            return None
    
    def _is_next_page(self, current_url: str, next_href: str) -> bool:
        """Verificar si el href corresponde a la siguiente página"""
        try:
            # Extraer números de página de las URLs
            current_match = re.search(r'_Desde_(\d+)', current_url)
            next_match = re.search(r'_Desde_(\d+)', next_href)
            
            if current_match and next_match:
                current_page = int(current_match.group(1))
                next_page = int(next_match.group(1))
                return next_page > current_page
            elif next_match and not current_match:
                # Primera página a segunda página
                return True
                
            return False
        except:
            return False
    
    async def scrape_product_details(self, product_urls: List[str]) -> List[Dict[str, Any]]:
        """Scraper detallado para URLs específicas de productos"""
        detailed_products = []
        
        if not product_urls:
            logger.warning("No se proporcionaron URLs para scraping detallado")
            return []
        
        try:
            await self.browser_manager.start()
            context = await self.browser_manager.create_context()
            await self._setup_stealth_headers(context)
            
            # Usar pool de páginas para paralelización controlada
            page_pool = PagePool(context, size=min(SCRAPING_CONFIG.concurrent_pages, 3))
            await page_pool.initialize()
            
            logger.info(f"Iniciando scraping detallado de {len(product_urls)} productos")
            
            for i, url in enumerate(product_urls[:self.max_products]):
                try:
                    logger.debug(f"Procesando detalle {i+1}/{len(product_urls)}: {url}")
                    
                    page = await page_pool.get_page()
                    product_detail = await self._scrape_single_product_detail(page, url)
                    
                    if product_detail:
                        detailed_products.append(product_detail)
                        logger.debug(f"✅ Detalle extraído: {product_detail.get('titulo', 'N/A')[:50]}...")
                    else:
                        logger.debug(f"❌ No se pudo extraer detalle de: {url}")
                    
                    await page_pool.return_page(page)
                    
                    # Delay entre productos para evitar rate limiting
                    if i < len(product_urls) - 1:
                        await random_delay(2, 4)
                    
                except Exception as e:
                    logger.error(f"❌ Error scrapeando detalle de {url}: {e}")
                    continue
            
            await page_pool.close_all()
            logger.info(f"✅ Scraping detallado completado: {len(detailed_products)} productos procesados")
            return detailed_products
            
        except Exception as e:
            logger.error(f"❌ Error en scraping de detalles: {e}", exc_info=True)
            raise
        finally:
            await self.browser_manager.close()
    
    @retry_async(max_retries=2, delay=3, backoff=1.5)
    async def _scrape_single_product_detail(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        """Scraper para detalle individual de producto con reintentos"""
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await self._handle_bot_detection(page)
            
            # Verificar que la página del producto cargó correctamente
            if not await self._verify_product_page_loaded(page):
                logger.warning(f"Página de producto no cargó correctamente: {url}")
                return None
            
            # Usar el parser para extraer detalles
            product_detail = await self.parser.parse_product_detail_page(page, url)
            
            if product_detail and product_detail.get('titulo'):
                return product_detail
            else:
                logger.debug(f"Detalle de producto vacío o inválido: {url}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error scrapeando detalle de producto {url}: {e}")
            return None
    
    async def _verify_product_page_loaded(self, page: Page) -> bool:
        """Verificar que la página de producto individual cargó correctamente"""
        try:
            # Selectores que indican una página de producto válida
            product_indicators = [
                '.ui-pdp-title',
                '.ui-pdp-price',
                '[data-testid="price"]',
                '.ui-pdp-container'
            ]
            
            for selector in product_indicators:
                if await page.query_selector(selector):
                    return True
            
            # Verificar por contenido de texto
            page_text = await page.text_content('body') or ""
            if 'precio' in page_text.lower() and len(page_text.strip()) > 200:
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error verificando página de producto: {e}")
            return False