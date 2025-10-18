import tkinter as tk
from tkinter import messagebox
import json
import time
import os
import math
import shutil
import csv
import datetime
import tempfile
import logging

DATA_FILE = "lanhouse_data.json"
BACKUP_DIR = "backups"
LOG_FILE = "lanhouse.log"
TRANSACTION_LOG = "transactions.log" # Novo log de transações para auditoria

# setup logger for main events
logger = logging.getLogger("lanhouse")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(fh)

# setup transaction logger for billing/top-up events
trans_logger = logging.getLogger("transactions")
trans_logger.setLevel(logging.INFO)
if not trans_logger.handlers:
    tfh = logging.FileHandler(TRANSACTION_LOG)
    tfh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    trans_logger.addHandler(tfh)

# --- Helper functions ---
def load_data():
    # Load data from the provided lanhouse_data.json
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Ensure basic structure if missing after load
            data.setdefault("computers", {})
            data.setdefault("hourly_rate", 15.0) 
            return data
    else:
        return {"computers": {}, "hourly_rate": 15.0}

def atomic_write_json(path, data):
    # write to a temp file then atomically replace
    dirn = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(prefix="tmp", dir=dirn)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

def make_backup(path):
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = os.path.join(BACKUP_DIR, f"lanhouse_{ts}.json")
        shutil.copy2(path, dst)
        logger.info(f"Backup created: {dst}")
    except Exception as e:
        logger.exception("Failed to create backup")

def save_data(data):
    # create backup first if file exists
    try:
        if os.path.exists(DATA_FILE):
            make_backup(DATA_FILE)
        atomic_write_json(DATA_FILE, data)
        logger.info("Data saved")
    except Exception:
        logger.exception("Failed to save data")

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

