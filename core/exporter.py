import json
import csv
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Protocol
from dataclasses import asdict, is_dataclass
from abc import ABC, abstractmethod

import pandas as pd

from .logger import get_logger, LogConfig

# Configurar logger
config = LogConfig(json_format=False)
logger = get_logger("exporter", config)


class DataExporter(Protocol):
    """Protocolo para exportadores de datos"""
    async def export(self, data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
        ...


class BaseExporter(ABC):
    """Clase base para todos los exportadores"""
    
    def __init__(self, add_timestamp: bool = True):
        self.add_timestamp = add_timestamp
    
    @abstractmethod
    async def export(self, data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
        """Exportar datos al formato específico"""
        pass
    
    def _prepare_filepath(self, filepath: Union[str, Path]) -> Path:
        """Preparar el filepath añadiendo timestamp si es necesario"""
        path = Path(filepath)
        
        if self.add_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = path.stem
            suffix = path.suffix
            path = path.parent / f"{stem}_{timestamp}{suffix}"
        
        # Crear directorio si no existe
        path.parent.mkdir(parents=True, exist_ok=True)
        
        return path
    
    def _normalize_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalizar datos para exportación"""
        normalized = []
        
        for item in data:
            if is_dataclass(item):
                item = asdict(item)
            
            # Convertir valores None a string vacío
            normalized_item = {}
            for key, value in item.items():
                if value is None:
                    normalized_item[key] = ""
                elif isinstance(value, (list, dict)):
                    normalized_item[key] = json.dumps(value, ensure_ascii=False)
                else:
                    normalized_item[key] = str(value)
            
            normalized.append(normalized_item)
        
        return normalized


class JSONExporter(BaseExporter):
    """Exportador a formato JSON"""
    
    def __init__(self, indent: int = 2, ensure_ascii: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.indent = indent
        self.ensure_ascii = ensure_ascii
    
    async def export(self, data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
        """Exportar datos a JSON"""
        path = self._prepare_filepath(filepath)
        
        try:
            # Normalizar datos para dataclasses
            export_data = []
            for item in data:
                if is_dataclass(item):
                    export_data.append(asdict(item))
                else:
                    export_data.append(item)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, 
                         indent=self.indent, 
                         ensure_ascii=self.ensure_ascii,
                         default=str)
            
            logger.info(f"Datos exportados a JSON: {path} ({len(data)} registros)")
            
        except Exception as e:
            logger.error(f"Error exportando a JSON: {e}")
            raise


class CSVExporter(BaseExporter):
    """Exportador a formato CSV"""
    
    def __init__(self, delimiter: str = ',', quoting: int = csv.QUOTE_MINIMAL, **kwargs):
        super().__init__(**kwargs)
        self.delimiter = delimiter
        self.quoting = quoting
    
    async def export(self, data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
        """Exportar datos a CSV"""
        if not data:
            logger.warning("No hay datos para exportar a CSV")
            return
        
        path = self._prepare_filepath(filepath)
        normalized_data = self._normalize_data(data)
        
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f, 
                    fieldnames=normalized_data[0].keys(),
                    delimiter=self.delimiter,
                    quoting=self.quoting
                )
                writer.writeheader()
                writer.writerows(normalized_data)
            
            logger.info(f"Datos exportados a CSV: {path} ({len(data)} registros)")
            
        except Exception as e:
            logger.error(f"Error exportando a CSV: {e}")
            raise


class ExcelExporter(BaseExporter):
    """Exportador a formato Excel"""
    
    def __init__(self, sheet_name: str = "Datos", **kwargs):
        super().__init__(**kwargs)
        self.sheet_name = sheet_name
    
    async def export(self, data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
        """Exportar datos a Excel"""
        if not data:
            logger.warning("No hay datos para exportar a Excel")
            return
        
        path = self._prepare_filepath(filepath)
        normalized_data = self._normalize_data(data)
        
        try:
            # Ejecutar en thread pool para operaciones I/O
            await asyncio.get_event_loop().run_in_executor(
                None, self._write_excel, normalized_data, path
            )
            
            logger.info(f"Datos exportados a Excel: {path} ({len(data)} registros)")
            
        except Exception as e:
            logger.error(f"Error exportando a Excel: {e}")
            raise
    
    def _write_excel(self, data: List[Dict[str, Any]], path: Path) -> None:
        """Escribir datos a Excel (método sincrónico)"""
        df = pd.DataFrame(data)
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=self.sheet_name, index=False)


class MultiFormatExporter:
    """Exportador que puede manejar múltiples formatos"""
    
    def __init__(self):
        self.exporters = {
            'json': JSONExporter(),
            'csv': CSVExporter(),
            'excel': ExcelExporter(),
            'xlsx': ExcelExporter(),
        }
    
    async def export(
        self, 
        data: List[Dict[str, Any]], 
        filepath: Union[str, Path],
        format: Optional[str] = None
    ) -> None:
        """Exportar datos detectando formato por extensión o especificado"""
        path = Path(filepath)
        
        if format is None:
            format = path.suffix.lower().lstrip('.')
        
        if format not in self.exporters:
            raise ValueError(f"Formato no soportado: {format}. Soportados: {list(self.exporters.keys())}")
        
        exporter = self.exporters[format]
        await exporter.export(data, filepath)
    
    def add_exporter(self, format: str, exporter: DataExporter) -> None:
        """Agregar un nuevo exportador personalizado"""
        self.exporters[format] = exporter


class BatchExporter:
    """Exportador que maneja datos en lotes para datasets grandes"""
    
    def __init__(self, batch_size: int = 1000):
        self.batch_size = batch_size
        self.multi_exporter = MultiFormatExporter()
    
    async def export_batches(
        self,
        data_generator,  # Generator que yield lotes de datos
        base_filepath: Union[str, Path],
        format: str = 'json'
    ) -> List[Path]:
        """Exportar datos en lotes"""
        exported_files = []
        batch_number = 1
        
        async for batch in data_generator:
            if not batch:
                continue
            
            # Crear nombre de archivo para el lote
            path = Path(base_filepath)
            batch_filepath = path.parent / f"{path.stem}_batch_{batch_number:03d}{path.suffix}"
            
            await self.multi_exporter.export(batch, batch_filepath, format)
            exported_files.append(batch_filepath)
            
            logger.info(f"Lote {batch_number} exportado: {len(batch)} registros")
            batch_number += 1
        
        logger.info(f"Exportación por lotes completada: {len(exported_files)} archivos")
        return exported_files


class DataAggregator:
    """Agregador de datos con funcionalidades de análisis básico"""
    
    @staticmethod
    async def aggregate_and_export(
        data: List[Dict[str, Any]], 
        filepath: Union[str, Path],
        group_by: Optional[str] = None,
        format: str = 'json'
    ) -> None:
        """Agregar datos y exportar con estadísticas básicas"""
        
        if not data:
            logger.warning("No hay datos para agregar")
            return
        
        # Crear resumen
        summary = {
            "metadata": {
                "total_records": len(data),
                "export_timestamp": datetime.now().isoformat(),
                "fields": list(data[0].keys()) if data else []
            },
            "data": data
        }
        
        # Agregar agrupación si se especifica
        if group_by and group_by in data[0]:
            grouped = {}
            for item in data:
                key = item.get(group_by, 'unknown')
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(item)
            
            summary["grouped_data"] = {
                group: {
                    "count": len(items),
                    "items": items
                }
                for group, items in grouped.items()
            }
        
        exporter = MultiFormatExporter()
        await exporter.export([summary], filepath, format)


# Instancia global del exportador multi-formato
exporter = MultiFormatExporter()
batch_exporter = BatchExporter()
aggregator = DataAggregator()


# Funciones de conveniencia
async def export_to_json(data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
    """Función de conveniencia para exportar a JSON"""
    await exporter.export(data, filepath, 'json')


async def export_to_csv(data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
    """Función de conveniencia para exportar a CSV"""
    await exporter.export(data, filepath, 'csv')


async def export_to_excel(data: List[Dict[str, Any]], filepath: Union[str, Path]) -> None:
    """Función de conveniencia para exportar a Excel"""
    await exporter.export(data, filepath, 'excel')