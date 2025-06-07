"""
Sistema de Web Scraping para LinkedIn Jobs Argentina
Extrae información de empleos y almacena en formato CSV
"""

import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import argparse

# Importar módulos locales
from .scraper import LinkedInJobsScraper, scrape_linkedin_jobs
from .parser import JobData
from core.utils import retry_async
from core.logger import get_logger, LogConfig

# Configuración del logger
config = LogConfig(json_format=False)
logger = get_logger("linkedin_main", config)


class CSVExporter:
    """Exportador de datos de empleos a formato CSV"""
    
    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.required_fields = [
            'indice', 'fecha_extraccion', 'titulo_puesto', 'empresa', 
            'ubicacion', 'url_empleo', 'modalidad', 'fecha_publicacion',
            'descripcion_breve', 'nivel_experiencia', 'beneficios_ofrecidos'
        ]
    
    def export_to_csv(self, jobs: List[JobData], filename: str = None) -> str:
        """Exportar empleos a CSV"""
        if not jobs:
            logger.warning("No hay empleos para exportar")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_jobs_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.required_fields)
                writer.writeheader()
                
                valid_jobs = 0
                for job in jobs:
                    job_dict = self._job_to_dict(job)
                    if self._is_valid_job(job_dict):
                        writer.writerow(job_dict)
                        valid_jobs += 1
            
            logger.info(f"✅ CSV exportado: {filepath} ({valid_jobs} empleos)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ Error exportando CSV: {e}")
            raise
    
    def _job_to_dict(self, job: JobData) -> Dict[str, str]:
        """Convertir JobData a diccionario"""
        return {
            'indice': str(job.indice),
            'fecha_extraccion': job.fecha_extraccion,
            'titulo_puesto': self._clean_text(job.titulo_puesto),
            'empresa': self._clean_text(job.empresa),
            'ubicacion': self._clean_text(job.ubicacion),
            'url_empleo': job.url_empleo,
            'modalidad': self._clean_text(job.modalidad),
            'fecha_publicacion': self._clean_text(job.fecha_publicacion),
            'descripcion_breve': self._clean_text(job.descripcion_breve),
            'nivel_experiencia': self._clean_text(job.nivel_experiencia),
            'beneficios_ofrecidos': self._clean_text(job.beneficios_ofrecidos)
        }
    
    def _clean_text(self, text: str) -> str:
        """Limpiar texto para CSV"""
        if not text or text in ['N/A', 'Desconocido', 'Sin información']:
            return 'No disponible'
        return text.strip().replace('\n', ' ').replace('\r', ' ')
    
    def _is_valid_job(self, job_dict: Dict[str, str]) -> bool:
        """Validar datos mínimos del empleo"""
        title = job_dict.get('titulo_puesto', '')
        company = job_dict.get('empresa', '')
        
        return (title and title != 'No disponible' and len(title) >= 3 and 
                company and company != 'No disponible')


class LinkedInScraper:
    """Scraper principal para LinkedIn Jobs"""
    
    def __init__(self, search_terms: List[str] = None, max_jobs: int = 50):
        self.search_terms = search_terms or self._get_default_terms()
        self.max_jobs = max_jobs
        self.csv_exporter = CSVExporter()
    
    def _get_default_terms(self) -> List[str]:
        """Términos de búsqueda por defecto"""
        return [
            "python developer",
            "data analyst", 
            "frontend developer",
            "backend developer",
            "project manager"
        ]
    
    async def run(self) -> Dict[str, Any]:
        """Ejecutar scraping completo"""
        start_time = datetime.now()
        logger.info("🚀 Iniciando scraping de LinkedIn")
        logger.info(f"📝 Términos: {', '.join(self.search_terms)}")
        logger.info(f"🎯 Max empleos por término: {self.max_jobs}")
        
        try:
            # Ejecutar scraping
            jobs = await self._scrape_jobs()
            
            if not jobs:
                logger.error("❌ No se encontraron empleos")
                return {'success': False, 'jobs_count': 0}
            
            # Exportar a CSV
            csv_file = self.csv_exporter.export_to_csv(jobs)
            
            # Calcular estadísticas básicas
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Scraping completado en {duration:.1f}s")
            logger.info(f"💼 {len(jobs)} empleos extraídos")
            logger.info(f"📄 Archivo: {csv_file}")
            
            return {
                'success': True,
                'jobs_count': len(jobs),
                'csv_file': csv_file,
                'duration': duration
            }
            
        except Exception as e:
            logger.error(f"❌ Error en scraping: {e}")
            return {'success': False, 'error': str(e)}
    
    @retry_async(max_retries=3, delay=5)
    async def _scrape_jobs(self) -> List[JobData]:
        """Ejecutar scraping con reintentos"""
        try:
            jobs = await scrape_linkedin_jobs(
                search_terms=self.search_terms,
                max_jobs=self.max_jobs,
                include_details=True  # Habilitar para usar campos completos
            )
            
            if not jobs:
                raise RuntimeError("Scraping no devolvió resultados")
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error en _scrape_jobs: {e}")
            raise


async def main():
    
    parser = argparse.ArgumentParser(
        description='LinkedIn Jobs Scraper - Argentina'
    )
    parser.add_argument(
        '--terms', 
        nargs='+', 
        help='Términos de búsqueda personalizados'
    )
    parser.add_argument(
        '--max-jobs', 
        type=int, 
        default=50, 
        help='Máximo empleos por término (default: 50)'
    )
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='Modo prueba (10 empleos máximo)'
    )
    
    args = parser.parse_args()
    
    # Configurar parámetros
    max_jobs = 10 if args.test else args.max_jobs
    
    try:
        # Crear y ejecutar scraper
        scraper = LinkedInScraper(
            search_terms=args.terms,
            max_jobs=max_jobs
        )
        
        results = await scraper.run()
        
        if results['success']:
            logger.info("\n🎉 ¡SCRAPING COMPLETADO!")
            logger.info(f"💼 {results['jobs_count']} empleos extraídos")
            logger.info(f"📄 Archivo: {results['csv_file']}")
            return 0
        else:
            logger.error("❌ Scraping falló")
            return 1
        
    except KeyboardInterrupt:
        logger.warning("⚠️ Interrumpido por usuario")
        return 130
    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"🔥 Error del sistema: {e}")
        sys.exit(1)