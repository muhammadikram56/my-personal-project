import os
import time
import re
import subprocess
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ==========================================
# CONFIGURATION
# ==========================================

# 🔹 IMPORTANT: REPLACE THE PATH BELOW WITH YOUR ACTUAL CHROME USER DATA PATH
# Example: r"C:\Users\YourName\AppData\Local\Google\Chrome\User Data"
# We use the parent 'User Data' folder here, and specify 'Profile 45' in the launch args below.
USER_DATA_DIR = r"C:\Users\Muhammad Ikram\AppData\Local\Google\Chrome\User Data"
PROFILE_DIR = "Profile 45" # Specific profile directory name

# Credentials
EMAIL = "pat.ai.cummims@gmail.com"
PASSWORD = "Pat@#(56561303)Good"

# Folder containing images to process
IMAGES_FOLDER = r"C:\Users\Muhammad Ikram\Desktop\Playwrite Bot\test_images"  # Update if needed

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

def load_images(folder_path):
    """
    Reads all supported image files from a directory and sorts them.
    """
    supported_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    if not os.path.exists(folder_path):
        print(f"❌ Error: Image folder not found at {folder_path}")
        return []

    images = [f for f in os.listdir(folder_path) if f.lower().endswith(supported_extensions)]
    images.sort()  # Sort alphabetically
    
    print(f"📂 Found {len(images)} images in {folder_path}")
    return images

