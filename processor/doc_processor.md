# DataProcessor - Documentación Completa

## Descripción General

`DataProcessor` es una clase de Python diseñada para procesar y analizar datos de dos fuentes principales:
- **MercadoLibre**: Productos, precios, vendedores y características de envío
- **LinkedIn**: Ofertas de trabajo, experiencia requerida, modalidad y ubicación

La clase limpia los datos, realiza análisis estadísticos y genera reportes en formato CSV para facilitar la toma de decisiones comerciales y de recursos humanos.

## Instalación y Dependencias

### Dependencias Requeridas

```python
pip install pandas numpy
```

### Dependencias del Sistema
- Python 3.7+
- Módulos estándar: `datetime`, `re`, `os`

## Estructura de Archivos

```
proyecto/
├── main.py                 # Archivo principal con la clase DataProcessor
├── data/                   # Directorio de datos de entrada
│   ├── mercadolibre_productos_*.csv
│   └── linkedin_jobs_*.csv
└── outputs/                # Directorio de salida (se crea automáticamente)
    ├── productos_por_rango_precio.csv
    ├── productos_por_vendedor.csv
    ├── productos_por_factor_personalizado.csv
    ├── empleos_por_fecha_publicacion.csv
    ├── empleos_por_nivel_experiencia.csv
    ├── empleos_por_factor_personalizado.csv
    └── reporte_resumen.csv
```

## Formato de Datos de Entrada

### Archivo CSV de MercadoLibre
Debe contener las siguientes columnas:
- `producto`: Nombre del producto
- `precio`: Precio en formato "$X.XXX,XX" o similar
- `vendedor`: Nombre del vendedor
- `reputacion_vendedor`: Reputación del vendedor
- `disponible`: "Sí"/"No" - Disponibilidad del producto
- `envio_gratis`: "Sí"/"No" - Si incluye envío gratis
- `categoria`: Categoría del producto

### Archivo CSV de LinkedIn
Debe contener las siguientes columnas:
- `titulo_puesto`: Título del puesto de trabajo
- `empresa`: Nombre de la empresa
- `fecha_publicacion`: Fecha de publicación del empleo
- `nivel_experiencia`: Nivel de experiencia requerido
- `modalidad`: Modalidad de trabajo (remoto, presencial, híbrido)
- `ubicacion`: Ubicación del empleo

## Uso Básico

### Ejemplo Simple

```python
from main import DataProcessor

# Rutas de los archivos CSV
mercadolibre_file = "data/mercadolibre_productos.csv"
linkedin_file = "data/linkedin_jobs.csv"

# Crear instancia del procesador
processor = DataProcessor(mercadolibre_file, linkedin_file)

# Ejecutar análisis completo
processor.run_analysis()
```

### Uso Avanzado - Análisis Específicos

```python
# Crear instancia
processor = DataProcessor(mercadolibre_file, linkedin_file)

# Generar solo reportes de MercadoLibre
processor.generate_mercadolibre_reports()

# Generar solo reportes de LinkedIn
processor.generate_linkedin_reports()

# Generar reporte resumen
processor.generate_summary_report()
```

## Documentación de la API

### Clase DataProcessor

#### `__init__(mercadolibre_file, linkedin_file)`
**Inicializa el procesador de datos**

**Parámetros:**
- `mercadolibre_file` (str): Ruta al archivo CSV de MercadoLibre
- `linkedin_file` (str): Ruta al archivo CSV de LinkedIn

**Funcionalidad:**
- Carga los archivos CSV en DataFrames de pandas
- Crea el directorio `outputs/` si no existe
- Ejecuta automáticamente la limpieza de datos

#### `_clean_data()`
**Método privado que coordina la limpieza de datos**

Ejecuta secuencialmente:
- `_clean_mercadolibre_data()`
- `_clean_linkedin_data()`

#### `_clean_mercadolibre_data()`
**Limpia y normaliza los datos de MercadoLibre**

**Transformaciones realizadas:**
- **Precios**: Convierte formato "$1.234.567,89" a float
- **Vendedores**: Reemplaza "No disponible" por "Vendedor no especificado"
- **Reputación**: Categoriza en: "Buena reputación", "Reputación regular", "Mala reputación", "Vendedor nuevo", "Sin información"
- **Disponibilidad**: Convierte "Sí"/"No" a boolean
- **Envío gratis**: Convierte "Sí"/"No" a boolean

