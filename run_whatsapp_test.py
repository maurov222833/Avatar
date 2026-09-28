import os
from bridges.whatsapp_reader import WhatsAppWebReader

profile_dir = os.path.join(os.getcwd(), 'memory', 'whatsapp_profile')
reader = WhatsAppWebReader(profile_dir=profile_dir, headless=False)
try:
    reader.launch()
    state = reader.login_state()
    print('Login state:', state)
    # Capture screenshot of the current page
    screenshot_path = os.path.join(os.getcwd(), 'whatsapp_login.png')
    reader._page.screenshot(path=screenshot_path)
    print('Screenshot saved to', screenshot_path)
finally:
    reader.close()