def upload_image(page, section_name, file_path, index=0):
    """
    Uploads an image with extensive fallback and debug logging.
    """
    print(f"  ⬆️ Uploading to '{section_name}'...")
    try:
        # 1. Find Header
        header = page.get_by_text(section_name, exact=True).first
        if not header.is_visible():
             header = page.get_by_text(re.compile(f"^{section_name}", re.IGNORECASE)).first
        
        if not header.is_visible():
            print(f"    ⚠️ Header for '{section_name}' not found.")
            return False
            
        header_box = header.bounding_box()
        # 2. Find Container
        container = header.locator("xpath=..")
        card_found = None
        for i in range(5):
            try:
                box = container.bounding_box()
                if box and box['height'] > 150:
                    card_found = container
                    break
                container = container.locator("xpath=..")
            except: pass
            
        # Strategy A: Direct Input
        if card_found:
            inputs = card_found.locator("input[type='file']").all()
            if inputs:
                print(f"    👉 Found {len(inputs)} file input(s). Attempting direct upload...")
                try:
                    inputs[0].set_input_files(file_path)
                    print("    ✅ Uploaded via direct input match.")
                    return True
                except: pass
        
        # Strategy B: Visual Icon Search (SVG or IMG)
        print("    👉 Fallback: locating Pencil/Icon...")
        candidates = page.locator("svg, img, button:has(svg)").all()
        target_icon = None
        min_dist = 9999
        
        for icon in candidates:
            if not icon.is_visible(): continue
            box = icon.bounding_box()
            if not box: continue
            
            # Check relative to header
            dy = box['y'] - header_box['y']
            dx = abs(box['x'] - (header_box['x'] + 20)) 
            
            if 20 < dy < 350 and dx < 300: 
                 if dy < min_dist:
                        min_dist = dy
                        target_icon = icon
                        
        if target_icon:
            icon_box = target_icon.bounding_box()
            center_x = icon_box['x'] + icon_box['width'] / 2
            bottom_y = icon_box['y'] + icon_box['height']
            print(f"    👉 Found likely Icon at ({center_x}, {icon_box['y']}).")
            
            # Click Below
            click_y = bottom_y + 60
            print(f"    👉 Clicking 60px below icon at ({center_x}, {click_y})...")
            try:
                 with page.expect_file_chooser(timeout=5000) as fc:
                     page.mouse.click(center_x, click_y)
                 fc.value.set_files(file_path)
                 print("    ✅ Uploaded via 'Click Below Icon'.")
                 return True
            except: pass
            
        # Final Fallback: Header Relative (if container failed)
        if not card_found and not target_icon:
             print(f"    ⚠️ Container not found. Trying Blind Click below Header...")
             try:
                 # Assume upload area is roughly 100px below header
                 hx = header_box['x'] + header_box['width'] / 2
                 hy = header_box['y'] + 100
                 with page.expect_file_chooser(timeout=3000) as fc:
                     page.mouse.click(hx, hy)
                 fc.value.set_files(file_path)
                 print("    ✅ Uploaded via Header-Relative Click.")
                 return True
             except: pass

        # Strategy C: Text Search "Upload Image" (Any element)
        if not card_found and not target_icon: # Only try if others failed
            print("    👉 Fallback: Searching for 'Upload Image' text...")
            if card_found:
                text_el = card_found.get_by_text("Upload Image", exact=False).first
                if text_el.is_visible():
                    print("    👉 Found 'Upload Image' text element. Clicking...")
                    try:
                        with page.expect_file_chooser(timeout=5000) as fc:
                            text_el.click()
                        fc.value.set_files(file_path)
                        print("    ✅ Uploaded via Text Click.")
                        return True
                    except: pass

        # --- NEW: Handle "Tiks" (Checkboxes) ---
        # User: "dont turn off the tik and make sure they must be on"
        # We look for a checkbox in the container and ensure it's checked.
        if card_found:
            checkboxes = card_found.locator("input[type='checkbox'], div[role='checkbox']").all()
            if checkboxes:
                print(f"    ☑️ Found {len(checkboxes)} checkbox(es). Ensuring they are ON...")
                for cb in checkboxes:
                    try:
                        if cb.get_attribute("role") == "checkbox":
                            if cb.get_attribute("aria-checked") == "false":
                                cb.click()
                                print("      👉 Clicked custom checkbox to ON.")
                        elif not cb.is_checked():
                            cb.check() # Native check
                            print("      👉 Checked native checkbox.")
                        else:
                             print("      ✅ Checkbox already ON.")
                    except Exception as cb_err:
                        print(f"      ⚠️ Failed to handle checkbox: {cb_err}")
            else:
                 print("    ℹ️ No checkboxes found in this section.")

        # Dump HTML for debugging
        if card_found:
            print(f"\n[DEBUG HTML Dump for {section_name}]\n")
            print(card_found.inner_html()[:2000]) # First 2000 chars
            print("\n[End Debug Dump]\n")
        
        print("    ❌ Failed to trigger upload dialog.")
        return False

    except Exception as e:
        print(f"    ❌ Failed: {e}")
        return False

    except Exception as e:
        print(f"    ❌ Failed to upload to {section_name}: {e}")
        return False

