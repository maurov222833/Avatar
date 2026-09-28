import requests
import re
from urllib.parse import quote_plus

def get_first_youtube_video(query):
    encoded = quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            # Buscar IDs de video de la forma "videoId":"abc123xyz"
            ids = re.findall(r'"videoId":"([^"]+)"', res.text)
            if ids:
                first_id = ids[0]
                return f"https://www.youtube.com/watch?v={first_id}&autoplay=1"
    except Exception as e:
        print(f"Error: {e}")
    return f"https://www.youtube.com/results?search_query={encoded}"

if __name__ == "__main__":
    url = get_first_youtube_video("bonito bonito")
    print("DIRECT VIDEO URL:", url)
