import re

def sanitize_query(raw_query: str) -> str:
    if not raw_query:
        return "bonito bonito"
        
    clean = re.sub(
        r'(?i)\b(en\s+el\s+mismo\s+youtube|que\s+ya\s+se\s+encuentra\s+abierto|no\s+abras\s+otro|no\s+habras\s+otro|en\s+el\s+mismo|dale\s+play\s+a\s+la|dale\s+play|ahora\s+reproduce|ahora\s+repruduce|reproduce\s+esa\s+misma|esta\s+misma|esa\s+misma|nuevamente|ve\s+a\s+mi\s+navegador(\s+y)?|abre\s+youtube(\s+y)?|reproduce(\s+ahora|\s+la\s+canción|\s+la\s+cancion|\s+musica|\s+música)?|canción|cancion|en\s+youtube|e\.\s*youtube|por\s+favor|pon\s+la|escuchar|quiero\s+que\s+reproduscas|la)\b',
        ' ',
        raw_query
    )
    clean = re.sub(r'[^\w\s]', ' ', clean)
    clean = ' '.join(clean.split()).strip()
    return clean if clean else "bonito bonito"

queries = [
    'Quiero que reproduscas la canción bonito bonito en el mismo YouTube que ya se encuentra abierto, no abras otro.',
    'Ahora reproduce en el mismo YouTube, no abras otro. ayer y hoy, canción vallenata,',
    'Dale play a la canción',
    'Ahora repruduce esa misma canción nuevamente.'
]

for q in queries:
    print(f"BEFORE: {q}")
    print(f"AFTER:  {sanitize_query(q)}\n")
