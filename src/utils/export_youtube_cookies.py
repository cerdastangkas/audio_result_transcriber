import os
import json
import logging
from yt_dlp.cookies import extract_cookies_from_browser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def export_cookies():
    """Export cookies from browser to a file."""
    try:
        # Try different browsers in order of preference
        browsers = ['opera']
        cookies = None
        
        for browser in browsers:
            try:
                logger.info(f"Trying to extract cookies from {browser}...")
                cookies = list(extract_cookies_from_browser(browser))
                if cookies:
                    logger.info(f"Successfully extracted cookies from {browser}")
                    break
            except Exception as e:
                logger.warning(f"Could not extract cookies from {browser}: {e}")
        
        if not cookies:
            raise Exception("Could not extract cookies from any browser")
        
        # Filter for youtube.com cookies and format them for Netscape format
        cookie_lines = ["# Netscape HTTP Cookie File"]
        for cookie in cookies:
            if '.youtube.com' in cookie.domain:
                # Format: domain, domain_specified, path, secure, expiry, name, value
                domain = cookie.domain if cookie.domain.startswith('.') else '.' + cookie.domain
                domain_specified = "TRUE"
                path = cookie.path or "/"
                secure = "TRUE" if cookie.secure else "FALSE"
                expiry = str(int(cookie.expires)) if cookie.expires else "0"
                
                cookie_line = f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expiry}\t{cookie.name}\t{cookie.value}"
                cookie_lines.append(cookie_line)
        
        # Save cookies in Netscape format
        cookies_file = 'youtube.cookies'
        with open(cookies_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cookie_lines))
        
        logger.info(f"Successfully saved {len(cookie_lines)-1} YouTube cookies to {cookies_file}")
        logger.info("You can now copy this file to your SSH server")
        
    except Exception as e:
        logger.error(f"Error exporting cookies: {e}")

if __name__ == "__main__":
    export_cookies()