#### `_clean_linkedin_data()`
**Limpia y normaliza los datos de LinkedIn**

**Transformaciones realizadas:**
- **Fechas**: Convierte texto como "hace 2 días" a datetime
- **Nivel de experiencia**: Categoriza en: "Entry level", "Mid level", "Senior level", "No especificado"
- **Modalidad**: Normaliza a: "Remoto", "Presencial", "Híbrido"

#### `generate_mercadolibre_reports()`
**Genera reportes específicos de MercadoLibre**

**Reportes generados:**
1. **productos_por_rango_precio.csv**: Análisis por rango de precios (Bajo, Medio, Alto)
2. **productos_por_vendedor.csv**: Estadísticas por vendedor y reputación
3. **productos_por_factor_personalizado.csv**: Ranking de productos basado en puntaje de valor

#### `generate_linkedin_reports()`
**Genera reportes específicos de LinkedIn**

**Reportes generados:**
1. **empleos_por_fecha_publicacion.csv**: Empleos por antigüedad de publicación
2. **empleos_por_nivel_experiencia.csv**: Empleos por nivel de experiencia requerido
3. **empleos_por_factor_personalizado.csv**: Empleos por modalidad y ubicación

#### `generate_summary_report()`
**Genera un reporte resumen con estadísticas generales**

**Incluye:**
- Total de productos y empleos procesados
- Estadísticas de precios (promedio, mediana)
- Conteos de productos disponibles y con envío gratis
- Distribución de empleos por modalidad

#### `run_analysis()`
**Ejecuta el análisis completo**

Método principal que ejecuta secuencialmente:
1. Reportes de MercadoLibre
2. Reportes de LinkedIn  
3. Reporte resumen
4. Lista de archivos generados

## Descripción de Reportes Generados

### Reportes de MercadoLibre

#### 1. productos_por_rango_precio.csv
**Análisis de productos por rango de precio**

| Columna | Descripción |
|---------|-------------|
| rango_precio | Bajo (<$100k), Medio ($100k-$500k), Alto (>$500k) |
| cantidad_productos | Número de productos en el rango |
| precio_promedio | Precio promedio del rango |
| precio_minimo | Precio mínimo del rango |
| precio_maximo | Precio máximo del rango |

#### 2. productos_por_vendedor.csv
**Estadísticas por vendedor**

| Columna | Descripción |
|---------|-------------|
| vendedor_limpio | Nombre del vendedor |
| reputacion_limpia | Categoría de reputación |
| cantidad_productos | Productos publicados por el vendedor |
| precio_promedio | Precio promedio de sus productos |
| productos_disponibles | Productos actualmente disponibles |
| productos_envio_gratis | Productos con envío gratis |

#### 3. productos_por_factor_personalizado.csv
**Ranking de productos por puntaje de valor**

**Algoritmo de puntaje:**
- Reputación del vendedor: 0-4 puntos
- Disponibilidad: +2 puntos
- Envío gratis: +1 punto  
- Relación precio/rango: 0-3 puntos (productos más baratos en su rango obtienen más puntos)

### Reportes de LinkedIn

#### 4. empleos_por_fecha_publicacion.csv
**Empleos por antigüedad de publicación**

| Columna | Descripción |
|---------|-------------|
| categoria_fecha | Últimas 24 horas, Última semana, Más de una semana |
| cantidad_empleos | Número de empleos en la categoría |
| empresas_unicas | Empresas únicas que publicaron en la categoría |

#### 5. empleos_por_nivel_experiencia.csv
**Empleos por nivel de experiencia**

| Columna | Descripción |
|---------|-------------|
| nivel_experiencia_limpio | Entry level, Mid level, Senior level, No especificado |
| cantidad_empleos | Empleos que requieren este nivel |
| empresas_unicas | Empresas que buscan este nivel |

#### 6. empleos_por_factor_personalizado.csv
**Empleos por modalidad y ubicación**

| Columna | Descripción |
|---------|-------------|
| modalidad_limpia | Remoto, Presencial, Híbrido |
| ubicacion | Ubicación del empleo |
| cantidad_empleos | Empleos en esta modalidad/ubicación |
| empresas_unicas | Empresas que ofrecen esta modalidad/ubicación |