def login(page, email, password):
    """
    Attempts to log in to Google/Whisk.
    Includes fallback to manual input if blocked.
    """
    print("  🔑 Attempting automated login...")
    try:
        # Check if we are redirected to a login page
        # Generic check: is there an email input?
        try:
            email_input = page.locator("input[type='email']")
            if email_input.count() > 0:
                print("    Found email input. Filling...")
                email_input.first.fill(email)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000) # Wait for password slide
                
                # Password
                password_input = page.locator("input[type='password']")
                if password_input.count() > 0:
                    print("    Found password input. Filling...")
                    password_input.first.fill(password)
                    page.keyboard.press("Enter")
                    
                    print("    ⏳ Waiting for login navigation...")
                    # Wait for either success (whisk url) or manual intervention needed
                    page.wait_for_url("**/tools/whisk/**", timeout=15000)
                    print("    ✅ Login appears successful.")
                else:
                    print("    ⚠️ Password input not found after email.")
            else:
                print("    ℹ️ Already logged in or no login form detected.")
                
        except Exception as step_err:
             print(f"    ⚠️ Login step incomplete: {step_err}")

    except Exception as e:
        print(f"    ❌ Auto-login error: {e}")
    
    # Always offer manual fallback because Google bot detection varies
    print("\n" + "="*50)
    print("⚠️  CHECK LOGIN STATUS")
    print("If login requires 2FA or failed, please complete it manually now.")
    print("="*50 + "\n")
    # input("⌨️  Press Enter here in the terminal once logged in and ready... ")
    # User asked to proceed, so we'll use a timeout-based check or just a short pause if it seemed to work?
    # Better to keep the input for safety unless we are VERY sure.
    # Given the user said "procceed further", let's try to verify if we are on the project page.
    
    try:
        # Handle consecutive onboarding modals (User reported 2 screens)
        print("    👀 Checking for onboarding modals (Welcome/Whisk it all together)...")
        
        # Loop to handle multiple sequential modals
        max_modals = 5
        for i in range(max_modals): 
            try:
                # 1. Check for "CONTINUE" (Standard onboarding)
                continue_btn = page.get_by_role("button", name="CONTINUE").filter(has_text="CONTINUE").first
                if continue_btn.is_visible(timeout=2000):
                    print(f"    👋 Found 'CONTINUE' button. Clicking...")
                    continue_btn.click()
                    page.wait_for_timeout(4000)
                    continue

                # 2. Check for "Precise Mode" modal -> Click Close (X) button
                # User requested to click the cross button for this specific screen
                # 2. Check for "Precise Mode" modal -> Click Close (X) button
                # User requested to click the cross button for this specific screen
                if page.locator("text=Precise Mode").first.is_visible(timeout=3000):
                     print("    👋 Found 'Precise Mode' modal. Clicking Close button...")
                     # Try generic close button selectors usually found in dialogs
                     close_btn = page.get_by_label("Close").first
                     if not close_btn.is_visible():
                         close_btn = page.locator("button[aria-label='Close']").first
                         
                     if close_btn.is_visible():
                         close_btn.click()
                         print("    ✅ Clicked Close button.")
                         page.wait_for_timeout(2000)
                     else:
                         print("    ⚠️ Could not find explicit Close button. Sending Escape key.")
                         page.keyboard.press("Escape")
                         page.wait_for_timeout(1000)
                     continue

                # 3. Check if we are done (Upload text exists)
                if page.locator("text=Upload").count() > 0:
                    print("    ✅ 'Upload' text detected. Onboarding complete.")
                    break
                    
            except Exception as e:
                # Ignore errors during polling
                time.sleep(1)

        print("    ⏳ Verifying Project page access...")
        
        # 4. Handle Sidebar Toggle (User specific request)
        print("    👀 Locating Black Circular Sidebar Toggle (Strict Mode)...")
        try:
            # We want to avoid the "Hamburger Menu" (usually top-left, yellow/transparent)
            # We want the "Sidebar Toggle" (usually below menu, BLACK, circular)
            
            toggle_found = False
            
            # Helper to check if a button is likely the menu
            def is_menu_button(btn):
                label = (btn.get_attribute("aria-label") or "").lower()
                text = (btn.text_content() or "").lower()
                return "menu" in label or "navigation" in label or "menu" in text

            # Helper to check if a button is likely the target (Black, Circular)
            def is_target_candidate(btn):
                if not btn.is_visible(): return False
                box = btn.bounding_box()
                if not box: return False
                
                # Geometrics: Left side, not too wide (icon button)
                if box['x'] > 100 or box['width'] > 60: return False
                
                # Exclude top-left menu (usually y < 60)
                # The sidebar toggle is usually centered vertically or below header
                # Let's assume header is ~60px.
                if box['y'] < 50: return False 
                
                return True

            # Strategy 1: Explicit Accessible Name (Best Practice)
            # "Expand sidebar", "Open sidebar", "Show tools"
            potential_names = ["expand", "open sidebar", "show tools", "show project"]
            for name in potential_names:
                candidate = page.get_by_role("button", name=re.compile(name, re.IGNORECASE))
                if candidate.count() > 0 and candidate.first.is_visible():
                    print(f"    👉 Found toggle by name: '{name}'")
                    # Double check it's not the menu
                    if not is_menu_button(candidate.first):
                         candidate.first.click()
                         toggle_found = True
                         break
            
            # Strategy 2: Visual Scan (Fallback if no name match)
            if not toggle_found:
                print("    ⚠️ Strategy 1 failed. Scanning left-side buttons visually...")
                btns = page.locator("button").all()
                
                # Sort by Y position (Top to Bottom)
                btns_sorted = []
                for b in btns:
                    if is_target_candidate(b):
                        btns_sorted.append(b)
                
                btns_sorted.sort(key=lambda b: b.bounding_box()['y'])
                
                found_black_btn = False
                
                for btn in btns_sorted:
                    # Check Background Color
                    bg = btn.evaluate("el => window.getComputedStyle(el).backgroundColor")
                    is_dark = "0, 0, 0" in bg or "32, 33, 36" in bg 
                    
                    # Check Shape
                    box = btn.bounding_box()
                    is_circle = abs(box['width'] - box['height']) < 8
                    
                    if is_dark:
                         print(f"    👉 Found BLACK candidate at y={box['y']}. This is likely it.")
                         try:
                            btn.evaluate("el => el.style.border = '4px solid #00FF00'") # GREEN
                            page.wait_for_timeout(500)
                         except: pass
                         
                         btn.click()
                         toggle_found = True
                         found_black_btn = True
                         break
                    elif is_circle and not is_menu_button(btn):
                         # Maybe it's not strictly black computed style but looks distinct
                         print(f"    👉 Found CIRCULAR candidate at y={box['y']} (BG: {bg}). Checking...")
                
                if not found_black_btn and len(btns_sorted) > 0 and not toggle_found:
                    # Last resort: click the first non-menu button below header
                    print("    ⚠️ No black button found. Clicking first likely candidate below header...")
                    btns_sorted[0].click()
                    toggle_found = True

            # Verification
            if toggle_found:
                 print("    ✅ Clicked a candidate button.")
            else:
                 print("    ❌ Could not identify sidebar toggle.")

        except Exception as toggle_err:
            print(f"    ❌ Error interacting with Sidebar Toggle: {toggle_err}")

        print("    ⏳ Verifying Sidebar is Open (Key for next steps)...")
        try:
            # We NEED "Subject" or "Style" to be visible
            page.wait_for_selector("text=Subject", timeout=4000)
            print("    ✅ Sidebar is definitely OPEN.")
        except:
            print("\n" + "!"*50)
            print("    ⚠️ SIDEBAR DID NOT OPEN AUTOMATICALLY.")
            print("    Please manually click the BLACK BUTTON with the Arrow/Chevron on the left.")
            print("!"*50 + "\n")
            # Wait for user to fix it manually before failing
            time.sleep(5)
        
        # Fallback check for Upload buttons
        if page.locator("text=Upload").count() == 0:
             print("    ⚠️ 'Upload' text not visible yet.")
        
    except Exception as e:
        print(f"    ⚠️ Could not assist past onboarding automatically: {e}")
        print("    Please ensure you are on the Project page manually.")
        
        print("    🕵️ Starting manual fallback loop: Waiting for 'Upload' button...")
        for _ in range(30): # Wait up to 60s more
            if page.locator("text=Upload").count() > 0:
                print("    ✅ Detected project page!")
                break
            time.sleep(2)
        else:
            print("    ❌ Timed out waiting for project page even after manual fallback time.")

