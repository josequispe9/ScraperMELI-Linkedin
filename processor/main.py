import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import os

class DataProcessor:
    def __init__(self, mercadolibre_file, linkedin_file):
        """
        Inicializa el procesador de datos con los archivos CSV
        """
        self.ml_df = pd.read_csv(mercadolibre_file)
        self.linkedin_df = pd.read_csv(linkedin_file)
        
        # Crear directorio de salida si no existe
        os.makedirs('outputs', exist_ok=True)
        
        # Limpiar y preparar los datos
        self._clean_data()
    
    def _clean_data(self):
        """
        Limpia y prepara los datos para el análisis
        """
        print("Limpiando datos...")
        
        # Limpiar datos de MercadoLibre
        self._clean_mercadolibre_data()
        
        # Limpiar datos de LinkedIn
        self._clean_linkedin_data()
        
        print("Datos limpiados exitosamente")
    
    def _clean_mercadolibre_data(self):
        """
        Limpia los datos de MercadoLibre
        """
        # Limpiar precios - formato específico con $ y puntos como separadores de miles
        def clean_price(price_str):
            if pd.isna(price_str) or str(price_str).lower() in ['no disponible', 'nan']:
                return 0
            
            # Remover $ y espacios
            cleaned = str(price_str).replace('$', '').replace(' ', '')
            # Remover puntos que actúan como separadores de miles
            cleaned = cleaned.replace('.', '')
            # Si hay coma, es separador decimal
            if ',' in cleaned:
                cleaned = cleaned.replace(',', '.')
            
            try:
                return float(cleaned)
            except:
                return 0
        
        self.ml_df['precio_numerico'] = self.ml_df['precio'].apply(clean_price)
        
        # Limpiar vendedor (manejar "No disponible")
        def clean_vendor(vendor_str):
            if pd.isna(vendor_str) or str(vendor_str).lower() == 'no disponible':
                return 'Vendedor no especificado'
            return str(vendor_str)
        
        self.ml_df['vendedor_limpio'] = self.ml_df['vendedor'].apply(clean_vendor)
        
        # Limpiar reputación del vendedor (muchos son "No disponible")
        def clean_reputation(rep_str):
            if pd.isna(rep_str) or str(rep_str).lower() == 'no disponible':
                return 'Sin información de reputación'
            
            rep_str = str(rep_str).lower()
            if 'verde' in rep_str or 'buena' in rep_str or 'excelente' in rep_str:
                return 'Buena reputación'
            elif 'amarilla' in rep_str or 'regular' in rep_str:
                return 'Reputación regular'
            elif 'roja' in rep_str or 'mala' in rep_str:
                return 'Mala reputación'
            elif 'nuevo' in rep_str or 'sin reputación' in rep_str:
                return 'Vendedor nuevo'
            else:
                return 'Sin información de reputación'
        
        self.ml_df['reputacion_limpia'] = self.ml_df['reputacion_vendedor'].apply(clean_reputation)
        
        # Limpiar disponibilidad (formato "Sí"/"No")
        self.ml_df['disponible_bool'] = self.ml_df['disponible'].apply(
            lambda x: True if str(x).lower() in ['sí', 'si', 'true', '1', 'disponible'] else False
        )
        
        # Limpiar envío gratis (formato "Sí"/"No")
        self.ml_df['envio_gratis_bool'] = self.ml_df['envio_gratis'].apply(
            lambda x: True if str(x).lower() in ['sí', 'si', 'true', '1', 'gratis'] else False
        )
    
    def _clean_linkedin_data(self):
        """
        Limpia los datos de LinkedIn
        """
        # Convertir fecha de publicación - muchos son "No encontrado" o fechas específicas
        def parse_date(date_str):
            if pd.isna(date_str) or str(date_str).lower() in ['no encontrado', 'nan']:
                # Si no hay fecha, asumir que es reciente (últimas 24 horas)
                return datetime.now() - timedelta(hours=12)
            
            # Si es una fecha específica como "2025-06-04"
            try:
                return datetime.strptime(str(date_str), '%Y-%m-%d')
            except:
                pass
            
            date_str = str(date_str).lower()
            now = datetime.now()
            
            if 'hora' in date_str or 'hour' in date_str:
                hours = re.findall(r'\d+', date_str)
                if hours:
                    return now - timedelta(hours=int(hours[0]))
            elif 'día' in date_str or 'day' in date_str or 'hace' in date_str:
                days = re.findall(r'\d+', date_str)
                if days:
                    return now - timedelta(days=int(days[0]))
            elif 'semana' in date_str or 'week' in date_str:
                weeks = re.findall(r'\d+', date_str)
                if weeks:
                    return now - timedelta(weeks=int(weeks[0]))
            elif 'mes' in date_str or 'month' in date_str:
                months = re.findall(r'\d+', date_str)
                if months:
                    return now - timedelta(days=int(months[0])*30)
            
            return now - timedelta(hours=12)  # Default: hace 12 horas
        
        self.linkedin_df['fecha_publicacion_dt'] = self.linkedin_df['fecha_publicacion'].apply(parse_date)
        
        # Limpiar nivel de experiencia - viene en el formato complejo que muestras
        def clean_experience_level(level_str):
            if pd.isna(level_str) or str(level_str).lower() in ['no disponible', 'nan']:
                return 'No especificado'
            
            level_str = str(level_str).lower()
            
            # Buscar patrones específicos
            if 'desenvolvedor' in level_str or 'developer' in level_str:
                if 'senior' in level_str or 'sr' in level_str:
                    return 'Senior level'
                elif 'junior' in level_str or 'jr' in level_str:
                    return 'Entry level'
                else:
                    return 'Mid level'
            elif 'entry' in level_str or 'junior' in level_str or 'trainee' in level_str:
                return 'Entry level'
            elif 'senior' in level_str or 'sr' in level_str:
                return 'Senior level'
            elif 'mid' in level_str or 'semi' in level_str or 'pleno' in level_str:
                return 'Mid level'
            else:
                return 'No especificado'
        
        self.linkedin_df['nivel_experiencia_limpio'] = self.linkedin_df['nivel_experiencia'].apply(clean_experience_level)
        
        # Limpiar modalidad - ya viene limpia
        def clean_modality(modality_str):
            if pd.isna(modality_str) or str(modality_str).lower() == 'no disponible':
                return 'No especificado'
            
            modality_str = str(modality_str).lower()
            if 'remoto' in modality_str or 'remote' in modality_str:
                return 'Remoto'
            elif 'presencial' in modality_str or 'on-site' in modality_str or 'oficina' in modality_str:
                return 'Presencial'
            elif 'híbrido' in modality_str or 'hybrid' in modality_str:
                return 'Híbrido'
            else:
                return str(modality_str).title()
        
        self.linkedin_df['modalidad_limpia'] = self.linkedin_df['modalidad'].apply(clean_modality)
    
    def generate_mercadolibre_reports(self):
        """
        Genera los reportes de MercadoLibre
        """
        print("Generando reportes de MercadoLibre...")
        
        # 1. Productos por rango de precio
        def categorize_price(price):
            if price < 100000:
                return 'Bajo'
            elif price <= 500000:
                return 'Medio'
            else:
                return 'Alto'
        
        self.ml_df['rango_precio'] = self.ml_df['precio_numerico'].apply(categorize_price)
        
        productos_precio = self.ml_df.groupby('rango_precio').agg({
            'producto': 'count',
            'precio_numerico': ['mean', 'min', 'max']
        }).round(2)
        
        productos_precio.columns = ['cantidad_productos', 'precio_promedio', 'precio_minimo', 'precio_maximo']
        productos_precio = productos_precio.reset_index()
        productos_precio.to_csv('outputs/productos_por_rango_precio.csv', index=False)
        
        # 2. Productos por vendedor
        productos_vendedor = self.ml_df.groupby(['vendedor_limpio', 'reputacion_limpia']).agg({
            'producto': 'count',
            'precio_numerico': 'mean',
            'disponible_bool': 'sum',
            'envio_gratis_bool': 'sum'
        }).round(2)
        
        productos_vendedor.columns = ['cantidad_productos', 'precio_promedio', 'productos_disponibles', 'productos_envio_gratis']
        productos_vendedor = productos_vendedor.reset_index()
        productos_vendedor = productos_vendedor.sort_values('cantidad_productos', ascending=False)
        productos_vendedor.to_csv('outputs/productos_por_vendedor.csv', index=False)
        
        # 3. Factor personalizado: Relación precio/reputación con disponibilidad
        def calculate_value_score(row):
            """
            Calcula un puntaje de valor basado en precio, reputación y disponibilidad
            """
            base_score = 0
            
            # Puntaje por reputación
            reputation_scores = {
                'Buena reputación': 4,
                'Reputación regular': 2,
                'Vendedor nuevo': 1,
                'Mala reputación': 0,
                'Sin información de reputación': 0
            }
            base_score += reputation_scores.get(row['reputacion_limpia'], 0)
            
            # Puntaje por disponibilidad
            if row['disponible_bool']:
                base_score += 2
            
            # Puntaje por envío gratis
            if row['envio_gratis_bool']:
                base_score += 1
            
            # Normalizar por precio (productos más baratos en su rango obtienen mejor puntaje)
            if row['precio_numerico'] > 0:
                # Crear rangos de precio para normalización
                if row['precio_numerico'] < 100000:  # Rango bajo
                    price_score = max(0, 3 - (row['precio_numerico'] / 50000))
                elif row['precio_numerico'] <= 500000:  # Rango medio
                    price_score = max(0, 2 - ((row['precio_numerico'] - 100000) / 200000))
                else:  # Rango alto
                    price_score = max(0, 1 - ((row['precio_numerico'] - 500000) / 500000))
                base_score += price_score
            
            return round(base_score, 2)
        
        self.ml_df['puntaje_valor'] = self.ml_df.apply(calculate_value_score, axis=1)
        
        factor_personalizado = self.ml_df[['producto', 'precio_numerico', 'reputacion_limpia', 
                                         'disponible_bool', 'envio_gratis_bool', 'puntaje_valor', 
                                         'categoria', 'vendedor_limpio']].copy()
        factor_personalizado = factor_personalizado.sort_values('puntaje_valor', ascending=False)
        factor_personalizado.to_csv('outputs/productos_por_factor_personalizado.csv', index=False)
        
        print("Reportes de MercadoLibre generados exitosamente")
    
    def generate_linkedin_reports(self):
        """
        Genera los reportes de LinkedIn
        """
        print("Generando reportes de LinkedIn...")
        
        # 1. Empleos por fecha de publicación
        def categorize_publication_date(pub_date):
            now = datetime.now()
            diff = now - pub_date
            
            if diff.days == 0:
                return 'Últimas 24 horas'
            elif diff.days <= 7:
                return 'Última semana'
            else:
                return 'Más de una semana'
        
        self.linkedin_df['categoria_fecha'] = self.linkedin_df['fecha_publicacion_dt'].apply(categorize_publication_date)
        
        empleos_fecha = self.linkedin_df.groupby('categoria_fecha').agg({
            'titulo_puesto': 'count',
            'empresa': 'nunique'
        })
        
        empleos_fecha.columns = ['cantidad_empleos', 'empresas_unicas']
        empleos_fecha = empleos_fecha.reset_index()
        empleos_fecha.to_csv('outputs/empleos_por_fecha_publicacion.csv', index=False)
        
        # 2. Empleos por nivel de experiencia
        empleos_experiencia = self.linkedin_df.groupby('nivel_experiencia_limpio').agg({
            'titulo_puesto': 'count',
            'empresa': 'nunique'
        })
        
        empleos_experiencia.columns = ['cantidad_empleos', 'empresas_unicas']
        empleos_experiencia = empleos_experiencia.reset_index()
        empleos_experiencia = empleos_experiencia.sort_values('cantidad_empleos', ascending=False)
        empleos_experiencia.to_csv('outputs/empleos_por_nivel_experiencia.csv', index=False)
        
        # 3. Factor personalizado: Empleos por modalidad y ubicación
        empleos_modalidad = self.linkedin_df.groupby(['modalidad_limpia', 'ubicacion']).agg({
            'titulo_puesto': 'count',
            'empresa': 'nunique'
        })
        
        empleos_modalidad.columns = ['cantidad_empleos', 'empresas_unicas']
        empleos_modalidad = empleos_modalidad.reset_index()
        empleos_modalidad = empleos_modalidad.sort_values('cantidad_empleos', ascending=False)
        empleos_modalidad.to_csv('outputs/empleos_por_factor_personalizado.csv', index=False)
        
        print("Reportes de LinkedIn generados exitosamente")
    
    def generate_summary_report(self):
        """
        Genera un reporte resumen con estadísticas generales
        """
        print("Generando reporte resumen...")
        
        summary = {
            'fecha_analisis': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_productos_ml': len(self.ml_df),
            'total_empleos_linkedin': len(self.linkedin_df),
            'precio_promedio_ml': round(self.ml_df['precio_numerico'].mean(), 2),
            'precio_mediano_ml': round(self.ml_df['precio_numerico'].median(), 2),
            'productos_disponibles': self.ml_df['disponible_bool'].sum(),
            'productos_envio_gratis': self.ml_df['envio_gratis_bool'].sum(),
            'empleos_remotos': len(self.linkedin_df[self.linkedin_df['modalidad_limpia'] == 'Remoto']),
            'empleos_presenciales': len(self.linkedin_df[self.linkedin_df['modalidad_limpia'] == 'Presencial']),
            'empleos_hibridos': len(self.linkedin_df[self.linkedin_df['modalidad_limpia'] == 'Híbrido'])
        }
        
        summary_df = pd.DataFrame([summary])
        summary_df.to_csv('outputs/reporte_resumen.csv', index=False)
        
        print("Reporte resumen generado exitosamente")
    
    def run_analysis(self):
        """
        Ejecuta todo el análisis y genera todos los reportes
        """
        print("Iniciando análisis completo...")
        
        # Generar reportes de MercadoLibre
        self.generate_mercadolibre_reports()
        
        # Generar reportes de LinkedIn
        self.generate_linkedin_reports()
        
        # Generar reporte resumen
        self.generate_summary_report()
        
        print("\n" + "="*50)
        print("ANÁLISIS COMPLETADO EXITOSAMENTE")
        print("="*50)
        print("Archivos generados:")
        print("- outputs/productos_por_rango_precio.csv")
        print("- outputs/productos_por_vendedor.csv")
        print("- outputs/productos_por_factor_personalizado.csv")
        print("- outputs/empleos_por_fecha_publicacion.csv")
        print("- outputs/empleos_por_nivel_experiencia.csv")
        print("- outputs/empleos_por_factor_personalizado.csv")
        print("- outputs/reporte_resumen.csv")
        print("="*50)

# Ejemplo de uso
if __name__ == "__main__":
    # Reemplazar con las rutas de tus archivos CSV
    MERCADOLIBRE_FILE = "C:/Users/Jose Quispe}/Desktop/repositorios/ScraperMELI-Linkedin/data/mercadolibre_productos_20250603_161938.csv"  
    LINKEDIN_FILE = "C:/Users/Jose Quispe}/Desktop/repositorios/ScraperMELI-Linkedin/data/linkedin_jobs_20250604_160527.csv"  
     
    try:
        # Crear instancia del procesador
        processor = DataProcessor(MERCADOLIBRE_FILE, LINKEDIN_FILE)
        
        # Ejecutar análisis completo
        processor.run_analysis()
        
    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo especificado. {e}")
        print("Por favor, asegúrate de que los archivos CSV estén en el directorio correcto.")
    except Exception as e:
        print(f"Error durante el procesamiento: {e}")
