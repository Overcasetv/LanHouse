# LAN House Manager

A professional LAN house management app for tracking computer usage, billing, rest periods, and more. Built with Python and Tkinter.

## Features
- Assign users to computers
- Track hours and rest time per PC
- Visual cues (red/green/blink) for status
- Adjustable window/grid for any number of PCs
- Atomic saves, backups, and logging
- CSV export for usage and billing
- Billing/rates UI (set hourly rate, see charges)
- Operator authentication (coming soon)
- Scheduled backups (coming soon)
- Audit log, operator accounts, daily sales report, POS integration (coming soon)

## Installation

### Prerequisites
- Python 3.8 or newer (recommended: Python 3.10+)
- Tkinter (usually included with Python)

### Steps
1. **Clone or download the project folder**
   - Place all files in a single directory (e.g., `gameing house project`).
2. **Install required Python packages**
   - No external packages required for basic usage.
   - For advanced features (CSV export, logging), all dependencies are standard library.
3. **Run the app**
   - Open a terminal in the project directory.
   - Run:
     ```sh
     python3 lan_house_manager.py
     ```
   - The GUI will open. Use the controls to manage PCs, assign users, set rates, and more.

### Optional: Build Standalone Executable
- Use `setup.py` or a tool like PyInstaller to create a standalone app for Windows/Mac/Linux.
- Example (with PyInstaller):
  ```sh
  pip install pyinstaller
  pyinstaller --onefile lan_house_manager.py
  ```
- The executable will be in the `dist/` folder.

## Data Files
- Usage data is saved in `lanhouse_data.json`.
- Backups are stored in the `backups/` folder.
- Logs are written to `lanhouse.log`.
- Reports are exported as CSV files in the project directory.

## Support
For help or feature requests, open an issue or contact the developer.

---
*Last updated: October 17, 2025*