def run_generation(page):
    """
    Clicks the Run button by finding the RIGHT-MOST element with a DARK BACKGROUND in the bottom area.
    This avoids clicking the transparent 'Dice' or 'Aspect Ratio' buttons which are to the left of it.
    """
    print("  ▶️ Clicking Run (Black Arrow Button)...")
    try:
        # 1. Wait for 'Stop' button to disappear (generation in progress)
        for i in range(15): 
            stop_btn = page.locator("button[aria-label*='Stop'], button[aria-label*='Cancel']").first
            if stop_btn.is_visible():
                print(f"    ⏳ Generation in progress (Stop button visible). Waiting... ({i+1}/15)")
                time.sleep(2)
            else:
                break
        
        target_btn = None
        
        # 2. Find Candidates (Broad Search)
        # We look for ANY clickable element or SVG container
        candidates = page.locator("button, [role='button'], div[onclick], a[role='button'], svg").all()
        
        vp_size = page.viewport_size
        if not vp_size: vp_size = {"width": 1280, "height": 720}
        
        threshold_y = vp_size['height'] * 0.6 # Bottom 40%
        threshold_x = vp_size['width'] * 0.5  # Right 50%
        
        valid_candidates = []
        
        for el in candidates:
            if not el.is_visible(): continue
            box = el.bounding_box()
            if not box: continue
            
            # Position Check: Must be in bottom-right area
            if box['y'] > threshold_y and box['x'] > threshold_x:
                
                # Visual Check: Must be DARK/BLACK background
                # The other buttons (Dice, Aspect Ratio) are transparent or light gray
                try:
                   bg = el.evaluate("el => window.getComputedStyle(el).backgroundColor")
                   # Check for black/dark gray (rgb values < 50)
                   # bg acts like 'rgb(32, 33, 36)' or 'rgba(0, 0, 0, 0)'
                   
                   is_transparent = "rgba(0, 0, 0, 0)" in bg or "transparent" in bg
                   if is_transparent: 
                       continue # Skip transparent buttons (Dice, Aspect Ratio)

                   # Parse RGB to be sure it's dark
                   # Simple check: if it contains "255" it's white/light. If it contains small numbers it's dark.
                   # Let's count low numbers.
                   is_dark = "0, 0, 0" in bg or "32, 33, 36" in bg or "31, 31, 31" in bg or "26, 26, 26" in bg
                   
                   if is_dark:
                       valid_candidates.append((el, box))
                       # print(f"      Potential Candidate at x={box['x']}: BG={bg}")
                except: pass

        # Sort by X position (Descending) -> The Run button is the RIGHT-MOST element
        if valid_candidates:
            valid_candidates.sort(key=lambda x: x[1]['x'], reverse=True)
            
            target_btn = valid_candidates[0][0]
            print(f"    👉 Found Best Candidate (Right-Most Black Button) at x={valid_candidates[0][1]['x']}")
            
            # Highlight for debug
            try:
                target_btn.evaluate("el => el.style.border = '5px solid red'")
                time.sleep(0.5)
            except: pass
            
            print("    👉 Clicking...")
            try: 
                target_btn.click(force=True)
                print("    ✅ Clicked candidate.")
                return True
            except:
                try:
                    target_btn.evaluate("el => el.click()")
                    print("    ✅ JS Clicked candidate.")
                    return True
                except: pass
        
        print("    ❌ Failed to find a valid Run button candidate (Right-Most Black Button).")
        
        # Fallback: Enter Key
        print("    ⚠️ Fallback: Pressing Enter...")
        page.keyboard.press("Enter")
        return True

    except Exception as e:
        print(f"    ❌ Error during generation: {e}")
        return False

