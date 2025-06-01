import asyncio
import random
import functools
from typing import Callable, Any
from .logger import get_logger, LogConfig

# Configurar el logger con formato legible para consola
config = LogConfig(json_format=False)

logger = get_logger("scraper", config)

async def random_delay(min_delay: float = 1, max_delay: float = 3):
    """Delay aleatorio para simular comportamiento humano"""
    delay = random.uniform(min_delay, max_delay)
    await asyncio.sleep(delay)

def retry_async(max_retries: int = 3, delay: float = 1, backoff: float = 2):
    """Decorador para reintentos con backoff exponencial"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Función {func.__name__} falló después de {max_retries} intentos: {e}")
                        raise last_exception
                    
                    logger.warning(f"Intento {attempt + 1} falló para {func.__name__}: {e}")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator

# Funciones específicas para Playwright - van en core/utils.py
async def safe_extract_text(page_or_element, selector: str = None, default: str = "N/A") -> str:
    """Extracción segura de texto - funciona con Page o ElementHandle"""
    try:
        if selector:
            element = await page_or_element.query_selector(selector)
            if element:
                return (await element.inner_text()).strip()
        else:
            # Si no hay selector, asumir que page_or_element es un elemento
            return (await page_or_element.inner_text()).strip()
    except:
        pass
    return default

async def safe_extract_attribute(page_or_element, attribute: str, selector: str = None, default: str = "N/A") -> str:
    """Extracción segura de atributos"""
    try:
        if selector:
            element = await page_or_element.query_selector(selector)
            if element:
                value = await element.get_attribute(attribute)
                return value.strip() if value else default
        else:
            value = await page_or_element.get_attribute(attribute)
            return value.strip() if value else default
    except:
        pass
    return default


# ============================================================================= #
#            Pequeño script para probar el modulo logger desde utils            #
# ============================================================================= #

# cd /app
# python -m core.utils

if __name__ == "__main__":
    import asyncio

    async def test_logger():
        logger.debug("✅ DEBUG: mensaje de depuración")
        logger.info("ℹ️ INFO: mensaje informativo")
        logger.warning("⚠️ WARNING: algo no está bien")
        logger.error("❌ ERROR: ocurrió un error")
        logger.critical("🔥 CRITICAL: error grave")

    @retry_async(max_retries=2, delay=1)
    async def test_retry():
        logger.info("Intentando ejecutar test_retry()")
        raise RuntimeError("Falla simulada para probar el retry")

    async def main():
        print("\n--- Probando distintos niveles del logger ---\n")
        await test_logger()
        
        print("\n--- Probando el decorador retry_async ---\n")
        try:
            await test_retry()
        except Exception as e:
            logger.error(f"Excepción final capturada: {e}")

    asyncio.run(main())
