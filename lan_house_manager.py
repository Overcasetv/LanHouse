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

# setup simple file logger
logger = logging.getLogger("lanhouse")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(fh)

# --- Helper functions ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    else:
        return {"computers": {}}

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
        self.title("LAN House Manager")
        self.geometry("480x420")
        self.resizable(False, False)

        self.data = load_data()
        # initialize computers list from data if present, else default 6
        saved_keys = list(self.data.get("computers", {}).keys())
        if saved_keys:
            self.computers = saved_keys
        else:
            self.computers = [f"PC-{i}" for i in range(1, 7)]

        tk.Label(self, text="LAN House Time Manager", font=("Helvetica", 18, "bold")).pack(pady=10)

        # top controls: number of PCs, rename, and billing rate
        top_ctrl = tk.Frame(self)
        top_ctrl.pack(pady=(0,8))
        tk.Label(top_ctrl, text="# PCs:").pack(side=tk.LEFT)
        self.pc_count_var = tk.IntVar(value=len(self.computers))
        pc_spin = tk.Spinbox(top_ctrl, from_=1, to=32, width=4, textvariable=self.pc_count_var, command=self.on_pc_count_change)
        pc_spin.pack(side=tk.LEFT, padx=(4,8))
        tk.Button(top_ctrl, text="Rename PC", command=self.rename_pc_dialog).pack(side=tk.LEFT)

        # Billing rate UI
        tk.Label(top_ctrl, text="Hourly Rate ($):").pack(side=tk.LEFT, padx=(16,2))
        self.rate_var = tk.DoubleVar(value=self.data.get("hourly_rate", 5.0))
        rate_entry = tk.Entry(top_ctrl, textvariable=self.rate_var, width=6)
        rate_entry.pack(side=tk.LEFT)
        tk.Button(top_ctrl, text="Set Rate", command=self.set_rate).pack(side=tk.LEFT, padx=(2,0))

        self.frame = tk.Frame(self)
        self.frame.pack(pady=10)

        self.pc_buttons = {}
    def set_rate(self):
        try:
            rate = float(self.rate_var.get())
            if rate < 0:
                raise ValueError()
            self.data["hourly_rate"] = rate
            save_data(self.data)
            messagebox.showinfo("Rate Set", f"Hourly rate set to ${rate:.2f}")
        except Exception:
            messagebox.showerror("Invalid", "Enter a valid non-negative rate.")
        # Ensure data structure for each PC exists
        for pc in self.computers:
            if pc not in self.data.get("computers", {}):
                self.data.setdefault("computers", {})[pc] = {
                    "running": False,
                    "start_time": None,
                    "elapsed": 0.0,
                    # new fields
                    "user": None,
                    # hours remaining in seconds
                    "hours_remaining": 0.0,
                    # rest_until: epoch timestamp until which PC is resting
                    "rest_until": 0.0,
                }

        # Create UI tiles for each PC (this will also size the window)
        self.build_pc_tiles()

        # UI control row
        ctrl = tk.Frame(self)
        ctrl.pack(pady=8)
        tk.Button(ctrl, text="Save Now", command=self.save_now).pack(side=tk.LEFT, padx=6)
        tk.Button(ctrl, text="Reset All", command=self.reset_all).pack(side=tk.LEFT, padx=6)
        tk.Button(ctrl, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=(8,0))
        # Fit to screen toggle
        self.fit_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Fit to Screen", variable=self.fit_var, command=self.on_fit_toggle).pack(side=tk.LEFT, padx=(8,0))
        # allow manual resizing
        self.resizable(True, True)
        self._saved_geometry = None

        # start periodic UI update
        self._running_update = True
        self.update_display()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_pc_tiles(self):
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
                    # new fields
                    "user": None,
                    # hours remaining in seconds
                    "hours_remaining": 0.0,
                }

        # compute grid layout: try to make it roughly square, min 2 cols
        n = len(self.computers)
        cols = max(2, int(math.ceil(math.sqrt(n))))
        rows = int(math.ceil(n / cols))

        # resize main window to accommodate tiles
        width = max(600, cols * 240)
        height = max(400, rows * 200 + 150)
        try:
            self.geometry(f"{width}x{height}")
        except Exception:
            # ignore if geometry fails for some reason
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

            assign_btn = tk.Button(tile, text="Assign", command=lambda p=pc: self.assign_user(p))
            assign_btn.pack(pady=(4,0))

            # preset top-up buttons
            presets = tk.Frame(tile)
            presets.pack(pady=(4,0))
            tk.Button(presets, text="+15m", width=4, command=lambda p=pc: self.topup_preset(p, 15)).pack(side=tk.LEFT, padx=2)
            tk.Button(presets, text="+30m", width=4, command=lambda p=pc: self.topup_preset(p, 30)).pack(side=tk.LEFT, padx=2)
            tk.Button(presets, text="+1h", width=4, command=lambda p=pc: self.topup_preset(p, 60)).pack(side=tk.LEFT, padx=2)
            topup_btn = tk.Button(tile, text="Top-up", command=lambda p=pc: self.topup_hours(p))
            topup_btn.pack()

            btn_text = tk.StringVar()
            btn = tk.Button(tile, textvariable=btn_text, width=10, command=lambda p=pc: self.toggle_pc(p))
            btn.pack()

            # store widgets and vars
            # store the default background color so we can restore it
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
                # runtime flags (not persisted)
                "_notified_time_up": False,
                "_notified_rest_done": False,
                "assign_btn": assign_btn,
                "topup_btn": topup_btn,
            }
    def get_charge_text(self, pc):
        info = self.data["computers"][pc]
        rate = self.data.get("hourly_rate", 5.0)
        used_seconds = info.get("elapsed", 0)
        if info.get("running") and info.get("start_time"):
            used_seconds += time.time() - info["start_time"]
        charge = (used_seconds / 3600) * rate
        return f"Charge: ${charge:.2f}"

    

    def toggle_pc(self, pc):
        info = self.data["computers"][pc]
        if info.get("running"):
            # stop
            start = info.get("start_time")
            if start:
                elapsed = time.time() - start
                info["elapsed"] = info.get("elapsed", 0) + elapsed
            info["running"] = False
            info["start_time"] = None
        else:
            # prevent starting if resting
            now = time.time()
            if info.get("rest_until", 0) > now:
                messagebox.showwarning("Resting", f"PC {pc} is resting for {format_time(int(info['rest_until'] - now))} more.")
                return
            # start only if there are hours remaining
            if info.get("hours_remaining", 0) <= 0:
                messagebox.showwarning("No hours", f"PC {pc} has no hours remaining. Top-up before starting.")
                return
            # consume any hours as the session runs; store start time
            info["running"] = True
            info["start_time"] = time.time()
        self.save_now()

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
            self.save_now()

        dlg = tk.Toplevel(self)
        dlg.title(f"Set rest for {pc}")
        tk.Label(dlg, text="Minutes to rest:").pack(padx=8, pady=(8,0))
        entry = tk.Entry(dlg)
        entry.insert(0, "5")
        entry.pack(padx=8, pady=8)
        tk.Button(dlg, text="Set Rest", command=do_set).pack(pady=(0,8))

    def assign_user(self, pc):
        info = self.data["computers"][pc]
        def do_assign():
            name = entry.get().strip()
            if name == "":
                messagebox.showwarning("Invalid", "Please enter a non-empty name")
                return
            info["user"] = name
            self.pc_buttons[pc]["user_var"].set(name)
            dlg.destroy()
            self.save_now()

        dlg = tk.Toplevel(self)
        dlg.title(f"Assign user to {pc}")
        tk.Label(dlg, text="User name:").pack(padx=8, pady=(8,0))
        entry = tk.Entry(dlg)
        entry.insert(0, info.get("user") or "")
        entry.pack(padx=8, pady=8)
        tk.Button(dlg, text="Assign", command=do_assign).pack(pady=(0,8))

    def topup_hours(self, pc):
        info = self.data["computers"][pc]
        def do_topup():
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
            # convert to seconds and add
            info["hours_remaining"] = info.get("hours_remaining", 0) + added
            self.pc_buttons[pc]["hours_var"].set(f"Hours: {info['hours_remaining']/3600:.2f}")
            dlg.destroy()
            self.save_now()

        dlg = tk.Toplevel(self)
        dlg.title(f"Top-up hours for {pc}")
        tk.Label(dlg, text="Hours to add:").grid(row=0, column=0, padx=8, pady=(8,0))
        tk.Label(dlg, text="Minutes to add:").grid(row=1, column=0, padx=8, pady=(4,0))
        entry_hours = tk.Entry(dlg, width=8)
        entry_hours.insert(0, "1")
        entry_hours.grid(row=0, column=1, padx=8, pady=(8,0))
        entry_mins = tk.Entry(dlg, width=8)
        entry_mins.insert(0, "0")
        entry_mins.grid(row=1, column=1, padx=8, pady=(4,0))
        tk.Button(dlg, text="Top-up", command=do_topup).grid(row=2, column=0, columnspan=2, pady=(8,8))

    def topup_preset(self, pc, minutes):
        info = self.data["computers"][pc]
        added = minutes * 60
        info["hours_remaining"] = info.get("hours_remaining", 0) + added
        self.pc_buttons[pc]["hours_var"].set(f"Hours: {info['hours_remaining']/3600:.2f}")
        # clear time-up notification if any
        self.pc_buttons[pc]["_notified_time_up"] = False
        self.save_now()

    def notify(self, title, message):
        try:
            # simple audible bell
            self.bell()
        except Exception:
            pass
        try:
            messagebox.showinfo(title, message)
        except Exception:
            # fallback to logger
            logger.info(f"{title}: {message}")

    def update_display(self):
        # update time labels and button text
        for pc, widgets in self.pc_buttons.items():
            info = self.data["computers"][pc]
            elapsed = info.get("elapsed", 0)
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
                    self.save_now()
            widgets["time_var"].set(format_time(elapsed))
            widgets["btn_text"].set("Stop" if info.get("running") else "Start")
            widgets["hours_var"].set(f"Hours: {info.get('hours_remaining', 0)/3600:.2f}")
            # update charge display
            widgets["charge_var"].set(self.get_charge_text(pc))
            # update rest label if resting
            now = time.time()
            rest_until = info.get("rest_until", 0)
            if rest_until > now:
                widgets["rest_var"].set(f"Rest: {format_time(int(rest_until - now))}")
            else:
                widgets["rest_var"].set("")
                # notify when rest finished (once)
                if widgets.get("_notified_rest_done") is False and info.get("rest_until", 0) > 0:
                    self.notify("Rest finished", f"PC {pc} rest period finished.")
                    widgets["_notified_rest_done"] = True

            # update remaining countdown display
            remaining = int(info.get('hours_remaining', 0))
            widgets.get('remaining_var', tk.StringVar()).set(format_time(remaining))

            # special case: if no user assigned and no hours, show solid green
            if (info.get("hours_remaining", 0) <= 0 and not info.get("running") and not info.get("user")):
                try:
                    widgets["frame"].configure(bg="#ddffdd")
                    widgets["_blink"] = False
                except Exception:
                    pass
            # blinking when hours are up (and not running)
            elif info.get("hours_remaining", 0) <= 0 and not info.get("running"):
                # toggle blink flag per widget
                blink = widgets.get("_blink", False)
                blink = not blink
                widgets["_blink"] = blink
                if blink:
                    widgets["frame"].configure(bg="#ff4444")
                else:
                    # lighter red to create blink effect
                    widgets["frame"].configure(bg="#ffdddd")
            else:
                # restore default
                try:
                    widgets["frame"].configure(bg=widgets.get("default_bg", None))
                    widgets["_blink"] = False
                except Exception:
                    pass

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
        self.save_now()

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
        # write current usage data to CSV
        try:
            path = f"lanhouse_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(path, 'w', newline='') as csvfile:
                w = csv.writer(csvfile)
                w.writerow(["PC", "User", "Elapsed (s)", "Elapsed (H:M:S)", "Hours Remaining (h)", "Running", "Charge ($)"])
                rate = self.data.get("hourly_rate", 5.0)
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
            self.save_now()

        tk.Button(dlg, text="Rename", command=do_rename).pack(pady=(0,8))

    def save_now(self):
        # ensure running timers have start_time stored and elapsed preserved
        save_data(self.data)
        messagebox.showinfo("Saved", "Data saved.")

    def reset_all(self):
        if not messagebox.askyesno("Reset", "Reset all timers and data?"):
            return
        for pc in self.computers:
            self.data["computers"][pc] = {"running": False, "start_time": None, "elapsed": 0.0}
        self.save_now()

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


def main():
    app = LanHouseManager()
    app.mainloop()


if __name__ == "__main__":
    main()