def clear_inputs(page):
    """
    Clears inputs ONLY from Subject, Scene, and Style sections.
    """
    print("  🧹 Clearing inputs (Subject, Scene, Style)...")
    sections = ["Subject", "Scene", "Style"]
    
    for section in sections:
        try:
            # 1. Find Header
            header = page.get_by_text(section, exact=True).first
            if not header.is_visible():
                 header = page.get_by_text(re.compile(f"^{section}", re.IGNORECASE)).first
            
            if not header.is_visible():
                continue

            # 2. Find Container
            container = header.locator("xpath=..")
            card_found = None
            for i in range(5):
                try:
                    box = container.bounding_box()
                    if box and box['height'] > 150:
                        card_found = container
                        break
                    container = container.locator("xpath=..")
                except: pass
            
            if card_found:
                 # 3. Find Remove Button INSIDE container
                 # Look for 'X' button or aria-label 'Remove'/'Clear'
                 found_remove = False
                 btns = card_found.locator("button, div[role='button']").all()
                 
                 for btn in btns:
                     if not btn.is_visible(): continue
                     lbl = (btn.get_attribute("aria-label") or "").lower()
                     txt = (btn.text_content() or "").lower()
                     
                     # Target "Remove image" or just "Remove" or "X"
                     if "remove" in lbl or "clear" in lbl or "delete" in lbl or "x" == txt.strip():
                         btn.click()
                         print(f"    ✅ Cleared '{section}'.")
                         found_remove = True
                         time.sleep(0.5)
                         break
                 
                 if not found_remove:
                     # Check for specific "trash" icon if standard methods fail
                     trash_icon = card_found.locator("svg[data-testid*='trash'], svg[class*='trash']").first
                     if trash_icon.is_visible():
                         # click parent button usually
                         trash_icon.locator("xpath=..").click()
                         print(f"    ✅ Cleared '{section}' via Trash Icon.")

        except Exception as e:
            print(f"    ⚠️ Error checking '{section}': {e}")

