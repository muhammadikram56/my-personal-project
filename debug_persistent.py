from playwright.sync_api import sync_playwright
import os

USER_DATA_DIR = r"C:\Users\Muhammad Ikram\AppData\Local\Google\Chrome\User Data"
PROFILE_DIR = "Profile 45"

def test_persistent():
    print("Testing persistent context launch...")
    try:
        with sync_playwright() as p:
            print(f"Launching with USER_DATA_DIR: {USER_DATA_DIR}")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                args=[], # removed profile arg
                timeout=15000 # Short timeout
            )
            print("Launched successfully!")
            print(f"Pages: {len(browser.pages)}")
            browser.close()
    except Exception as e:
        print(f"Persistent launch failed: {e}")

if __name__ == "__main__":
    test_persistent()
