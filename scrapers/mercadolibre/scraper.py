"""
Scraper para MercadoLibre Argentina
Extrae información de productos con manejo de paginación y detección anti-bot
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
from core.logger import get_logger, LogContext, PerformanceLogger
from core.utils import retry_async, random_delay, safe_extract_text, safe_extract_attribute
from .parser import MercadoLibreParser, ProductData

logger = get_logger("mercadolibre_scraper")
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
            
            for term in search_terms:
                with LogContext(logger, search_term=term):
                    logger.info(f"Iniciando scraping para término: {term}")
                    products = await self._scrape_search_term(context, term)
                    all_products.extend(products)
                    
                    # Delay entre términos de búsqueda
                    await random_delay(3, 6)
            
            perf_logger.end(success=True, total_products=len(all_products))
            return all_products
            
        except Exception as e:
            logger.error(f"Error en sesión de scraping: {e}", exc_info=True)
            perf_logger.end(success=False)
            raise
        finally:
            await self.browser_manager.close()
    
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
        """Scraper para un término de búsqueda específico con paginación"""
        page = await context.new_page()
        products = []
        
        try:
            # Construir URL de búsqueda
            search_url = f"{self.base_url}/{search_term.replace(' ', '-')}"
            logger.info(f"Navegando a: {search_url}")
            
            await page.goto(search_url, wait_until='networkidle')
            await self._handle_bot_detection(page)
            
            page_number = 1
            products_scraped = 0
            
            while products_scraped < self.max_products:
                logger.info(f"Procesando página {page_number}")
                
                # Esperar a que carguen los productos
                await page.wait_for_selector('.ui-search-results__item', timeout=10000)
                
                # Extraer productos de la página actual
                page_products = await self._extract_products_from_page(page, search_term)
                
                if not page_products:
                    logger.warning(f"No se encontraron productos en página {page_number}")
                    break
                
                products.extend(page_products)
                products_scraped += len(page_products)
                
                logger.info(f"Extraídos {len(page_products)} productos de página {page_number}")
                
                # Verificar si hay más páginas
                if products_scraped >= self.max_products:
                    break
                    
                next_page_url = await self._get_next_page_url(page)
                if not next_page_url:
                    logger.info("No hay más páginas disponibles")
                    break
                
                # Navegar a siguiente página
                await random_delay(2, 4)
                await page.goto(next_page_url, wait_until='networkidle')
                await self._handle_bot_detection(page)
                
                page_number += 1
            
            logger.info(f"Scraping completado para '{search_term}': {len(products)} productos")
            return products[:self.max_products]  # Limitar al máximo configurado
            
        except Exception as e:
            logger.error(f"Error scrapeando término '{search_term}': {e}", exc_info=True)
            raise
        finally:
            await page.close()
    
    async def _handle_bot_detection(self, page: Page):
        """Manejar posible detección de bot"""
        try:
            # Verificar si aparece CAPTCHA o página de verificación
            captcha_selectors = [
                '[data-testid="captcha"]',
                '.captcha-container',
                'iframe[src*="captcha"]',
                '.g-recaptcha'
            ]
            
            for selector in captcha_selectors:
                element = await page.query_selector(selector)
                if element:
                    logger.warning("Detección de CAPTCHA - implementar manejo manual si es necesario")
                    await random_delay(5, 10)
                    break
            
            # Verificar mensaje de "demasiadas solicitudes"
            rate_limit_texts = [
                'demasiadas solicitudes',
                'many requests',
                'blocked',
                'verificación'
            ]
            
            page_text = await page.text_content('body') or ""
            for text in rate_limit_texts:
                if text.lower() in page_text.lower():
                    logger.warning(f"Posible rate limiting detectado: {text}")
                    await random_delay(10, 20)
                    break
                    
        except Exception as e:
            logger.debug(f"Error en detección de bot: {e}")
    
    async def _extract_products_from_page(self, page: Page, search_term: str) -> List[ProductData]:
        """Extraer productos de la página actual"""
        products = []
        
        try:
            # Obtener todos los elementos de producto
            product_elements = await page.query_selector_all('.ui-search-results__item')
            
            if not product_elements:
                logger.warning("No se encontraron elementos de producto con selector principal")
                # Intentar selector alternativo
                product_elements = await page.query_selector_all('[data-testid="result-item"]')
            
            logger.debug(f"Encontrados {len(product_elements)} elementos de producto")
            
            for element in product_elements:
                try:
                    product_data = await self.parser.parse_product_element(element, search_term)
                    if product_data:
                        products.append(product_data)
                        
                except Exception as e:
                    logger.debug(f"Error parseando producto individual: {e}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Error extrayendo productos de página: {e}", exc_info=True)
            return []
    
    async def _get_next_page_url(self, page: Page) -> Optional[str]:
        """Obtener URL de la siguiente página"""
        try:
            # Buscar botón "Siguiente"
            next_selectors = [
                '.andes-pagination__button--next:not(.andes-pagination__button--disabled)',
                '.ui-search-pagination [title="Siguiente"]',
                'a[aria-label="Siguiente"]',
                '.ui-search-pagination .ui-search-pagination__button--next'
            ]
            
            for selector in next_selectors:
                next_button = await page.query_selector(selector)
                if next_button:
                    href = await next_button.get_attribute('href')
                    if href:
                        # Construir URL completa si es relativa
                        if href.startswith('/'):
                            return f"https://listado.mercadolibre.com.ar{href}"
                        return href
            
            return None
            
        except Exception as e:
            logger.debug(f"Error obteniendo URL de siguiente página: {e}")
            return None
    
    async def scrape_product_details(self, product_urls: List[str]) -> List[Dict[str, Any]]:
        """Scraper detallado para URLs específicas de productos"""
        detailed_products = []
        
        try:
            await self.browser_manager.start()
            context = await self.browser_manager.create_context()
            
            # Usar pool de páginas para paralelización
            page_pool = PagePool(context, size=SCRAPING_CONFIG.concurrent_pages)
            await page_pool.initialize()
            
            for url in product_urls[:self.max_products]:
                try:
                    page = await page_pool.get_page()
                    product_detail = await self._scrape_single_product_detail(page, url)
                    
                    if product_detail:
                        detailed_products.append(product_detail)
                    
                    await page_pool.return_page(page)
                    await random_delay(1, 3)
                    
                except Exception as e:
                    logger.error(f"Error scrapeando detalle de {url}: {e}")
                    continue
            
            await page_pool.close_all()
            return detailed_products
            
        except Exception as e:
            logger.error(f"Error en scraping de detalles: {e}", exc_info=True)
            raise
        finally:
            await self.browser_manager.close()
    
    @retry_async(max_retries=2, delay=3)
    async def _scrape_single_product_detail(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        """Scraper para detalle individual de producto"""
        try:
            await page.goto(url, wait_until='networkidle')
            await self._handle_bot_detection(page)
            
            return await self.parser.parse_product_detail_page(page, url)
            
        except Exception as e:
            logger.error(f"Error scrapeando detalle de producto {url}: {e}")
            return None