def main():
    print("🚀 Starting Whisk Automation...")
    
    images = load_images(IMAGES_FOLDER)
    if not images:
        print("No images to process. Exiting.")
        return

    # Check if paths are placeholders
    if "USERNAME" in USER_DATA_DIR:
        print("\n⚠️  WARNING: You are using the default placeholder for USER_DATA_DIR.")
        print("Please edit the script and set the correct path to your Chrome User Data.")
        print("Example: user_data_dir = r'C:\\Users\\Bob\\AppData\\Local\\Google\\Chrome\\User Data'")
        return

    # Ensure clean slate
    kill_existing_chrome()

    print("🔌 Launching Browser (Persistent Context)...")
    
    with sync_playwright() as p:
        try:
            # proper args for persistent context
            # Launch Incognito Browser
            browser = p.chromium.launch(
                headless=False,
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                args=[
                    "--start-maximized",
                    "--incognito",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu"
                ],
                ignore_default_args=["--enable-automation"],
                timeout=60000
            )
            
            # Create a new context and page
            # Note: --start-maximized in args works best when no_viewport is handled or we rely on the window args.
            # logic for max window size in playwright often needs no_viewport=True in new_context if not using persistent.
            context = browser.new_context(no_viewport=True)
            page = context.new_page()

            print(f"🌐 Navigating to {WHISK_URL}...")
            try:
                page.goto(WHISK_URL, timeout=60000)
            except Exception as nav_err:
                 print(f"    ⚠️ Navigation warning: {nav_err}")
            
            # Perform Login
            login(page, EMAIL, PASSWORD)

            print("\n🏁 Starting Image Processing Loop\n")
            
            for idx, img_name in enumerate(images):
                img_path = os.path.join(IMAGES_FOLDER, img_name)
                print(f"[{idx+1}/{len(images)}] Processing: {img_name}")
                
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
                
                # 3. Cleanup Inputs (ALWAYS run this to clear partial uploads or successful ones)
                try:
                    clear_inputs(page)
                    print("    ⏳ Stabilizing UI after cleanup (5s)...")
                    time.sleep(5)
                except: pass
                
                print("-----------------------------------")
                time.sleep(2) # Cooldown between iterations
                
            print("\n🎉 All images processed!")
            time.sleep(5) # Let user see final result
            
            browser.close()
            
        except Exception as e:
            print(f"\n❌ Critical Error: {e}")
            print("Tip: Ensure all Chrome instances are closed before running this script.")

if __name__ == "__main__":
    main()

