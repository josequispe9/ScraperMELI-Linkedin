"""
Parser simplificado para extraer datos de productos de MercadoLibre
Versión optimizada manteniendo robustez y funcionalidad esencial
"""

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from playwright.async_api import ElementHandle, Page

from core.logger import get_logger

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
    imagen_url: str = ""
    condicion: str = ""

class MercadoLibreParser:
    """Parser simplificado para MercadoLibre Argentina"""
    
    def __init__(self):
        # Selectores principales más efectivos
        self.selectors = {
            'containers': [
                ".ui-search-layout__item",
                ".ui-search-results__item", 
                'div[data-testid*="result"]'
            ],
            'titles': [
                ".poly-component__title",
                ".ui-search-item__title",
                "h2 a"
            ],
            'prices': [
                ".andes-money-amount__fraction",
                ".price-tag-fraction"
            ],
            'links': [
                "a.poly-component__title",
                ".ui-search-item__title a"
            ],
            'sellers': [
                ".poly-component__seller",
                ".ui-search-item__seller-info"
            ],
            'shipping': [
                ".poly-component__shipping",
                ".ui-search-item__shipping"
            ]
        }
    
    async def find_product_elements(self, page: Page) -> List[ElementHandle]:
        """Encuentra elementos de productos de forma robusta"""
        for selector in self.selectors['containers']:
            try:
                await page.wait_for_selector(selector, timeout=10000)
                elements = await page.query_selector_all(selector)
                
                if elements:
                    # Validar elementos con contenido útil
                    valid_elements = []
                    for element in elements[:20]:  # Limitar a 20
                        try:
                            text = await element.text_content()
                            if text and len(text.strip()) > 50 and any(
                                indicator in text.lower() for indicator in ['$', 'precio', 'envío']
                            ):
                                valid_elements.append(element)
                        except:
                            continue
                    
                    if valid_elements:
                        logger.info(f"✅ Encontrados {len(valid_elements)} productos válidos")
                        return valid_elements
                        
            except Exception as e:
                logger.debug(f"Selector {selector} falló: {e}")
                continue
        
        logger.error("❌ No se encontraron productos")
        return []

    async def parse_product_element(self, element: ElementHandle, search_term: str = "") -> Optional[ProductData]:
        """Parse de un elemento producto desde listado"""
        try:
            product = ProductData()
            product.categoria = search_term
            
            # Extraer datos básicos
            product.producto = await self._extract_with_selectors(element, self.selectors['titles'])
            product.precio = await self._extract_price(element)
            product.url_producto = await self._extract_url(element)
            product.vendedor = await self._extract_with_selectors(element, self.selectors['sellers']) or "Desconocido"
            product.envio_gratis = "Sí" if await self._has_free_shipping(element) else "No"
            product.disponible = "Sí"
            product.imagen_url = await self._extract_image(element)
            
            # Validaciones básicas
            if not product.producto or len(product.producto.strip()) < 5:
                return None
            if not product.precio or product.precio == "N/A":
                return None
                
            return product
            
        except Exception as e:
            logger.debug(f"Error parseando producto: {e}")
            return None
    
    async def _extract_with_selectors(self, element: ElementHandle, selectors: List[str]) -> str:
        """Extrae texto usando lista de selectores"""
        for selector in selectors:
            try:
                el = await element.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        return text.strip()
            except:
                continue
        return "N/A"
    
    async def _extract_price(self, element: ElementHandle) -> str:
        """Extrae precio formateado"""
        price_text = await self._extract_with_selectors(element, self.selectors['prices'])
        if price_text != "N/A":
            return f"${price_text}"
        return "N/A"
    
    async def _extract_url(self, element: ElementHandle) -> str:
        """Extrae URL del producto"""
        for selector in self.selectors['links']:
            try:
                link = await element.query_selector(selector)
                if link:
                    href = await link.get_attribute("href")
                    if href:
                        if href.startswith('/'):
                            return f"https://articulo.mercadolibre.com.ar{href}"
                        elif href.startswith('http'):
                            return href
            except:
                continue
        return "N/A"
    
    async def _has_free_shipping(self, element: ElementHandle) -> bool:
        """Verifica si tiene envío gratis"""
        for selector in self.selectors['shipping']:
            try:
                if await element.query_selector(selector):
                    return True
            except:
                continue
        return False
    
    async def _extract_image(self, element: ElementHandle) -> str:
        """Extrae URL de imagen"""
        try:
            img = await element.query_selector("img")
            if img:
                src = await img.get_attribute('src')
                if src and src.startswith('http'):
                    return src
        except:
            pass
        return "N/A"
    
    async def scrape_product_details(self, page: Page, url: str) -> Dict[str, str]:
        """Scraper detallado para página individual"""
        details = {"ubicacion": "Desconocida", "reputacion_vendedor": "Desconocida"}
        
        try:
            if not url or not url.startswith("http"):
                return details
            
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Extraer ubicación
            location_selectors = [
                "div.ui-seller-info__status-info__subtitle",
                ".ui-seller-location"
            ]
            location = await self._extract_from_page(page, location_selectors)
            if location != "N/A":
                details["ubicacion"] = location
            
            # Extraer reputación
            reputation_selectors = [
                "div.ui-seller-info__header__title + div span",
                ".ui-seller-info__status-info__title"
            ]
            reputation = await self._extract_from_page(page, reputation_selectors)
            if reputation != "N/A":
                details["reputacion_vendedor"] = reputation
            
            return details
            
        except Exception as e:
            logger.error(f"Error scrapeando detalles: {e}")
            return details
    
    async def _extract_from_page(self, page: Page, selectors: List[str]) -> str:
        """Extrae texto de página usando selectores"""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        return text.strip()
            except:
                continue
        return "N/A"
    
    async def parse_product_detail_page(self, page: Page, url: str) -> Dict[str, Any]:
        """Parse completo de página de producto"""
        try:
            details = await self.scrape_product_details(page, url)
            
            product_detail = {
                'titulo': await self._extract_from_page(page, ['.ui-pdp-title', 'h1.ui-pdp-title']),
                'precio': await self._extract_from_page(page, ['.andes-money-amount__fraction']),
                'url': url,
                'vendedor': await self._extract_from_page(page, ['.ui-pdp-seller__header__title']),
                'ubicacion': details.get('ubicacion', 'Desconocida'),
                'reputacion': details.get('reputacion_vendedor', 'Desconocida'),
                'condicion': await self._extract_from_page(page, ['.ui-pdp-subtitle'])
            }
            
            # Limpiar valores vacíos
            for key, value in product_detail.items():
                if not value or value == 'N/A':
                    product_detail[key] = 'No disponible'
            
            return product_detail
            
        except Exception as e:
            logger.error(f"Error en parse detallado: {e}")
            return {'url': url, 'error': str(e)}