# Whisk Automation Bot 🤖

An automated image generation workflow for **Google Labs Whisk**. This script automates the process of uploading local images, triggering the generation process, and looping through multiple images without manual intervention.

## ✨ Features
- **Automatic Login**: Handles Google account authentication.
- **Smart Upload**: Automatically uploads images to the 'Subject', 'Scene', and 'Style' sections.
- **Intelligent Run Detection**: Uses location-based and visual cues to locate and click the 'Run' button reliably.
- **Robust Looping**: Processes an entire directory of images sequentially.
- **Browser Persistence**: Options for persistent profiles or incognito mode.
- **Process Management**: Automatically handles Chrome process conflicts.

## 🛠️ Prerequisites
- Python 3.8+
- [Playwright](https://playwright.dev/python/docs/intro)
- Google Chrome installed on your system.

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/muhammadikram56/my-personal-project.git
   cd my-personal-project
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

## ⚙️ Configuration

Open `whisk_automation.py` and configure the following variables:

- `EMAIL` / `PASSWORD`: Your Google Account credentials.
- `IMAGES_FOLDER`: Path to the folder containing your source images.
- `WHISK_URL`: The target Whisk project URL.

## 🎮 Usage

Run the automation script:
```bash
python whisk_automation.py
```

The script will:
1. Launch Chrome (Incognito).
2. Log in to Whisk Lab.
3. Open the sidebar.
4. For each image in your folder:
   - Upload it to all relevant sections.
   - Wait for stability (12 seconds).
   - Click the **Run** button.
   - Proceed to the next image once generation starts.

## 📄 License
MIT License - Feel free to use and modify for your personal projects.
