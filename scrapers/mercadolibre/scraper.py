"""
Scraper optimizado para MercadoLibre Argentina
Versión simplificada y optimizada basada en el parser mejorado
"""

import asyncio
import random
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from playwright.async_api import Page, Browser, BrowserContext
from core.browser import BrowserManager
from core.config import MERCADOLIBRE_CONFIG, SCRAPING_CONFIG
from core.logger import get_logger, LogContext, PerformanceLogger, LogConfig
from core.utils import retry_async, random_delay
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
        
    async def scrape_products(self, search_terms: List[str] = None) -> List[ProductData]:
        """Scraper principal optimizado"""
        if not search_terms:
            search_terms = getattr(MERCADOLIBRE_CONFIG, 'search_terms', ['zapatillas'])
            
        perf_logger.start("MercadoLibre scraping session")
        
        try:
            await self.browser_manager.start()
            context = await self.browser_manager.create_context()
            await self._setup_stealth_context(context)
            
            all_products = []
            
            for i, term in enumerate(search_terms):
                with LogContext(logger, search_term=term):
                    logger.info(f"Scraping término {i+1}/{len(search_terms)}: {term}")
                    
                    products = await self._scrape_search_term(context, term)
                    all_products.extend(products)
                    
                    logger.info(f"Completado '{term}': {len(products)} productos")
                    
                    # Delay entre términos
                    if i < len(search_terms) - 1:
                        await random_delay(3, 7)
            
            # Eliminar duplicados
            unique_products = self._remove_duplicates(all_products)
            logger.info(f"Productos únicos: {len(unique_products)}")
            
            perf_logger.end(success=True, total_products=len(unique_products))
            return unique_products
            
        except Exception as e:
            logger.error(f"Error en scraping: {e}")
            perf_logger.end(success=False)
            raise
        finally:
            await self.browser_manager.close()
    
    def _remove_duplicates(self, products: List[ProductData]) -> List[ProductData]:
        """Eliminar duplicados por URL y título+precio"""
        seen = set()
        unique = []
        
        for product in products:
            # Usar URL como identificador principal
            if product.url_producto != "N/A":
                key = product.url_producto
            else:
                # Fallback: título + precio + vendedor
                key = f"{product.producto}_{product.precio}_{product.vendedor}"
            
            if key not in seen:
                seen.add(key)
                unique.append(product)
        
        return unique
    
    async def _setup_stealth_context(self, context: BrowserContext):
        """Configuración stealth simplificada"""
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['es-AR', 'es']});
        """)
    
    @retry_async(max_retries=3, delay=2, backoff=2)
    async def _scrape_search_term(self, context: BrowserContext, search_term: str) -> List[ProductData]:
        """Scraper optimizado para un término de búsqueda"""
        page = await context.new_page()
        
        try:
            # URL de búsqueda
            search_url = f"{self.base_url}/{search_term.replace(' ', '-')}"
            logger.info(f"Navegando a: {search_url}")
            
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await self._handle_page_load(page)
            
            # Extraer productos usando el parser optimizado
            products = await self._extract_products_with_parser(page, search_term)
            
            if products:
                logger.info(f"✅ Extraídos {len(products)} productos")
                
                # Enriquecer algunos productos con detalles adicionales
                enriched = await self._enrich_selected_products(context, products)
                return enriched
            else:
                logger.warning("No se encontraron productos")
                return []
            
        except Exception as e:
            logger.error(f"Error scrapeando '{search_term}': {e}")
            raise
        finally:
            await page.close()
    
    async def _handle_page_load(self, page: Page):
        """Manejo optimizado de carga de página"""
        try:
            # Esperar productos con timeout corto
            await page.wait_for_selector(".ui-search-layout__item", timeout=10000)
            await asyncio.sleep(1)  # Breve espera para carga completa
            
        except Exception:
            # Si no carga, intentar detección de problemas
            await self._handle_page_issues(page)
    
    async def _handle_page_issues(self, page: Page):
        """Detectar y manejar problemas de página"""
        try:
            page_text = await page.text_content('body') or ""
            
            # Detectar problemas comunes
            issues = ['robot', 'captcha', 'blocked', 'demasiadas solicitudes']
            
            if any(issue in page_text.lower() for issue in issues):
                logger.warning("Posible bloqueo detectado")
                await random_delay(8, 15)
            elif len(page_text.strip()) < 200:
                logger.warning("Página con contenido mínimo")
                await random_delay(3, 8)
                
        except Exception as e:
            logger.debug(f"Error en detección de problemas: {e}")
    
    async def _extract_products_with_parser(self, page: Page, search_term: str) -> List[ProductData]:
        """Extraer productos usando el parser optimizado"""
        try:
            # Usar el método del parser para encontrar elementos
            product_elements = await self.parser.find_product_elements(page)
            
            if not product_elements:
                logger.warning("No se encontraron elementos de productos")
                return []
            
            products = []
            max_items = min(len(product_elements), self.max_products)
            
            for i, element in enumerate(product_elements[:max_items]):
                try:
                    # Usar el parser para extraer datos
                    product = await self.parser.parse_product_element(element, search_term)
                    
                    if product:
                        products.append(product)
                        logger.debug(f"✅ Producto {i+1}: {product.producto[:40]}...")
                    else:
                        logger.debug(f"❌ Producto {i+1} descartado")
                        
                except Exception as e:
                    logger.debug(f"Error procesando elemento {i+1}: {e}")
                    continue
            
            logger.info(f"✅ Productos válidos extraídos: {len(products)}")
            return products
            
        except Exception as e:
            logger.error(f"Error en extracción de productos: {e}")
            return []
    
    async def _enrich_selected_products(self, context: BrowserContext, products: List[ProductData]) -> List[ProductData]:
        """Enriquecer productos seleccionados con detalles adicionales"""
        if not products:
            return products
        
        # Enriquecer solo los primeros productos para optimizar tiempo
        products_to_enrich = products[:min(8, len(products))]
        logger.info(f"Enriqueciendo {len(products_to_enrich)} productos con detalles...")
        
        for i, product in enumerate(products_to_enrich):
            try:
                if product.url_producto and product.url_producto.startswith("http"):
                    detail_page = await context.new_page()
                    
                    try:
                        # Usar el método del parser para obtener detalles
                        details = await self.parser.scrape_product_details(detail_page, product.url_producto)
                        
                        # Actualizar producto con detalles
                        if details.get('ubicacion') != "Desconocida":
                            product.ubicacion = details['ubicacion']
                        if details.get('reputacion_vendedor') != "Desconocida":
                            product.reputacion_vendedor = details['reputacion_vendedor']
                        
                        logger.debug(f"✅ Enriquecido {i+1}: {product.producto[:30]}...")
                        
                    finally:
                        await detail_page.close()
                    
                    # Delay entre productos
                    if i < len(products_to_enrich) - 1:
                        await random_delay(1, 2)
                
            except Exception as e:
                logger.debug(f"Error enriqueciendo producto {i+1}: {e}")
                continue
        
        logger.info(f"✅ Enriquecimiento completado")
        return products
    
    async def scrape_product_details(self, product_urls: List[str]) -> List[Dict[str, Any]]:
        """Scraper detallado para URLs específicas - optimizado"""
        if not product_urls:
            return []
        
        try:
            await self.browser_manager.start()
            context = await self.browser_manager.create_context()
            await self._setup_stealth_context(context)
            
            detailed_products = []
            urls_to_process = product_urls[:self.max_products]
            
            logger.info(f"Scraping detallado de {len(urls_to_process)} productos")
            
            for i, url in enumerate(urls_to_process):
                try:
                    page = await context.new_page()
                    
                    # Usar el método del parser para obtener detalles completos
                    product_detail = await self.parser.parse_product_detail_page(page, url)
                    
                    await page.close()
                    
                    if product_detail and not product_detail.get('error'):
                        detailed_products.append(product_detail)
                        logger.debug(f"✅ Detalle {i+1}: {product_detail.get('titulo', 'N/A')[:40]}...")
                    
                    # Delay entre productos
                    if i < len(urls_to_process) - 1:
                        await random_delay(1, 3)
                    
                except Exception as e:
                    logger.debug(f"Error scrapeando {url}: {e}")
                    continue
            
            logger.info(f"✅ Detalles extraídos: {len(detailed_products)}")
            return detailed_products
            
        except Exception as e:
            logger.error(f"Error en scraping de detalles: {e}")
            raise
        finally:
            await self.browser_manager.close()

# Función de prueba optimizada
async def test_scraper(search_terms: List[str] = None):
    """Función de prueba optimizada"""
    if not search_terms:
        search_terms = ["zapatillas"]
    
    scraper = MercadoLibreScraper()
    
    try:
        print(f"🚀 Iniciando scraping de términos: {search_terms}")
        products = await scraper.scrape_products(search_terms)
        
        print(f"\n✅ Scraping completado!")
        print(f"📦 Productos extraídos: {len(products)}")
        
        if products:
            print(f"\n📋 Muestra de productos:")
            for i, product in enumerate(products[:3]):
                print(f"\n{i+1}. {product.producto}")
                print(f"   💰 Precio: {product.precio}")
                print(f"   🏪 Vendedor: {product.vendedor}")
                print(f"   📍 Ubicación: {product.ubicacion}")
                print(f"   🚚 Envío gratis: {product.envio_gratis}")
                print(f"   ⭐ Reputación: {product.reputacion_vendedor}")
        
        return products
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_scraper(["zapatillas"]))