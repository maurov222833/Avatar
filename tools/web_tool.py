import requests
import re
from urllib.parse import quote_plus

class WebTool:
    """
    MÓDULO DE INVESTIGACIÓN PROFUNDA (DEEP RESEARCH ENGINE) PARA AVATAR AI.
    Permite a Avatar buscar documentación web y leer páginas técnicas en tiempo real.
    """

    @staticmethod
    def search_web(query: str, max_results: int = 5) -> str:
        """
        Realiza una búsqueda web para obtener información o documentación actualizada.
        """
        try:
            encoded = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
            }
            res = requests.get(url, headers=headers, timeout=12)
            
            if res.status_code == 200:
                html = res.text
                results = []
                # Extraer enlaces y descripciones
                matches = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
                snippets = re.findall(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
                
                output = f"[RESULTADOS DE BÚSQUEDA WEB PARA: '{query}']\n\n"
                for i in range(min(len(matches), max_results)):
                    raw_url, raw_title = matches[i]
                    title = re.sub(r'<[^>]+>', '', raw_title).strip()
                    snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else "Sin resumen disponible"
                    output += f"{i+1}. {title}\n   Enlace: {raw_url.strip()}\n   Resumen: {snippet}\n\n"
                
                if not matches:
                    output += "No se pudieron extraer resultados estructurados. Puedes usar FETCH_URL con un enlace directo."
                return output
            else:
                # Fallback con Wikipedia/API abierta
                wiki_url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json"
                wiki_res = requests.get(wiki_url, timeout=10)
                if wiki_res.status_code == 200:
                    data = wiki_res.json()
                    search_items = data.get("query", {}).get("search", [])
                    output = f"[BÚSQUEDA WIKIPEDIA / DOCUMENTACIÓN PARA: '{query}']\n\n"
                    for i, item in enumerate(search_items[:max_results]):
                        snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                        output += f"{i+1}. {item.get('title')}\n   Resumen: {snippet}\n\n"
                    return output
                return f"[Aviso Web]: Búsqueda no disponible en este momento ({res.status_code})."
        except Exception as e:
            return f"[Error en Búsqueda Web]: {str(e)}"

    @staticmethod
    def fetch_url(url: str, max_chars: int = 4000) -> str:
        """
        Descarga y lee el texto principal de una página web o documentación en línea.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code == 200:
                html = res.text
                clean_text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                clean_text = re.sub(r'<style[^>]*>.*?</style>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
                clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
                clean_text = ' '.join(clean_text.split()).strip()
                
                truncated = clean_text[:max_chars]
                return f"[CONTENIDO DE PÁGINA WEB: {url}]\n\n{truncated}\n\n... (Texto resumido a los primeros {max_chars} caracteres)."
            else:
                return f"[Error HTTP {res.status_code}]: No se pudo abrir la URL {url}."
        except Exception as e:
            return f"[Error al descargar la página web]: {str(e)}"
