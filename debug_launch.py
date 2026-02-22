from playwright.sync_api import sync_playwright

def test_launch():
    print("Testing basic launch...")
    with sync_playwright() as p:
        try:
            print("Launching new context (non-persistent)...")
            browser = p.chromium.launch(headless=False, channel="chrome")
            print("Launched successfully!")
            page = browser.new_page()
            page.goto("https://google.com")
            print("Navigated successfully!")
            browser.close()
        except Exception as e:
            print(f"Launch failed: {e}")

if __name__ == "__main__":
    test_launch()