# --- Main Application ---
class LanHouseManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.data = load_data()
        # Janela agora exibe a taxa horária
        self.title(f"Game House Manager - Rate: ${self.data.get('hourly_rate', 15.0):.2f}/h")
        self.geometry("480x420")
        self.resizable(False, False)

        # Set transparent background for main window (where supported)
        try:
            self.wm_attributes('-transparentcolor', self['bg'])
        except Exception:
            pass

        # initialize computers list from data if present, else default 6
        saved_keys = list(self.data.get("computers", {}).keys())
        if saved_keys:
            self.computers = saved_keys
        else:
            self.computers = [f"PC-{i}" for i in range(1, 7)]

        tk.Label(self, text="Game House Time Manager", font=("Helvetica", 18, "bold")).pack(pady=10)

        # top controls: number of PCs, rename, and billing rate
        top_ctrl = tk.Frame(self)
        top_ctrl.pack(pady=(0,8))
        tk.Label(top_ctrl, text="# PCs:").pack(side=tk.LEFT)
        self.pc_count_var = tk.IntVar(value=len(self.computers))
        pc_spin = tk.Spinbox(top_ctrl, from_=1, to_=32, width=4, textvariable=self.pc_count_var, command=self.on_pc_count_change)
        pc_spin.pack(side=tk.LEFT, padx=(4,8))
        tk.Button(top_ctrl, text="Rename PC", command=self.rename_pc_dialog).pack(side=tk.LEFT)


        # Per-PC billing rate UI
        tk.Label(top_ctrl, text="Set Rate for PC:").pack(side=tk.LEFT, padx=(16,2))
        self.rate_pc_var = tk.StringVar(value=self.computers[0] if self.computers else "")
        self.rate_val_var = tk.DoubleVar(value=15.0)
        self.rate_menu = tk.OptionMenu(top_ctrl, self.rate_pc_var, *self.computers, command=self._on_rate_pc_change)
        self.rate_menu.pack(side=tk.LEFT)
        rate_entry = tk.Entry(top_ctrl, textvariable=self.rate_val_var, width=6)
        rate_entry.pack(side=tk.LEFT)
        tk.Button(top_ctrl, text="Set Rate", command=self.set_rate).pack(side=tk.LEFT, padx=(2,0))
        self._on_rate_pc_change(self.rate_pc_var.get())


        # --- Scrollable area for PC tiles ---
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.frame = tk.Frame(self.canvas)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.hsb = tk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True, pady=10)
        self.canvas.create_window((0,0), window=self.frame, anchor="nw")

        def _on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.frame.bind("<Configure>", _on_frame_configure)

        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.pc_buttons = {}

        # Ensure data structure for each PC exists and build UI
        self.build_pc_tiles()

        # UI control row
        ctrl = tk.Frame(self)
        ctrl.pack(pady=8)
        # Salvamento silencioso por padrão, com opção de mostrar info
        tk.Button(ctrl, text="Save Now", command=lambda: self.save_now(show_info=True)).pack(side=tk.LEFT, padx=6)
        tk.Button(ctrl, text="Reset All", command=self.reset_all).pack(side=tk.LEFT, padx=6)
        tk.Button(ctrl, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=(8,0))
        # Fit to screen toggle
        self.fit_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Fit to Screen", variable=self.fit_var, command=self.on_fit_toggle).pack(side=tk.LEFT, padx=(8,0))
        # allow manual resizing
        self.resizable(True, True)
        self._saved_geometry = None

        # Add button to show transaction history
        tk.Button(ctrl, text="Show Transactions", command=self.show_transactions_window).pack(side=tk.LEFT, padx=(8,0))

        # start periodic UI update
        self._running_update = True
        self.update_display()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _on_rate_pc_change(self, pc):
        # Update rate_val_var to match selected PC's rate
        rate = self.data["computers"].get(pc, {}).get("rate", self.data.get("hourly_rate", 15.0))
        self.rate_val_var.set(rate)

    def set_rate(self):
        pc = self.rate_pc_var.get()
        try:
            rate = float(self.rate_val_var.get())
            if rate < 0:
                raise ValueError()
            # Set per-PC rate
            self.data["computers"].setdefault(pc, {})["rate"] = rate
            save_data(self.data)
            messagebox.showinfo("Rate Set", f"Hourly rate for {pc} set to ${rate:.2f}")
        except Exception:
            messagebox.showerror("Invalid", "Enter a valid non-negative rate.")

    def build_pc_tiles(self):
        # Update rate menu if PCs changed
        if hasattr(self, 'rate_menu'):
            menu = self.rate_menu['menu']
            menu.delete(0, 'end')
            for pc in self.computers:
                menu.add_command(label=pc, command=lambda v=pc: self.rate_pc_var.set(v))
        # clear existing
        for child in self.frame.winfo_children():
            child.destroy()
        self.pc_buttons.clear()

        # Ensure data structure for each PC exists
        for pc in self.computers:
            if pc not in self.data.get("computers", {}):
                self.data.setdefault("computers", {})[pc] = {
                    "running": False,
                    "start_time": None,
                    "elapsed": 0.0,
                    "user": None,
                    "hours_remaining": 0.0,
                    "rest_until": 0.0,
                    "rate": self.data.get("hourly_rate", 15.0),
                }
            # Ensure rate exists for all PCs
            if "rate" not in self.data["computers"][pc]:
                self.data["computers"][pc]["rate"] = self.data.get("hourly_rate", 15.0)

        # compute grid layout: try to make it roughly square, min 2 cols
        n = len(self.computers)
        cols = max(2, int(math.ceil(math.sqrt(n))))
        rows = int(math.ceil(n / cols))

        # resize main window to accommodate tiles
        width = max(480, cols * 240)
        height = max(420, rows * 200 + 150)
        try:
            self.geometry(f"{width}x{height}")
        except Exception:
            pass

        for i, pc in enumerate(self.computers):
            row = i // cols
            col = i % cols
            tile = tk.Frame(self.frame, relief=tk.RAISED, borderwidth=1, padx=8, pady=8)
            tile.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            label = tk.Label(tile, text=pc, font=("Helvetica", 14, "bold"))
            label.pack()

            time_var = tk.StringVar(value=format_time(self.data["computers"][pc].get("elapsed", 0)))
            time_label = tk.Label(tile, textvariable=time_var, font=("Helvetica", 12))
            time_label.pack(pady=(4, 8))

            user_var = tk.StringVar(value=self.data["computers"][pc].get("user") or "(empty)")
            user_label = tk.Label(tile, textvariable=user_var, font=("Helvetica", 10))
            user_label.pack()

            hours_var = tk.StringVar(value=f"Hours: {self.data['computers'][pc].get('hours_remaining', 0)/3600:.2f}")
            hours_label = tk.Label(tile, textvariable=hours_var, font=("Helvetica", 10))
            hours_label.pack()

            remaining_var = tk.StringVar(value=format_time(self.data['computers'][pc].get('hours_remaining', 0)))
            remaining_label = tk.Label(tile, textvariable=remaining_var, font=("Helvetica", 10))
            remaining_label.pack()

            # Billing charge display
            charge_var = tk.StringVar(value=self.get_charge_text(pc))
            charge_label = tk.Label(tile, textvariable=charge_var, font=("Helvetica", 10), fg="blue")
            charge_label.pack()

            # rest display and control
            rest_var = tk.StringVar(value="")
            rest_label = tk.Label(tile, textvariable=rest_var, font=("Helvetica", 10), fg="red")
            rest_label.pack()

            rest_btn = tk.Button(tile, text="Rest", command=lambda p=pc: self.set_rest_dialog(p))
            rest_btn.pack(pady=(4,0))
            
            # NOVO: Botão Checkout para finalizar a cobrança
            checkout_btn = tk.Button(tile, text="Checkout", command=lambda p=pc: self.checkout_pc(p))
            checkout_btn.pack(pady=(4,0))

            # NOVO: Botão Assign/Top-up para setup rápido
            assign_btn = tk.Button(tile, text="Assign/Top-up", command=lambda p=pc: self.topup_and_assign_dialog(p))
            assign_btn.pack(pady=(4,0))

            # preset top-up buttons
            presets = tk.Frame(tile)
            presets.pack(pady=(4,0))
            tk.Button(presets, text="+15m", width=4, command=lambda p=pc: self.topup_preset(p, 15)).pack(side=tk.LEFT, padx=2)
            tk.Button(presets, text="+30m", width=4, command=lambda p=pc: self.topup_preset(p, 30)).pack(side=tk.LEFT, padx=2)
            tk.Button(presets, text="+1h", width=4, command=lambda p=pc: self.topup_preset(p, 60)).pack(side=tk.LEFT, padx=2)
            
            btn_text = tk.StringVar()
            btn = tk.Button(tile, textvariable=btn_text, width=10, command=lambda p=pc: self.toggle_pc(p))
            btn.pack()

            # Show total time added for this session
            total_added = 0
            if 'topups' in self.data['computers'][pc]:
                total_added = sum(t['amount'] for t in self.data['computers'][pc]['topups'])
            added_time_var = tk.StringVar(value=f"Added: {format_time(total_added)}")
            added_time_label = tk.Label(tile, textvariable=added_time_var, font=("Helvetica", 10), fg="purple")
            added_time_label.pack()

            # Notes for this PC
            pc_info = self.data['computers'][pc]
            note_var = tk.StringVar(value=pc_info.get('note', ''))
            def save_note(event=None, pc=pc, var=note_var):
                self.data['computers'][pc]['note'] = var.get()
                self.save_now(show_info=False)
            note_entry = tk.Entry(tile, textvariable=note_var, width=18, font=("Helvetica", 10), fg="darkgreen")
            note_entry.pack(pady=(2,0))
            note_entry.bind('<FocusOut>', lambda e, pc=pc, var=note_var: save_note(pc=pc, var=var))
            note_entry.bind('<Return>', lambda e, pc=pc, var=note_var: save_note(pc=pc, var=var))
            note_entry.config(highlightbackground="#b0e0b0", highlightcolor="#008000")

            # store widgets and vars
            default_bg = tile.cget("bg")

            self.pc_buttons[pc] = {
                "frame": tile,
                "label": label,
                "time_var": time_var,
                "time_label": time_label,
                "button": btn,
                "btn_text": btn_text,
                "user_var": user_var,
                "user_label": user_label,
                "hours_var": hours_var,
                "remaining_var": remaining_var,
                "remaining_label": remaining_label,
                "hours_label": hours_label,
                "charge_var": charge_var,
                "charge_label": charge_label,
                "default_bg": default_bg,
                "rest_var": rest_var,
                "rest_label": rest_label,
                "rest_btn": rest_btn,
                "checkout_btn": checkout_btn,
                "assign_btn": assign_btn,
                # runtime flags (not persisted)
                "_notified_time_up": False,
                "_notified_rest_done": False,
                "_blink": False,
                # Added time widgets
                "added_time_var": added_time_var,
                "added_time_label": added_time_label,
                # Note widgets
                "note_var": note_var,
                "note_entry": note_entry,
            }
    
    def get_charge_text(self, pc, final=False):
        info = self.data["computers"][pc]
        # If there are tracked topups, sum their cost for the session
        if info.get("topups"):
            total_due = sum(t["cost"] for t in info["topups"])
            # If session is running, add the value of time used since last top-up
            if info.get("running") and info.get("start_time"):
                now = time.time()
                last_topup_time = max((t["timestamp"] for t in info["topups"]), default=info["start_time"])
                extra_seconds = now - info["start_time"]
                # Only charge for extra time if user has used more than what was topped up
                # (e.g., if they run out of topped-up time and keep running)
                if info.get("hours_remaining", 0) <= 0:
                    rate = info.get("rate", self.data.get("hourly_rate", 15.0))
                    extra_charge = (extra_seconds / 3600) * rate
                    total_due += extra_charge
                    return f"Total Due: ${total_due:.2f} (all top-ups + overtime)"
            return f"Total Due: ${total_due:.2f} (all top-ups)"
        # fallback to elapsed * rate if no topups (legacy)
        rate = info.get("rate", self.data.get("hourly_rate", 15.0))
        used_seconds = info.get("elapsed", 0)
        if info.get("running") and info.get("start_time") and not final:
            used_seconds += time.time() - info["start_time"]
        charge = (used_seconds / 3600) * rate
        return f"Charge: ${charge:.2f} (Rate: ${rate:.2f}/h)"

    def checkout_pc(self, pc):
        # Finaliza a sessão, calcula a cobrança e reseta o PC.
        info = self.data["computers"][pc]
        
        # 1. Stop if running to finalize elapsed time
        if info.get("running"):
            self.toggle_pc(pc) # Vai parar e atualizar o elapsed time
            
        # 2. Get final charge
        final_charge_text = self.get_charge_text(pc, final=True)
        used_time = format_time(info.get("elapsed", 0))
        user_name = info.get("user") or "N/A"
        
        # 3. Confirm and display final bill
        if not messagebox.askyesno("Final Checkout", 
                                   f"PC: {pc}\nUser: {user_name}\nTime Used: {used_time}\n\nTotal Due: {final_charge_text}\n\nConfirm payment and reset station?"):
            return
            
        # 4. Log the transaction
        trans_logger.info(f"CHECKOUT: PC={pc}, User={user_name}, Elapsed={used_time}, Charge={final_charge_text}")
        
        # 5. Reset station data (zero out)
        self.data["computers"][pc] = {
            "running": False,
            "start_time": None,
            "elapsed": 0.0,
            "user": None,
            "hours_remaining": 0.0,
            "rest_until": 0.0,
        }
        
        # Reset UI flags
        widgets = self.pc_buttons[pc]
        widgets["_notified_time_up"] = False
        widgets["_notified_rest_done"] = False
        widgets["_blink"] = False
        
        self.save_now(show_info=False) # Salva silenciosamente
        self.update_display() # Força a atualização da UI
        messagebox.showinfo("Checkout Complete", f"Payment confirmed. PC {pc} is now available.")


    def toggle_pc(self, pc):
        info = self.data["computers"][pc]
        
        # If running, stop the session
        if info.get("running"):
            start = info.get("start_time")
            if start:
                elapsed = time.time() - start
                info["elapsed"] = info.get("elapsed", 0) + elapsed
                # decrement hours_remaining by delta seconds
                info["hours_remaining"] = max(0.0, info.get("hours_remaining", 0) - elapsed)
                
            info["running"] = False
            info["start_time"] = None
            self.save_now(show_info=False)
            return

        # If not running: check conditions for starting
        now = time.time()
        # 1. Prevent starting if resting
        if info.get("rest_until", 0) > now:
            messagebox.showwarning("Resting", f"PC {pc} is resting for {format_time(int(info['rest_until'] - now))} more.")
            return

        # 2. If no user or no hours, redirect to Top-up/Assign dialog
        if info.get("hours_remaining", 0) <= 0 or not info.get("user"):
            if not messagebox.askyesno("Start Session", f"PC {pc} needs to be assigned and topped up. Open setup dialog?"):
                return
            self.topup_and_assign_dialog(pc)
            return

        # 3. Start the session
        info["running"] = True
        info["start_time"] = time.time()
        self.save_now(show_info=False)
        
    def topup_and_assign_dialog(self, pc):
        # Dialog for Assign User and Top-up Hours, with price calculation
        info = self.data["computers"][pc]
        rate = info.get("rate", self.data.get("hourly_rate", 15.0))

        def update_price(*args):
            try:
                hrs = float(entry_hours.get() or 0)
                mins = float(entry_mins.get() or 0)
                total_hours = hrs + mins/60
                if total_hours < 0:
                    raise ValueError()
                price = total_hours * rate
                price_var.set(f"Amount to pay: ${price:.2f} (Rate: ${rate:.2f}/h)")
            except Exception:
                price_var.set("")

        def do_topup_assign():
            # 1. Assign User
            name = entry_user.get().strip()
            if name == "":
                messagebox.showwarning("Invalid", "Please enter a non-empty name")
                return
            info["user"] = name
            self.pc_buttons[pc]["user_var"].set(name)

            # 2. Top-up Hours
            try:
                hrs = float(entry_hours.get() or 0)
                mins = float(entry_mins.get() or 0)
                if hrs < 0 or mins < 0:
                    raise ValueError()
            except Exception:
                messagebox.showwarning("Invalid", "Enter non-negative numbers for hours and minutes")
                return
            added = hrs * 3600 + mins * 60
            if added <= 0:
                 messagebox.showwarning("Invalid", "Enter a positive amount to add")
                 return

            # Convert to seconds and add
            info["hours_remaining"] = info.get("hours_remaining", 0) + added
            self.pc_buttons[pc]["hours_var"].set(f"Hours: {info['hours_remaining']/3600:.2f}")

            # Track this top-up for the session
            if "topups" not in info:
                info["topups"] = []
            info["topups"].append({
                "amount": added,
                "rate": rate,
                "cost": (added/3600) * rate,
                "timestamp": time.time(),
            })
            # Update added time label if present
            if "added_time_var" in self.pc_buttons[pc]:
                total_added = sum(t['amount'] for t in info['topups'])
                self.pc_buttons[pc]["added_time_var"].set(f"Added: {format_time(total_added)}")

            # Log the Top-up transaction
            trans_logger.info(f"TOPUP: PC={pc}, User={name}, HoursAdded={round(added/3600, 2)}, Rate={rate}")

            self.pc_buttons[pc]["_notified_time_up"] = False

            dlg.destroy()
            self.save_now(show_info=False)

            # Prompt to start if session wasn't running
            if not info.get("running"):
                 if messagebox.askyesno("Start Now?", f"Hours topped up for {pc}. Do you want to START the session now?"):
                    self.toggle_pc(pc)

        dlg = tk.Toplevel(self)
        dlg.title(f"Setup Session for {pc}")

        # User assignment section
        tk.Label(dlg, text="1. User name:").grid(row=0, column=0, padx=8, pady=(8,0), sticky='w')
        entry_user = tk.Entry(dlg)
        entry_user.insert(0, info.get("user") or "")
        entry_user.grid(row=0, column=1, padx=8, pady=(8,0))

        # Hours top-up section
        tk.Label(dlg, text="2. Hours to add:").grid(row=1, column=0, padx=8, pady=(4,0), sticky='w')
        entry_hours = tk.Entry(dlg, width=8)
        entry_hours.insert(0, "1")
        entry_hours.grid(row=1, column=1, padx=8, pady=(4,0))

        tk.Label(dlg, text="Minutes to add:").grid(row=2, column=0, padx=8, pady=(4,0), sticky='w')
        entry_mins = tk.Entry(dlg, width=8)
        entry_mins.insert(0, "0")
        entry_mins.grid(row=2, column=1, padx=8, pady=(4,0))

        # Price display
        price_var = tk.StringVar()
        price_label = tk.Label(dlg, textvariable=price_var, fg="blue", font=("Helvetica", 11, "bold"))
        price_label.grid(row=3, column=0, columnspan=2, pady=(8,0))

        entry_hours.bind('<KeyRelease>', update_price)
        entry_mins.bind('<KeyRelease>', update_price)
        update_price()

        tk.Button(dlg, text="Confirm Setup & Top-up", command=do_topup_assign).grid(row=4, column=0, columnspan=2, pady=(16,8))

    def set_rest_dialog(self, pc):
        info = self.data["computers"][pc]
        def do_set():
            try:
                mins = float(entry.get())
                if mins <= 0:
                    raise ValueError()
            except Exception:
                messagebox.showwarning("Invalid", "Enter a positive number of minutes")
                return
            info["rest_until"] = time.time() + mins * 60
            self.pc_buttons[pc]["rest_var"].set(f"Rest: {format_time(int(info['rest_until'] - time.time()))}")
            dlg.destroy()
            self.save_now(show_info=False)

        dlg = tk.Toplevel(self)
        dlg.title(f"Set rest for {pc}")
        tk.Label(dlg, text="Minutes to rest:").pack(padx=8, pady=(8,0))
        entry = tk.Entry(dlg)
        entry.insert(0, "5")
        entry.pack(padx=8, pady=8)
        tk.Button(dlg, text="Set Rest", command=do_set).pack(pady=(0,8))


    def topup_preset(self, pc, minutes):
        info = self.data["computers"][pc]
        added = minutes * 60
        info["hours_remaining"] = info.get("hours_remaining", 0) + added
        self.pc_buttons[pc]["hours_var"].set(f"Hours: {info['hours_remaining']/3600:.2f}")
        # Log the Top-up transaction
        trans_logger.info(f"TOPUP: PC={pc}, User={info.get('user', 'N/A')}, HoursAdded={round(added/3600, 2)}")
        self.pc_buttons[pc]["_notified_time_up"] = False
        self.save_now(show_info=False)

        # Track this top-up for the session
        if "topups" not in info:
            info["topups"] = []
        rate = info.get("rate", self.data.get("hourly_rate", 15.0))
        info["topups"].append({
            "amount": added,
            "rate": rate,
            "cost": (added/3600) * rate,
            "timestamp": time.time(),
        })
        # Update added time label if present
        if "added_time_var" in self.pc_buttons[pc]:
            total_added = sum(t['amount'] for t in info['topups'])
            self.pc_buttons[pc]["added_time_var"].set(f"Added: {format_time(total_added)}")

    def notify(self, title, message):
        try:
            # simple audible bell
            self.bell()
        except Exception:
            pass
        try:
            # Use simple top-level window for non-intrusive notification
            tld = tk.Toplevel(self)
            tld.title(title)
            tk.Label(tld, text=message, padx=20, pady=20).pack()
        except Exception:
            # fallback to logger
            logger.info(f"{title}: {message}")

    def update_display(self):
        # update time labels and button text
        for pc, widgets in self.pc_buttons.items():
            info = self.data["computers"][pc]
            elapsed = info.get("elapsed", 0)
            
            # --- Timer Logic ---
            if info.get("running") and info.get("start_time"):
                now = time.time()
                delta = now - info["start_time"]
                elapsed = elapsed + delta
                # decrement hours_remaining by delta seconds
                info["hours_remaining"] = max(0.0, info.get("hours_remaining", 0) - delta)
                # move start_time forward to now so we don't double-count next tick
                info["start_time"] = now 
                
                # auto-stop if we've run out of hours
                if info.get("hours_remaining", 0) <= 0:
                    # finalize elapsed and stop
                    info["running"] = False
                    info["start_time"] = None
                    # notify once
                    if not widgets.get("_notified_time_up"):
                        self.notify("Time's up", f"PC {pc} time has expired.")
                        widgets["_notified_time_up"] = True
                    # save state
                    self.save_now(show_info=False)
            
            # --- UI Updates ---
            widgets["time_var"].set(format_time(elapsed))
            widgets["btn_text"].set("Stop" if info.get("running") else "Start")
            widgets["hours_var"].set(f"Hours: {info.get('hours_remaining', 0)/3600:.2f}")
            widgets["charge_var"].set(self.get_charge_text(pc))
            remaining = int(info.get('hours_remaining', 0))
            widgets.get('remaining_var', tk.StringVar()).set(format_time(remaining))

            # --- Rest Timer Check ---
            now = time.time()
            rest_until = info.get("rest_until", 0)
            if rest_until > now:
                widgets["rest_var"].set(f"Rest: {format_time(int(rest_until - now))}")
                if widgets.get("_notified_rest_done"):
                    widgets["_notified_rest_done"] = False # reset flag after update
            else:
                widgets["rest_var"].set("")
                if widgets.get("_notified_rest_done") is False and info.get("rest_until", 0) > 0:
                    self.notify("Rest finished", f"PC {pc} rest period finished.")
                    widgets["_notified_rest_done"] = True
            
            # --- Visual Status (Color Coding) ---
            default_bg = widgets.get("default_bg", None)
            
            # State 1: Available (Green) - No user, not running, no time
            if (info.get("hours_remaining", 0) <= 0 and not info.get("running") and not info.get("user")):
                widgets["frame"].configure(bg="#ddffdd")
                widgets["_blink"] = False
            # State 2: Time Expired (Blinking Red) - Has user/elapsed time, but no hours left
            elif info.get("hours_remaining", 0) <= 0 and not info.get("running") and (info.get("user") or info.get("elapsed", 0) > 0):
                blink = widgets.get("_blink", False)
                blink = not blink
                widgets["_blink"] = blink
                if blink:
                    widgets["frame"].configure(bg="#ff4444")
                else:
                    widgets["frame"].configure(bg="#ffdddd")
            # State 3: Running - Low Time Warning (Yellow)
            elif info.get("running") and info.get("hours_remaining", 0) <= (10 * 60): # 10 minutes warning
                 widgets["frame"].configure(bg="#ffffcc")
                 widgets["_blink"] = False
            # State 4: Default/Normal
            else:
                widgets["frame"].configure(bg=default_bg)
                widgets["_blink"] = False

            # Update added time label
            total_added = 0
            if 'topups' in info:
                total_added = sum(t['amount'] for t in info['topups'])
            if "added_time_var" in widgets:
                widgets["added_time_var"].set(f"Added: {format_time(total_added)}")

        if self._running_update:
            self.after(500, self.update_display)

    def on_pc_count_change(self):
        # Adjust number of PCs to match spinbox value
        try:
            new_count = int(self.pc_count_var.get())
        except Exception:
            return
        curr = len(self.computers)
        if new_count == curr:
            return
        if new_count > curr:
            # append new PC names, avoid name collisions
            i = 1
            while len(self.computers) < new_count:
                name = f"PC-{i}"
                if name not in self.computers:
                    self.computers.append(name)
                i += 1
        else:
            # confirm removal of last PCs
            if not messagebox.askyesno("Remove PCs", f"Remove last {curr - new_count} PCs and their data?"):
                # revert spinbox
                self.pc_count_var.set(curr)
                return
            to_remove = list(self.computers[new_count:])
            for pc in to_remove:
                self.computers.remove(pc)
                if pc in self.data.get("computers", {}):
                    del self.data["computers"][pc]
        # rebuild UI
        self.build_pc_tiles()
        self.save_now(show_info=False)

    def on_fit_toggle(self):
        # toggle fit to screen: maximize to available screen area or restore previous geometry
        if self.fit_var.get():
            # save current geometry and maximize
            try:
                self._saved_geometry = self.geometry()
                w = self.winfo_screenwidth()
                h = self.winfo_screenheight()
                # leave a small margin for the taskbar
                self.geometry(f"{w-40}x{h-80}+0+0")
            except Exception:
                pass
        else:
            # restore
            try:
                if self._saved_geometry:
                    self.geometry(self._saved_geometry)
            except Exception:
                pass

    def export_report(self):
        try:
            path = f"lanhouse_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(path, 'w', newline='') as csvfile:
                w = csv.writer(csvfile)
                w.writerow(["PC", "User", "Elapsed (s)", "Elapsed (H:M:S)", "Hours Remaining (h)", "Running", "Charge ($)"])
                rate = self.data.get("hourly_rate", 15.0)
                for pc in self.computers:
                    info = self.data.get('computers', {}).get(pc, {})
                    elapsed = info.get('elapsed', 0)
                    if info.get('running') and info.get('start_time'):
                        elapsed = elapsed + (time.time() - info.get('start_time'))
                    charge = (elapsed / 3600) * rate
                    w.writerow([pc, info.get('user') or '', int(elapsed), format_time(elapsed), round(info.get('hours_remaining', 0)/3600, 2), bool(info.get('running')), f"{charge:.2f}"])
            logger.info(f"Exported report: {path}")
            messagebox.showinfo("Exported", f"Report exported to {path}")
        except Exception:
            logger.exception("Failed to export report")
            messagebox.showerror("Error", "Failed to export report")

    def rename_pc_dialog(self):
        # dialog to pick a PC and rename it
        dlg = tk.Toplevel(self)
        dlg.title("Rename PC")
        tk.Label(dlg, text="Select PC:").pack(padx=8, pady=(8,0))
        pc_var = tk.StringVar(value=self.computers[0] if self.computers else "")
        pc_menu = tk.OptionMenu(dlg, pc_var, *self.computers)
        pc_menu.pack(padx=8, pady=4)
        tk.Label(dlg, text="New name:").pack(padx=8, pady=(8,0))
        entry = tk.Entry(dlg)
        entry.pack(padx=8, pady=4)

        def do_rename():
            old = pc_var.get()
            new = entry.get().strip()
            if not new:
                messagebox.showwarning("Invalid", "Enter a non-empty name")
                return
            if new in self.computers:
                messagebox.showwarning("Invalid", "A PC with that name already exists")
                return
            # move data under new key
            self.data.setdefault("computers", {})
            self.data["computers"][new] = self.data["computers"].pop(old, {"running": False, "start_time": None, "elapsed": 0.0, "user": None, "hours_remaining": 0.0})
            # replace in computers list
            idx = self.computers.index(old)
            self.computers[idx] = new
            dlg.destroy()
            self.build_pc_tiles()
            self.save_now(show_info=False)

        tk.Button(dlg, text="Rename", command=do_rename).pack(pady=(0,8))

    def save_now(self, show_info=True):
        # ensure running timers have start_time stored and elapsed preserved
        save_data(self.data)
        if show_info:
            messagebox.showinfo("Saved", "Data saved.")

    def reset_all(self):
        if not messagebox.askyesno("Reset", "Reset all timers and data? This action CANNOT be undone."):
            return
        for pc in self.computers:
            user = self.data["computers"].get(pc, {}).get("user")
            self.data["computers"][pc] = {
                "running": False, 
                "start_time": None, 
                "elapsed": 0.0, 
                "user": user, # Keep user assigned if one exists
                "hours_remaining": 0.0,
                "rest_until": 0.0
            }
        self.save_now(show_info=False)

    def on_close(self):
        # stop running timers and persist elapsed time
        for pc in self.computers:
            info = self.data["computers"][pc]
            if info.get("running") and info.get("start_time"):
                now = time.time()
                delta = now - info.get("start_time")
                info["elapsed"] = info.get("elapsed", 0) + delta
                info["hours_remaining"] = max(0.0, info.get("hours_remaining", 0) - delta)
                info["running"] = False
                info["start_time"] = None
        save_data(self.data)
        self._running_update = False
        self.destroy()

    def show_transactions_window(self):
        import re
        import datetime
        win = tk.Toplevel(self)
        win.title("Transaction History")
        win.geometry("800x500")
        # Table header
        header = ["Time", "Type", "PC", "User", "Amount ($)", "Details"]
        for col, text in enumerate(header):
            tk.Label(win, text=text, font=("Helvetica", 10, "bold"), borderwidth=1, relief="solid", padx=4, pady=2).grid(row=0, column=col, sticky="nsew")
        # Read and parse transactions.log
        rows = []
        total = 0.0
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        try:
            with open(TRANSACTION_LOG, "r") as f:
                for line in f:
                    # Example: 2025-10-17 14:23:01,123 INFO: CHECKOUT: PC=PC-1, User=John, Elapsed=01:00:00, Charge: $15.00
                    m = re.match(r"(\d{4}-\d{2}-\d{2} [\d:,]+) [A-Z]+: (\w+): PC=(.*?), User=(.*?),.*?Charge:? \$([\d.]+)", line)
                    if m:
                        t, typ, pc, user, amt = m.groups()
                        if t.startswith(today):
                            rows.append((t, typ, pc, user, amt, line.strip()))
                            if typ == "CHECKOUT":
                                try:
                                    total += float(amt)
                                except Exception:
                                    pass
        except Exception as e:
            tk.Label(win, text=f"Could not read {TRANSACTION_LOG}: {e}", fg="red").grid(row=1, column=0, columnspan=6)
            return
        # Show rows
        for r, row in enumerate(rows, 1):
            for c, val in enumerate(row):
                tk.Label(win, text=val, font=("Helvetica", 10), borderwidth=1, relief="solid", padx=2, pady=1, anchor="w").grid(row=r, column=c, sticky="nsew")
        # Show total
        tk.Label(win, text=f"Total money made today: ${total:.2f}", font=("Helvetica", 12, "bold"), fg="blue").grid(row=len(rows)+1, column=0, columnspan=6, pady=10)

def main():
    app = LanHouseManager()
    app.mainloop()

if __name__ == "__main__":
    main()
