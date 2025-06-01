"""
Scraper para MercadoLibre Argentina - Versión Corregida
Basado en el código funcional de meli.py con estructura robusta
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
        self.base_url = "https://listado.mercadolibre.com.ar"
        self.max_products = getattr(MERCADOLIBRE_CONFIG, 'max_products_per_term', 50)
        self.scraped_products = []
        
    async def scrape_products(self, search_terms: List[str] = None) -> List[ProductData]:
        """Scraper principal para extraer productos de MercadoLibre"""
        if not search_terms:
            search_terms = getattr(MERCADOLIBRE_CONFIG, 'search_terms', ['zapatillas'])
            
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
                    if i < len(search_terms) - 1:
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
        """)
    
    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _scrape_search_term(self, context: BrowserContext, search_term: str) -> List[ProductData]:
        """Scraper para un término de búsqueda específico - simplificado pero robusto"""
        page = await context.new_page()
        products = []
        
        try:
            # Construir URL de búsqueda simple (como en meli.py)
            search_url = f"{self.base_url}/{search_term.replace(' ', '-')}"
            logger.info(f"Navegando a: {search_url}")
            
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await self._handle_bot_detection(page)
            
            # Esperar a que carguen los productos
            await self._wait_for_products_to_load(page)
            
            # Extraer productos de la primera página usando método robusto
            page_products = await self._extract_products_from_page_simple(page, search_term)
            
            if page_products:
                products.extend(page_products)
                logger.info(f"✅ Extraídos {len(page_products)} productos de la primera página")
                
                # Enriquecer con detalles adicionales (ubicación y reputación)
                enriched_products = await self._enrich_products_with_details(context, page_products)
                return enriched_products
            else:
                logger.warning("No se encontraron productos en la página")
                return []
            
        except Exception as e:
            logger.error(f"❌ Error scrapeando término '{search_term}': {e}", exc_info=True)
            raise
        finally:
            await page.close()
    
    async def _wait_for_products_to_load(self, page: Page):
        """Esperar a que los productos se carguen - versión simplificada"""
        try:
            # Usar el selector principal que sabemos que funciona
            await page.wait_for_selector(".ui-search-layout__item", timeout=15000)
            logger.debug("✅ Productos cargados correctamente")
            await asyncio.sleep(2)  # Pequeña espera adicional para asegurar carga completa
        except Exception as e:
            logger.warning(f"⚠️ Timeout esperando productos, continuando: {e}")
            await asyncio.sleep(3)
    
    async def _extract_products_from_page_simple(self, page: Page, search_term: str) -> List[ProductData]:
        """Extraer productos usando el método simple pero efectivo de meli.py"""
        products = []
        
        try:
            # Usar el selector que sabemos que funciona
            product_elements = await page.query_selector_all(".ui-search-layout__item")
            logger.info(f"Se encontraron {len(product_elements)} productos en la página")
            
            # Limitar a los primeros productos para evitar problemas
            limited_elements = product_elements[:min(20, self.max_products)]
            
            for i, producto in enumerate(limited_elements):
                try:
                    product_data = ProductData()
                    product_data.categoria = search_term
                    
                    # Extraer información básica usando selectores comprobados
                    # Nombre
                    nombre_el = await producto.query_selector(".poly-component__title")
                    nombre = await nombre_el.inner_text() if nombre_el else "Sin nombre"
                    product_data.producto = nombre.strip()
                    
                    # Precio
                    precio_el = await producto.query_selector(".andes-money-amount__fraction")
                    precio = await precio_el.inner_text() if precio_el else "Sin precio"
                    product_data.precio = f"${precio.strip()}"
                    
                    # Link
                    link_el = await producto.query_selector("a.poly-component__title")
                    link = await link_el.get_attribute("href") if link_el else "Sin link"
                    product_data.url_producto = link.strip() if link else "N/A"
                    
                    # Vendedor
                    vendedor_el = await producto.query_selector(".poly-component__seller")
                    vendedor = await vendedor_el.inner_text() if vendedor_el else "Desconocido"
                    product_data.vendedor = vendedor.strip()
                    
                    # Envío gratis
                    envio = "Sí" if await producto.query_selector(".poly-component__shipping") else "No"
                    product_data.envio_gratis = envio
                    
                    # Valores por defecto
                    product_data.disponible = "Sí"
                    product_data.ubicacion = "Desconocida"
                    product_data.reputacion_vendedor = "Desconocida"
                    
                    # Validar que el producto tenga información mínima
                    if (product_data.producto != "Sin nombre" and 
                        product_data.precio != "$Sin precio" and
                        len(product_data.producto.strip()) > 5):
                        
                        products.append(product_data)
                        logger.debug(f"✅ Producto {i+1} extraído: {product_data.producto[:50]}...")
                    else:
                        logger.debug(f"❌ Producto {i+1} descartado por datos incompletos")
                    
                except Exception as e:
                    logger.debug(f"❌ Error al extraer producto {i+1}: {e}")
                    continue
            
            logger.info(f"✅ Extracción completada: {len(products)} productos válidos")
            return products
            
        except Exception as e:
            logger.error(f"❌ Error en extracción de productos: {e}", exc_info=True)
            return []
    
    async def _enrich_products_with_details(self, context: BrowserContext, products: List[ProductData]) -> List[ProductData]:
        """Enriquecer productos con detalles adicionales (ubicación y reputación)"""
        if not products:
            return products
        
        logger.info(f"Enriqueciendo {len(products)} productos con detalles adicionales...")
        enriched_products = []
        
        # Procesar solo algunos productos para evitar rate limiting
        products_to_enrich = products[:min(10, len(products))]
        
        for i, product in enumerate(products_to_enrich):
            try:
                if product.url_producto and product.url_producto.startswith("http"):
                    logger.debug(f"Enriqueciendo producto {i+1}/{len(products_to_enrich)}: {product.producto[:30]}...")
                    
                    # Crear nueva página para el producto
                    detail_page = await context.new_page()
                    
                    try:
                        await detail_page.goto(product.url_producto, wait_until='domcontentloaded', timeout=20000)
                        await asyncio.sleep(2)  # Pequeña espera
                        
                        # Extraer ubicación
                        try:
                            ubicacion_el = await detail_page.query_selector("div.ui-seller-info__status-info__subtitle")
                            if ubicacion_el:
                                ubicacion = await ubicacion_el.inner_text()
                                if ubicacion and ubicacion.strip():
                                    product.ubicacion = ubicacion.strip()
                                    logger.debug(f"✅ Ubicación extraída: {product.ubicacion}")
                        except Exception as e:
                            logger.debug(f"Error extrayendo ubicación: {e}")
                        
                        # Extraer reputación
                        try:
                            reputacion_el = await detail_page.query_selector("div.ui-seller-info__header__title + div span")
                            if reputacion_el:
                                # Intentar obtener texto primero
                                reputacion_text = await reputacion_el.inner_text()
                                if reputacion_text and reputacion_text.strip():
                                    product.reputacion_vendedor = reputacion_text.strip()
                                else:
                                    # Si no hay texto, intentar con clase CSS
                                    reputacion_class = await reputacion_el.get_attribute("class")
                                    if reputacion_class:
                                        product.reputacion_vendedor = reputacion_class
                                
                                logger.debug(f"✅ Reputación extraída: {product.reputacion_vendedor}")
                        except Exception as e:
                            logger.debug(f"Error extrayendo reputación: {e}")
                        
                    finally:
                        await detail_page.close()
                    
                    # Delay entre productos para evitar rate limiting
                    if i < len(products_to_enrich) - 1:
                        await random_delay(1, 3)
                
                enriched_products.append(product)
                
            except Exception as e:
                logger.debug(f"Error enriqueciendo producto {i+1}: {e}")
                # Agregar el producto sin enriquecer
                enriched_products.append(product)
                continue
        
        # Agregar los productos restantes sin enriquecer
        if len(products) > len(products_to_enrich):
            enriched_products.extend(products[len(products_to_enrich):])
        
        logger.info(f"✅ Productos enriquecidos: {len(enriched_products)}")
        return enriched_products
    
    async def _handle_bot_detection(self, page: Page):
        """Manejar posible detección de bot - versión simplificada"""
        try:
            # Verificar CAPTCHA básico
            captcha_selectors = [
                '[data-testid="captcha"]',
                '.captcha-container',
                '.g-recaptcha'
            ]
            
            for selector in captcha_selectors:
                if await page.query_selector(selector):
                    logger.warning("🤖 CAPTCHA detectado - aplicando espera")
                    await random_delay(10, 20)
                    return
            
            # Verificar contenido de la página
            page_text = await page.text_content('body') or ""
            page_text_lower = page_text.lower()
            
            suspicious_phrases = [
                'demasiadas solicitudes',
                'many requests',
                'blocked',
                'robot',
                'verificación'
            ]
            
            for phrase in suspicious_phrases:
                if phrase in page_text_lower:
                    logger.warning(f"🚫 Posible detección: {phrase}")
                    await random_delay(8, 15)
                    return
            
            # Si la página tiene muy poco contenido, puede estar bloqueada
            if len(page_text.strip()) < 200:
                logger.warning("⚠️ Página con contenido mínimo - posible bloqueo")
                await random_delay(5, 10)
                        
        except Exception as e:
            logger.debug(f"Error en detección de bot: {e}")
    
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
            
            logger.info(f"Iniciando scraping detallado de {len(product_urls)} productos")
            
            # Procesar productos secuencialmente para evitar problemas
            for i, url in enumerate(product_urls[:self.max_products]):
                try:
                    logger.debug(f"Procesando detalle {i+1}/{len(product_urls)}: {url}")
                    
                    page = await context.new_page()
                    product_detail = await self._scrape_single_product_detail(page, url)
                    await page.close()
                    
                    if product_detail:
                        detailed_products.append(product_detail)
                        logger.debug(f"✅ Detalle extraído: {product_detail.get('titulo', 'N/A')[:50]}...")
                    else:
                        logger.debug(f"❌ No se pudo extraer detalle de: {url}")
                    
                    # Delay entre productos
                    if i < len(product_urls) - 1:
                        await random_delay(2, 4)
                    
                except Exception as e:
                    logger.error(f"❌ Error scrapeando detalle de {url}: {e}")
                    continue
            
            logger.info(f"✅ Scraping detallado completado: {len(detailed_products)} productos procesados")
            return detailed_products
            
        except Exception as e:
            logger.error(f"❌ Error en scraping de detalles: {e}", exc_info=True)
            raise
        finally:
            await self.browser_manager.close()
    
    @retry_async(max_retries=2, delay=3, backoff=1.5)
    async def _scrape_single_product_detail(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        """Scraper para detalle individual de producto"""
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await self._handle_bot_detection(page)
            
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


# ============================================== #
#    Función de utilidad para pruebas rápidas    #
# ============================================== #


async def test_scraper(search_terms: List[str] = None):
    """Función de prueba para el scraper"""
    if not search_terms:
        search_terms = ["zapatillas"]
    
    scraper = MercadoLibreScraper()
    
    try:
        products = await scraper.scrape_products(search_terms)
        
        print(f"\n✅ Scraping completado exitosamente!")
        print(f"📦 Total de productos extraídos: {len(products)}")
        
        if products:
            print(f"\n📋 Muestra de productos extraídos:")
            for i, product in enumerate(products[:3]):
                print(f"\n{i+1}. {product.producto}")
                print(f"   Precio: {product.precio}")
                print(f"   Vendedor: {product.vendedor}")
                print(f"   Ubicación: {product.ubicacion}")
                print(f"   Envío gratis: {product.envio_gratis}")
                print(f"   URL: {product.url_producto[:80]}...")
        
        return products
        
    except Exception as e:
        print(f"❌ Error en scraping: {e}")
        raise


if __name__ == "__main__":
    # Ejecutar prueba
    asyncio.run(test_scraper(["zapatillas"]))