import os


def build_ytdlp_auth_options(cookies_browser: str = "", cookies_file: str = "") -> dict:
    cookie_file = cookies_file.strip()
    if cookie_file:
        cookie_file_path = os.path.abspath(os.path.expanduser(cookie_file))
        if os.path.exists(cookie_file_path):
            return {"cookiefile": cookie_file_path}

    browser = cookies_browser.strip().lower()
    if browser:
        return {"cookiesfrombrowser": (browser,)}

    return {}
