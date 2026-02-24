import os
import time
import re
import subprocess
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ==========================================
# CONFIGURATION
# ==========================================

# Persistent browser profile — saves your login so you don't have to sign in every time.
# This creates a separate folder just for this bot (won't interfere with your real Chrome).
BOT_PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisk_bot_profile")

# Folders containing images to process (two people working on it)
IMAGES_FOLDER_1 = r"C:\Users\Muhammad Ikram\Desktop\Playwrite Bot\test_images"  # Person 1
IMAGES_FOLDER_2 = r"D:\test images"  # Person 2

# Whisk Lab URL
WHISK_URL = "https://labs.google/fx/tools/whisk/project"

# Selectors (Text-based for robustness, can be updated if UI changes)
# keys map to the visible text label of the upload section
SELECTORS = {
    "sections": ["Scene", "Subject", "Style"],
    "run_button": "Run",  # Text on the generate button
    "loading_indicator": "Generating...", # Text or state indicating work in progress
    "result_container": ".result-image-container", # Generic class placeholder - update if known
}

# ==========================================
# FUNCTIONS
# ==========================================

def kill_existing_chrome():
    """Force kills any running Chrome instances to free up the profile."""
    print("🔪 Killing existing Chrome processes to avoid profile locks...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        time.sleep(2) # Wait for file locks to release
    except Exception as e:
        print(f"⚠️ Could not kill Chrome: {e}")

def load_images(folder_paths):
    """
    Reads all supported image files from multiple directories and sorts them.
    Returns a list of (full_path, filename) tuples.
    """
    supported_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    all_images = []

    for folder_path in folder_paths:
        if not os.path.exists(folder_path):
            print(f"⚠️ Image folder not found at {folder_path}, skipping...")
            continue

        images = [f for f in os.listdir(folder_path) if f.lower().endswith(supported_extensions)]
        images.sort()
        print(f"📂 Found {len(images)} images in {folder_path}")
        for img in images:
            all_images.append((os.path.join(folder_path, img), img))

    print(f"📂 Total images to process: {len(all_images)}")
    return all_images

def find_section_container(page, section_name):
    """
    Finds the section header and its parent container for Subject/Scene/Style.
    Returns (header, container) or (None, None).
    """
    try:
        # Try exact match first, then regex
        header = page.locator(f"h4:has-text('{section_name}')").first
        if not header.is_visible(timeout=2000):
            header = page.get_by_text(section_name, exact=True).first
        
        if not header.is_visible(timeout=1000):
            return None, None
        
        # Walk up to find the parent container (needs to be tall enough to contain upload area)
        container = header.locator("xpath=..")
        for _ in range(6):
            try:
                box = container.bounding_box()
                if box and box['height'] > 120:
                    return header, container
                container = container.locator("xpath=..")
            except:
                container = container.locator("xpath=..")
        
        return header, None
    except:
        return None, None

def delete_existing_image(page, section_name, container):
    """
    Deletes any existing image in a section using the 'Delete image' button.
    """
    if not container:
        return
    try:
        delete_btns = container.locator("button[aria-label='Delete image']").all()
        for btn in delete_btns:
            if btn.is_visible(timeout=500):
                btn.click()
                print(f"    🗑️ Deleted existing image in '{section_name}'.")
                time.sleep(1)
                return True
    except:
        pass
    return False

def upload_image(page, section_name, file_path, index=0):
    """
    Uploads an image to a section (Subject/Scene/Style).
    Strategy: 
      1. Find the section container
      2. Delete any existing image first
      3. Try direct file input
      4. Try clicking the empty upload area (draggable div)
      5. Try clicking "Add new category" button
    """
    print(f"  ⬆️ Uploading to '{section_name}'...")
    try:
        header, container = find_section_container(page, section_name)
        
        if not header:
            print(f"    ⚠️ Header for '{section_name}' not found.")
            return False
        
        header_box = header.bounding_box()
        
        # Step 1: Delete existing image if present
        if container:
            delete_existing_image(page, section_name, container)
            time.sleep(1)
            # Re-find container after deletion (DOM may have changed)
            header, container = find_section_container(page, section_name)
        
        # Step 2: Try direct file input
        if container:
            inputs = container.locator("input[type='file']").all()
            if inputs:
                print(f"    👉 Found {len(inputs)} file input(s). Uploading directly...")
                try:
                    inputs[0].set_input_files(file_path)
                    print(f"    ✅ Uploaded to '{section_name}' via file input.")
                    time.sleep(1)
                    return True
                except Exception as e:
                    print(f"    ⚠️ Direct input failed: {e}")
        
        # Step 3: Try clicking the empty draggable upload area
        if container:
            # The empty upload area is: div[role='button'][aria-roledescription='draggable'] with no <img> inside
            draggable = container.locator("div[role='button'][aria-roledescription='draggable']").first
            try:
                if draggable.is_visible(timeout=1000):
                    # Check if it's empty (no image inside)
                    has_img = draggable.locator("img").count() > 0
                    if not has_img:
                        print(f"    👉 Found empty upload area. Clicking...")
                        try:
                            with page.expect_file_chooser(timeout=5000) as fc:
                                draggable.click()
                            fc.value.set_files(file_path)
                            print(f"    ✅ Uploaded to '{section_name}' via upload area click.")
                            time.sleep(1)
                            return True
                        except Exception as e:
                            print(f"    ⚠️ Upload area click failed: {e}")
            except:
                pass
        
        # Step 4: Try clicking below the header (blind click on upload zone)
        if header_box:
            print(f"    👉 Trying click below header...")
            click_x = header_box['x'] + header_box['width'] / 2
            click_y = header_box['y'] + 120
            try:
                with page.expect_file_chooser(timeout=5000) as fc:
                    page.mouse.click(click_x, click_y)
                fc.value.set_files(file_path)
                print(f"    ✅ Uploaded to '{section_name}' via header-relative click.")
                time.sleep(1)
                return True
            except:
                pass
        
        # Step 5: Try "Add new category" button inside the section
        if container:
            try:
                add_btn = container.locator("button[aria-label='Add new category']").first
                if add_btn.is_visible(timeout=1000):
                    print(f"    👉 Clicking 'Add new category' button...")
                    try:
                        with page.expect_file_chooser(timeout=5000) as fc:
                            add_btn.click()
                        fc.value.set_files(file_path)
                        print(f"    ✅ Uploaded to '{section_name}' via 'Add new category'.")
                        time.sleep(1)
                        return True
                    except:
                        pass
            except:
                pass
        
        # Step 6: Search page-wide for any file inputs near this section
        print(f"    👉 Last resort: scanning all file inputs on page...")
        all_inputs = page.locator("input[type='file']").all()
        if all_inputs:
            # Pick the one closest in Y to our header
            best_input = None
            best_dist = 9999
            for inp in all_inputs:
                try:
                    inp_box = inp.bounding_box()
                    if inp_box and header_box:
                        dist = abs(inp_box['y'] - header_box['y'])
                        if dist < best_dist:
                            best_dist = dist
                            best_input = inp
                except:
                    pass
            
            if best_input:
                try:
                    best_input.set_input_files(file_path)
                    print(f"    ✅ Uploaded to '{section_name}' via nearest file input.")
                    time.sleep(1)
                    return True
                except:
                    pass
        
        print(f"    ❌ Failed to upload to '{section_name}'.")
        return False

    except Exception as e:
        print(f"    ❌ Error uploading to '{section_name}': {e}")
        return False

def login(page):
    """
    Waits for the user to manually log in with their own Google account.
    No credentials are hardcoded — each user logs in themselves.
    """
    print("\n" + "="*50)
    print("🔑  MANUAL LOGIN REQUIRED")
    print("Please log in with your Google account in the browser window.")
    print("="*50 + "\n")
    
    # STEP 1: Check if already logged in (persistent profile saves session)
    print("    🔍 Checking if already logged in...")
    page.wait_for_timeout(3000)
    
    # If we're already on the Whisk page with sections visible, skip login entirely
    try:
        if page.locator("h4:has-text('Subject')").first.is_visible(timeout=3000):
            print("    ✅ Already logged in! Sections visible. Skipping login.")
            return
    except:
        pass
    
    # Check if we're on the Whisk page (not redirected to Google sign-in)
    current_url = page.url
    parsed = urlparse(current_url)
    hostname = parsed.hostname or ""
    
    if "accounts.google" in hostname:
        # Need to log in
        print("    ⏳ Waiting for you to finish logging in...")
        print("    (You only need to do this ONCE — your session will be saved)\n")
    
    for attempt in range(180):  # Wait up to ~6 minutes
        current_url = page.url
        parsed = urlparse(current_url)
        hostname = parsed.hostname or ""
        path = parsed.path or ""
        
        # Accept any labs.google page (not accounts.google.com)
        on_whisk = ("labs.google" in hostname and "accounts.google" not in hostname)
        
        # Also check if key UI elements are visible
        has_ui = False
        try:
            has_ui = (page.locator("h4:has-text('Subject')").first.is_visible(timeout=300) or
                      page.locator("h4:has-text('Scene')").first.is_visible(timeout=300) or
                      page.locator("text=Upload").first.is_visible(timeout=300))
        except:
            pass
        
        if has_ui:
            print(f"    ✅ Whisk UI detected! Sections are visible.")
            return
        
        if on_whisk:
            print(f"    ✅ On Whisk page: {current_url[:80]}")
            break
        
        if attempt % 15 == 0 and attempt > 0:
            print(f"    ⏳ Still waiting... ({attempt * 2}s elapsed)")
        time.sleep(2)
    else:
        print("    ⚠️ Timed out waiting for Whisk page. Continuing anyway...")
    
    # STEP 2: Wait for the page to fully load
    print("    ⏳ Waiting for Whisk UI to fully load...")
    page.wait_for_timeout(5000)  # Let the page settle
    
    # Handle onboarding modals
    print("    👀 Checking for onboarding modals...")
    for i in range(5):
        try:
            # CONTINUE button
            continue_btn = page.get_by_role("button", name="CONTINUE").first
            if continue_btn.is_visible(timeout=2000):
                print(f"    👋 Clicking 'CONTINUE' button...")
                continue_btn.click()
                page.wait_for_timeout(3000)
                continue
            
            # Precise Mode / any modal -> close or escape
            modal_texts = ["Precise Mode", "What's new", "Welcome"]
            for mt in modal_texts:
                try:
                    if page.locator(f"text={mt}").first.is_visible(timeout=1000):
                        print(f"    👋 Found '{mt}' modal. Closing...")
                        close_btn = page.locator("button[aria-label='Close'], button[aria-label='close']").first
                        if close_btn.is_visible(timeout=1000):
                            close_btn.click()
                        else:
                            page.keyboard.press("Escape")
                        page.wait_for_timeout(2000)
                        break
                except:
                    pass
            
            # Check if we can see section headers
            if page.locator("h4:has-text('Subject')").first.is_visible(timeout=1000):
                print("    ✅ Whisk UI loaded — sections visible.")
                return
                
        except:
            pass
        time.sleep(1)
    
    # STEP 3: If sections aren't visible, the sidebar may need to be opened
    print("    👀 Sections not visible yet. Trying to open sidebar...")
    
    # Try clicking sidebar toggle
    sidebar_opened = False
    try:
        # Look for buttons with expand/sidebar/panel in aria-label
        for name_pattern in ["expand", "open sidebar", "show tool", "show project", "panel"]:
            btn = page.get_by_role("button", name=re.compile(name_pattern, re.IGNORECASE)).first
            if btn.is_visible(timeout=1000):
                print(f"    👉 Found sidebar toggle: '{name_pattern}'")
                btn.click()
                page.wait_for_timeout(3000)
                sidebar_opened = True
                break
    except:
        pass
    
    if not sidebar_opened:
        # Scan for small icon buttons on the left side
        try:
            btns = page.locator("button").all()
            for btn in btns:
                if not btn.is_visible():
                    continue
                box = btn.bounding_box()
                if not box:
                    continue
                # Left side, small, below header
                if box['x'] < 80 and box['width'] < 60 and box['y'] > 50 and box['y'] < 400:
                    label = (btn.get_attribute("aria-label") or "").lower()
                    if "menu" not in label and "navigation" not in label:
                        print(f"    👉 Trying left-side button at y={box['y']:.0f}...")
                        btn.click()
                        page.wait_for_timeout(3000)
                        if page.locator("text=Subject").first.is_visible(timeout=2000):
                            sidebar_opened = True
                            print("    ✅ Sidebar opened!")
                            break
        except:
            pass
    
    # STEP 4: Final verification — wait for Subject to be visible
    print("    ⏳ Verifying sections are visible...")
    for wait_attempt in range(30):  # Up to 60 seconds
        try:
            if page.locator("h4:has-text('Subject')").first.is_visible(timeout=1000):
                print("    ✅ Ready! Subject/Scene/Style sections visible.")
                return
        except:
            pass
        
        if wait_attempt == 10:
            print("\n" + "!"*50)
            print("    ⚠️ Sections still not visible after 20 seconds.")
            print("    Please ensure you are on the Whisk project page")
            print("    and the sidebar with Subject/Scene/Style is open.")
            print("!"*50 + "\n")
        time.sleep(2)
    
    print("    ⚠️ Could not verify sections. Proceeding anyway...")

def run_generation(page):
    """
    Clicks the Run/Generate/Whisk button using multiple detection strategies.
    """
    print("  ▶️ Clicking Run button...")
    try:
        # 1. Wait for any ongoing generation to finish first
        for i in range(15):
            stop_btn = page.locator("button[aria-label*='Stop'], button[aria-label*='Cancel']").first
            try:
                if stop_btn.is_visible(timeout=500):
                    print(f"    ⏳ Previous generation running. Waiting... ({i+1}/15)")
                    time.sleep(2)
                else:
                    break
            except:
                break
        
        # First, dump all button aria-labels for debug (one-time)
        print("    🔍 Scanning all visible buttons...")
        all_buttons = page.locator("button").all()
        bottom_buttons_debug = []
        vp = page.viewport_size or {"width": 1280, "height": 720}
        
        for btn in all_buttons:
            try:
                if not btn.is_visible(timeout=200):
                    continue
                box = btn.bounding_box()
                if not box:
                    continue
                label = btn.get_attribute("aria-label") or ""
                text = (btn.text_content() or "").strip()[:30]
                # Log buttons in the bottom 50% for debug
                if box['y'] > vp['height'] * 0.5:
                    bottom_buttons_debug.append(f"'{label or text}' at ({box['x']:.0f},{box['y']:.0f})")
            except:
                continue
        
        if bottom_buttons_debug:
            print(f"    📍 Bottom-area buttons: {', '.join(bottom_buttons_debug)}")
        
        # Strategy A: Find the "Whisk it" / "Run" / "Generate" button by aria-label
        # Use EXACT or near-exact matches to avoid false positives (e.g., "go" matching "category")
        exact_labels = ["Run", "Generate", "Whisk", "Whisk it", "Submit", "Create image"]
        for label in exact_labels:
            btn = page.locator(f"button[aria-label='{label}']").first
            try:
                if btn.is_visible(timeout=300):
                    print(f"    👉 Found button: aria-label='{label}'")
                    btn.click(force=True)
                    print("    ✅ Clicked Run button.")
                    return True
            except:
                continue
        
        # Strategy B: Find button by visible text content (exact role match)
        text_patterns = ["Whisk it", "Run", "Generate", "Create"]
        for text in text_patterns:
            btn = page.get_by_role("button", name=text, exact=True).first
            try:
                if btn.is_visible(timeout=300):
                    print(f"    👉 Found button with text: '{text}'")
                    btn.click(force=True)
                    print("    ✅ Clicked Run button.")
                    return True
            except:
                continue
        
        # Strategy C: Find button containing a play/arrow SVG icon in the bottom area
        # The Run button typically has a play_arrow or send icon
        print("    👉 Looking for action button with arrow/play icon in bottom area...")
        
        all_btns = page.locator("button").all()
        bottom_btns = []
        
        skip_labels = ["stop", "cancel", "delete", "download", "aspect", "inspire", 
                        "add new", "category", "refine", "select", "menu", "close",
                        "expand", "collapse"]
        
        for btn in all_btns:
            try:
                if not btn.is_visible(timeout=200):
                    continue
                box = btn.bounding_box()
                if not box:
                    continue
                # Must be in the bottom 40% of the page
                if box['y'] > vp['height'] * 0.6:
                    label = (btn.get_attribute("aria-label") or "").lower()
                    text = (btn.text_content() or "").strip().lower()
                    # Skip known non-action buttons
                    if any(x in label for x in skip_labels):
                        continue
                    if any(x in text for x in ["stop", "cancel"]):
                        continue
                    bottom_btns.append((btn, box))
            except:
                continue
        
        # Pick the right-most button in the bottom area (Run is typically the last action button)
        if bottom_btns:
            bottom_btns.sort(key=lambda x: x[1]['x'], reverse=True)
            target = bottom_btns[0][0]
            target_box = bottom_btns[0][1]
            print(f"    👉 Clicking right-most bottom button at x={target_box['x']:.0f}, y={target_box['y']:.0f}")
            try:
                target.click(force=True)
                print("    ✅ Clicked candidate button.")
                return True
            except:
                try:
                    target.evaluate("el => el.click()")
                    print("    ✅ JS-clicked candidate button.")
                    return True
                except:
                    pass
        
        # Strategy D: Keyboard shortcut
        print("    ⚠️ No Run button found. Trying Enter key as fallback...")
        page.keyboard.press("Enter")
        return True

    except Exception as e:
        print(f"    ❌ Error during run_generation: {e}")
        return False

def clear_inputs(page):
    """
    Clears uploaded images from Subject, Scene, and Style sections
    using the 'Delete image' button (aria-label from actual UI).
    """
    print("  🧹 Clearing inputs (Subject, Scene, Style)...")
    sections = ["Subject", "Scene", "Style"]
    
    for section in sections:
        try:
            header, container = find_section_container(page, section)
            if not container:
                continue
            
            # Delete all images in this section
            deleted_any = False
            for attempt in range(5):  # Handle multiple images per section
                delete_btn = container.locator("button[aria-label='Delete image']").first
                try:
                    if delete_btn.is_visible(timeout=500):
                        delete_btn.click()
                        print(f"    ✅ Deleted image from '{section}'.")
                        deleted_any = True
                        time.sleep(0.5)
                    else:
                        break
                except:
                    break
            
            if not deleted_any:
                # Fallback: try other remove/clear button labels
                btns = container.locator("button, div[role='button']").all()
                for btn in btns:
                    try:
                        if not btn.is_visible(timeout=200):
                            continue
                        lbl = (btn.get_attribute("aria-label") or "").lower()
                        if any(word in lbl for word in ["remove", "clear", "delete", "close"]):
                            btn.click()
                            print(f"    ✅ Cleared '{section}' via '{lbl}'.")
                            time.sleep(0.5)
                            break
                    except:
                        continue

        except Exception as e:
            print(f"    ⚠️ Error clearing '{section}': {e}")

def main():
    print("🚀 Starting Whisk Automation...")
    
    images = load_images([IMAGES_FOLDER_1, IMAGES_FOLDER_2])
    if not images:
        print("No images to process. Exiting.")
        return

    # Ensure clean slate
    kill_existing_chrome()

    print(f"🔌 Launching Browser (Persistent Profile: {BOT_PROFILE_DIR})...")
    print("    ℹ️ Your login will be saved — you only need to sign in once!")
    
    with sync_playwright() as p:
        try:
            # Use persistent context so cookies/login are saved between runs
            context = p.chromium.launch_persistent_context(
                user_data_dir=BOT_PROFILE_DIR,
                headless=False,
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu"
                ],
                ignore_default_args=["--enable-automation"],
                no_viewport=True,
                timeout=60000
            )
            
            # Get or create a page
            page = context.pages[0] if context.pages else context.new_page()

            print(f"🌐 Navigating to {WHISK_URL}...")
            try:
                page.goto(WHISK_URL, timeout=60000)
            except Exception as nav_err:
                 print(f"    ⚠️ Navigation warning: {nav_err}")
            
            # Perform Login (manual — each user logs in with their own Google account)
            login(page)

            print("\n🏁 Starting Image Processing Loop\n")
            
            # Debug: Print current page state before starting
            print(f"    📍 Current URL: {page.url}")
            print(f"    📍 Page title: {page.title()}")
            try:
                has_subject = page.locator("h4:has-text('Subject')").first.is_visible(timeout=2000)
                has_scene = page.locator("h4:has-text('Scene')").first.is_visible(timeout=1000)
                has_style = page.locator("h4:has-text('Style')").first.is_visible(timeout=1000)
                print(f"    📍 Sections visible — Subject: {has_subject}, Scene: {has_scene}, Style: {has_style}")
                
                if not (has_subject or has_scene or has_style):
                    print("    ⚠️ No sections visible! Waiting 15 seconds for page to load...")
                    time.sleep(15)
                    # Try one more time
                    has_subject = page.locator("h4:has-text('Subject')").first.is_visible(timeout=3000)
                    print(f"    📍 After wait — Subject visible: {has_subject}")
                    
                    if not has_subject:
                        print("    ⚠️ Still no sections. Dumping page text for debug...")
                        body_text = page.locator("body").inner_text()[:500]
                        print(f"    📍 Page text: {body_text}")
            except Exception as dbg_e:
                print(f"    ⚠️ Debug check error: {dbg_e}")
            
            for idx, (img_path, img_name) in enumerate(images):
                print(f"[{idx+1}/{len(images)}] Processing: {img_name} (from {os.path.dirname(img_path)})")
                
                # 1. Upload to all 3 sections (Sequence: Subject -> Scene -> Style)
                # Ensure the SELECTORS["sections"] are in this order or sort them.
                # Current list is ["Scene", "Subject", "Style"] -> Reordering to User Request
                ordered_sections = ["Subject", "Scene", "Style"]
                
                for idx_section, section in enumerate(ordered_sections):
                    # We pass the index (0, 1, 2) to target the 1st, 2nd, 3rd button
                    if not upload_image(page, section, img_path, index=idx_section):
                        # Use a warning but DO NOT BREAK. User wants to force run.
                        print(f"    ⚠️ Upload to '{section}' failed, but proceeding anyway...")
                    time.sleep(1) # Brief stability pause
                
                # NO 'else' block here. We run this unconditionally.
                
                # NEW: Wait 12 seconds as requested by user
                print("    ⏳ Waiting 12 seconds before generating...")
                time.sleep(12)

                # 2. Run Generation (ALWAYS run this)
                run_generation(page)
                
                # 3. Wait for generation to complete before moving on
                print("    ⏳ Waiting for generation to complete...")
                generation_started = False
                for wait_i in range(60):  # Wait up to ~2 minutes
                    try:
                        # Check if a Stop/Cancel button appears (means generation started)
                        stop_btn = page.locator("button[aria-label*='Stop'], button[aria-label*='Cancel']").first
                        if stop_btn.is_visible(timeout=500):
                            if not generation_started:
                                print("    🔄 Generation in progress...")
                                generation_started = True
                            time.sleep(2)
                            continue
                        
                        # Check for loading/generating indicators
                        if page.locator("text=Generating").first.is_visible(timeout=300):
                            if not generation_started:
                                print("    🔄 Generation in progress...")
                                generation_started = True
                            time.sleep(2)
                            continue
                        
                        # If generation had started and stop button is gone, it's done
                        if generation_started:
                            print("    ✅ Generation complete!")
                            time.sleep(2)
                            break
                        
                        # If generation never visibly started, wait a bit and move on
                        if wait_i > 5:
                            print("    ⚠️ No generation detected. Moving on...")
                            break
                            
                    except:
                        pass
                    time.sleep(2)
                
                # 4. Cleanup Inputs (ALWAYS run this to clear partial uploads or successful ones)
                try:
                    clear_inputs(page)
                    print("    ⏳ Stabilizing UI after cleanup (5s)...")
                    time.sleep(5)
                except: pass
                
                print("-----------------------------------")
                time.sleep(2) # Cooldown between iterations
                
            print("\n🎉 All images processed!")
            time.sleep(5) # Let user see final result
            
            context.close()
            
        except Exception as e:
            print(f"\n❌ Critical Error: {e}")
            print("Tip: Ensure all Chrome instances are closed before running this script.")

if __name__ == "__main__":
    main()

