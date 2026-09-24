import os
import sys
import logging
from pathlib import Path
import webview
import comtypes

# Set up simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] %(name)s: %(message)s'
)

from web_api import WebApi

def main():
    # Initialize COM for the main thread
    comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
    
    api = WebApi()
    
    # Path to our web directory
    web_dir = os.path.join(os.path.dirname(__file__), 'web', 'index.html')
    
    # Create the webview window
    window = webview.create_window(
        'Phone Backup Manager (Web UI)', 
        url=web_dir,
        js_api=api,
        width=1100,
        height=720,
        min_size=(900, 600)
    )
    
    # Start the application
    webview.start()
    
    # Uninitialize COM when app closes
    comtypes.CoUninitialize()

if __name__ == '__main__':
    main()
