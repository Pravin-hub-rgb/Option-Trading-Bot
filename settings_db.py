import json
import os
import shutil

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "market_start": {"value": "09:15", "type": "time", "label": "Market Start", "category": "timing"},
    "market_end": {"value": "15:30", "type": "time", "label": "Market End", "category": "timing"},
    "strategy_start": {"value": "09:15", "type": "time", "label": "Strategy Start", "category": "timing"},
    "entry_window_end": {"value": "15:00", "type": "time", "label": "Entry Window End", "category": "timing"},
    "market_open_delay": {"value": "40", "type": "number", "label": "Market Open Delay (s)", "category": "timing"},
    "max_wait_candles": {"value": "2", "type": "number", "label": "Max Wait Candles", "category": "strategy"},
    "allow_reference_shift": {"value": "true", "type": "boolean", "label": "Allow Reference Shift", "category": "strategy"},
    "initial_sl_points": {"value": "5", "type": "number", "label": "Initial SL (points)", "category": "risk"},
    "trailing_trigger": {"value": "5", "type": "number", "label": "Trailing Trigger (points)", "category": "risk"},
    "trailing_step": {"value": "5", "type": "number", "label": "Trailing Step (points)", "category": "risk"},
    "stop_after_first_win": {"value": "true", "type": "boolean", "label": "Stop After First Win", "category": "limits"},
    "max_trades_per_side": {"value": "2", "type": "number", "label": "Max Trades Per Side", "category": "limits"},
    "log_level": {"value": "VERBOSE", "type": "select", "options": "VERBOSE,MINIMAL", "label": "Log Level", "category": "logging"},
    "log_every_tick": {"value": "false", "type": "boolean", "label": "Log Every Tick", "category": "logging"},
    "log_candle_updates": {"value": "true", "type": "boolean", "label": "Log Candle Updates", "category": "logging"},
    "access_token": {"value": "", "type": "password", "label": "Upstox Access Token", "category": "credentials"},
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        for key, default in DEFAULT_SETTINGS.items():
            if key not in data:
                data[key] = dict(default)
        return data
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULT_SETTINGS)

def save_settings(settings):
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(settings, f, indent=2)
    shutil.move(tmp, SETTINGS_FILE)

def get_setting(key):
    settings = load_settings()
    entry = settings.get(key)
    if not entry:
        return None
    return entry["value"]

def save_setting(key, value):
    settings = load_settings()
    if key in settings:
        settings[key]["value"] = value
        save_settings(settings)
        return True
    return False

def reset_settings():
    save_settings(DEFAULT_SETTINGS)
    return dict(DEFAULT_SETTINGS)

def get_settings_meta():
    return [{"key": k, **v} for k, v in load_settings().items()]

def apply_settings_to_config():
    settings = load_settings()
    overrides = {}
    for key, entry in settings.items():
        val = entry["value"]
        if entry.get("type") == "boolean":
            val = val.lower() == "true"
        elif entry.get("type") == "number":
            try:
                val = int(val)
            except ValueError:
                pass
        overrides[key] = val
    return overrides
