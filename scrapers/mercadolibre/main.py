"""
Sistema de Web Scraping para MercadoLibre Argentina - Versión Simplificada
Extrae información de productos y almacena en formato CSV
"""

import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

# Importar módulos locales
from .scraper import MercadoLibreScraper
from .parser import ProductData
from core.logger import get_logger, LogConfig

# Configuración del logger
config = LogConfig(json_format=False)
logger = get_logger("main", config)

class CSVExporter:
    """Exportador de datos a formato CSV optimizado"""
    
    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Campos requeridos
        self.required_fields = [
            'producto', 'precio', 'vendedor', 'ubicacion', 
            'reputacion_vendedor', 'fecha_extraccion', 'url_producto',
            'disponible', 'envio_gratis', 'categoria'
        ]
    
    def export_to_csv(self, products: List[ProductData], filename: str = None) -> Optional[str]:
        """Exportar productos a CSV"""
        if not products:
            logger.warning("No hay productos para exportar")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mercadolibre_productos_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.required_fields)
                writer.writeheader()
                
                valid_products = 0
                for product in products:
                    product_dict = self._product_to_dict(product)
                    if self._is_valid_product(product_dict):
                        writer.writerow(product_dict)
                        valid_products += 1
            
            logger.info(f"✅ CSV exportado: {filepath} ({valid_products} productos)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ Error exportando CSV: {e}")
            return None
    
    def _product_to_dict(self, product: ProductData) -> Dict[str, str]:
        """Convertir ProductData a diccionario"""
        return {
            'producto': self._clean_text(product.producto),
            'precio': self._clean_price(product.precio),
            'vendedor': self._clean_text(product.vendedor),
            'ubicacion': self._clean_text(product.ubicacion),
            'reputacion_vendedor': self._clean_text(product.reputacion_vendedor),
            'fecha_extraccion': product.fecha_extraccion,
            'url_producto': product.url_producto,
            'disponible': product.disponible,
            'envio_gratis': product.envio_gratis,
            'categoria': self._clean_text(product.categoria)
        }
    
    def _clean_text(self, text: str) -> str:
        """Limpiar texto para CSV"""
        if not text or text in ['N/A', 'Desconocido']:
            return 'No disponible'
        return text.strip().replace('\n', ' ').replace('\r', ' ')
    
    def _clean_price(self, price: str) -> str:
        """Limpiar precio"""
        if not price or price == 'N/A':
            return 'Precio no disponible'
        return price.strip() if price.startswith('$') else f"${price.strip()}"
    
    def _is_valid_product(self, product_dict: Dict[str, str]) -> bool:
        """Validar producto básico"""
        return (
            product_dict.get('producto', '') not in ['', 'No disponible'] and
            product_dict.get('precio', '') not in ['', 'Precio no disponible'] and
            len(product_dict.get('producto', '')) >= 5
        )


class ScrapingSession:
    """Gestor simplificado de sesión de scraping"""
    
    def __init__(self, search_terms: List[str] = None, max_products: int = 50):
        self.search_terms = search_terms or self._get_default_terms()
        self.max_products = max_products
        self.scraper = MercadoLibreScraper()
        self.csv_exporter = CSVExporter()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _get_default_terms(self) -> List[str]:
        """Términos de búsqueda por defecto"""
        return ["notebook", "smartphone", "televisor", "heladera"]
    
    async def run_scraping(self) -> Dict[str, Any]:
        """Ejecutar sesión de scraping"""
        logger.info(f"🚀 Iniciando scraping - Términos: {', '.join(self.search_terms)}")
        
        session_results = {
            'session_id': self.session_id,
            'start_time': datetime.now(),
            'products_scraped': 0,
            'csv_file': None,
            'success': False,
            'error': None
        }
        
        try:
            # Configurar scraper
            self.scraper.max_products = self.max_products
            
            # Ejecutar scraping
            products = await self.scraper.scrape_products(self.search_terms)
            
            if products:
                session_results['products_scraped'] = len(products)
                
                # Exportar CSV
                csv_file = self.csv_exporter.export_to_csv(products)
                session_results['csv_file'] = csv_file
                
                # Mostrar resumen básico
                self._show_summary(products)
                
                session_results['success'] = True
                logger.info(f"✅ Scraping completado - {len(products)} productos")
            else:
                logger.error("❌ No se extrajeron productos")
                session_results['error'] = "No se extrajeron productos"
            
            session_results['end_time'] = datetime.now()
            return session_results
            
        except Exception as e:
            logger.error(f"❌ Error en scraping: {e}")
            session_results['error'] = str(e)
            session_results['end_time'] = datetime.now()
            return session_results
    
    def _show_summary(self, products: List[ProductData]):
        """Mostrar resumen básico"""
        logger.info(f"📊 Resumen:")
        logger.info(f"   • Total productos: {len(products)}")
        
        # Contar por categoría
        categories = {}
        for product in products:
            cat = product.categoria or 'sin_categoria'
            categories[cat] = categories.get(cat, 0) + 1
        
        logger.info(f"   • Categorías: {len(categories)}")
        for cat, count in categories.items():
            logger.info(f"     - {cat}: {count} productos")


async def main():
    """Función principal simplificada"""
    parser = argparse.ArgumentParser(
        description='Sistema de Web Scraping para MercadoLibre Argentina'
    )
    parser.add_argument(
        '--terms', 
        nargs='+', 
        help='Términos de búsqueda'
    )
    parser.add_argument(
        '--max-products', 
        type=int, 
        default=50, 
        help='Máximo productos por término (default: 50)'
    )
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='Modo de prueba (10 productos)'
    )
    
    args = parser.parse_args()
    
    # Configurar parámetros
    search_terms = args.terms
    max_products = 10 if args.test else args.max_products
    
    logger.info("🎯 Sistema de Web Scraping MercadoLibre")
    
    try:
        # Crear y ejecutar sesión
        session = ScrapingSession(
            search_terms=search_terms, 
            max_products=max_products
        )
        
        results = await session.run_scraping()
        
        # Mostrar resultado final
        if results['success']:
            logger.info(f"🎉 ¡Scraping exitoso!")
            logger.info(f"📊 {results['products_scraped']} productos extraídos")
            if results['csv_file']:
                logger.info(f"📄 Archivo: {results['csv_file']}")
            
            duration = (results['end_time'] - results['start_time']).total_seconds()
            logger.info(f"⏱️ Tiempo: {duration:.1f} segundos")
        else:
            logger.error(f"❌ Error: {results.get('error', 'Desconocido')}")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("⚠️ Interrumpido por el usuario")
        return 130
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"🔥 Error crítico: {e}")
        sys.exit(1)