#### 7. reporte_resumen.csv
**Estadísticas generales del análisis completo**

## Manejo de Errores

### Errores Comunes y Soluciones

#### FileNotFoundError
```python
Error: No se encontró el archivo especificado
```
**Solución:** Verificar que las rutas de los archivos CSV sean correctas

#### Datos Faltantes
La clase maneja automáticamente:
- Precios "No disponible" → 0
- Fechas "No encontrado" → Fecha estimada reciente
- Vendedores "No disponible" → "Vendedor no especificado"
- Niveles de experiencia vacíos → "No especificado"

#### Formatos de Precio Incorrectos
El sistema intenta múltiples estrategias de parsing:
- Elimina símbolos ($, espacios)
- Maneja separadores de miles (puntos)
- Maneja separadores decimales (comas)
- Valor por defecto: 0 si no puede convertir

## Personalización y Extensión

### Agregar Nuevos Rangos de Precio

```python
def categorize_price(price):
    if price < 50000:
        return 'Muy Bajo'
    elif price < 100000:
        return 'Bajo'
    elif price <= 300000:
        return 'Medio-Bajo'
    elif price <= 500000:
        return 'Medio'
    elif price <= 1000000:
        return 'Alto'
    else:
        return 'Premium'
```

### Modificar el Algoritmo de Puntaje de Valor

```python
def calculate_value_score(row):
    # Tu lógica personalizada aquí
    # Ejemplo: dar más peso a productos con envío gratis
    base_score = 0
    
    if row['envio_gratis_bool']:
        base_score += 3  # Aumentado de 1 a 3
    
    # ... resto de la lógica
    return base_score
```

### Agregar Nuevos Reportes

```python
def generate_custom_report(self):
    """Genera un reporte personalizado"""
    # Tu análisis personalizado
    custom_analysis = self.ml_df.groupby('categoria').agg({
        'precio_numerico': ['mean', 'count', 'std']
    })
    
    custom_analysis.to_csv('outputs/reporte_personalizado.csv')
```

## Mejores Prácticas

### 1. Preparación de Datos
- Asegúrate de que los archivos CSV tengan las columnas esperadas
- Verifica que las rutas de archivo sean correctas
- Mantén copias de respaldo de los datos originales

### 2. Monitoreo de Resultados
- Revisa el reporte resumen para detectar anomalías
- Verifica que los conteos sean consistentes con tus expectativas
- Compara resultados entre diferentes ejecuciones

### 3. Optimización de Rendimiento
- Para datasets grandes (>100k filas), considera procesar en lotes
- Usa `pd.read_csv(chunksize=1000)` para archivos muy grandes
- Implementa logging para trackear el progreso

### 4. Mantenimiento
- Actualiza las funciones de limpieza cuando cambien los formatos de datos
- Documenta cualquier modificación al algoritmo de puntaje
- Mantén las dependencias actualizadas

## Troubleshooting

### Problema: Archivos de salida vacíos
**Posibles causas:**
- Datos de entrada malformados
- Errores en la limpieza de datos
- Permisos de escritura insuficientes

**Solución:**
```python
# Verificar que los datos se cargaron correctamente
print(f"Productos ML: {len(processor.ml_df)}")
print(f"Empleos LinkedIn: {len(processor.linkedin_df)}")

# Verificar muestra de datos limpios
print(processor.ml_df[['precio_numerico', 'disponible_bool']].head())
```

### Problema: Errores de memoria
**Para datasets muy grandes:**
```python
# Procesar en chunks
chunk_size = 1000
for chunk in pd.read_csv(filename, chunksize=chunk_size):
    # Procesar chunk por chunk
    process_chunk(chunk)
```

### Problema: Fechas incorrectas en LinkedIn
**Verificar el parsing de fechas:**
```python
# Examinar fechas originales vs procesadas
sample = processor.linkedin_df[['fecha_publicacion', 'fecha_publicacion_dt']].head(10)
print(sample)
```

## Licencia y Contribuciones

Este código está diseñado para uso interno y análisis de datos comerciales. Para contribuir mejoras o reportar bugs, contacta al equipo de desarrollo.

---

**Última actualización:** Junio 2025  
**Versión:** 1.0  
**Autor:** Equipo de Data Science