"""
Parser para extraer y estructurar datos de productos de MercadoLibre
"""

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
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
    fecha_extraccion: str = field(default_factory=lambda: datetime.now().isoformat())
    url_producto: str = ""
    disponible: str = ""
    envio_gratis: str = ""
    categoria: str = ""
    
    # Campos adicionales útiles
    descuento: str = ""
    cuotas: str = ""
    imagen_url: str = ""
    condicion: str = ""  # Nuevo, Usado, etc.

class MercadoLibreParser:
    """Parser especializado para MercadoLibre Argentina"""
    
    def __init__(self):
        self.precio_patterns = [
            r'[\$\s]*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})?)',
            r'([0-9]{1,3}(?:\.[0-9]{3})*)',
        ]
    
    async def parse_product_element(self, element: ElementHandle, search_term: str = "") -> Optional[ProductData]:
        """Parse de un elemento producto desde listado de búsqueda"""
        try:
            product = ProductData()
            product.categoria = search_term
            
            # Extraer título/nombre del producto
            product.producto = await self._extract_product_title(element)
            
            # Extraer precio
            product.precio = await self._extract_price(element)
            
            # Extraer URL del producto
            product.url_producto = await self._extract_product_url(element)
            
            # Extraer información del vendedor
            product.vendedor = await self._extract_seller_name(element)
            product.reputacion_vendedor = await self._extract_seller_reputation(element)
            
            # Extraer ubicación
            product.ubicacion = await self._extract_location(element)
            
            # Extraer información de envío
            product.envio_gratis = await self._extract_free_shipping(element)
            
            # Extraer disponibilidad
            product.disponible = await self._extract_availability(element)
            
            # Extraer información adicional
            product.descuento = await self._extract_discount(element)
            product.cuotas = await self._extract_installments(element)
            product.imagen_url = await self._extract_image_url(element)
            product.condicion = await self._extract_condition(element)
            
            # Validar que el producto tenga información mínima
            if not product.producto or not product.precio:
                logger.debug("Producto descartado por falta de información básica")
                return None
                
            return product
            
        except Exception as e:
            logger.debug(f"Error parseando elemento de producto: {e}")
            return None
    
    async def _extract_product_title(self, element: ElementHandle) -> str:
        """Extraer título del producto"""
        selectors = [
            '.ui-search-item__title',
            '.ui-search-results__item-title',
            'h2 a',
            '.ui-search-item__group__element--title a',
            '[data-testid="item-title"]'
        ]
        
        for selector in selectors:
            title = await safe_extract_text(element, selector)
            if title != "N/A":
                return title.strip()
        
        return "N/A"
    
    async def _extract_price(self, element: ElementHandle) -> str:
        """Extraer precio del producto"""
        selectors = [
            '.andes-money-amount__fraction',
            '.price-tag-fraction',
            '.ui-search-price__part',
            '.price-tag .price-tag-amount',
            '[data-testid="price"] .andes-money-amount__fraction'
        ]
        
        for selector in selectors:
            price_element = await element.query_selector(selector)
            if price_element:
                price_text = await safe_extract_text(price_element)
                if price_text != "N/A":
                    # Limpiar y formatear precio
                    return self._clean_price(price_text)
        
        # Intentar extraer precio de texto completo
        full_text = await safe_extract_text(element)
        price_match = re.search(r'\$\s*([0-9]{1,3}(?:\.[0-9]{3})*)', full_text)
        if price_match:
            return f"${price_match.group(1)}"
        
        return "N/A"
    
    def _clean_price(self, price_text: str) -> str:
        """Limpiar y formatear texto de precio"""
        if not price_text or price_text == "N/A":
            return "N/A"
        
        # Remover caracteres no numéricos excepto puntos y comas
        cleaned = re.sub(r'[^\d\.,]', '', price_text)
        
        # Formatear como precio argentino
        if cleaned:
            return f"${cleaned}"
        
        return "N/A"
    
    async def _extract_product_url(self, element: ElementHandle) -> str:
        """Extraer URL del producto"""
        selectors = [
            '.ui-search-item__title a',
            '.ui-search-results__item-title a',
            'h2 a',
            'a[href*="/MLA-"]'
        ]
        
        for selector in selectors:
            url = await safe_extract_attribute(element, 'href', selector)
            if url != "N/A" and 'mercadolibre' in url:
                return url
        
        return "N/A"
    
    async def _extract_seller_name(self, element: ElementHandle) -> str:
        """Extraer nombre del vendedor"""
        selectors = [
            '.ui-search-item__seller-info',
            '.ui-search-official-store-label',
            '.ui-search-item__brand-discoverability',
            '[data-testid="seller-info"]'
        ]
        
        for selector in selectors:
            seller = await safe_extract_text(element, selector)
            if seller != "N/A":
                return seller.strip()
        
        return "N/A"
    
    async def _extract_seller_reputation(self, element: ElementHandle) -> str:
        """Extraer reputación del vendedor"""
        selectors = [
            '.ui-search-item__seller-reputation',
            '.ui-search-seller-reputation',
            '[data-testid="seller-reputation"]'
        ]
        
        for selector in selectors:
            reputation = await safe_extract_text(element, selector)
            if reputation != "N/A":
                return reputation.strip()
        
        # Buscar elementos de reputación por clase CSS
        reputation_element = await element.query_selector('[class*="reputation"]')
        if reputation_element:
            rep_text = await safe_extract_text(reputation_element)
            if rep_text != "N/A":
                return rep_text
        
        return "N/A"
    
    async def _extract_location(self, element: ElementHandle) -> str:
        """Extraer ubicación del producto/vendedor"""
        selectors = [
            '.ui-search-item__location',
            '.ui-search-item__location-label',
            '[data-testid="item-location"]'
        ]
        
        for selector in selectors:
            location = await safe_extract_text(element, selector)
            if location != "N/A":
                return location.strip()
        
        return "N/A"
    
    async def _extract_free_shipping(self, element: ElementHandle) -> str:
        """Extraer información de envío gratis"""
        shipping_selectors = [
            '.ui-search-item__shipping',
            '[data-testid="shipping-info"]',
            '.ui-search-shipping-label'
        ]
        
        for selector in shipping_selectors:
            shipping_element = await element.query_selector(selector)
            if shipping_element:
                shipping_text = await safe_extract_text(shipping_element)
                if 'gratis' in shipping_text.lower() or 'free' in shipping_text.lower():
                    return "Sí"
        
        # Buscar texto que contenga "envío gratis"
        full_text = await safe_extract_text(element)
        if 'envío gratis' in full_text.lower() or 'envio gratis' in full_text.lower():
            return "Sí"
        
        return "No"
    
    async def _extract_availability(self, element: ElementHandle) -> str:
        """Extraer disponibilidad del producto"""
        # Buscar indicadores de stock
        stock_selectors = [
            '.ui-search-item__stock-info',
            '[data-testid="stock-info"]'
        ]
        
        for selector in stock_selectors:
            stock_info = await safe_extract_text(element, selector)
            if stock_info != "N/A":
                if 'sin stock' in stock_info.lower() or 'agotado' in stock_info.lower():
                    return "No disponible"
                elif 'disponible' in stock_info.lower():
                    return "Disponible"
        
        # Si no hay información específica de stock, asumir disponible
        return "Disponible"
    
    async def _extract_discount(self, element: ElementHandle) -> str:
        """Extraer información de descuento"""
        discount_selectors = [
            '.ui-search-price-discount',
            '.ui-search-item__discount',
            '[data-testid="discount"]'
        ]
        
        for selector in discount_selectors:
            discount = await safe_extract_text(element, selector)
            if discount != "N/A" and '%' in discount:
                return discount.strip()
        
        return "N/A"
    
    async def _extract_installments(self, element: ElementHandle) -> str:
        """Extraer información de cuotas"""
        installment_selectors = [
            '.ui-search-installments',
            '.ui-search-item__installments',
            '[data-testid="installments"]'
        ]
        
        for selector in installment_selectors:
            installments = await safe_extract_text(element, selector)
            if installments != "N/A" and ('cuotas' in installments.lower() or 'sin interés' in installments.lower()):
                return installments.strip()
        
        return "N/A"
    
    async def _extract_image_url(self, element: ElementHandle) -> str:
        """Extraer URL de imagen del producto"""
        img_selectors = [
            '.ui-search-result-image img',
            '.ui-search-item__image img',
            'img[data-testid="item-image"]'
        ]
        
        for selector in img_selectors:
            img_url = await safe_extract_attribute(element, 'src', selector)
            if img_url != "N/A" and 'http' in img_url:
                return img_url
        
        return "N/A"
    
    async def _extract_condition(self, element: ElementHandle) -> str:
        """Extraer condición del producto (Nuevo, Usado, etc.)"""
        condition_selectors = [
            '.ui-search-item__condition',
            '[data-testid="item-condition"]'
        ]
        
        for selector in condition_selectors:
            condition = await safe_extract_text(element, selector)
            if condition != "N/A":
                return condition.strip()
        
        # Buscar en el texto completo
        full_text = await safe_extract_text(element)
        condition_keywords = ['nuevo', 'usado', 'reacondicionado', 'refurbished']
        
        for keyword in condition_keywords:
            if keyword in full_text.lower():
                return keyword.capitalize()
        
        return "Nuevo"  # Default
    
    async def parse_product_detail_page(self, page: Page, url: str) -> Dict[str, Any]:
        """Parse detallado de página individual de producto"""
        try:
            product_detail = {}
            
            # Información básica
            product_detail['titulo'] = await safe_extract_text(page, '.ui-pdp-title')
            product_detail['precio'] = await safe_extract_text(page, '.andes-money-amount__fraction')
            product_detail['url'] = url
            
            # Información del vendedor
            product_detail['vendedor'] = await safe_extract_text(page, '.ui-pdp-seller__header__title')
            product_detail['reputacion'] = await safe_extract_text(page, '.ui-seller-info__status-info__title')
            
            # Características técnicas
            characteristics = await self._extract_technical_specs(page)
            product_detail['caracteristicas'] = characteristics
            
            # Descripción
            product_detail['descripcion'] = await safe_extract_text(page, '.ui-pdp-description__content')
            
            # Información de envío
            product_detail['envio_info'] = await safe_extract_text(page, '.ui-pdp-shipping')
            
            return product_detail
            
        except Exception as e:
            logger.error(f"Error parseando página de detalle: {e}")
            return {}
    
    async def _extract_technical_specs(self, page: Page) -> Dict[str, str]:
        """Extraer especificaciones técnicas del producto"""
        specs = {}
        
        try:
            # Buscar tabla de especificaciones
            spec_rows = await page.query_selector_all('.andes-table__row')
            
            for row in spec_rows:
                key_element = await row.query_selector('.andes-table__header')
                value_element = await row.query_selector('.andes-table__column')
                
                if key_element and value_element:
                    key = await safe_extract_text(key_element)
                    value = await safe_extract_text(value_element)
                    
                    if key != "N/A" and value != "N/A":
                        specs[key] = value
            
            return specs
            
        except Exception as e:
            logger.debug(f"Error extrayendo especificaciones técnicas: {e}")
            return {}