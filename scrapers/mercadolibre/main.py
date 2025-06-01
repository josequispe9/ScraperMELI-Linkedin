"""
Sistema de Web Scraping para MercadoLibre Argentina
Extrae información de productos y almacena en formato CSV
Versión robusta y modular basada en la arquitectura existente
"""

import asyncio
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

# Importar módulos locales
from .scraper import MercadoLibreScraper, test_scraper
from .parser import ProductData, MercadoLibreParser
from core.utils import retry_async, random_delay
from core.logger import get_logger, LogConfig, LogContext, PerformanceLogger

# Configuración del logger
config = LogConfig(json_format=False)
logger = get_logger("main", config)
perf_logger = PerformanceLogger(logger)

class CSVExporter:
    """Exportador de datos a formato CSV con validación y formato robusto"""
    
    def __init__(self, output_dir: str = "data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Campos requeridos según especificación
        self.required_fields = [
            'producto', 'precio', 'vendedor', 'ubicacion', 
            'reputacion_vendedor', 'fecha_extraccion', 'url_producto',
            'disponible', 'envio_gratis', 'categoria'
        ]
    
    def export_to_csv(self, products: List[ProductData], filename: str = None) -> str:
        """Exportar productos a CSV con validación completa"""
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
                    if self._validate_product_data(product_dict):
                        writer.writerow(product_dict)
                        valid_products += 1
                    else:
                        logger.debug(f"Producto inválido omitido: {product.producto[:30]}...")
            
            logger.info(f"✅ CSV exportado exitosamente: {filepath}")
            logger.info(f"📊 Productos válidos exportados: {valid_products}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ Error exportando CSV: {e}", exc_info=True)
            raise
    
    def _product_to_dict(self, product: ProductData) -> Dict[str, str]:
        """Convertir ProductData a diccionario con formato consistente"""
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
        """Limpiar y normalizar texto para CSV"""
        if not text or text in ['N/A', 'Desconocido', 'Sin información']:
            return 'No disponible'
        return text.strip().replace('\n', ' ').replace('\r', ' ')
    
    def _clean_price(self, price: str) -> str:
        """Limpiar y formatear precio"""
        if not price or price in ['N/A', 'Sin precio']:
            return 'Precio no disponible'
        
        # Asegurar formato consistente de precio
        if not price.startswith('$'):
            return f"${price.strip()}"
        return price.strip()
    
    def _validate_product_data(self, product_dict: Dict[str, str]) -> bool:
        """Validar que el producto tenga datos mínimos requeridos"""
        required_for_validation = ['producto', 'precio', 'categoria']
        
        for field in required_for_validation:
            value = product_dict.get(field, '')
            if not value or value in ['No disponible', 'Precio no disponible', '']:
                return False
        
        # Validar que el nombre del producto no sea demasiado corto
        if len(product_dict['producto']) < 5:
            return False
        
        return True


class ScrapingSession:
    """Gestor de sesión completa de scraping con configuración robusta"""
    
    def __init__(self, search_terms: List[str] = None, max_products: int = 50):
        self.search_terms = search_terms or self._get_default_search_terms()
        self.max_products = max_products
        self.scraper = MercadoLibreScraper()
        self.csv_exporter = CSVExporter()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _get_default_search_terms(self) -> List[str]:
        """Términos de búsqueda por defecto según especificación"""
        return [
            "notebook",
            "smartphone",
            "televisor led",
            "heladera",
            "aire acondicionado",
            "microondas"
        ]
    
    async def run_complete_scraping(self) -> Dict[str, Any]:
        """Ejecutar sesión completa de scraping con manejo de errores robusto"""
        perf_logger.start(f"Sesión completa de scraping - ID: {self.session_id}")
        
        session_results = {
            'session_id': self.session_id,
            'start_time': datetime.now(),
            'search_terms': self.search_terms,
            'products_scraped': 0,
            'csv_files_generated': [],
            'success': False,
            'errors': []
        }
        
        try:
            with LogContext(logger, session_id=self.session_id):
                logger.info(f"🚀 Iniciando sesión de scraping completa")
                logger.info(f"📝 Términos de búsqueda: {', '.join(self.search_terms)}")
                logger.info(f"🎯 Objetivo: {self.max_products} productos por término")
                
                # Ejecutar scraping principal
                products = await self._execute_scraping()
                
                if products:
                    session_results['products_scraped'] = len(products)
                    
                    # Generar reportes
                    csv_files = await self._generate_reports(products)
                    session_results['csv_files_generated'] = csv_files
                    
                    # Mostrar estadísticas
                    await self._display_session_statistics(products, session_results)
                    
                    session_results['success'] = True
                    logger.info(f"✅ Sesión completada exitosamente - ID: {self.session_id}")
                else:
                    logger.error("❌ No se extrajeron productos en la sesión")
                    session_results['errors'].append("No se extrajeron productos")
                
                session_results['end_time'] = datetime.now()
                session_results['duration'] = (session_results['end_time'] - session_results['start_time']).total_seconds()
                
                perf_logger.end(success=session_results['success'], 
                              total_products=session_results['products_scraped'])
                
                return session_results
                
        except Exception as e:
            logger.error(f"❌ Error en sesión de scraping: {e}", exc_info=True)
            session_results['errors'].append(str(e))
            session_results['end_time'] = datetime.now()
            perf_logger.end(success=False)
            raise
    
    @retry_async(max_retries=3, delay=5, backoff=2)
    async def _execute_scraping(self) -> List[ProductData]:
        """Ejecutar scraping con reintentos automáticos"""
        logger.info("🔍 Iniciando extracción de productos...")
        
        # Usar el scraper configurado
        self.scraper.max_products = self.max_products
        products = await self.scraper.scrape_products(self.search_terms)
        
        if not products:
            raise RuntimeError("El scraping no devolvió productos")
        
        logger.info(f"✅ Scraping completado: {len(products)} productos extraídos")
        return products
    
    async def _generate_reports(self, products: List[ProductData]) -> List[str]:
        """Generar reportes CSV organizados por categoría y completo"""
        csv_files = []
        
        try:
            # Archivo CSV completo
            complete_csv = self.csv_exporter.export_to_csv(
                products, 
                f"mercadolibre_completo_{self.session_id}.csv"
            )
            if complete_csv:
                csv_files.append(complete_csv)
            
            # CSVs por categoría
            products_by_category = self._group_by_category(products)
            
            for category, category_products in products_by_category.items():
                if category_products:
                    category_csv = self.csv_exporter.export_to_csv(
                        category_products,
                        f"mercadolibre_{category}_{self.session_id}.csv"
                    )
                    if category_csv:
                        csv_files.append(category_csv)
            
            logger.info(f"📊 Reportes generados: {len(csv_files)} archivos CSV")
            return csv_files
            
        except Exception as e:
            logger.error(f"❌ Error generando reportes: {e}")
            raise
    
    def _group_by_category(self, products: List[ProductData]) -> Dict[str, List[ProductData]]:
        """Agrupar productos por categoría"""
        grouped = {}
        for product in products:
            category = product.categoria or 'sin_categoria'
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(product)
        return grouped
    
    async def _display_session_statistics(self, products: List[ProductData], session_results: Dict[str, Any]):
        """Mostrar estadísticas detalladas de la sesión"""
        logger.info("\n" + "="*60)
        logger.info("📊 ESTADÍSTICAS DE LA SESIÓN")
        logger.info("="*60)
        
        # Estadísticas generales
        logger.info(f"🆔 ID de Sesión: {session_results['session_id']}")
        logger.info(f"⏱️ Duración: {session_results.get('duration', 0):.2f} segundos")
        logger.info(f"📦 Total productos extraídos: {len(products)}")
        
        # Estadísticas por categoría
        categories = self._group_by_category(products)
        logger.info(f"🏷️ Categorías procesadas: {len(categories)}")
        
        for category, category_products in categories.items():
            logger.info(f"   - {category}: {len(category_products)} productos")
        
        # Estadísticas de vendedores
        sellers = {}
        for product in products:
            seller = product.vendedor
            sellers[seller] = sellers.get(seller, 0) + 1
        
        logger.info(f"🏪 Vendedores únicos: {len(sellers)}")
        
        # Top vendedores
        top_sellers = sorted(sellers.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info("🏆 Top 5 vendedores:")
        for seller, count in top_sellers:
            logger.info(f"   - {seller}: {count} productos")
        
        # Estadísticas de precios
        valid_prices = []
        for product in products:
            try:
                price_str = product.precio.replace('$', '').replace('.', '').replace(',', '')
                if price_str.isdigit():
                    valid_prices.append(int(price_str))
            except:
                continue
        
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            logger.info(f"💰 Precio promedio: ${avg_price:,.0f}")
            logger.info(f"💰 Precio mínimo: ${min(valid_prices):,.0f}")
            logger.info(f"💰 Precio máximo: ${max(valid_prices):,.0f}")
        
        # Estadísticas de ubicaciones
        locations = {}
        for product in products:
            if product.ubicacion and product.ubicacion != "Desconocida":
                locations[product.ubicacion] = locations.get(product.ubicacion, 0) + 1
        
        if locations:
            logger.info(f"📍 Ubicaciones únicas: {len(locations)}")
            top_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:3]
            logger.info("🌟 Top 3 ubicaciones:")
            for location, count in top_locations:
                logger.info(f"   - {location}: {count} productos")
        
        # Archivos generados
        logger.info(f"📄 Archivos CSV generados: {len(session_results['csv_files_generated'])}")
        for csv_file in session_results['csv_files_generated']:
            logger.info(f"   - {os.path.basename(csv_file)}")
        
        logger.info("="*60)


async def main():
    """Función principal del sistema de scraping"""
    parser = argparse.ArgumentParser(
        description='Sistema de Web Scraping para MercadoLibre Argentina'
    )
    parser.add_argument(
        '--terms', 
        nargs='+', 
        help='Términos de búsqueda personalizados (ej: --terms notebook smartphone televisor)'
    )
    parser.add_argument(
        '--max-products', 
        type=int, 
        default=50, 
        help='Máximo número de productos por término (default: 50)'
    )
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='Ejecutar en modo de prueba con menos productos'
    )
    
    args = parser.parse_args()
    
    # Configurar parámetros
    search_terms = args.terms
    max_products = 10 if args.test else args.max_products
    
    logger.info("🎯 Sistema de Web Scraping MercadoLibre Argentina")
    logger.info("="*50)
    
    try:
        # Crear y ejecutar sesión de scraping
        session = ScrapingSession(search_terms=search_terms, max_products=max_products)
        results = await session.run_complete_scraping()
        
        # Mostrar resumen final
        if results['success']:
            logger.info("\n🎉 ¡SCRAPING COMPLETADO EXITOSAMENTE!")
            logger.info(f"📊 {results['products_scraped']} productos extraídos")
            logger.info(f"📄 {len(results['csv_files_generated'])} archivos CSV generados")
            logger.info(f"⏱️ Tiempo total: {results.get('duration', 0):.2f} segundos")
            
            # Mostrar archivos generados
            if results['csv_files_generated']:
                logger.info("\n📁 Archivos generados:")
                for csv_file in results['csv_files_generated']:
                    logger.info(f"   ✅ {csv_file}")
        else:
            logger.error("❌ El scraping no se completó exitosamente")
            if results['errors']:
                logger.error(f"Errores: {', '.join(results['errors'])}")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("⚠️ Scraping interrumpido por el usuario")
        return 130
    except Exception as e:
        logger.error(f"❌ Error fatal en el sistema: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"🔥 Error crítico del sistema: {e}")
        sys.exit(1)