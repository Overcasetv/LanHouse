# Game House Manager

A professional LAN house management system for tracking PC usage, billing, transactions, and operator notes. Built with Python and Tkinter.

## Features
- Per-PC hourly rates (set different rates for each PC)
- Assign users and top-up hours/minutes per PC
- Automatic price calculation for top-ups
- Transaction history window (shows all top-ups and checkouts, with daily totals)
- Visual status indicators (available, running, time expired, rest)
- Rest timer for PCs
- Fit-to-screen, scrollable, and manual resizing
- Atomic data saves and backup system
- Logging of all transactions and events
- CSV export for daily usage and billing reports
- Easy PC count adjustment and renaming
- Transparent background for professional look
- **Live charge calculation**: See the current amount due for each PC as time is used
- **Session time tracking**: See total time added for each session, updated live
- **Per-PC notes**: Add and save operator notes for each PC

## Installation
1. Ensure you have Python 3.8+ installed.
2. Clone or download this repository.
3. Install required packages (if any):
   ```bash
   pip install tk
   ```
4. Run the application:
   ```bash
   python lan_house_manager.py
   ```

## Usage
- Set the number of PCs and rename them as needed.
- Set hourly rates for each PC individually.
- Assign users and top-up hours/minutes; the app will show the amount to pay.
- Use the transaction history window to view all transactions and total daily revenue.
- Export reports to CSV for accounting.
- Add notes for each PC (e.g., maintenance, user requests, etc.).
- All data is saved atomically and backed up automatically.

## Data Files
- `lanhouse_data.json`: Main data file (PCs, users, rates, sessions, notes)
- `transactions.log`: Transaction log (top-ups, checkouts)
- `backups/`: Automatic backups of data
- `lanhouse.log`: General event log

## Professional Features
- Scheduled backups (coming soon)
- Operator accounts and audit log (coming soon)
- POS/payment integration (optional, planned)
- Settings and help dialogs (planned)

## Support
For issues or feature requests, open an issue in this repository.

## License
MIT License
