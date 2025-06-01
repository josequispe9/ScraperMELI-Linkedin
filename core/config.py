from dotenv import load_dotenv
import os
from dataclasses import dataclass, field
from typing import Optional
from random import choice

load_dotenv()

@dataclass
class BrowserConfig:
    headless: bool = True
    user_agents: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_3) AppleWebKit/537.36 Chrome/89.0.4389.82"
    ])
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 30000
    slow_mo: int = 100  # ms entre acciones para parecer más humano

    def get_random_user_agent(self) -> str:
        return choice(self.user_agents)
    
      
@dataclass
class ScrapingConfig:
    max_retries: int = 3
    delay_range: tuple = (2, 5)
    concurrent_pages: int = 3
    batch_size: int = 50
    storage_state_path: str = "data/linkedin_session.json"

@dataclass
class LinkedInConfig:
    email: str = os.getenv("LINKEDIN_EMAIL", "")
    password: str = os.getenv("LINKEDIN_PASSWORD", "")
    base_url: str = "https://www.linkedin.com/jobs/search/"
    max_jobs_per_search: int = 100
    
    def __post_init__(self):
        if not self.email or not self.password:
            raise ValueError("LinkedIn credentials not found in environment variables")
@dataclass
class MercadoLibreConfig:
    base_url: str = "https://listado.mercadolibre.com.ar"
    search_terms: list[str] = field(default_factory=lambda: ["monitor", "notebook"])
    max_products_per_term: int = 50
    country_code: str = "AR"


# Instancias globales
BROWSER_CONFIG = BrowserConfig()
SCRAPING_CONFIG = ScrapingConfig()
LINKEDIN_CONFIG = LinkedInConfig()
MERCADOLIBRE_CONFIG = MercadoLibreConfig()


"""
print("BrowserConfig:", BROWSER_CONFIG)
print("ScrapingConfig:", SCRAPING_CONFIG)
print("LinkedInConfig:", LINKEDIN_CONFIG)
print("MercadoLibreConfig:", MERCADOLIBRE_CONFIG)
"""