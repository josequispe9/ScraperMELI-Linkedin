"""
Parser para extraer y estructurar datos de productos de MercadoLibre
Versión mejorada basada en selectores funcionales comprobados
"""

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from playwright.async_api import ElementHandle, Page

from core.logger import get_logger
from core.utils import safe_extract_text, safe_extract_attribute

logger = get_logger("mercadolibre_parser")

@dataclass
class ProductData:
    """Estructura de datos para productos de MercadoLibre"""
    producto: str = ""
    precio: str = ""
    vendedor: str = ""
    ubicacion: str = ""
    reputacion_vendedor: str = ""
    fecha_extraccion: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    url_producto: str = ""
    disponible: str = ""
    envio_gratis: str = ""
    categoria: str = ""
    
    # Campos adicionales útiles
    descuento: str = ""
    cuotas: str = ""
    imagen_url: str = ""
    condicion: str = ""

class MercadoLibreParser:
    """Parser especializado para MercadoLibre Argentina con selectores funcionales comprobados"""
    
    def __init__(self):
        # Selectores principales basados en el código funcional de meli.py
        self.product_container_selectors = [
            ".ui-search-layout__item",
            ".ui-search-results__item", 
            ".ui-search-result",
            'div[data-testid*="result"]'
        ]
        
        # Selectores específicos para cada campo
        self.title_selectors = [
            ".poly-component__title",
            ".ui-search-item__title",
            ".ui-search-results__item-title",
            "h2 a"
        ]
        
        self.price_selectors = [
            ".andes-money-amount__fraction",
            ".price-tag-fraction",
            ".ui-search-price__part"
        ]
        
        self.link_selectors = [
            "a.poly-component__title",
            ".ui-search-item__title a",
            "a[href*='MLA-']"
        ]
        
        self.seller_selectors = [
            ".poly-component__seller",
            ".ui-search-item__seller-info",
            ".ui-search-official-store-label"
        ]
        
        self.shipping_selectors = [
            ".poly-component__shipping",
            ".ui-search-item__shipping",
            ".ui-search-shipping-label"
        ]
    
    async def find_product_elements_robust(self, page: Page) -> List[ElementHandle]:
        """
        Estrategia robusta para encontrar elementos de productos
        Basada en selectores comprobados que funcionan
        """
        product_elements = []
        
        # Intentar con cada selector de contenedor
        for selector in self.product_container_selectors:
            try:
                logger.info(f"Probando selector: {selector}")
                
                # Esperar a que aparezcan los elementos
                await page.wait_for_selector(selector, timeout=10000)
                elements = await page.query_selector_all(selector)
                
                if elements:
                    logger.info(f"✅ Selector funcionando: {selector} - {len(elements)} elementos encontrados")
                    
                    # Validar que los elementos contengan información útil
                    valid_elements = []
                    for element in elements:
                        try:
                            # Verificar que tenga contenido significativo
                            text_content = await element.text_content()
                            if text_content and len(text_content.strip()) > 50:
                                # Verificar que contenga indicadores de producto
                                if any(indicator in text_content.lower() for indicator in ['$', 'precio', 'envío']):
                                    valid_elements.append(element)
                        except:
                            continue
                    
                    if valid_elements:
                        logger.info(f"✅ Elementos válidos encontrados: {len(valid_elements)}")
                        return valid_elements[:20]  # Limitar a 20 productos máximo
                        
            except Exception as e:
                logger.debug(f"❌ Selector {selector} no funcionó: {e}")
                continue
        
        logger.error("❌ No se pudieron encontrar elementos de productos con ningún selector")
        return []

    async def parse_product_element(self, element: ElementHandle, search_term: str = "") -> Optional[ProductData]:
        """Parse de un elemento producto desde listado de búsqueda"""
        try:
            product = ProductData()
            product.categoria = search_term
            
            # Extraer información básica del listado
            product.producto = await self._extract_product_title(element)
            product.precio = await self._extract_price(element)
            product.url_producto = await self._extract_product_url(element)
            product.vendedor = await self._extract_seller_name(element)
            product.envio_gratis = await self._extract_free_shipping(element)
            product.disponible = "Sí"  # Si está en el listado, asumimos que está disponible
            product.imagen_url = await self._extract_image_url(element)
            
            # Validaciones básicas
            if not product.producto or product.producto == "N/A" or len(product.producto.strip()) < 5:
                logger.debug("Producto descartado: título inválido o muy corto")
                return None
            
            if not product.precio or product.precio == "N/A":
                logger.debug("Producto descartado: precio no encontrado")
                return None
                
            return product
            
        except Exception as e:
            logger.debug(f"Error parseando elemento de producto: {e}")
            return None
    
    async def _extract_product_title(self, element: ElementHandle) -> str:
        """Extraer título del producto usando selectores comprobados"""
        for selector in self.title_selectors:
            try:
                title_element = await element.query_selector(selector)
                if title_element:
                    title = await title_element.inner_text()
                    if title and title.strip() and len(title.strip()) > 5:
                        return title.strip()
            except Exception as e:
                logger.debug(f"Error con selector de título {selector}: {e}")
                continue
        
        logger.debug("No se pudo extraer título del producto")
        return "N/A"
    
    async def _extract_price(self, element: ElementHandle) -> str:
        """Extraer precio usando selectores comprobados"""
        for selector in self.price_selectors:
            try:
                price_element = await element.query_selector(selector)
                if price_element:
                    price = await price_element.inner_text()
                    if price and price.strip():
                        # Limpiar y formatear precio
                        cleaned_price = price.strip()
                        return f"${cleaned_price}"
            except Exception as e:
                logger.debug(f"Error con selector de precio {selector}: {e}")
                continue
        
        logger.debug("No se pudo extraer precio del producto")
        return "N/A"
    
    async def _extract_product_url(self, element: ElementHandle) -> str:
        """Extraer URL del producto usando selectores comprobados"""
        for selector in self.link_selectors:
            try:
                link_element = await element.query_selector(selector)
                if link_element:
                    href = await link_element.get_attribute("href")
                    if href:
                        # Convertir URL relativa a absoluta si es necesario
                        if href.startswith('/'):
                            return f"https://articulo.mercadolibre.com.ar{href}"
                        elif href.startswith('http'):
                            return href
            except Exception as e:
                logger.debug(f"Error con selector de URL {selector}: {e}")
                continue
        
        logger.debug("No se pudo extraer URL del producto")
        return "N/A"
    
    async def _extract_seller_name(self, element: ElementHandle) -> str:
        """Extraer nombre del vendedor usando selectores comprobados"""
        for selector in self.seller_selectors:
            try:
                seller_element = await element.query_selector(selector)
                if seller_element:
                    seller = await seller_element.inner_text()
                    if seller and seller.strip():
                        return seller.strip()
            except Exception as e:
                logger.debug(f"Error con selector de vendedor {selector}: {e}")
                continue
        
        return "Desconocido"
    
    async def _extract_free_shipping(self, element: ElementHandle) -> str:
        """Extraer información de envío gratis usando selectores comprobados"""
        for selector in self.shipping_selectors:
            try:
                shipping_element = await element.query_selector(selector)
                if shipping_element:
                    return "Sí"
            except Exception as e:
                logger.debug(f"Error con selector de envío {selector}: {e}")
                continue
        
        return "No"
    
    async def _extract_image_url(self, element: ElementHandle) -> str:
        """Extraer URL de imagen del producto"""
        img_selectors = [
            "img",
            ".ui-search-result-image img",
            ".ui-search-item__image img"
        ]
        
        for selector in img_selectors:
            try:
                img_element = await element.query_selector(selector)
                if img_element:
                    img_url = await img_element.get_attribute('src')
                    if img_url and img_url.startswith('http'):
                        return img_url
            except:
                continue
        
        return "N/A"
    
    async def scrape_product_details_from_url(self, page: Page, url: str) -> Dict[str, str]:
        """
        Scraper detallado para página individual de producto
        Basado en el código funcional de meli.py
        """
        details = {
            "ubicacion": "Desconocida",
            "reputacion_vendedor": "Desconocida"
        }
        
        try:
            if not url or url == "N/A" or not url.startswith("http"):
                return details
            
            logger.info(f"Navegando a página de producto: {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Extraer ubicación usando selectores comprobados
            location_selectors = [
                "div.ui-seller-info__status-info__subtitle",
                ".ui-seller-location",
                "[data-testid='seller-location']"
            ]
            
            for selector in location_selectors:
                try:
                    location_element = await page.query_selector(selector)
                    if location_element:
                        location = await location_element.inner_text()
                        if location and location.strip():
                            details["ubicacion"] = location.strip()
                            logger.debug(f"✅ Ubicación extraída: {details['ubicacion']}")
                            break
                except Exception as e:
                    logger.debug(f"Error extrayendo ubicación con {selector}: {e}")
                    continue
            
            # Extraer reputación del vendedor
            reputation_selectors = [
                "div.ui-seller-info__header__title + div span",
                ".ui-seller-info__status-info__title",
                "[data-testid='seller-reputation']"
            ]
            
            for selector in reputation_selectors:
                try:
                    reputation_element = await page.query_selector(selector)
                    if reputation_element:
                        # Intentar obtener texto o clase CSS
                        reputation_text = await reputation_element.inner_text()
                        if reputation_text and reputation_text.strip():
                            details["reputacion_vendedor"] = reputation_text.strip()
                            logger.debug(f"✅ Reputación extraída: {details['reputacion_vendedor']}")
                            break
                        else:
                            # Si no hay texto, intentar con atributo class
                            reputation_class = await reputation_element.get_attribute("class")
                            if reputation_class:
                                details["reputacion_vendedor"] = reputation_class
                                logger.debug(f"✅ Reputación (clase) extraída: {details['reputacion_vendedor']}")
                                break
                except Exception as e:
                    logger.debug(f"Error extrayendo reputación con {selector}: {e}")
                    continue
            
            return details
            
        except Exception as e:
            logger.error(f"❌ Error scrapeando detalles de {url}: {e}")
            return details
    
    async def parse_product_detail_page(self, page: Page, url: str) -> Dict[str, Any]:
        """Parse detallado de página individual de producto - método de compatibilidad"""
        try:
            details = await self.scrape_product_details_from_url(page, url)
            
            # Agregar información básica si está disponible
            product_detail = {
                'titulo': await safe_extract_text(page, '.ui-pdp-title'),
                'precio': await safe_extract_text(page, '.andes-money-amount__fraction'),
                'url': url,
                'vendedor': await safe_extract_text(page, '.ui-pdp-seller__header__title'),
                'ubicacion': details.get('ubicacion', 'Desconocida'),
                'reputacion': details.get('reputacion_vendedor', 'Desconocida')
            }
            
            return product_detail
            
        except Exception as e:
            logger.error(f"Error parseando página de detalle: {e}")
            return {'url': url, 'error': str(e)}

# Agregar estos métodos al final de la clase MercadoLibreParser en parser.py

async def parse_product_detail_page(self, page: Page, url: str) -> Dict[str, Any]:
    """Parse detallado de página individual de producto - versión mejorada"""
    try:
        details = await self.scrape_product_details_from_url(page, url)
        
        # Extraer información básica de la página de producto
        product_detail = {
            'titulo': await self._safe_extract_text(page, [
                '.ui-pdp-title',
                'h1.ui-pdp-title',
                '[data-testid="product-title"]'
            ]),
            'precio': await self._safe_extract_text(page, [
                '.andes-money-amount__fraction',
                '.ui-pdp-price__fraction',
                '[data-testid="price-fraction"]'
            ]),
            'url': url,
            'vendedor': await self._safe_extract_text(page, [
                '.ui-pdp-seller__header__title',
                '.ui-seller-info__title',
                '[data-testid="seller-name"]'
            ]),
            'ubicacion': details.get('ubicacion', 'Desconocida'),
            'reputacion': details.get('reputacion_vendedor', 'Desconocida'),
            'descripcion': await self._safe_extract_text(page, [
                '.ui-pdp-description__content',
                '.ui-pdp-description p',
                '[data-testid="product-description"]'
            ]),
            'condicion': await self._safe_extract_text(page, [
                '.ui-pdp-subtitle',
                '.ui-pdp-condition',
                '[data-testid="product-condition"]'
            ])
        }
        
        # Limpiar datos vacíos o inválidos
        for key, value in product_detail.items():
            if not value or value in ['N/A', 'Sin información', '']:
                if key == 'titulo':
                    product_detail[key] = 'Producto sin título'
                elif key == 'precio':
                    product_detail[key] = 'Precio no disponible'
                elif key == 'vendedor':
                    product_detail[key] = 'Vendedor desconocido'
                else:
                    product_detail[key] = 'No disponible'
        
        return product_detail
        
    except Exception as e:
        logger.error(f"Error parseando página de detalle: {e}")
        return {'url': url, 'error': str(e), 'titulo': 'Error al extraer'}

async def _safe_extract_text(self, page: Page, selectors: List[str]) -> str:
    """Extraer texto de forma segura usando múltiples selectores"""
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                if text and text.strip():
                    return text.strip()
        except Exception as e:
            logger.debug(f"Error con selector {selector}: {e}")
            continue
    
    return "N/A"