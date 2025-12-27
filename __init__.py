import random
import math
import json
import os
import requests
import uuid
import threading
import aqt 
from aqt import mw, gui_hooks
from aqt.qt import *
from aqt.utils import showInfo, tooltip, getOnlyText

# ==========================================
# 1. CONFIGURATION
# ==========================================

# --- SETTINGS ---
DEBUG_MODE = True  
SERVER_URL = "https://jerryshen100.pythonanywhere.com"

# --- GAME CONSTANTS ---
BASE_MAP_SIZE = 350       
LEVEL_GROWTH = 50         
STARTING_RADIUS = 0 
VISION_RANGE_DEFAULT = 2  

# --- Visual Style ---
COLOR_BG_CANVAS = "#f7f9fc"  
COLOR_BG_WIDGET = "#ffffff"
COLOR_HEX_BORDER = "#dfe6e9" 
COLOR_TEXT_MAIN = "#2d3436"
COLOR_PRIMARY = "#0984e3"
COLOR_ACCENT = "#f1c40f" # Sunflower Yellow
COLOR_CANCEL = "#e17055" # Soft Red for Cancel button

PALETTE = {
    "plains":   "#8bc34a", 
    "hills":    "#cddc39", 
    "forest":   "#2d5a27", 
    "dunes":    "#ffd54f", 
    "swamp":    "#5d4037", 
    "lake":     "#2980b9", 
    "scrub":    "#8c9e5e", 
    "ruins":    "#8e44ad", # Changed to purple for distinction
    "tundra":   "#b2ebf2", 
    "wasteland":"#2d3436", 
    "volcanic": "#d84315", 
    "mountain": "#95a5a6", 
    "wall":     "#2d3436", 
    "start":    "#55efc4", 
    "exit":     "#f1c40f", 
    "trap":     "#e74c3c",
    "key":      "#00d2d3", 
    "p0_hex":   "#0984e3", 
    "p1_hex":   "#9b59b6", 
}

TERRAIN_CONFIG = {
    "plains": {"cost": 20, "color": PALETTE["plains"], "name": "Plains", "desc": "Standard open terrain. Low movement cost with clear visibility."},
    "hills": {"cost": 40, "color": PALETTE["hills"], "name": "Hills", "desc": "Uneven ground. Slightly higher coin cost to traverse."},
    "forest": {"cost": 50, "color": PALETTE["forest"], "name": "Forest", "desc": "Dense canopy. Limits visibility over forest tiles and limits visibility to 1 while within."},
    "dunes": {"cost": 40, "color": PALETTE["dunes"], "name": "Dunes", "desc": "Shifting sands. Causes Blindness: You forget your map. 300 Reviews to clear the sand from your eyes."},
    "swamp": {"cost": 50, "color": PALETTE["swamp"], "name": "Bog", "desc": "Treacherous mud. 20% chance to sink and lose 50% of your current coins."},
    "lake": {"cost": 0, "color": PALETTE["lake"], "name": "Lake", "desc": "Deep water. Impassable barrier that must be navigated around."}, 
    "scrub": {"cost": 60, "color": PALETTE["scrub"], "name": "Scrub", "desc": "Dense, thorny brush. High movement cost that can be decreased by doing reviews quickly."},
    "ruins": {"cost": 0, "color": PALETTE["ruins"], "name": "Ancient Ruins", "desc": "Mysterious structures. Study 500 cards here to reveal the location of a Key or the Artifact."},
    "mountain": {"cost": 0, "color": PALETTE["mountain"], "name": "Mountain", "desc": "Blocks normal movement. Spend 100 reviews to Climb for massive vision."},
    "tundra": {"cost": 100, "color": PALETTE["tundra"], "name": "Tundra", "desc": "Freezing winds. 33% chance to Freeze (Debt: 150 Speedy Reviews < 5s/card)."},
    "wasteland":{"cost": 100, "color": PALETTE["wasteland"], "name": "Jagged Peaks", "desc": "Unstable cliffs. 33% chance of Rockslide (Debt: Achieve 100 Consistent High Quality Reviews)."},
    "volcanic": {"cost": 100, "color": PALETTE["volcanic"], "name": "Volcanic", "desc": "Active magma. 33% chance to Burn (Debt: 200 Reviews)."},
    "trap": {"cost": 0, "color": PALETTE["trap"], "name": "Trap", "desc": "Hidden mine. Stepping on an enemy trap triggers a 100 Review Lockdown."},
    "wall": {"cost": 0, "color": PALETTE["wall"], "name": "Bedrock", "desc": "Indestructible solid rock barrier."},
    "start": {"cost": 0, "color": PALETTE["start"], "name": "Base", "desc": "Your safe zone. Use the 'Recall' item to return here instantly."},
    "exit": {"cost": 0, "color": PALETTE["exit"], "name": "Artifact", "desc": "The Objective. The first player to reach this Golden Tile wins the match."},
    "key": {"cost": 0, "color": PALETTE["key"], "name": "Key", "desc": "Ancient Mechanism. Required to unlock the Artifact."}
}

STYLE_BUTTON_CSS = f"""
    QPushButton {{ 
        background-color: {COLOR_PRIMARY}; 
        color: white; 
        border-radius: 8px; 
        padding: 10px 16px; 
        font-weight: bold; 
        font-size: 13px; 
        border: none; 
    }}
    QPushButton:hover {{ background-color: #74b9ff; }}
    QPushButton:pressed {{ background-color: #065a9e; }}
    QPushButton:disabled {{ background-color: #b2bec3; }}
"""

STYLE_INPUT_CSS = """
    QLineEdit, QComboBox {
        background-color: #f7f9fc;
        border: 1px solid #dfe6e9;
        border-radius: 6px;
        padding: 8px;
        font-size: 13px;
        color: #2d3436;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #0984e3;
        background-color: #ffffff;
    }
    QLabel { color: #2d3436; }
"""

# ==========================================
# 2. LOGIC
# ==========================================

class StatEngine:
    @staticmethod
    def get_today_stats():
        return {"volume": 100, "retention": 85.0, "new_count": 10, "avg_time": 5.0}

class Tile:
    def __init__(self, q, r):
        self.q = q; self.r = r; self.type = "plains"; self.cost = 20
        self.visible = False; self.visited = False; self.is_locked = False
        self.trap_owner = None; self.variant = random.randint(0, 100)
        self.trap_group_id = None 

    def to_dict(self):
        d = {
            "q": self.q, "r": self.r, "type": self.type, "cost": self.cost,
            "visible": self.visible, "visited": self.visited,
            "is_locked": self.is_locked, "trap_owner": self.trap_owner,
            "variant": self.variant
        }
        if self.trap_group_id: d["trap_group_id"] = self.trap_group_id
        return d

    @classmethod
    def from_dict(cls, d):
        t = cls(d["q"], d["r"]); t.type = d["type"]; t.cost = d["cost"]
        t.visible = d.get("visible", False)
        t.visited = d.get("visited", False)
        t.is_locked = d.get("is_locked", False)
        t.trap_owner = d.get("trap_owner")
        t.variant = d.get("variant", 0)
        t.trap_group_id = d.get("trap_group_id")
        return t



class WorldMap:
    def __init__(self, radius, level=1, generate=True, seed=None):
        self.radius = 0; self.level = level; self.tiles = {}; self.start_pos = (0, 0); self.exit_pos = None
        self.seed = seed if seed else random.randint(100000, 999999)
        if generate: self.generate_world()
    def to_dict(self):
        return {"radius": self.radius, "level": self.level, "start_pos": list(self.start_pos), "exit_pos": list(self.exit_pos), "seed": self.seed, "tiles": {f"{c[0]},{c[1]}": t.to_dict() for c, t in self.tiles.items()}}
    @classmethod
    def from_dict(cls, d):
        w = cls(0, d["level"], False); w.radius = d["radius"]; w.start_pos = tuple(d["start_pos"]); w.exit_pos = tuple(d["exit_pos"]); w.seed = d.get("seed")
        for k, v in d["tiles"].items(): q, r = map(int, k.split(',')); w.tiles[(q, r)] = Tile.from_dict(v)
        return w
    def get_neighbors(self, q, r): return [(q+dq, r+dr) for dq, dr in [(1,0),(1,-1),(0,-1),(-1,0),(-1,1),(0,1)]]
    def hex_dist(self, a, b): return (abs(a[0]-b[0]) + abs(a[1]-b[1]) + abs(a[0]+a[1]-b[0]-b[1])) / 2
    
    def generate_world(self):
        random.seed(self.seed) 
        target_size = BASE_MAP_SIZE + (self.level * LEVEL_GROWTH)
        self.tiles = {}; self.tiles[(0,0)] = Tile(0,0)
        current_layer = [(0,0)]
        while len(self.tiles) < target_size:
            next_layer = set()
            for curr in current_layer:
                for n in self.get_neighbors(*curr):
                    if n not in self.tiles: next_layer.add(n)
            if not next_layer: break
            candidates = list(next_layer); random.shuffle(candidates)
            take_count = max(1, int(len(candidates) * 0.85)) if len(self.tiles) > 20 else len(candidates)
            added = []
            for i in range(min(take_count, target_size - len(self.tiles))):
                c = candidates[i]; self.tiles[c] = Tile(c[0], c[1]); added.append(c)
            current_layer = added

        keys = list(self.tiles.keys())
        for _ in range(3): 
            new_tiles = {}
            for c in keys:
                for n in self.get_neighbors(*c):
                    if n not in self.tiles and n not in new_tiles:
                        neighbor_count = sum(1 for nn in self.get_neighbors(*n) if nn in self.tiles)
                        if neighbor_count >= 4: new_tiles[n] = Tile(n[0], n[1])
            if not new_tiles: break
            self.tiles.update(new_tiles); keys.extend(new_tiles.keys())

        max_dist = 0
        for c in self.tiles:
            d = self.hex_dist((0,0), c)
            if d > max_dist: max_dist = d
        self.radius = int(max_dist) + 1

        rot = random.uniform(0, 2*math.pi)
        for c, t in self.tiles.items():
            dist = self.hex_dist((0,0), c)
            if dist <= 3: t.type = random.choice(["plains", "plains", "hills"])
            elif dist <= (self.radius * 0.4):
                if random.random() > 0.94: t.type = "mountain"
                else: t.type = random.choice(["hills", "plains", "forest"]) 
            else:
                angle = math.atan2(math.sqrt(3)/2*c[0] + math.sqrt(3)*c[1], 3/2*c[0]) + rot
                if angle < 0: angle += 2*math.pi
                sector = int((angle / (2*math.pi)) * 3) % 3
                moisture = math.sin((c[0]) * 0.25) + math.cos((c[1]) * 0.25)
                if dist > (self.radius * 0.55):
                    if moisture > 0: t.type = random.choice(["tundra", "tundra", "wasteland"])
                    else: t.type = random.choice(["volcanic", "wasteland", "mountain"])
                else:
                    if moisture > 0.8: t.type = "lake" 
                    elif moisture > 0.2: t.type = random.choice(["swamp", "swamp", "swamp", "plains"])
                    elif moisture < -0.5: t.type = random.choice(["dunes", "scrub", "dunes"])
                    else: t.type = random.choice(["plains", "hills", "scrub", "mountain"])
            t.cost = TERRAIN_CONFIG[t.type]["cost"]
        
        # --- RUIN GENERATION (Update) ---
        # Very rare, middle distance (4-9), isolated
        ruin_locs = []
        for c, t in self.tiles.items():
            dist = self.hex_dist((0,0), c)
            
            # 1. Distance Check: Middle Band
            if 4 <= dist <= 9 and t.type not in ["lake", "mountain", "start", "exit"]:
                # 2. Rarity Check: 1.5% chance (0.015)
                if random.random() < 0.015: 
                    
                    # 3. Isolation Check: Ensure no other ruins are neighbors
                    # We check distance to existing ruins. If dist <= 2, they are neighbors/too close.
                    too_close = False
                    for r_loc in ruin_locs:
                        if self.hex_dist(c, r_loc) <= 4: 
                             too_close = True
                             break
                    
                    if not too_close:
                        t.type = "ruins"
                        t.cost = 0 # Studying is free (currency-wise)
                        ruin_locs.append(c)

        self.start_pos = (0,0); self.tiles[self.start_pos].type = "start"; self.tiles[self.start_pos].cost = 0
        all_coords = list(self.tiles.keys())
        hard_tiles = [c for c in all_coords if self.tiles[c].type in ["tundra", "wasteland", "volcanic"] and self.hex_dist((0,0), c) > self.radius * 0.6]
        self.exit_pos = random.choice(hard_tiles) if hard_tiles else max(all_coords, key=lambda c: self.hex_dist((0,0), c))
        
        self.tiles[self.exit_pos].type = "exit"
        self.tiles[self.exit_pos].cost = 0
        
        self.generate_forest_clusters(); self.generate_lakes(); self.generate_keys()

    def generate_forest_clusters(self):
        valid = [c for c in self.tiles.keys() if self.hex_dist((0,0), c) > 2 and c != self.start_pos and c != self.exit_pos and self.tiles[c].type not in ["mountain", "volcanic", "tundra", "wasteland", "ruins"]]
        count = random.randint(4, 7) 
        for _ in range(count):
            if not valid: break
            seed = random.choice(valid); blob_size = random.randint(6, 12); cluster = {seed}; attempts = 0
            while len(cluster) < blob_size and attempts < 30:
                attempts += 1; source = random.choice(list(cluster)); neighbors = self.get_neighbors(*source); random.shuffle(neighbors)
                for n in neighbors:
                    if n in self.tiles and n not in cluster and n != self.start_pos and n != self.exit_pos and self.tiles[n].type in ["plains", "hills", "scrub"]:
                        cluster.add(n); break
            for c in cluster:
                self.tiles[c].type = "forest"; self.tiles[c].cost = TERRAIN_CONFIG["forest"]["cost"]
                if c in valid: valid.remove(c)

    def generate_lakes(self):
        valid = [c for c in self.tiles.keys() if self.hex_dist((0,0), c) < self.radius - 1 and c != self.start_pos and c != self.exit_pos and self.tiles[c].type != "ruins"]
        count = random.randint(3, 5)
        for _ in range(count):
            if not valid: break
            seed = random.choice(valid); blob_size = random.randint(4, 9); lake_cluster = {seed}; attempts = 0
            while len(lake_cluster) < blob_size and attempts < 20:
                attempts += 1; source = random.choice(list(lake_cluster)); neighbors = self.get_neighbors(*source); random.shuffle(neighbors)
                for n in neighbors:
                    if n in self.tiles and n not in lake_cluster and n != self.start_pos and n != self.exit_pos:
                        lake_cluster.add(n); break 
            for c in lake_cluster:
                self.tiles[c].type = "lake"; self.tiles[c].cost = 0
                if c in valid: valid.remove(c)

    def generate_keys(self):
        candidates = []
        min_dist_from_exit = self.radius * 0.55
        
        valid_coords = [c for c in self.tiles.keys() if c != self.start_pos and c != self.exit_pos and self.tiles[c].type not in ["wall", "lake", "ruins"]]
        
        for c in valid_coords:
            if self.hex_dist(c, self.exit_pos) > min_dist_from_exit:
                candidates.append(c)
        
        if not candidates: candidates = valid_coords 

        key1 = random.choice(candidates)
        self.tiles[key1].type = "key"
        self.tiles[key1].cost = 0
        
        candidates_for_2 = [c for c in candidates if c != key1 and self.hex_dist(c, key1) > (self.radius * 0.4)]
        if not candidates_for_2: candidates_for_2 = [c for c in candidates if c != key1] 
        
        if candidates_for_2:
            key2 = random.choice(candidates_for_2)
            self.tiles[key2].type = "key"
            self.tiles[key2].cost = 0

# ==========================================
# 3. FILE I/O & ID MANAGEMENT
# ==========================================

def get_save_path(): 
    profile_name = mw.pm.name
    safe_name = "".join([c for c in profile_name if c.isalnum()])
    filename = f"lumina_save_{safe_name}.json"
    return os.path.join(os.path.dirname(__file__), filename)

def load_game_data():
    path = get_save_path()
    try: 
        data = json.load(open(path, "r"))
        if "uid" not in data: return None
        return data
    except: return None

def save_game_data(data):
    path = get_save_path()
    try: json.dump(data, open(path, "w"), indent=2)
    except Exception as e: print(f"Realm Save Error: {e}")

def get_uid():
    d = load_game_data()
    if not d or "uid" not in d:
        u = str(uuid.uuid4())
        if not d: d = {"username": f"Explorer {u[:4]}", "category": "Other"}
        d["uid"] = u
        save_game_data(d)
        return u
    return d["uid"]

def get_all_traps():
    traps = {} 
    return traps

def update_currency(amt):
    d = load_game_data()
    if not d: return
    if "world" not in d: return
    d["currency"] = d.get("currency", 0) + amt
    save_game_data(d)
    return d["currency"]

def generate_pills_html(d):
    pills = ""
    def make_pill(icon, text, bg):
        return (f"""<div style='background:{bg}; color:white; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:800; margin-left:6px; display:inline-flex; align-items:center; box-shadow:0 1px 3px rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.2); font-family:sans-serif;'>{icon} {text}</div>""")
    
    if d.get("wager_active"): pills += make_pill("🎲", f"{d.get('wager_progress',0)}/200", "#9b59b6")
    if d.get("ruin_active"): pills += make_pill("🏛", f"{d.get('ruin_progress',0)}/500", "#8e44ad")
    if d.get("freeze_debt", 0) > 0: pills += make_pill("❄", f"{d['freeze_debt']}", "#0984e3")
    if d.get("trap_debt", 0) > 0: pills += make_pill("⚠", f"{d['trap_debt']}", "#d63031")
    if d.get("rock_debt", 0) > 0: pills += make_pill("⛰", f"{d['rock_debt']}", "#2d3436")
    if d.get("burn_debt", 0) > 0: pills += make_pill("🔥", f"{d['burn_debt']}", "#d35400")
    if d.get("climb_debt", 0) > 0: pills += make_pill("▲", f"{d['climb_debt']}", "#f1c40f")
    if d.get("disorientation_debt", 0) > 0: pills += make_pill("≋", f"{d['disorientation_debt']}", "#fab1a0")
    return pills

def on_card_answered(reviewer, card, ease):
    d = load_game_data()
    if not d or "world" not in d: return

    # --- 1. CURRENCY ---
    if ease > 1:
        d["currency"] = d.get("currency", 0) + 5

    # --- 2. ARCHIVE / RUIN LOGIC (Multi-Ping Support) ---
    if d.get("ruin_active"):
        d["ruin_progress"] = d.get("ruin_progress", 0) + 1
        
        if d["ruin_progress"] >= 500:
            d["ruin_active"] = False
            d["ruin_progress"] = 0
            
            # Mark Ruin Complete
            curr_loc = d.get("current_ruin_location")
            if curr_loc:
                completed = d.get("completed_ruins", [])
                if curr_loc not in completed: completed.append(curr_loc)
                d["completed_ruins"] = completed
                d["current_ruin_location"] = None

            # Multi-Ping Radar Logic
            tiles_dict = d.get("world", {}).get("tiles", {})
            current_pings = d.get("radar_targets", [])
            possible_pings = []
            
            for k, v in tiles_dict.items():
                # FIX: Use 'visited' to ignore keys we found but walked away from
                if v.get("type") in ["key", "exit"] and not v.get("visited", False):
                    if k not in current_pings: possible_pings.append(k)
            
            if possible_pings:
                new_target = str(random.choice(possible_pings))
                current_pings.append(new_target)
                d["radar_targets"] = current_pings
                tooltip(f"Archive Deciphered! New signal at {new_target}.", period=4000)
            else:
                # If everything is visited/pinged, give a refund or empty message
                tooltip("Archive Deciphered! No unknown signals remain.", period=4000)
        else:
            if d["ruin_progress"] % 50 == 0:
                tooltip(f"Archive Progress: {d['ruin_progress']}/500")

    # --- 3. WAGER LOGIC ---
    if d.get("wager_active", False):
        d["wager_progress"] = d.get("wager_progress", 0) + 1
        if ease > 1: d["wager_correct"] = d.get("wager_correct", 0) + 1
        
        prog = d["wager_progress"]
        if prog >= 200:
            retention = (d["wager_correct"] / 200.0) * 100.0
            if retention >= 90.0:
                d["currency"] += 500 
                tooltip(f"WAGER WON! {retention:.1f}% (+500 Coins)", period=5000)
            else:
                tooltip(f"WAGER LOST. {retention:.1f}%", period=5000)
            d["wager_active"] = False; d["wager_progress"] = 0; d["wager_correct"] = 0

    # --- 4. DEBT REDUCTION (Now clears Flags Immediately) ---
    
    # Freeze (Requires answering quickly < 5s)
    if d.get("freeze_debt", 0) > 0:
        time_ms = reviewer.card.time_taken()
        if time_ms < 5000: 
            d["freeze_debt"] -= 1
            if d["freeze_debt"] <= 0: 
                d["freeze_debt"] = 0
                d["is_frozen"] = False # Clear flag immediately
                tooltip("Thawed! You can move again.")
    
    # Trap
    if d.get("trap_debt", 0) > 0: 
        d["trap_debt"] -= 1
        if d["trap_debt"] <= 0:
            d["trap_debt"] = 0
            d["is_trapped"] = False
            tooltip("Trap disabled.")

    # Climb
    if d.get("climb_debt", 0) > 0: 
        d["climb_debt"] -= 1
        if d["climb_debt"] <= 0:
            d["climb_debt"] = 0
            d["is_climbing"] = False
            tooltip("Summit reached.")

    # Burn
    if d.get("burn_debt", 0) > 0: 
        d["burn_debt"] -= 1
        if d["burn_debt"] <= 0:
            d["burn_debt"] = 0
            d["is_burned"] = False
            tooltip("Flames extinguished.")
    
    # Rockslide (Quality Check)
    if d.get("rock_debt", 0) > 0:
        if ease >= 2: 
            d["rock_debt"] -= 1
            if d["rock_debt"] <= 0: 
                d["rock_debt"] = 0
                d["is_buried"] = False
                tooltip("Dug out! Path is clear.")
        else:
            d["rock_debt"] += 5
            tooltip("Mistake! Rocks slide back (+5)")

    # --- 5. SANDSTONE / DISORIENTATION FIX ---
    if d.get("disorientation_debt", 0) > 0:
        d["disorientation_debt"] -= 1
        
        lost_mem = d.get("lost_memory")
        if lost_mem:
            # Determine how many to restore
            if d["disorientation_debt"] <= 0: 
                count_to_restore = 999999 # Restore ALL
            else: 
                # Proportional restore: if debt is 300 and we have 300 tiles, restore 1 per click.
                # Use length of memory to estimate.
                total_mem = len(lost_mem) if isinstance(lost_mem, list) else len(lost_mem.keys())
                count_to_restore = math.ceil(total_mem / max(1, d["disorientation_debt"]))
                count_to_restore = max(1, count_to_restore)

            # Handle Dict
            if isinstance(lost_mem, dict):
                keys = list(lost_mem.keys())
                world_tiles = d.get("world", {}).get("tiles", {})
                
                for _ in range(min(len(keys), int(count_to_restore))):
                    k = keys.pop(0)
                    state = lost_mem.pop(k)
                    if k in world_tiles:
                        world_tiles[k]["visible"] = state.get("vis", False)
                        world_tiles[k]["visited"] = state.get("vst", False)
                
                d["lost_memory"] = lost_mem
                d["world"]["tiles"] = world_tiles
                
            # Handle List (Legacy)
            elif isinstance(lost_mem, list):
                restored = []
                for _ in range(min(len(lost_mem), int(count_to_restore))):
                    restored.append(lost_mem.pop(0))
                
                world_tiles = d.get("world", {}).get("tiles", {})
                for c_str in restored:
                    if c_str in world_tiles: world_tiles[c_str]["visited"] = True
                
                d["lost_memory"] = lost_mem
                d["world"]["tiles"] = world_tiles

        if d["disorientation_debt"] <= 0: 
            d["disorientation_debt"] = 0
            d["is_disoriented"] = False
            tooltip("Vision fully restored!")

    # -----------------------------------------

    save_game_data(d)

    if mw.reviewer.web:
        new_coins = d.get('currency', 0)
        new_pills = generate_pills_html(d).replace("'", "\\'")
        js = f"""
        var c = document.getElementById('realm-coins');
        if(c) c.innerHTML = '{new_coins}';
        var p = document.getElementById('realm-pills-container');
        if(p) p.innerHTML = '{new_pills}';
        """
        mw.reviewer.web.eval(js)

gui_hooks.reviewer_did_answer_card.append(on_card_answered)

# ==========================================
# 4. NETWORK MANAGER
# ==========================================

class NetworkManager:
    @staticmethod
    def sync_join(uid):
        try:
            r = requests.post(f"{SERVER_URL}/join", json={'uid': uid}, timeout=3)
            if r.status_code == 200: return r.json()
        except: return None
    @staticmethod
    def sync_status(uid):
        try:
            r = requests.post(f"{SERVER_URL}/status", json={'uid': uid}, timeout=3)
            if r.status_code == 200: return r.json()
        except: return None
    @staticmethod
    def send_move(uid, q, r, found):
        def _send():
            try: requests.post(f"{SERVER_URL}/move", json={'uid': uid, 'q': q, 'r': r, 'found': found}, timeout=3)
            except: pass
        threading.Thread(target=_send, daemon=True).start()

from aqt.utils import tooltip  # Ensure this is imported at the top

class NetworkWorker(QObject):
    data_received = pyqtSignal(dict)
    log_message = pyqtSignal(str) 
    opponent_left = pyqtSignal()
    match_result = pyqtSignal(str)
    match_expired = pyqtSignal()
    
    # --- NEW SIGNAL ---
    trap_hit = pyqtSignal() 
    
    def __init__(self, uid): 
        super().__init__()
        self.uid = uid

    def do_status_check(self):
        def _task():
            try:
                r = requests.post(f"{SERVER_URL}/status", json={'uid': self.uid}, timeout=3)
                if r.status_code == 200: 
                    data = r.json()
                    status = data.get('status')
                    
                    if status == 'opponent_left': self.opponent_left.emit()
                    elif status == 'won': self.match_result.emit("won")
                    elif status == 'lost': self.match_result.emit("lost")
                    elif status == 'expired': self.match_expired.emit()        
                    elif status == 'idle': self.opponent_left.emit()

                    self.data_received.emit(data)
            except Exception as e: 
                self.log_message.emit(f"Status Error: {e}")
        threading.Thread(target=_task, daemon=True).start()

    def do_join(self, username, category):
        def _task():
            try:
                payload = {'uid': self.uid, 'username': username, 'category': category}
                r = requests.post(f"{SERVER_URL}/join", json=payload, timeout=3)
                if r.status_code == 200: self.data_received.emit(r.json())
            except Exception as e: self.log_message.emit(f"Join Error: {e}")
        threading.Thread(target=_task, daemon=True).start()

    def do_leave(self):
        def _task():
            try: requests.post(f"{SERVER_URL}/leave", json={'uid': self.uid}, timeout=2)
            except: pass
        threading.Thread(target=_task, daemon=True).start()

    def do_send_move(self, q, r, found):
        def _task():
            try: 
                res = requests.post(f"{SERVER_URL}/move", json={'uid': self.uid, 'q': q, 'r': r, 'found': found}, timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    
                    # --- TRAP DETECTION ---
                    if data.get("status") == "trapped":
                        self.trap_hit.emit()
                    elif data.get("status") == "game_over":
                        self.match_result.emit("lost")
            except: pass
        threading.Thread(target=_task, daemon=True).start()

    # --- NEW FUNCTION ---
    def do_place_trap(self, q, r):
        def _task():
            try: requests.post(f"{SERVER_URL}/place_trap", json={'uid': self.uid, 'q': q, 'r': r}, timeout=2)
            except: pass
        threading.Thread(target=_task, daemon=True).start()
    # Inside class NetworkWorker:

    
    def do_clear_trap(self, q, r):
        """
        Tells the server to remove the trap at q,r because the debt has been paid.
        """
        def _task():
            try: 
                # We assume the server has a /clear_trap endpoint
                requests.post(f"{SERVER_URL}/clear_trap", json={'uid': self.uid, 'q': q, 'r': r}, timeout=2)
            except: pass
        threading.Thread(target=_task, daemon=True).start()

# ==========================================
# 5. UI COMPONENTS
# ==========================================

class ModernAlert(QDialog):
    def __init__(self, parent, title, message, color="#e74c3c"):
        super().__init__(parent); self.setWindowTitle(title); self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.resize(300, 180)
        layout = QVBoxLayout(self); frame = QFrame(); frame.setStyleSheet(f"background-color: rgba(255, 255, 255, 0.95); border: 2px solid {color}; border-radius: 15px;"); fl = QVBoxLayout(frame)
        lbl_title = QLabel(title.upper()); lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl_title.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: 900; border: none;")
        lbl_msg = QLabel(message); lbl_msg.setWordWrap(True); lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl_msg.setStyleSheet("color: #2d3436; font-size: 13px; margin: 10px; border: none;")
        btn = QPushButton("OK"); btn.setStyleSheet(f"background-color: {color}; color: white; border-radius: 8px; padding: 6px; border:none;"); btn.clicked.connect(self.accept)
        fl.addWidget(lbl_title); fl.addWidget(lbl_msg); fl.addWidget(btn); layout.addWidget(frame)

class TutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tutorial")
        self.resize(750, 600)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLOR_BG_WIDGET}; }}
            QTabWidget::pane {{ border: 1px solid {COLOR_HEX_BORDER}; border-radius: 8px; background: white; }}
            QTabBar::tab {{
                background: {COLOR_BG_CANVAS};
                color: {COLOR_TEXT_MAIN};
                padding: 10px 24px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            QTabBar::tab:selected {{
                background: white;
                color: {COLOR_PRIMARY};
                border-bottom: 2px solid {COLOR_PRIMARY};
            }}
            QLabel {{ color: {COLOR_TEXT_MAIN}; font-size: 13px; line-height: 1.5; }}
            h2 {{ color: {COLOR_PRIMARY}; font-weight: 900; font-size: 18px; margin-bottom: 15px; letter-spacing: 0.5px; }}
            h3 {{ color: {COLOR_TEXT_MAIN}; font-weight: 800; font-size: 14px; margin-top: 20px; margin-bottom: 5px; }}
            .tile-box {{ 
                background: #f7f9fc; 
                border-left: 4px solid {COLOR_HEX_BORDER}; 
                padding: 12px; 
                margin-bottom: 8px; 
                border-radius: 4px;
            }}
            .key-term {{ font-weight: bold; color: {COLOR_PRIMARY}; }}
            .cost-tag {{ 
                background: #dfe6e9; color: #2d3436; 
                padding: 2px 6px; border-radius: 4px; 
                font-size: 11px; font-weight: bold; 
                margin-left: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # --- HEADER ---
        header = QLabel("TUTORIAL")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 26px; font-weight: 900; color: #2d3436; margin-bottom: 20px; letter-spacing: 2px;")
        layout.addWidget(header)

        # --- TABS ---
        tabs = QTabWidget()
        tabs.addTab(self.create_objective_tab(), "Objective")
        tabs.addTab(self.create_controls_tab(), "Controls")
        tabs.addTab(self.create_map_tab(), "The Map")
        tabs.addTab(self.create_shop_tab(), "Shop")
        
        layout.addWidget(tabs)

        # --- FOOTER ---
        btn = QPushButton("CLOSE")
        btn.setFixedWidth(120)
        btn.setStyleSheet(STYLE_BUTTON_CSS)
        btn.clicked.connect(self.close)
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        h_btn.addStretch()
        layout.addLayout(h_btn)

    def create_scrollable_tab(self, content_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content_widget)
        return scroll

    def create_objective_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(25); l.setContentsMargins(35, 30, 35, 30)
        
        # --- 1. GLOBAL ARENA ---
        l.addWidget(QLabel("<h2>GLOBAL ARENA</h2>"))
        
        comp_text = QLabel(
            "Compete against a global community ranging from medical and law students "
            "to language enthusiasts and everyday learners."
        )
        comp_text.setWordWrap(True)
        comp_text.setStyleSheet(f"font-size: 13px; color: {COLOR_TEXT_MAIN}; line-height: 1.5;")
        l.addWidget(comp_text)

        # --- 2. THE GOAL ---
        l.addWidget(QLabel("<h2>THE GOAL</h2>"))
        
        goal_text = QLabel(
            "Race your opponent through the fog to secure the <span style='color:#f1c40f; font-weight:bold;'>Artifact</span>."
        )
        goal_text.setWordWrap(True)
        goal_text.setStyleSheet(f"font-size: 14px; color: {COLOR_TEXT_MAIN}; font-weight:500;")
        l.addWidget(goal_text)
        
        # --- 3. GAME RULES (Clean List, No Emojis) ---
        rules_layout = QVBoxLayout(); rules_layout.setSpacing(12)
        
        def rule_row(header, text, color):
            lbl = QLabel(f"<span style='color:{color}; font-weight:bold;'>{header.upper()}</span> &nbsp; {text}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size:13px; color:#2d3436; line-height:1.4;")
            rules_layout.addWidget(lbl)

        rule_row("Hidden Keys", "Two keys exist on the map. You must find at least one to break the seal.", "#00d2d3")
        rule_row("The Artifact", "One Golden Artifact is hidden in the distance. The first player to step on it wins.", "#f1c40f")
        rule_row("Inactivity", "If you do not make a move for 7 consecutive days, the match ends automatically.", "#e74c3c")
        
        l.addLayout(rules_layout)

        # --- 4. MATCHMAKING & ETIQUETTE ---
        l.addWidget(QLabel("<h2>MATCHMAKING</h2>"))
        
        mm_text = QLabel(
            "<b>Queue System:</b> If no opponent is immediately available, you will be placed in a background queue. "
            "You can continue studying normally while waiting for a match.<br><br>"
            "<b>Usernames:</b> Please use polite and appropriate usernames. Offensive names may result in a ban."
        )
        mm_text.setWordWrap(True)
        mm_text.setStyleSheet(f"font-size: 13px; color: {COLOR_TEXT_MAIN}; line-height: 1.5;")
        l.addWidget(mm_text)

        # --- 5. DIVIDER ---
        l.addSpacing(10)
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #ecf0f1; background-color: #ecf0f1; height: 1px; border:none;")
        l.addWidget(line)

        # --- 6. TIME ESTIMATE ---
        time_layout = QHBoxLayout()
        
        lbl_time = QLabel("ESTIMATED GAME LENGTH")
        lbl_time.setStyleSheet("font-weight:bold; color:#636e72; font-size:12px;")
        
        val_time = QLabel("2 - 4 Days")
        val_time.setStyleSheet(f"font-weight:bold; color:{COLOR_PRIMARY}; font-size:12px;")
        
        sub_time = QLabel("(Based on 500 reviews/day)")
        sub_time.setStyleSheet("color:#b2bec3; font-size:11px;")
        
        time_layout.addWidget(lbl_time)
        time_layout.addWidget(val_time)
        time_layout.addWidget(sub_time)
        time_layout.addStretch()
        
        l.addLayout(time_layout)
        l.addStretch()
        
        return self.create_scrollable_tab(w)

    def create_controls_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(15); l.setContentsMargins(20, 20, 20, 20)
        
        l.addWidget(QLabel("<h2>CURRENCY & HUD</h2>"))
        
        l.addWidget(QLabel(
            "Your Anki reviews are your fuel. Correct answers earn <b>Realm Coins</b> which are used for movement and items."
        ))
        
        # HUD Description Grid
        grid = QGridLayout()
        grid.setSpacing(10)
        
        def hud_item(row, label, desc):
            l1 = QLabel(label); l1.setStyleSheet("font-weight:bold; color:#636e72;")
            l2 = QLabel(desc); l2.setStyleSheet("color:#2d3436;")
            grid.addWidget(l1, row, 0); grid.addWidget(l2, row, 1)

        hud_item(0, "COINS", "+5 per review. Used to move or buy items.")
        hud_item(1, "DIST", "Signal bars indicating distance to the Artifact.")
        hud_item(2, "KEY SLOT", "Shows if you have found the required Key.")
        hud_item(3, "STATUS", "Active effects (Freeze, Burn, etc.) appear as pills at the bottom.")
        
        l.addLayout(grid)
        l.addWidget(QLabel("<hr style='border:none; border-top:1px solid #dfe6e9; margin:10px 0;'>"))

        l.addWidget(QLabel("<h2>MOVEMENT</h2>"))
        l.addWidget(QLabel(
            "Click adjacent hexagonal tiles to move. Different terrain types have different costs.<br>"
            "If you cannot afford a move, you must do more reviews."
        ))

        l.addStretch()
        return self.create_scrollable_tab(w)

    def create_map_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(8); l.setContentsMargins(20, 20, 20, 20)
        
        l.addWidget(QLabel("<h2>TERRAIN & BIOMES</h2>"))
        l.addWidget(QLabel("The world is procedurally generated. Use terrain to your advantage."))

        # Modern Tile Row Helper
        def tile_row(name, cost, color, desc):
            row = QFrame(); row.setProperty("class", "tile-box"); row.setStyleSheet(f"border-left-color: {color};")
            rl = QVBoxLayout(row); rl.setSpacing(4); rl.setContentsMargins(10, 8, 10, 8)
            
            top = QHBoxLayout()
            lbl_name = QLabel(name.upper())
            lbl_name.setStyleSheet(f"font-weight:800; color: {color}; font-size:12px;")
            
            lbl_cost = QLabel(f"${cost}" if cost > 0 else "FREE")
            lbl_cost.setProperty("class", "cost-tag")
            
            top.addWidget(lbl_name); top.addWidget(lbl_cost); top.addStretch()
            
            lbl_desc = QLabel(desc)
            lbl_desc.setStyleSheet("color: #636e72; font-size: 12px;")
            
            rl.addLayout(top); rl.addWidget(lbl_desc)
            return row

        l.addWidget(QLabel("<h3>STANDARD</h3>"))
        l.addWidget(tile_row("Plains", 20, PALETTE["plains"], "Standard open terrain."))
        l.addWidget(tile_row("Hills", 40, PALETTE["hills"], "Uneven ground. Slightly higher movement cost."))
        l.addWidget(tile_row("Forest", 50, PALETTE["forest"], "Dense canopy. Reduces vision range to 1."))

        l.addWidget(QLabel("<h3>HAZARDS</h3>"))
        l.addWidget(tile_row("Tundra", 100, PALETTE["tundra"], "Freezing winds. 33% chance to Freeze (Debt: 150 Speedy Reviews <5s)."))
        l.addWidget(tile_row("Volcanic", 100, PALETTE["volcanic"], "Magma flows. 33% chance to Burn (Debt: 200 Reviews)."))
        l.addWidget(tile_row("Dunes", 40, PALETTE["dunes"], "Sandstorms. Causes Blindness (Debt: 300 Reviews)."))
        l.addWidget(tile_row("Wasteland", 100, PALETTE["wasteland"], "Unstable cliffs. 33% chance of Rockslide (Debt: 100 High Quality Reviews)."))
        l.addWidget(tile_row("Swamp", 50, PALETTE["swamp"], "Bog. 20% chance to sink and lose 50% of coins."))

        l.addWidget(QLabel("<h3>SPECIAL</h3>"))
        l.addWidget(tile_row("Mountain", 0, PALETTE["mountain"], "Impassable. Climb (100 Reviews) to gain massive vision."))
        l.addWidget(tile_row("Ruins", 0, PALETTE["ruins"], "Study (500 Reviews) to reveal a Key or Artifact location."))

        l.addStretch()
        return self.create_scrollable_tab(w)

    def create_shop_tab(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(15); l.setContentsMargins(20, 20, 20, 20)
        
        l.addWidget(QLabel("<h2>MARKETPLACE</h2>"))
        l.addWidget(QLabel("Purchase tactical items using Realm Coins."))

        def item_row(name, cost, desc):
            f = QFrame(); f.setStyleSheet(f"background: white; border-bottom: 1px solid {COLOR_HEX_BORDER}; padding: 10px 0;")
            fl = QVBoxLayout(f)
            
            top = QHBoxLayout()
            n = QLabel(name); n.setStyleSheet("font-weight:bold; color:#2d3436;")
            c = QLabel(f"${cost}"); c.setStyleSheet(f"color:{COLOR_PRIMARY}; font-weight:bold;")
            top.addWidget(n); top.addStretch(); top.addWidget(c)
            
            d = QLabel(desc); d.setStyleSheet("color:#636e72; font-size:12px; margin-top:4px;")
            d.setWordWrap(True)
            
            fl.addLayout(top); fl.addWidget(d)
            return f

        l.addWidget(item_row("RADAR", 250, "Pings the opponent's location and allows you to track their movement for the rest of the game."))
        l.addWidget(item_row("WAGER", 200, "Bet on your performance. Maintain >90% retention for 200 cards to win 500 Coins."))
        l.addWidget(item_row("RECALL", 600, "Teleport instantly back to the starting base."))
        l.addWidget(item_row("STASIS TRAP", 250, "Deploys a cluster of hidden mines (Center + 6 neighbors). If the opponent steps on one, they are trapped (100 Review Debt)."))

        l.addStretch()
        return self.create_scrollable_tab(w)

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Field Guide")
        self.resize(500, 600)
        self.setStyleSheet(f"background-color: {COLOR_BG_WIDGET}; color: {COLOR_TEXT_MAIN}; {STYLE_BUTTON_CSS}")
        
        ml = QVBoxLayout(self)
        ml.addWidget(QLabel("<h2>BIOME GUIDE</h2>"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        cw = QWidget()
        cl = QVBoxLayout(cw)
        
        for k in ["plains", "hills", "ruins", "forest", "dunes", "swamp", "lake", "scrub", "tundra", "volcanic", "wasteland", "mountain", "trap", "key"]:
            if k not in TERRAIN_CONFIG: continue 
            d = TERRAIN_CONFIG[k]
            
            name = QLabel(f"{d['name']} (${d.get('cost',0)})")
            name.setStyleSheet("font-weight: bold; font-size: 14px;")
            
            sw = QLabel()
            sw.setFixedSize(15,15)
            sw.setStyleSheet(f"background-color: {d['color']}; border: 1px solid #999; border-radius: 2px;")
            
            hr = QHBoxLayout()
            hr.addWidget(sw)
            hr.addWidget(name)
            hr.addStretch()
            
            desc = QLabel(d.get('desc', ''))
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #636e72; padding-left: 20px;")
            
            ec = QWidget()
            el = QVBoxLayout(ec)
            el.addLayout(hr)
            el.addWidget(desc)
            el.setContentsMargins(0, 5, 0, 15)
            cl.addWidget(ec)
            
        cl.addStretch()
        scroll.setWidget(cw)
        ml.addWidget(scroll)
        
        btn = QPushButton("Close")
        btn.clicked.connect(self.close)
        ml.addWidget(btn)

class LobbyWidget(QWidget):
    join_clicked = pyqtSignal(str, str)
    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None, uid="", initial_name="", saved_stats=None):
        super().__init__(parent)
        self.is_searching = False
        
        w, l = 0, 0
        if saved_stats:
             w = saved_stats.get('w', 0)
             l = saved_stats.get('l', 0)
        
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"background-color: {COLOR_BG_CANVAS}; {STYLE_INPUT_CSS} {STYLE_BUTTON_CSS}")

        card = QFrame()
        card.setFixedSize(400, 560)
        card.setStyleSheet(f"QFrame {{ background-color: {COLOR_BG_WIDGET}; border-radius: 16px; border: 1px solid {COLOR_HEX_BORDER}; }}")
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(15)
        card_layout.setContentsMargins(30, 40, 30, 40)

        title_container = QWidget()
        tl = QVBoxLayout(title_container)
        tl.setSpacing(5)
        tl.setContentsMargins(0,0,0,10)
        
        l_title = QLabel("ANKI REALM BATTLE")
        l_title.setStyleSheet(f"font-size: 26px; font-weight: 800; color: #2d3436; letter-spacing: 1px; border:none; background: transparent;")
        l_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        line = QFrame()
        line.setFixedSize(60, 4)
        line.setStyleSheet(f"background-color: {COLOR_ACCENT}; border-radius: 2px; background: {COLOR_ACCENT};")
        
        l_subtitle = QLabel(f"ID: {uid[:6]}")
        l_subtitle.setStyleSheet(f"font-size: 11px; font-weight: 600; color: #b2bec3; letter-spacing: 1px; border:none; background: transparent;")
        l_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tl.addWidget(l_title, alignment=Qt.AlignmentFlag.AlignCenter)
        tl.addWidget(line, alignment=Qt.AlignmentFlag.AlignCenter)
        tl.addWidget(l_subtitle, alignment=Qt.AlignmentFlag.AlignCenter)

        self.l_stats = QLabel(f"{w} WINS  -  {l} LOSSES")
        self.l_stats.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLOR_PRIMARY}; margin-bottom: 20px; border:none;")
        self.l_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)

        input_layout = QVBoxLayout()
        input_layout.setSpacing(10)
        
        lbl_name = QLabel("USERNAME")
        lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #636e72; border:none;")
        self.input_name = QLineEdit(initial_name or f"Explorer {uid[:4]}")
        self.input_name.setMaxLength(12)
        self.input_name.setPlaceholderText("Enter username...")
        
        lbl_cat = QLabel("STUDY FOCUS")
        lbl_cat.setStyleSheet("font-size: 11px; font-weight: bold; color: #636e72; border:none; margin-top: 10px;")
        self.input_cat = QComboBox()
        self.input_cat.addItems([
            "Medical", "Law", "Languages", "Science", "Arts & Humanities", "Computer Science", "General Knowledge", "Other"
        ])

        input_layout.addWidget(lbl_name)
        input_layout.addWidget(self.input_name)
        input_layout.addWidget(lbl_cat)
        input_layout.addWidget(self.input_cat)

        self.status_label = QLabel("READY")
        self.status_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #b2bec3; margin-top: 20px; border:none;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.join_btn = QPushButton("FIND MATCH")
        self.join_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.join_btn.setFixedHeight(45)
        self.join_btn.clicked.connect(self.on_click)
        
        self.help_btn = QPushButton("HOW TO PLAY")
        self.help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_btn.setFixedHeight(35)
        self.help_btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: white; 
                color: {COLOR_ACCENT}; 
                border: 2px solid {COLOR_ACCENT}; 
                border-radius: 8px; 
                font-weight: bold; 
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #fff9e6; }}
        """)
        self.help_btn.clicked.connect(self.show_tutorial)

        card_layout.addWidget(title_container)
        card_layout.addWidget(self.l_stats)
        card_layout.addLayout(input_layout)
        card_layout.addStretch()
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.join_btn)
        card_layout.addWidget(self.help_btn)

        main_layout.addWidget(card)

    def on_click(self): 
        if not self.is_searching:
            self.is_searching = True
            self.join_btn.setText("CANCEL SEARCH")
            self.join_btn.setStyleSheet(f"background-color: {COLOR_CANCEL}; color: white; border-radius: 8px; padding: 10px 16px; font-weight: bold; font-size: 13px; border: none;")
            self.status_label.setStyleSheet("color: #0984e3; font-weight: bold; border:none;")
            self.status_label.setText("CONNECTING...")
            self.join_clicked.emit(self.input_name.text(), self.input_cat.currentText())
        else:
            self.is_searching = False
            self.reset_ui()
            self.cancel_clicked.emit()
        
    def show_tutorial(self):
        TutorialDialog(self).exec()

    def update_stats(self, w, l): 
        self.l_stats.setText(f"{w} WINS  -  {l} LOSSES")

    def set_status(self, msg):
        self.status_label.setText(msg)
        if msg == "SEARCHING...":
            self.is_searching = True
            self.join_btn.setText("CANCEL SEARCH")
            self.join_btn.setStyleSheet(f"background-color: {COLOR_CANCEL}; color: white; border-radius: 8px; padding: 10px 16px; font-weight: bold; font-size: 13px; border: none;")
            self.status_label.setStyleSheet("color: #0984e3; font-weight: bold; border:none;")

    def reset_ui(self): 
        self.is_searching = False
        self.join_btn.setEnabled(True)
        self.join_btn.setText("FIND MATCH")
        self.join_btn.setStyleSheet(f"background-color: {COLOR_PRIMARY}; color: white; border-radius: 8px; padding: 10px 16px; font-weight: bold; font-size: 13px; border: none;")
        self.status_label.setText("READY")
        self.status_label.setStyleSheet("color: #b2bec3; font-weight: 600; border:none;")

    def log(self, msg): 
        pass

class HexMapWidget(QWidget):
    currency_updated = pyqtSignal(int); level_completed = pyqtSignal(); request_close = pyqtSignal(); save_requested = pyqtSignal()
    leave_match_clicked = pyqtSignal(); match_ended_signal = pyqtSignal(str) 

    trap_placed_signal = pyqtSignal(int, int)

    def __init__(self, world, currency, network_worker, parent=None):
        super().__init__(parent)
        self.world = world; self.currency = currency; self.network = network_worker
        self.profile_id = 0 
        
        self.active_traps = set()

        self.player_pos = world.start_pos; self.prev_pos = None; self.hex_r = 24.0
        self.cold_stacks = 0; self.is_frozen = False; self.freeze_debt = 0
        self.is_trapped = False; self.trap_debt = 0; self.is_buried = False; self.rock_debt = 0
        self.is_climbing = False; self.climb_debt = 0; self.is_burned = False; self.burn_debt = 0 
        self.is_disoriented = False; self.disorientation_debt = 0; self.lost_memory = []
        
        # Ruin State
        self.ruin_active = False 
        self.ruin_progress = 0
        self.current_ruin_location = None  # Tracks which tile we are studying
        self.completed_ruins = []          # Tracks tiles we finished
        self.radar_target = None           # Tracks the ping coordinate
        
        self.has_key = False
        self.wager_active = False; self.wager_progress = 0; self.wager_total = 200
        self.opponent_pos = None; self.opponent_visible = False; self.opponent_name = "Unknown"; self.opponent_cat = "Unknown"; self.opponent_stats = {"w":0, "l":0}; self.connection_status = "OFFLINE"
        self.placing_trap = False; self.thermometer_active = 0; self.thermometer_color = "#95a5a6"; self.shared_traps = get_all_traps(); self.match_terminated = False
        self.anim_time = 0; self.anim_timer = QTimer(self); self.anim_timer.timeout.connect(self.animate); self.anim_timer.start(50)
        self.setMouseTracking(True); self.update_fog_of_war(); self.setMinimumSize(400, 400); self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    def animate(self):
        self.anim_time += 0.15; 
        if self.thermometer_active > 0: self.thermometer_active -= 1
        if hasattr(self, 'active_ping') and self.active_ping:
            self.active_ping["timer"] -= 1
            if self.active_ping["timer"] <= 0:
                self.active_ping = None
        self.update()
    def update_grid_metrics(self):
        w = self.width(); h = self.height(); R = self.world.radius
        self.hex_r = min((w * 0.98) / (3.0 * R + 2.0), (h * 0.98) / (math.sqrt(3) * (2.0 * R + 1.0)))
    def update_fog_of_war(self):
        # 1. RESET ACTIVE SIGHT
        # We must turn off 'visible' for the whole map first. 
        # 'Visited' remains True forever, but 'visible' is only for what you see NOW.
        for t in self.world.tiles.values():
            t.visible = False

        # 2. Initialize BFS
        vis = {self.player_pos}
        queue = [(self.player_pos, 0)]
        
        # Current tile is always Bright & Visited
        self.world.tiles[self.player_pos].visible = True
        self.world.tiles[self.player_pos].visited = True
        
        # 3. Determine Vision Range
        limit = 2  # Standard
        current_type = self.world.tiles[self.player_pos].type
        
        # Mountain Bonus: Only Range 5 if debt is PAID
        is_on_summit = (current_type == "mountain" and self.climb_debt == 0)
        
        if is_on_summit:
            limit = 5
        elif current_type == "forest":
            limit = 1

        # 4. Determine Blockers
        blockers = ["wall"]
        if not is_on_summit:
            blockers.append("forest")
            blockers.append("lake")

        # 5. BFS Loop
        while queue:
            curr, dist = queue.pop(0)
            
            if curr != self.player_pos:
                 if self.world.tiles[curr].type in blockers:
                     continue
            
            if dist < limit:
                for n in self.world.get_neighbors(*curr):
                    if n in self.world.tiles and n not in vis:
                        vis.add(n)
                        
                        # Sandstorm Safety
                        new_dist = dist + 1
                        if not self.is_disoriented or new_dist <= 1:
                            self.world.tiles[n].visible = True
                            self.world.tiles[n].visited = True
                            queue.append((n, new_dist))
                        
        self.update()
        
    def get_move_cost(self, tile):
        c = tile.cost
        if tile.type == "scrub" and StatEngine.get_today_stats()['avg_time'] > 0 and StatEngine.get_today_stats()['avg_time'] < 8.0: return 20
        if tile.type == "swamp": return 50
        if tile.type == "ruins": return 0 # Moving into ruins is free, study costs cards
        if tile.type == "tundra": c += (self.cold_stacks * 20)
        return c
    def trigger_thermometer(self):
        if not self.opponent_pos: ModernAlert(self, "RADAR", "Opponent signal lost.", "#95a5a6").exec(); return
        d_me = self.world.hex_dist(self.player_pos, self.world.exit_pos); d_opp = self.world.hex_dist(self.opponent_pos, self.world.exit_pos)
        if d_me < d_opp: self.thermometer_color = "#e74c3c" 
        elif d_me > d_opp: self.thermometer_color = "#3498db" 
        else: self.thermometer_color = "#f1c40f"
        self.thermometer_active = 60; self.update(); ModernAlert(self, "RADAR ACTIVE", "Ping sent. Check player ring color.", self.thermometer_color).exec()
    
    def check_recovery(self):
        updated = False
        
        # Standard Debts
        if self.is_frozen and self.freeze_debt <= 0: self.is_frozen = False; updated = True; tooltip("Thawed out! You can move.")
        
        if self.is_trapped and self.trap_debt <= 0: 
            self.is_trapped = False
            updated = True
            tooltip("Systems rebooted. Area neutralized.")
            
            # Just clean up the visuals. No network call needed.
            # The server already deleted the trap data when you stepped on it.
            if self.player_pos in self.active_traps:
                self.active_traps.remove(self.player_pos)
            
            current_tile = self.world.tiles.get(self.player_pos)
            if current_tile:
                current_tile.trap_owner = None

        if self.is_buried and self.rock_debt <= 0: self.is_buried = False; updated = True; tooltip("Dug out of the rubble.")
        if self.is_burned and self.burn_debt <= 0: self.is_burned = False; updated = True; tooltip("Cooled down!")
        
        # --- FIX: ROBUST RESTORATION ---
        if self.is_disoriented and self.disorientation_debt <= 0: 
            self.is_disoriented = False
            updated = True
            
            if hasattr(self, 'lost_memory') and self.lost_memory:
                
                # Case 1: New Robust Dictionary Memory
                if isinstance(self.lost_memory, dict):
                    for c_str, state in self.lost_memory.items():
                        if "," in c_str:
                            parts = c_str.split(',')
                            q, r = int(parts[0]), int(parts[1])
                            if (q, r) in self.world.tiles:
                                # Restore EXACTLY as it was
                                self.world.tiles[(q, r)].visible = state.get("vis", False)
                                self.world.tiles[(q, r)].visited = state.get("vst", False)

                # Case 2: Old List Memory (Legacy Fallback)
                elif isinstance(self.lost_memory, list):
                    for c_str in self.lost_memory:
                        if "," in c_str:
                            parts = c_str.split(',')
                            q, r = int(parts[0]), int(parts[1])
                            if (q, r) in self.world.tiles:
                                self.world.tiles[(q, r)].visited = True # Best guess
                
                # Clear memory
                self.lost_memory = [] if isinstance(self.lost_memory, list) else {}
            
            tooltip("Vision fully restored!")
            self.update_fog_of_war()
        # -------------------------------

        # Climb Complete
        if self.is_climbing and self.climb_debt <= 0: 
            self.is_climbing = False
            updated = True
            ModernAlert(self, "SUMMIT REACHED", "Visibility increased significantly!", "#f1c40f").exec()
            self.update_fog_of_war() 

        if updated: 
            self.save_requested.emit()
            self.update()
            
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton: return
        
        # --- 1. MOVEMENT LOCK CHECK ---
        # If studying ruins, BLOCK ALL INTERACTION except leaving the match
        if self.ruin_active:
             tooltip(f"Archive Protocol Active: {self.ruin_progress}/500")
             return
        
        # Check other locks
        self.check_recovery()
        if self.is_frozen or self.is_trapped or self.is_buried or self.is_climbing or self.is_burned: 
            tooltip("Immobilized.")
            return
        # -----------------------------

        self.update_grid_metrics()
        clicked = self.pixel_to_hex(e.position().x(), e.position().y())
        
        # Leave Match Button (Top Left)
        if QRect(20, 20, 300, 100).contains(e.position().toPoint()):
             if e.position().x() > 220 and e.position().y() < 60: self.leave_match_clicked.emit(); return

        # Trap Placement Logic
        if self.placing_trap:
            if clicked in self.world.tiles:
                q, r = clicked  # <--- ADD THIS LINE to define q and r
                self.placing_trap = False
                self.trap_placed_signal.emit(q, r) 
                tooltip(f"Mine Cluster requested at {q},{r}")
            return

        # Movement Logic
        if clicked in self.world.get_neighbors(*self.player_pos) and clicked in self.world.tiles:
            tile = self.world.tiles[clicked]
            if tile.type in ["wall", "lake"]: tooltip("Blocked."); return
            
            if tile.type == "mountain":
                if QMessageBox.question(self, "Climb?", "Ascend?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                    self.is_climbing = True; self.climb_debt = 100; self.execute_move(clicked, 0)
                return
            
            # NOTE: Removed the "if tile.type == ruins" block from here 
            # because we moved it into execute_move for smoother handling.
            
            cost = self.get_move_cost(tile)
            if self.currency >= cost: self.execute_move(clicked, cost)
            else: ModernAlert(self, "NO FUNDS", "Go study more.", "#e74c3c").exec()

    def execute_move(self, target, cost):
        # 1. Update State
        self.currency -= cost
        self.player_pos = target
        tile = self.world.tiles[target]

        # ... [Keep Tundra, Wasteland, Volcanic logic] ...
        if tile.type == "tundra" and random.random() < 0.33:
            self.is_frozen = True; self.freeze_debt = 150
            ModernAlert(self, "FROZEN!", "Frozen solid. (150 Speedy Reviews)", "#74b9ff").exec()

        elif tile.type == "wasteland" and random.random() < 0.33:
            self.is_buried = True; self.rock_debt = 100
            ModernAlert(self, "ROCKSLIDE!", "Dug under rubble. (100 Quality Reviews)", "#636e72").exec()

        elif tile.type == "volcanic" and random.random() < 0.33:
            self.is_burned = True; self.burn_debt = 200
            ModernAlert(self, "OVERHEAT!", "Magma burns! (200 Reviews)", "#e74c3c").exec()

        # --- FIX: ROBUST MEMORY SNAPSHOT ---
        elif tile.type == "dunes":
             if not self.is_disoriented:
                 ModernAlert(self, "BLINDED", "Sandstorm! Map obscured.", "#f1c40f").exec()
                 self.is_disoriented = True; self.disorientation_debt = 300
                 
                 # Save EXACT state of every tile
                 snapshot = {}
                 for c, t in self.world.tiles.items():
                     # Save if it has ANY progress (visible or visited), 
                     # but don't hide the Start or Current Position
                     if (t.visible or t.visited) and c != self.world.start_pos and c != target:
                         coord_str = f"{c[0]},{c[1]}"
                         snapshot[coord_str] = {
                             "vis": t.visible,
                             "vst": t.visited
                         }
                         # Now hide it
                         t.visible = False
                         t.visited = False
                 
                 self.lost_memory = snapshot
        # -----------------------------------
        
        elif tile.type == "swamp" and random.random() < 0.2: 
            lost = int(self.currency * 0.5); self.currency -= lost
            ModernAlert(self, "SUNK!", f"Sank in bog! Lost {lost} coins.", "#d35400").exec()

        elif tile.type == "ruins":
            target_str = f"{target[0]},{target[1]}"
            if target_str in self.completed_ruins:
                tooltip("Archive already deciphered.")
            else:
                if QMessageBox.question(self, "Ancient Archive", "Study 500 cards to reveal objective?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                    self.ruin_active = True; self.ruin_progress = 0; self.current_ruin_location = target_str 
                    tooltip("Archive Accessed. Locked."); self.save_requested.emit()

        my_uid = get_uid()
        if target in self.shared_traps:
            trap_data = self.shared_traps[target]
            if trap_data.get("owner") != my_uid:
                self.is_trapped = True; self.trap_debt = 100
                ModernAlert(self, "TRAP!", "It's a trap! (100 Reviews)", "#e74c3c").exec()
                del self.shared_traps[target] 

        if hasattr(self, 'radar_targets') and self.radar_targets:
            t_str = f"{target[0]},{target[1]}"
            if t_str in self.radar_targets: self.radar_targets.remove(t_str)

        if tile.type == "key" and not self.has_key:
            self.has_key = True; ModernAlert(self, "KEY FOUND", "Artifact Unlocked.", "#00d2d3").exec()

        if target == self.world.exit_pos: 
            if not self.has_key: 
                tooltip("Locked! Find a Key.")
            else:
                self.network.do_send_move(target[0], target[1], True)
                self.match_ended_signal.emit("won")
                return

        self.update_fog_of_war() 
        self.update()
        self.currency_updated.emit(self.currency)
        self.save_requested.emit()
        self.network.do_send_move(target[0], target[1], False)

    def pixel_to_hex(self, x, y):
        cx, cy = self.width()/2, self.height()/2; q = (2./3 * (x-cx)) / self.hex_r; r = (-1./3 * (x-cx) + math.sqrt(3)/3 * (y-cy)) / self.hex_r
        rq, rr, rs = round(q), round(r), round(-q-r)
        if abs(rq-q) > abs(rr-r) and abs(rq-q) > abs(rs-(-q-r)): rq = -rr-rs
        elif abs(rr-r) > abs(rs-(-q-r)): rr = -rq-rs
        return (int(rq), int(rr))
    def get_hex_center(self, q, r): return (self.width()/2 + self.hex_r * (3/2 * q), self.height()/2 + self.hex_r * (math.sqrt(3)/2 * q + math.sqrt(3) * r))
    def draw_status_overlay(self, p):
        p.save(); p.setClipRect(self.rect()); w = self.width(); h = self.height(); pulse = (math.sin(self.anim_time * 2.5) + 1.0) / 2.0 
        
        # 1. Base Blindness (Sepia Overlay) - Always active if debt > 0
        if self.is_disoriented:
             # Increased strength from 50 to 180 for stronger effect
             p.fillRect(self.rect(), QColor(194, 178, 128, 180))

        # 2. Active Sandstorm Animation - Only if ON Dunes
        if self.is_disoriented and self.world.tiles[self.player_pos].type == "dunes":
             p.fillRect(self.rect(), QColor(225, 177, 44, 40))
             p.setPen(Qt.PenStyle.NoPen)
             for i in range(150):
                 speed = 60 + (i % 20) * 10; x = (self.anim_time * speed + i * 97) % (w + 50) - 25; y = (i * 37) % h; size = (i % 3) + 1
                 p.setBrush(QColor(240, 230, 140, 180)); p.drawEllipse(QPointF(x, y + math.sin(x*0.05)*10), size, size)

        # 3. Stacked Effects (Frozen, Buried, Trapped, Burned)
        if self.is_frozen:
             alpha = int(140 + (pulse * 60)); grad = QRadialGradient(w/2, h/2, max(w,h)/1.2); grad.setColorAt(0.5, QColor(0,0,0,0)); grad.setColorAt(1, QColor(100, 240, 255, alpha)); p.fillRect(self.rect(), QBrush(grad)); p.setPen(Qt.PenStyle.NoPen)
             for i in range(80): size = (i % 4) + 2; speed_y = (i % 3 + 2) * 20; speed_x = (i % 5 + 1) * 10; x_pos = (i * 73 + self.anim_time * speed_x) % (w + 50) - 25; y_pos = (i * 29 + self.anim_time * speed_y) % (h + 50) - 25; opacity = 150 + (i % 100); p.setBrush(QColor(255, 255, 255, opacity)); p.drawEllipse(QPointF(x_pos, y_pos), size, size)
        
        if self.is_buried:
             grad = QRadialGradient(w/2, h/2, max(w,h)*0.85); grad.setColorAt(0.3, QColor(0,0,0, 60)); grad.setColorAt(0.7, QColor(20, 15, 10, 200)); grad.setColorAt(1.0, QColor(0,0,0, 250)); p.fillRect(self.rect(), QBrush(grad))
             shake_amp = 2.5; off_x = math.sin(self.anim_time * 45) * shake_amp; off_y = math.cos(self.anim_time * 60) * shake_amp; p.save(); p.translate(off_x, off_y)
             p.setPen(Qt.PenStyle.NoPen)
             for i in range(50):
                 speed = 40 + (i % 5) * 15; x = (i * 67) % w; y = (self.anim_time * speed + i * 23) % (h + 100) - 50; size = (i % 3) + 1; p.setBrush(QColor(120, 110, 100, 80)); p.drawEllipse(QPointF(x, y), size, size)
             p.setBrush(QColor(35, 30, 25))
             for i in range(12):
                 speed = 200 + (i % 4) * 80; x = (i * 137) % (w + 100) - 50; y = (self.anim_time * speed) % (h + 300) - 150; rot_speed = 5 + (i % 3) * 5
                 p.save(); p.translate(x, y); p.rotate(self.anim_time * rot_speed * (1 if i%2==0 else -1))
                 rock_sz = 12 + (i % 5) * 10
                 path = QPainterPath(); path.moveTo(-rock_sz, -rock_sz*0.4); path.lineTo(-rock_sz*0.3, -rock_sz*0.9); path.lineTo(rock_sz*0.8, -rock_sz*0.5); path.lineTo(rock_sz, rock_sz*0.6); path.lineTo(-rock_sz*0.2, rock_sz); path.lineTo(-rock_sz*0.9, rock_sz*0.3); path.closeSubpath()
                 p.drawPath(path); p.restore()
             p.restore()

        if self.is_trapped:
             bg_alpha = int(100 + (pulse * 40)); p.fillRect(self.rect(), QColor(50, 0, 0, bg_alpha)); p.save(); p.setClipRect(self.rect()); stripe_w = 40; offset = (self.anim_time * 30) % (stripe_w * 2); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 0, 0, 40)); diag_len = w + h; steps = int(diag_len / stripe_w)
             p.translate(w/2, h/2); p.rotate(45); p.translate(-diag_len/2, -diag_len/2)
             for i in range(steps + 2): p.drawRect(QRectF((i * stripe_w * 2) - offset, 0, stripe_w, diag_len))
             p.restore(); p.save(); p.translate(w/2, h/2); p.rotate(self.anim_time * 15); p.setBrush(Qt.BrushStyle.NoBrush); pen = QPen(QColor(255, 50, 50, 200), 3); pen.setDashPattern([10, 10]); p.setPen(pen); radius = min(w, h) * 0.35; p.drawEllipse(QPointF(0,0), radius, radius)
             p.rotate(-self.anim_time * 30); pen.setWidth(2); pen.setDashPattern([5, 5]); p.setPen(pen); radius2 = radius * 0.8; p.drawEllipse(QPointF(0,0), radius2, radius2)
             p.rotate(90); p.setPen(QPen(QColor(255, 50, 50), 4)); dist = radius + 15
             for _ in range(4): p.rotate(90); p.drawLine(QPointF(dist, -10), QPointF(dist, 10)); p.drawLine(QPointF(dist, 0), QPointF(dist-10, 0))
             p.restore()
        
        if self.is_burned:
             alpha = int(100 + (pulse * 120)); grad = QRadialGradient(w/2, h/2, max(w,h)/1.6); grad.setColorAt(0.4, QColor(0,0,0,0)); grad.setColorAt(1, QColor(255, 69, 0, alpha)); p.fillRect(self.rect(), QBrush(grad)); p.setPen(Qt.PenStyle.NoPen)
             for i in range(15): radius = 20 + (i % 3) * 10; speed = 15 + (i % 5); p.setBrush(QColor(200, 200, 200, 60)); p.drawEllipse(QPointF((i * 137) % w + math.sin(self.anim_time + i) * 20, h - ((self.anim_time * speed + i * 50) % (h + 100))), radius, radius)
             for i in range(40): size = (i % 3) + 2; speed = 60 + (i % 40); ember_alpha = int(150 + math.sin(self.anim_time * 10 + i)*100); ember_alpha = max(0, min(255, ember_alpha)); col = QColor(255, 200, 50, ember_alpha) if i % 3 != 0 else QColor(255, 80, 50, ember_alpha); p.setBrush(col); p.drawEllipse(QPointF((i * 43) % w, h - ((self.anim_time * speed + i * 20) % (h + 50))), size, size)
        
        p.restore()
    def paintEvent(self, e):
        self.update_grid_metrics(); p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.fillRect(self.rect(), QColor(COLOR_BG_CANVAS)); pulse = (math.sin(self.anim_time) + 1) / 2; my_uid = get_uid()
        
        for c, t in self.world.tiles.items():
            cx, cy = self.get_hex_center(*c); 
            dist = self.world.hex_dist(c, self.player_pos); 
            is_revealed = t.visible   # Active Sight (Bright)
            is_visited = t.visited    # Memory (Faded)
            
            # 1. Sandstorm Masking
            if self.is_disoriented and dist > 1:
                path = QPainterPath(); r = self.hex_r
                for i in range(6): a = math.radians(60*i); x = cx + r*math.cos(a); y = cy + r*math.sin(a); path.lineTo(x,y) if i!=0 else path.moveTo(x,y)
                path.closeSubpath(); p.setBrush(QColor("#ffffff")); p.setPen(QPen(QColor("#dfe6e9"), 1)); p.drawPath(path); continue 
            
            # 2. Hidden Tiles (Never Visited)
            if not is_visited:
                 path = QPainterPath(); r = self.hex_r
                 for i in range(6): a = math.radians(60*i); x = cx + r*math.cos(a); y = cy + r*math.sin(a); path.lineTo(x,y) if i!=0 else path.moveTo(x,y)
                 path.closeSubpath(); p.setBrush(QColor("#ffffff")); p.setPen(QPen(QColor("#dfe6e9"), 1)); p.drawPath(path); continue 
            
            # 3. Draw Terrain (Base Color)
            fill = QColor(TERRAIN_CONFIG[t.type]["color"]); draw_trap_ring = False; trap_pulse = 0
            
            trap_pulse = (math.sin(self.anim_time * 0.8) + 1) / 2
            if t.trap_owner == my_uid:
                trap_col = QColor(231, 76, 60); trap_pulse = (math.sin(self.anim_time * 2.0) + 1) / 2; ratio = trap_pulse * 0.5 
                r = int(fill.red() * (1 - ratio) + trap_col.red() * ratio); g = int(fill.green() * (1 - ratio) + trap_col.green() * ratio); b = int(fill.blue() * (1 - ratio) + trap_col.blue() * ratio); fill = QColor(r, g, b); draw_trap_ring = True
            
            border_pen = QPen(QColor(COLOR_HEX_BORDER), 1)
            # Only highlight movement borders if actively visible or neighbor
            if c in self.world.get_neighbors(*self.player_pos):
                 if self.currency >= self.get_move_cost(t): border_pen = QPen(QColor("#2ecc71"), 3); border_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            
            self.draw_hex(p, cx, cy, fill, border_pen)
            self.draw_vector_icon(p, cx, cy, t)
            
            # 4. Draw Trap Ring
            if c in self.active_traps or t.trap_owner == my_uid:
                p.save()
                
                # A. The Glowing Ring (Breathing size and opacity)
                ring_alpha = int(60 + (trap_pulse * 140)) # Opacity range 60-200
                # Size oscillates between 55% and 85% of hex radius
                ring_size = self.hex_r * (0.35 + (trap_pulse * 0.2))
                
                ring_col = QColor(231, 76, 60)
                ring_col.setAlpha(ring_alpha)
                p.setPen(QPen(ring_col, 2.5)) # Thicker pen
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), ring_size, ring_size)

                # B. The Inner "Core" (Bright pulsating center dot)
                core_size = 3 + (trap_pulse * 1.5) # Size range 5-8 pixels
                core_col = QColor(255, 120, 120) # Brighter red center
                # Core gets brighter as ring expands
                core_col.setAlpha(int(180 + trap_pulse * 75)) 
                p.setBrush(core_col)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), core_size, core_size)

                p.restore()

            # 5. FOG OVERLAY (STRONGER EFFECT)
            # Increased Alpha from 120 -> 170
            if is_visited and not is_revealed: 
                self.draw_hex(p, cx, cy, QColor(255, 255, 255, 170), Qt.PenStyle.NoPen)
            
            # 6. Text Labels
            txt = ""; 
            if t.type == "mountain": txt = "CLIMB"
            elif t.type == "ruins": txt = "STUDY"
            elif t.cost > 0 or t.type == "swamp": txt = "FREE" if self.get_move_cost(t)==0 else f"${self.get_move_cost(t)}"
            
            if (is_revealed or is_visited) and txt:
                # Active = Bright White (230), Visited = Dim (100)
                text_alpha = 230 if is_revealed else 100
                font_scale = 0.20 if txt == "CLIMB" or txt == "STUDY" else 0.35; 
                f = p.font(); f.setPointSize(max(5, int(self.hex_r * font_scale))); f.setBold(True); 
                p.setFont(f); p.setPen(QColor(255, 255, 255, text_alpha))
                p.drawText(QRectF(cx - self.hex_r, cy + self.hex_r * 0.35, self.hex_r * 2, self.hex_r * 0.5), Qt.AlignmentFlag.AlignCenter, txt)

        # --- DRAW PERSISTENT RADAR PING ---
        if hasattr(self, 'radar_targets') and self.radar_targets:
            targets = self.radar_targets
            if isinstance(targets, str): targets = [targets]
            for target_str in targets:
                t_str = str(target_str).replace("(", "").replace(")", "").replace(" ", "")
                if "," in t_str:
                    parts = t_str.split(',')
                    t_q = int(parts[0]); t_r = int(parts[1])
                    ping_x, ping_y = self.get_hex_center(t_q, t_r)
                    
                    cycle_len = 7.0; t_ripple = self.anim_time % cycle_len
                    if t_ripple < (cycle_len * 0.7):
                        prog = t_ripple / (cycle_len * 0.7)
                        rip_r = self.hex_r * (0.5 + (prog * 3.0))
                        alpha = int(180 * (1.0 - (prog**2.5)))
                        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255, 0, 255, alpha), 2)) 
                        p.drawEllipse(QPointF(ping_x, ping_y), rip_r, rip_r)
                    
                    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 0, 255, 150))
                    p.drawEllipse(QPointF(ping_x, ping_y), self.hex_r * 0.3, self.hex_r * 0.3)
        
        # Player & HUD
        my_col = QColor(PALETTE["p0_hex"] if self.profile_id == 0 else PALETTE["p1_hex"])
        px, py = self.get_hex_center(*self.player_pos); 
        if self.thermometer_active > 0:
            p.setBrush(Qt.BrushStyle.NoBrush); radar_col = QColor(self.thermometer_color); radar_col.setAlpha(int(255 * (self.thermometer_active / 60.0))); p.setPen(QPen(radar_col, 4)); p.drawEllipse(QPointF(px, py), self.hex_r*1.4, self.hex_r*1.4)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(my_col.red(), my_col.green(), my_col.blue(), 50)); halo_r = self.hex_r * 0.55; p.drawEllipse(QPointF(px, py), halo_r, halo_r)
        scale_anim = 0.4 + (math.sin(self.anim_time * 2.5) * 0.05); core_r = self.hex_r * scale_anim; p.setBrush(my_col); p.setPen(QPen(Qt.GlobalColor.white, 2)); p.drawEllipse(QPointF(px, py), core_r, core_r); p.setBrush(Qt.GlobalColor.white); p.setPen(Qt.PenStyle.NoPen); inner_r = core_r * 0.4; p.drawEllipse(QPointF(px, py), inner_r, inner_r)
        
        if self.opponent_visible and self.opponent_pos:
            opx, opy = self.get_hex_center(*self.opponent_pos); opp_col = QColor(PALETTE["p1_hex"] if self.profile_id == 0 else PALETTE["p0_hex"]); p.save(); p.translate(opx, opy); p.rotate(-self.anim_time * 20.0); scan_r = self.hex_r * 0.75; gap = 25; span = (360 / 4) - gap; rect = QRectF(-scan_r, -scan_r, scan_r*2, scan_r*2); white_pen = QPen(QColor(255, 255, 255, 220), 5); white_pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(white_pen); p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(4): p.drawArc(rect, int(((i * 90) + (gap / 2)) * 16), int(span * 16))
            col_pen = QPen(opp_col, 2.5); col_pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(col_pen)
            for i in range(4): p.drawArc(rect, int(((i * 90) + (gap / 2)) * 16), int(span * 16))
            p.restore(); blip_pulse = (math.sin(self.anim_time * 8.0) + 1) / 2; p.save(); p.translate(opx, opy); p.rotate(45); blip_size = self.hex_r * (0.25 + (blip_pulse * 0.1)); p.setBrush(Qt.GlobalColor.white); p.setPen(Qt.PenStyle.NoPen); p.drawRect(QRectF(-blip_size/2 - 1.5, -blip_size/2 - 1.5, blip_size + 3, blip_size + 3)); p.setBrush(opp_col); p.drawRect(QRectF(-blip_size/2, -blip_size/2, blip_size, blip_size)); p.setBrush(Qt.GlobalColor.white); p.drawRect(QRectF(-blip_size*0.2, -blip_size*0.2, blip_size*0.4, blip_size*0.4)); p.restore()
        
        self.draw_status_overlay(p); self.draw_split_hud(p); self.draw_status_pill(p)
    
    def draw_standard_key(self, p, x, y, w, h, col):
        p.save()
        p.translate(x, y)
        p.rotate(-45) 
        thickness = w * 0.14; bow_outer_r = w * 0.35; bow_inner_r = w * 0.18; stem_len = w * 1.1; bit_size = w * 0.25
        bow_center_x = (bow_outer_r - stem_len) / 2
        bow_center = QPointF(bow_center_x, 0)
        solid_path = QPainterPath()
        solid_path.addEllipse(bow_center, bow_outer_r, bow_outer_r)
        solid_path.addRect(QRectF(bow_center.x(), -thickness/2, stem_len, thickness))
        solid_path.addRect(QRectF(bow_center.x() + stem_len - bit_size, thickness/2, bit_size, bit_size*0.8))
        solid_path = solid_path.simplified()
        hole_path = QPainterPath()
        hole_path.addEllipse(bow_center, bow_inner_r, bow_inner_r)
        final_path = solid_path.subtracted(hole_path)
        p.setBrush(QColor(col)); p.setPen(Qt.PenStyle.NoPen); p.drawPath(final_path)
        p.restore()

    def draw_split_hud(self, p):
        hud_w = 200; hud_h = 80
        p.setBrush(QColor(30, 39, 46, 250)); p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        left_rect = QRect(20, 20, hud_w, hud_h); p.drawRoundedRect(left_rect, 12, 12)
        key_slot_w = 60; data_w = hud_w - key_slot_w
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.drawLine(int(left_rect.x() + data_w), int(left_rect.y() + 10), int(left_rect.x() + data_w), int(left_rect.bottom() - 10))
        col_w = data_w / 2
        p.setPen(QColor("#ffffff")); font = p.font(); font.setPointSize(18); font.setBold(True); p.setFont(font)
        p.drawText(QRect(left_rect.x(), left_rect.y() + 15, int(col_w), 30), Qt.AlignmentFlag.AlignCenter, f"{self.currency}")
        p.setPen(QColor(COLOR_ACCENT)); font.setPointSize(7); font.setBold(True); font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1); p.setFont(font)
        p.drawText(QRect(left_rect.x(), left_rect.y() + 45, int(col_w), 20), Qt.AlignmentFlag.AlignCenter, "COINS")
        sig_center_x = left_rect.x() + col_w + (col_w/2)
        self.draw_signal_strength(p, QPoint(int(sig_center_x), int(left_rect.y() + 32))) 
        p.setPen(QColor(COLOR_ACCENT)); font.setPointSize(7); font.setBold(True); p.setFont(font)
        p.drawText(QRect(int(left_rect.x() + col_w), int(left_rect.y() + 45), int(col_w), 20), Qt.AlignmentFlag.AlignCenter, "DIST")
        slot_center_x = left_rect.x() + data_w + (key_slot_w / 2); slot_center_y = left_rect.center().y()
        p.setPen(QColor("#7f8c8d")); font.setPointSize(6); p.setFont(font)
        p.drawText(QRect(int(left_rect.x() + data_w), int(left_rect.y() + 58), int(key_slot_w), 20), Qt.AlignmentFlag.AlignCenter, "KEY")
        
        key_icon_size = 30
        
        if self.has_key:
            # Faster, higher energy pulse
            pulse = (math.sin(self.anim_time * 6.0) + 1) / 2 
            
            # --- SUPER GLOW EFFECT ---
            
            # 1. ATMOSPHERE (Wide, faint scattering)
            atmo_col = QColor(0, 210, 211)
            atmo_col.setAlpha(int(20 + pulse * 50)) # Very subtle
            atmo_pen = QPen(atmo_col, 22, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(atmo_pen)
            self.draw_standard_key(p, slot_center_x, slot_center_y - 3, key_icon_size, key_icon_size, "#00000000")

            # 2. BLOOM (The main light source)
            bloom_col = QColor(0, 255, 255) # Pure Bright Cyan
            bloom_col.setAlpha(int(80 + pulse * 120))
            bloom_pen = QPen(bloom_col, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(bloom_pen)
            self.draw_standard_key(p, slot_center_x, slot_center_y - 3, key_icon_size, key_icon_size, "#00000000")

            # 3. CORE (White Hot Intensity)
            core_col = QColor(255, 255, 255)
            core_col.setAlpha(int(150 + pulse * 105))
            core_pen = QPen(core_col, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(core_pen)
            self.draw_standard_key(p, slot_center_x, slot_center_y - 3, key_icon_size, key_icon_size, "#00000000")
            
            # 4. KEY BODY (Almost white fill to look bright)
            p.setBrush(QColor(220, 255, 255)) 
            p.setPen(Qt.PenStyle.NoPen)
            self.draw_standard_key(p, slot_center_x, slot_center_y - 3, key_icon_size, key_icon_size, "#00d2d3")
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 40), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            self.draw_standard_key(p, slot_center_x, slot_center_y - 3, key_icon_size, key_icon_size, QColor(255, 255, 255, 40))

        if self.connection_status == "VERSUS":
            font_name = p.font(); font_name.setPointSize(11); font_name.setBold(True); font_title = p.font(); font_title.setPointSize(8); font_title.setBold(False); font_pill = p.font(); font_pill.setPointSize(7); font_pill.setBold(True); name_txt = f"VS {self.opponent_name}"; title_txt = self.opponent_cat; stats_txt = f"{self.opponent_stats.get('w',0)}W-{self.opponent_stats.get('l',0)}L"; fm_name = QFontMetrics(font_name); fm_title = QFontMetrics(font_title); fm_pill = QFontMetrics(font_pill); w_name = fm_name.horizontalAdvance(name_txt); w_title = fm_title.horizontalAdvance(title_txt); w_pill_txt = fm_pill.horizontalAdvance(stats_txt); w_pill_box = w_pill_txt + 24; needed_w = max(w_name, w_title, w_pill_box) + 40; panel_h = 85; right_rect = QRect(self.width() - needed_w - 20, 20, needed_w, panel_h); p.setBrush(QColor(30, 39, 46, 250)); p.setPen(QPen(QColor(255, 255, 255, 30), 1)); p.drawRoundedRect(right_rect, 12, 12); cx = right_rect.center().x(); start_y = right_rect.y()
            p.setPen(QColor("#ff7675")); p.setFont(font_name); p.drawText(QRect(right_rect.left(), start_y + 10, right_rect.width(), 25), Qt.AlignmentFlag.AlignCenter, name_txt); pill_rect = QRect(int(cx - w_pill_box/2), start_y + 38, int(w_pill_box), 18); p.setBrush(QColor(0,0,0,150)); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(pill_rect, 9, 9); p.setPen(QColor("#dfe6e9")); p.setFont(font_pill); p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, stats_txt); p.setPen(QColor("#b2bec3")); p.setFont(font_title); p.drawText(QRect(right_rect.left(), start_y + 60, right_rect.width(), 20), Qt.AlignmentFlag.AlignCenter, title_txt)
        else:
            right_rect = QRect(self.width() - 180, 20, 160, 60); p.setBrush(QColor(30, 39, 46, 250)); p.setPen(QPen(QColor(255, 255, 255, 30), 1)); p.drawRoundedRect(right_rect, 12, 12); p.setPen(QColor("#bdc3c7")); font = p.font(); font.setPointSize(9); font.setBold(True); p.setFont(font); p.drawText(right_rect, Qt.AlignmentFlag.AlignCenter, self.connection_status)
            
    def draw_status_pill(self, p):
        statuses = []
        if self.is_frozen: statuses.append((f"❄ {self.freeze_debt} REV", "#74b9ff"))
        if self.ruin_active: statuses.append((f"🏛 {self.ruin_progress}/500", "#8e44ad"))
        if self.is_trapped: statuses.append((f"⚠ {self.trap_debt} REV", "#ff7675"))
        if self.is_buried: statuses.append((f"⛰ {self.rock_debt} REV", "#636e72")) 
        if self.is_burned: statuses.append((f"🔥 {self.burn_debt} REV", "#e74c3c"))
        if self.is_climbing: statuses.append((f"▲ {self.climb_debt} REV", "#ffeaa7"))
        if self.is_disoriented: statuses.append((f"≋ {self.disorientation_debt} REV", "#fab1a0"))
        if self.wager_active: statuses.append((f"🎲 {self.wager_progress}/{self.wager_total}", "#9b59b6"))
        if not statuses: return
        pill_w = 120; pill_h = 24; base_y = self.height() - 40; font = p.font(); font.setPointSize(9); font.setBold(True); p.setFont(font)
        for i, (msg, col) in enumerate(reversed(statuses)): y = base_y - (i * (pill_h + 5)); x = (self.width() - pill_w) // 2; p.setBrush(QColor(0,0,0,200)); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(QRect(x, y, pill_w, pill_h), 12, 12); p.setPen(QColor(col)); p.drawText(QRect(x, y, pill_w, pill_h), Qt.AlignmentFlag.AlignCenter, msg)
    def draw_signal_strength(self, p, center_pt):
        if not self.world.exit_pos: return
        dist = self.world.hex_dist(self.player_pos, self.world.exit_pos); bars = 0
        if dist <= 5: bars = 3
        elif dist <= 16: bars = 2
        elif dist > 16: bars = 1
        p.setPen(Qt.PenStyle.NoPen); bar_w = 4; spacing = 3; start_x = center_pt.x() - 8; base_y = center_pt.y() + 8; p.setBrush(QColor("#e74c3c") if bars >= 1 else QColor(255,255,255,50)); p.drawRoundedRect(QRect(int(start_x), int(base_y - 6), bar_w, 6), 1, 1); p.setBrush(QColor("#f1c40f") if bars >= 2 else QColor(255,255,255,50)); p.drawRoundedRect(QRect(int(start_x + bar_w + spacing), int(base_y - 10), bar_w, 10), 1, 1); p.setBrush(QColor("#2ecc71") if bars >= 3 else QColor(255,255,255,50)); p.drawRoundedRect(QRect(int(start_x + (bar_w + spacing)*2), int(base_y - 14), bar_w, 14), 1, 1)
    def draw_hex(self, p, cx, cy, fill, pen):
        path = QPainterPath(); r = self.hex_r
        for i in range(6): a = math.radians(60*i); x = cx + r*math.cos(a); y = cy + r*math.sin(a); path.lineTo(x,y) if i!=0 else path.moveTo(x,y)
        path.closeSubpath(); p.setBrush(fill); p.setPen(pen if pen else Qt.PenStyle.NoPen); p.drawPath(path)
    def draw_vector_icon(self, p, cx, cy, tile):
        t_type = tile.type; s = self.hex_r; 
        p.setBrush(QColor(255,255,255, 200)); p.setPen(Qt.PenStyle.NoPen)
        if t_type == "forest":
            path = QPainterPath()
            path.moveTo(cx, cy-s*0.4)
            path.lineTo(cx-s*0.25, cy+s*0.2)
            path.lineTo(cx+s*0.25, cy+s*0.2)
            path.closeSubpath(); p.drawPath(path)
            path = QPainterPath()
            path.moveTo(cx-s*0.3, cy-s*0.1)
            path.lineTo(cx-s*0.45, cy+s*0.2)
            path.lineTo(cx-s*0.15, cy+s*0.2)
            path.closeSubpath(); p.drawPath(path)
            path = QPainterPath()
            path.moveTo(cx+s*0.3, cy-s*0.1)
            path.lineTo(cx+s*0.15, cy+s*0.2)
            path.lineTo(cx+s*0.45, cy+s*0.2)
            path.closeSubpath(); p.drawPath(path)
        elif t_type == "mountain":
            path = QPainterPath()
            path.moveTo(cx-s*0.3, cy+s*0.3)
            path.lineTo(cx, cy-s*0.4)
            path.lineTo(cx+s*0.3, cy+s*0.3)
            path.closeSubpath(); p.drawPath(path)
        elif t_type == "lake":
            p.setPen(QPen(QColor(255,255,255,200), 2)); p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath(); start_x = cx - s*0.4; start_y = cy + s*0.1
            path.moveTo(start_x, start_y)
            path.cubicTo(start_x + s*0.2, start_y - s*0.2, start_x + s*0.2, start_y + s*0.2, start_x + s*0.4, start_y)
            path.cubicTo(start_x + s*0.6, start_y - s*0.2, start_x + s*0.6, start_y + s*0.2, start_x + s*0.8, start_y)
            p.drawPath(path)
        elif t_type == "wasteland":
            path = QPainterPath(); path.moveTo(cx-s*0.3, cy+s*0.3)
            path.lineTo(cx-s*0.1, cy-s*0.2); path.lineTo(cx+s*0.1, cy+s*0.3)
            path.lineTo(cx+s*0.3, cy-s*0.1); path.lineTo(cx+s*0.4, cy+s*0.3)
            path.closeSubpath(); p.drawPath(path)
        elif t_type == "dunes":
            p.setPen(QPen(QColor(45, 52, 54, 150), 2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx-s*0.4, cy-s*0.1, s*0.8, s*0.4), 0, 180*16)
            p.drawArc(QRectF(cx-s*0.2, cy-s*0.3, s*0.8, s*0.4), 0, 180*16)
        elif t_type == "swamp":
            p.drawEllipse(QPointF(cx, cy), s*0.15, s*0.15); p.drawEllipse(QPointF(cx-s*0.25, cy+s*0.1), s*0.1, s*0.1)
            p.drawEllipse(QPointF(cx+s*0.25, cy-s*0.05), s*0.12, s*0.12); p.drawEllipse(QPointF(cx-s*0.1, cy-s*0.3), s*0.08, s*0.08)
        elif t_type == "plains":
            p.setPen(QPen(QColor(45, 52, 54, 100), 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath(); base_y = cy + s*0.1
            path.moveTo(cx, base_y); path.lineTo(cx, cy-s*0.15)
            path.moveTo(cx, base_y); path.quadTo(cx-s*0.1, cy-s*0.05, cx-s*0.15, cy-s*0.1)
            path.moveTo(cx, base_y); path.quadTo(cx+s*0.1, cy-s*0.05, cx+s*0.15, cy-s*0.1)
            p.drawPath(path)
        elif t_type == "hills":
            path = QPainterPath(); path.moveTo(cx-s*0.5, cy+s*0.2)
            path.arcTo(QRectF(cx-s*0.5, cy-s*0.3, s, s), 180, -180)
            path.closeSubpath(); p.drawPath(path)
        elif t_type == "volcanic":
            path = QPainterPath(); path.moveTo(cx-s*0.4, cy+s*0.4)
            path.lineTo(cx-s*0.1, cy-s*0.3); path.lineTo(cx+s*0.1, cy-s*0.3)
            path.lineTo(cx+s*0.4, cy+s*0.4); path.closeSubpath(); p.drawPath(path)
            p.setBrush(QColor(255,255,255,100)); p.drawEllipse(QPointF(cx, cy-s*0.4), s*0.1, s*0.1)
            p.drawEllipse(QPointF(cx+s*0.1, cy-s*0.55), s*0.08, s*0.08)
        elif t_type == "tundra":
            p.setPen(QPen(QColor(255,255,255,200), 2))
            p.drawLine(QPointF(cx, cy-s*0.3), QPointF(cx, cy+s*0.3))
            p.drawLine(QPointF(cx-s*0.25, cy-s*0.15), QPointF(cx+s*0.25, cy+s*0.15))
            p.drawLine(QPointF(cx-s*0.25, cy+s*0.15), QPointF(cx+s*0.25, cy-s*0.15))
        elif t_type == "ruins":
            p.drawRect(QRectF(cx-s*0.4, cy+s*0.3, s*0.8, s*0.1))
            p.drawRect(QRectF(cx-s*0.35, cy-s*0.2, s*0.1, s*0.5))
            p.drawRect(QRectF(cx-s*0.05, cy-s*0.2, s*0.1, s*0.5))
        elif t_type == "scrub":
            p.setPen(QPen(QColor(255,255,255,200), 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath(); path.moveTo(cx-s*0.3, cy+s*0.2)
            path.quadTo(cx-s*0.2, cy-s*0.2, cx, cy+s*0.2)
            path.quadTo(cx+s*0.2, cy-s*0.2, cx+s*0.3, cy+s*0.2)
            p.drawPath(path)
        elif t_type == "key":
            pulse = (math.sin(self.anim_time * 3.0) + 1) / 2
            glow_col = QColor("#00d2d3"); glow_col.setAlpha(int(60 + pulse*80))
            p.setPen(QPen(glow_col, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            self.draw_standard_key(p, cx, cy, s*0.7, s*0.7, "#ffffff")
            p.setPen(QPen(QColor("#ffffff"), 1.5)); p.setBrush(QColor("#ffffff"))
            self.draw_standard_key(p, cx, cy, s*0.7, s*0.7, "#ffffff")
        elif t_type == "exit": 
            pulse = (math.sin(self.anim_time * 2.5) + 1) / 2
            base_gold = QColor("#f1c40f")
            if not self.has_key: base_gold = QColor("#bdc3c7")
            glow_col = QColor(base_gold); rad_glow = s * (0.65 + (pulse * 0.15)); glow_col.setAlpha(int(80 + (pulse * 100)))
            p.setBrush(glow_col); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QPointF(cx, cy), rad_glow, rad_glow)
            p.setBrush(base_gold); p.setPen(QPen(Qt.GlobalColor.white, 1.2))
            chalice = QPainterPath()
            chalice.moveTo(cx - s*0.2, cy + s*0.35); chalice.lineTo(cx + s*0.2, cy + s*0.35); chalice.lineTo(cx, cy + s*0.15); chalice.closeSubpath()
            p.drawPath(chalice)
            cup = QPainterPath()
            cup.moveTo(cx - s*0.25, cy - s*0.2)
            cup.cubicTo(cx - s*0.25, cy + s*0.2, cx + s*0.25, cy + s*0.2, cx + s*0.25, cy - s*0.2) 
            cup.closeSubpath()
            p.drawPath(cup)
            gem_col = QColor("#e74c3c") if self.has_key else QColor("#7f8c8d")
            p.setBrush(gem_col); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), s*0.1, s*0.1)
            if not self.has_key:
                p.setBrush(QColor(45, 52, 54)); p.setPen(QPen(QColor(200,200,200), 1))
                lock_w = s*0.3; lock_h = s*0.25
                p.drawRoundedRect(QRectF(cx - lock_w/2, cy, lock_w, lock_h), 3, 3)

class ShopDialog(QDialog):
    def __init__(self, parent, currency, wager_active=False):
        super().__init__(parent)
        self.setWindowTitle("Marketplace")
        self.resize(740, 380)
        self.currency = currency
        self.wager_active = wager_active
        self.choice = None
        
        # --- Clean Light Theme ---
        self.setStyleSheet("""
            QDialog { 
                background-color: #fcfcfc; 
            }
            QLabel { 
                border: none; 
                background: transparent; 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 35)
        layout.setSpacing(25)
        
        # --- HEADER ---
        header_layout = QHBoxLayout()
        
        title = QLabel("MARKETPLACE")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #2d3436; letter-spacing: 0.5px;")
        
        # --- COIN PILL (Dark Background for Contrast) ---
        coin_pill = QFrame()
        coin_pill.setObjectName("coinPill")
        coin_pill.setStyleSheet("""
            QFrame#coinPill {
                background-color: #2d3436; /* Dark Charcoal */
                border-radius: 18px;
                border: none;
            }
        """)
        
        pill_layout = QHBoxLayout(coin_pill)
        pill_layout.setContentsMargins(20, 8, 20, 8)
        pill_layout.setSpacing(10)
        
        lbl_funds = QLabel(str(currency))
        # Bright Yellow pops against the dark background
        lbl_funds.setStyleSheet("border: none; color: #f1c40f; font-weight: 900; font-size: 20px;")
        
        lbl_label = QLabel("COINS")
        # Light Grey text for the label
        lbl_label.setStyleSheet("border: none; color: #dfe6e9; font-weight: 700; font-size: 11px; margin-top: 5px;")
        
        pill_layout.addWidget(lbl_funds)
        pill_layout.addWidget(lbl_label)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(coin_pill)
        
        layout.addLayout(header_layout)
        
        # --- ITEMS GRID ---
        grid = QGridLayout()
        grid.setSpacing(20)
        
        # 1. Wager
        self.add_card(grid, 0, 0, "WAGER", "Bet on your skills. >90% retention wins +500 coins.", 200, "wager", "#9b59b6", is_active=self.wager_active)
        
        # 2. Recall
        self.add_card(grid, 0, 1, "RECALL", "Emergency teleport back to Base.", 600, "recall", "#2ecc71")
        
        # 3. Trap
        self.add_card(grid, 0, 2, "TRAP", "Deploy a cluster minefield. Traps enemy.", 250, "trap", "#e74c3c")
        
        # 4. Radar
        self.add_card(grid, 0, 3, "RADAR", "Reveal opponent location & distance.", 250, "vision", "#3498db")
        
        layout.addLayout(grid)
        layout.addStretch()
        
        # --- FOOTER ---
        cancel = QPushButton("Close Store")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedSize(140, 38)
        cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #636e72;
                border: 1px solid #dfe6e9;
                border-radius: 19px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f1f2f6;
                color: #2d3436;
                border: 1px solid #b2bec3;
            }
        """)
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignCenter)

    def add_card(self, layout, row, col, title, desc, cost, code, color, is_active=False):
        card_btn = QPushButton()
        card_btn.setFixedSize(170, 220)
        card_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        can_afford = self.currency >= cost
        
        if is_active:
            card_btn.setEnabled(False)
        else:
            card_btn.setEnabled(can_afford)
            
        card_btn.clicked.connect(lambda checked: self.buy(code, cost))

        # --- Internal Layout ---
        vl = QVBoxLayout(card_btn)
        vl.setContentsMargins(15, 20, 15, 20)
        vl.setSpacing(10)
        
        # 1. Title
        t = QLabel(title)
        # Dim title if unaffordable
        title_col = "#2d3436" if can_afford and not is_active else "#b2bec3"
        t.setStyleSheet(f"border: none; font-weight: 800; color: {title_col}; font-size: 15px; letter-spacing: 0.5px;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(t)

        # 2. Color Accent
        accent_line = QFrame()
        accent_line.setFixedSize(30, 4)
        accent_line.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        vl.addWidget(accent_line, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 3. Description
        d = QLabel(desc)
        # Dim description if unaffordable
        desc_col = "#636e72" if can_afford and not is_active else "#b2bec3"
        d.setStyleSheet(f"border: none; color: {desc_col}; font-size: 12px; font-weight: 500; line-height: 1.4;")
        d.setWordWrap(True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(d)
        
        vl.addStretch()
        
        # 4. Price Tag
        price_tag = QLabel()
        price_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if is_active:
            price_tag.setText("ACTIVE")
            txt_col = "#b2bec3" 
            bg_col = "#f1f2f6" 
        elif can_afford:
            price_tag.setText(f"${cost}")
            txt_col = color     
            bg_col = "#f1f2f6"  
        else:
            price_tag.setText(f"${cost}")
            txt_col = "#b2bec3" # Grey text
            bg_col = "#f1f2f6"  # Light grey bg
        
        price_tag.setStyleSheet(f"""
            background-color: {bg_col}; 
            color: {txt_col}; 
            font-weight: 800; 
            border-radius: 6px; 
            padding: 6px 14px;
            font-size: 13px;
            border: none;
        """)
        
        vl.addWidget(price_tag, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- CSS STYLING ---
        
        base_css = """
            QPushButton {
                background-color: white;
                border: 1px solid #dfe6e9; 
                border-radius: 12px;
                text-align: center;
                margin: 4px;
            }
        """
        
        if is_active:
            card_btn.setStyleSheet("""
                QPushButton {
                    background-color: #fafafa;
                    border: 1px dashed #dcdde1;
                    border-radius: 12px;
                    margin: 4px;
                }
            """)
        elif can_afford:
            card_btn.setStyleSheet(base_css + """
                QPushButton:hover {
                    border: 2px solid #2d3436; 
                    background-color: #ffffff;
                    margin-top: 2px;
                    margin-bottom: 6px;
                }
                QPushButton:pressed {
                    margin-top: 6px;
                    margin-bottom: 2px;
                    border-color: #2d3436;
                }
            """)
        else:
            # UNAFFORDABLE STATE
            card_btn.setStyleSheet(base_css + """
                QPushButton { 
                    opacity: 0.6; 
                    background-color: #fdfdfd; 
                }
            """)

        layout.addWidget(card_btn, row, col)

    def buy(self, code, cost):
        self.choice = (code, cost)
        self.accept()

class RealmDialog(QDialog):
    match_found_signal = pyqtSignal(int); opponent_left_signal = pyqtSignal(); lobby_state_signal = pyqtSignal(str); match_result_signal = pyqtSignal(str); stats_received_signal = pyqtSignal(int, int); match_expired_signal = pyqtSignal()
    def __init__(self, mw):
        self.profile_id = mw.pm.name
        super().__init__(mw); self.setWindowTitle("Anki Realm Battle"); self.resize(1200, 800); self.setStyleSheet(f"background-color: {COLOR_BG_WIDGET}; color: {COLOR_TEXT_MAIN}; {STYLE_BUTTON_CSS}")
        self.save_path = get_save_path(); self.uid = get_uid(); d = load_game_data() or {}
        self.last_trap_clusters = []
        self.stack = QStackedLayout()

        d = load_game_data() or {}
        self.currency = d.get("currency", 0)
        
        user_stats = d.get('stats', {'w': 0, 'l': 0})
        self.lobby = LobbyWidget(self, self.uid, d.get("username", ""), saved_stats=user_stats)
        
        self.lobby.join_clicked.connect(self.start_matchmaking)
        self.lobby.cancel_clicked.connect(self.cancel_matchmaking_from_lobby)

        container = QWidget(); container.setLayout(self.stack); self.stack.addWidget(self.lobby)
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.addWidget(container)
        
        self.ctrl_bar = QWidget()
        self.ctrl_bar.setStyleSheet("background-color: white; border-top: 1px solid #eee; padding: 12px;")
        self.ctrl_layout = QHBoxLayout(self.ctrl_bar)
        
        self.btn_guide = QPushButton("Field Guide")
        self.btn_guide.clicked.connect(self.open_help)
        
        self.btn_shop = QPushButton("SHOP")
        self.btn_shop.clicked.connect(self.open_shop)
        self.btn_shop.setStyleSheet("background-color: #f1c40f; color: white;")
        
        self.btn_leave = QPushButton("LEAVE MATCH")
        self.btn_leave.setStyleSheet("background-color: #e74c3c; color: white;")
        self.btn_leave.clicked.connect(self.on_user_leave_click)
        
        self.ctrl_layout.addWidget(self.btn_guide)
        self.ctrl_layout.addWidget(self.btn_shop)
        
        if DEBUG_MODE:
            btn_sim = QPushButton("Simulate Review"); btn_sim.setStyleSheet("background-color: #9b59b6; color: white;"); btn_sim.clicked.connect(self.simulate_review)
            self.ctrl_layout.addWidget(btn_sim)
            
        self.ctrl_layout.addWidget(self.btn_leave)
        main_layout.addWidget(self.ctrl_bar)
        
        self.ctrl_bar.setVisible(False)
        
        self.switching_profile = False
        self.match_processed = False
        
        # 1. Initialize the Worker
        self.worker = NetworkWorker(self.uid)
        self.network = self.worker 
        
        # 2. CONNECT SIGNALS (Check these carefully!)
        # ---------------------------------------------------------
        self.worker.data_received.connect(self.on_server_response)
        
        # These are the critical ones for ending the game:
        self.worker.opponent_left.connect(self.on_opponent_left)
        self.worker.match_result.connect(self.on_match_result)
        self.worker.match_expired.connect(self.on_match_expired)
        # ---------------------------------------------------------
        self.worker.trap_hit.connect(self.on_trap_hit)

        self.worker.log_message.connect(self.lobby.log)
        
        # 4. Connect Signals to local methods
        self.match_found_signal.connect(self.load_map_view)
        self.opponent_left_signal.connect(self.on_opponent_left)
        self.lobby_state_signal.connect(self.restore_lobby_state)
        self.match_result_signal.connect(self.on_match_result)
        self.stats_received_signal.connect(self.lobby.update_stats) 
        self.match_expired_signal.connect(self.on_match_expired)

        # 5. Initialize Timers
        self.timer = QTimer(self)
        # Use self.worker here to be consistent
        self.timer.timeout.connect(self.worker.do_status_check) 
        
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_state_from_disk)
        self.sync_timer.start(2000)
        
        # 6. Startup Check (Changed to use the worker)
        # We use a singleShot here to ensure the UI is fully painted before network hits
        QTimer.singleShot(500, self.worker.do_status_check)
        
        threading.Thread(target=self.startup_check, daemon=True).start()
    
    # Inside class RealmDialog

    def on_trap_placed(self, q, r):
        """
        User clicked to place a trap.
        We send the request, and we PREDICTIVELY draw the cluster rings
        so the UI feels instant. The next Server Sync will verify them.
        """
        # 1. Send Request (Server does the clustering math now)
        self.worker.do_place_trap(q, r)
        
        # 2. Predictive UI: Draw the cluster immediately
        # We assume the server will accept it.
        count = 1
        self.map.active_traps.add((q, r))
        
        if hasattr(self, 'map') and hasattr(self.map, 'world'):
            neighbors = self.map.world.get_neighbors(q, r)
            for n in neighbors:
                self.map.active_traps.add(n)
                count += 1
        
        self.map.update()
        
        # 3. Confirmation
        ModernAlert(self, "MINEFIELD ARMED", f"Cluster deployed.\n{count} mines active.", "#e74c3c").exec()

    def on_trap_hit(self):
        """
        Called when the NetworkWorker sees 'status': 'trapped' after a move.
        This applies the LOCAL penalty.
        """
        # 1. Update Local Data (Lock the player)
        d = load_game_data() or {}
        d["is_trapped"] = True
        d["trap_debt"] = 100
        save_game_data(d)

        # 2. Update Map UI
        if hasattr(self, 'map'):
            self.map.is_trapped = True
            self.map.trap_debt = 100
            
            # VISUAL FEEDBACK:
            # Even though the server deleted the trap, we want to show 
            # a red ring under the player's feet so they know what happened.
            current_pos = self.map.player_pos
            if current_pos:
                self.map.active_traps.add(current_pos)
                
                # Mark it as 'owned' by opponent locally for the red render
                if current_pos in self.map.world.tiles:
                    self.map.world.tiles[current_pos].trap_owner = "ENEMY_REVEALED"

            self.map.update()

        # 3. Show Alert
        ModernAlert(self, "AMBUSH!", "You triggered a hidden trap!\nSYSTEM LOCKDOWN (100 Reviews)", "#e74c3c").exec()
    
    def on_match_expired(self):
        if self.match_processed: return
        self.match_processed = True
        
        if hasattr(self, 'timer'): self.timer.stop()
        if hasattr(self, 'map') and self.map.match_terminated: return

        # Show the specific inactivity message
        self._end_game("GAME EXPIRED", "This match ended due to inactivity (7 Days).", "#95a5a6")

    def update_local_stats(self, is_win):
        d = load_game_data()
        if not d: d = {}
        
        if "stats" not in d: d["stats"] = {"w": 0, "l": 0}
        
        if is_win: 
            d["stats"]["w"] += 1
        else: 
            d["stats"]["l"] += 1
            
        save_game_data(d)
        self.lobby.update_stats(d["stats"]["w"], d["stats"]["l"])

    def simulate_review(self):
        # 1. Load Data
        d = load_game_data() 
        if not d: d = {}
        
        dec = 25 
        
        # 2. Update Logic (In Memory)
        d["currency"] = d.get("currency", 0) + 50 
        d["wager_progress"] = d.get("wager_progress", 0) + (dec if d.get("wager_active") else 0)
        
        # --- FIX: UPDATE BOOLEAN FLAGS IMMEDIATELY ---
        # When debt hits 0, we must turn off the "is_X" flag immediately
        # so the pill disappears without waiting for a sync.
        
        # Freeze
        if d.get("freeze_debt", 0) > 0:
            d["freeze_debt"] = max(0, d["freeze_debt"] - dec)
            if d["freeze_debt"] == 0: d["is_frozen"] = False

        # Trap
        if d.get("trap_debt", 0) > 0:
            d["trap_debt"] = max(0, d["trap_debt"] - dec)
            if d["trap_debt"] == 0: d["is_trapped"] = False

        # Rockslide
        if d.get("rock_debt", 0) > 0:
            d["rock_debt"] = max(0, d["rock_debt"] - dec)
            if d["rock_debt"] == 0: d["is_buried"] = False

        # Climb
        if d.get("climb_debt", 0) > 0:
            d["climb_debt"] = max(0, d["climb_debt"] - dec)
            if d["climb_debt"] == 0: d["is_climbing"] = False

        # Burn
        if d.get("burn_debt", 0) > 0:
            d["burn_debt"] = max(0, d["burn_debt"] - dec)
            if d["burn_debt"] == 0: d["is_burned"] = False
        # ---------------------------------------------

        # Archive Logic
        if d.get("ruin_active"):
            d["ruin_progress"] = d.get("ruin_progress", 0) + dec
            
            if d["ruin_progress"] >= 500:
                d["ruin_active"] = False
                d["ruin_progress"] = 0
                
                # Mark Complete
                curr_loc = d.get("current_ruin_location")
                if curr_loc:
                    completed = d.get("completed_ruins", [])
                    if curr_loc not in completed: completed.append(curr_loc)
                    d["completed_ruins"] = completed
                    d["current_ruin_location"] = None

                # Radar Logic
                tiles_dict = d.get("world", {}).get("tiles", {})
                current_pings = d.get("radar_targets", [])
                possible_pings = []
                
                for k, v in tiles_dict.items():
                    # --- FIX: Check 'visited' here too ---
                    if v.get("type") in ["key", "exit"] and not v.get("visited", False):
                        if k not in current_pings: possible_pings.append(k)
                
                if possible_pings:
                    new_target = str(random.choice(possible_pings))
                    current_pings.append(new_target)
                    d["radar_targets"] = current_pings
                    
                    if hasattr(self, 'map'):
                        self.map.radar_targets = current_pings
                        self.map.ruin_active = False
                        self.map.completed_ruins = completed
                        self.map.update() 
                        QApplication.processEvents()

                    ModernAlert(self, "ARCHIVE DECODED", f"New signal detected at {new_target}!", "#8e44ad").exec()
                else:
                    if hasattr(self, 'map'):
                        self.map.ruin_active = False
                        self.map.update()
                    ModernAlert(self, "ARCHIVE EMPTY", "No unknown signals remain.\n(All Keys/Artifacts visited)", "#8e44ad").exec()
        
        # Sandstone / Disorientation Logic
        if d.get("disorientation_debt", 0) > 0: 
            d["disorientation_debt"] = max(0, d["disorientation_debt"] - dec)
            
            lost_mem = d.get("lost_memory")
            
            if lost_mem:
                # If debt is 0, RESTORE EVERYTHING. Otherwise, restore chunk.
                if d["disorientation_debt"] == 0:
                    count_to_restore = 999999 
                else:
                    count_to_restore = 5
                
                # Robust Dict Handling
                if isinstance(lost_mem, dict):
                    keys = list(lost_mem.keys())
                    tiles_dict = d.get("world", {}).get("tiles", {})
                    
                    for _ in range(min(len(keys), count_to_restore)):
                        k = keys.pop(0)
                        state = lost_mem.pop(k) 
                        if k in tiles_dict:
                            tiles_dict[k]["visible"] = state.get("vis", False)
                            tiles_dict[k]["visited"] = state.get("vst", False)
                    
                    d["lost_memory"] = lost_mem
                    d["world"]["tiles"] = tiles_dict

                # Legacy List Handling (Fallback)
                elif isinstance(lost_mem, list):
                    restored = []
                    for _ in range(min(len(lost_mem), count_to_restore)):
                        restored.append(lost_mem.pop(0))
                    
                    tiles_dict = d.get("world", {}).get("tiles", {})
                    for c_str in restored:
                        if c_str in tiles_dict: tiles_dict[c_str]["visited"] = True
                    
                    d["lost_memory"] = lost_mem
                    d["world"]["tiles"] = tiles_dict
            
            if d["disorientation_debt"] == 0: d["is_disoriented"] = False

        # 3. Save to Disk
        save_game_data(d)

        # 4. UPDATE UI DIRECTLY (Immediate Feedback)
        if hasattr(self, 'map'):
            self.map.currency = d["currency"]
            
            # Values
            self.map.freeze_debt = d.get("freeze_debt", 0)
            self.map.trap_debt = d.get("trap_debt", 0)
            self.map.rock_debt = d.get("rock_debt", 0)
            self.map.climb_debt = d.get("climb_debt", 0)
            self.map.burn_debt = d.get("burn_debt", 0)
            self.map.disorientation_debt = d.get("disorientation_debt", 0)
            
            # --- CRITICAL FIX: UPDATE BOOLEANS TOO ---
            # This ensures the visual status pills disappear INSTANTLY
            self.map.is_frozen = d.get("is_frozen", False)
            self.map.is_trapped = d.get("is_trapped", False)
            self.map.is_buried = d.get("is_buried", False)
            self.map.is_climbing = d.get("is_climbing", False)
            self.map.is_burned = d.get("is_burned", False)
            self.map.is_disoriented = d.get("is_disoriented", False)
            # -----------------------------------------
            
            self.map.ruin_progress = d.get("ruin_progress", 0)
            self.map.ruin_active = d.get("ruin_active", False)
            self.map.completed_ruins = d.get("completed_ruins", [])
            self.map.radar_targets = d.get("radar_targets", [])
            
            current_tile = self.map.world.tiles.get(self.map.player_pos)
            if current_tile and current_tile.type == "mountain" and self.map.climb_debt == 0:
                self.map.update_fog_of_war()

            self.map.update()

    def sync_state_from_disk(self):
        if not hasattr(self, 'map'): return
        d = load_game_data()
        if not d: return

        # --- SMART SYNC HELPER ---
        # Prevents overwriting local active debt with 0 from an old save file
        def smart_sync_debt(local_val, key, is_active):
            disk_val = d.get(key, 0)
            # If we are locally trapped (val > 0) but disk says 0, 
            # it's a save lag. TRUST LOCAL.
            if is_active and local_val > 0 and disk_val == 0:
                return local_val
            # Otherwise (paying off debt or loading), trust the disk
            return disk_val
        # -------------------------

        # Sync Debts using Smart Logic
        self.map.freeze_debt = smart_sync_debt(self.map.freeze_debt, "freeze_debt", self.map.is_frozen)
        self.map.trap_debt = smart_sync_debt(self.map.trap_debt, "trap_debt", self.map.is_trapped)
        self.map.rock_debt = smart_sync_debt(self.map.rock_debt, "rock_debt", self.map.is_buried)
        self.map.climb_debt = smart_sync_debt(self.map.climb_debt, "climb_debt", self.map.is_climbing)
        self.map.burn_debt = smart_sync_debt(self.map.burn_debt, "burn_debt", self.map.is_burned)
        self.map.disorientation_debt = smart_sync_debt(self.map.disorientation_debt, "disorientation_debt", self.map.is_disoriented)

        # Sync Standard Variables
        self.map.currency = d.get("currency", self.map.currency)
        if "lost_memory" in d: self.map.lost_memory = d["lost_memory"]
        
        # Sync Archive & Radar
        if "ruin_active" in d: self.map.ruin_active = d["ruin_active"]
        if "ruin_progress" in d: self.map.ruin_progress = d["ruin_progress"]
        if "completed_ruins" in d: self.map.completed_ruins = d["completed_ruins"]
        if "current_ruin_location" in d: self.map.current_ruin_location = d["current_ruin_location"]
        if "radar_targets" in d: self.map.radar_targets = d["radar_targets"]
        
        # Update Map Tiles (Reveal new ones)
        updated = False
        disk_tiles = d.get("world", {}).get("tiles", {})
        map_tiles = self.map.world.tiles
        
        for c_str, t_data in disk_tiles.items():
            q, r = map(int, c_str.split(','))
            if (q,r) in map_tiles:
                local_t = map_tiles[(q,r)]
                if t_data.get("visited") and not local_t.visited:
                    local_t.visited = True
                    local_t.visible = True
                    updated = True
        
        if updated: self.map.update()
        
        current_tile = self.map.world.tiles.get(self.map.player_pos)
        if current_tile and current_tile.type == "mountain":
            self.map.update_fog_of_war()

        # Run check_recovery to clear statuses if they genuinely reached 0
        self.map.check_recovery() 
        self.map.update()

    def startup_check(self):
        res = NetworkManager.sync_status(self.uid)
        if res:
            if 'my_stats' in res: 
                ms = res['my_stats']
                self.stats_received_signal.emit(ms.get('w',0), ms.get('l',0))
            
            status = res.get('status')
            
            if status == 'won': 
                self.match_result_signal.emit("won")
            elif status == 'lost': 
                self.match_result_signal.emit("lost")
            elif status == 'opponent_left': 
                self.opponent_left_signal.emit()
            elif status == 'expired':
                self.match_expired_signal.emit()
            elif status in ['matched', 'active']: 
                seed = res.get('seed')
                if seed: self.match_found_signal.emit(seed)
            elif status == 'queued': 
                self.lobby_state_signal.emit("SEARCHING...")
            elif status == 'idle':
                # FIX: If idle, just make sure the UI is in the correct state
                # without triggering "Opponent Left"
                self.lobby.reset_ui()
                d = load_game_data() or {}
                d["in_match"] = False
                save_game_data(d)

    def restore_lobby_state(self, msg): self.lobby.set_status(msg); self.timer.start(2000)
    
    def start_matchmaking(self, username, category):
        self.match_processed = False 
        d = load_game_data()
        if d: 
            d['username'] = username
            d['category'] = category
            save_game_data(d)
        
        self.lobby.set_status("SEARCHING...")
        
        def _join_sequence():
            status_res = NetworkManager.sync_status(self.uid)
            if status_res:
                s = status_res.get('status')
                if s in ['queued', 'active', 'matched', 'won', 'lost', 'opponent_left']:
                    requests.post(f"{SERVER_URL}/leave", json={'uid': self.uid}, timeout=3)
            self.worker.do_join(username, category)
            QMetaObject.invokeMethod(self.timer, "start", Qt.ConnectionType.QueuedConnection, Q_ARG(int, 2000))

        threading.Thread(target=_join_sequence, daemon=True).start()

    def cancel_matchmaking_from_lobby(self):
        self.timer.stop() 
        self.worker.do_leave() 

    def on_opponent_left(self):
        # 1. STOP if we already handled this game
        if self.match_processed: return
        
        # 2. Check if we were actually playing
        # We only want to show the alert if a match was actually active
        d = load_game_data() or {}
        was_in_match = d.get("in_match", False)

        # 3. Stop the network loop
        if hasattr(self, 'timer'): self.timer.stop()

        # 4. Show the Alert ONLY if we were in a match
        if was_in_match:
            self.match_processed = True
            self._end_game("DISCONNECTED", "Your opponent left the match.")
        else:
            # Silently reset the lobby UI if we were just idling/searching
            self.lobby.reset_ui()
            d["in_match"] = False
            save_game_data(d)

    def on_match_result(self, result):
        # 1. STOP if we already handled this game
        if self.match_processed: return 
        
        # 2. Mark as handled immediately to block duplicate calls
        self.match_processed = True
        
        # 3. Stop the network loop
        if hasattr(self, 'timer'): self.timer.stop()

        if hasattr(self, 'map') and self.map.match_terminated: return

        if result == "won":
            # Send one last "ack" check
            if hasattr(self, 'network'):
                 QTimer.singleShot(100, self.network.do_status_check)
            
            self.update_local_stats(True)
            self._end_game("VICTORY", "You reached the Artifact first!", "#2ecc71")
            
        elif result == "lost":
            self.update_local_stats(False)
            self._end_game("DEFEAT", "Opponent reached the Artifact.", "#e74c3c")

    def _end_game(self, title, msg, color="#95a5a6"):
        # 1. Stop Polling
        if hasattr(self, 'timer'): self.timer.stop()
        
        # 2. Show Alert
        ModernAlert(self, title, msg, color).exec()
        
        # 3. Clean UI
        if hasattr(self, 'map'): 
            self.map.deleteLater()
            del self.map
            
        self.stack.setCurrentWidget(self.lobby)
        self.lobby.reset_ui() 
        
        # --- FIX START: RESET CURRENCY & STATE IMMEDIATELY ---
        self.currency = 0  # Reset memory variable
        
        d = load_game_data()
        if d:
            d["in_match"] = False
            d["currency"] = 0  # Reset coins on disk
            
            # Reset other active states so pills disappear from the dashboard
            d["wager_active"] = False
            d["ruin_active"] = False
            d["is_frozen"] = False
            d["is_trapped"] = False
            d["is_buried"] = False
            d["is_climbing"] = False
            d["is_burned"] = False
            d["is_disoriented"] = False
            
            save_game_data(d)
        
        # Force refresh the main Anki window stats (optional, ensures dashboard updates)
        mw.reset()
        # --- FIX END ---
        
        # Set status based on result
        if title == "VICTORY":
            self.lobby.set_status("VICTORY")
        elif title == "DEFEAT":
            self.lobby.set_status("DEFEAT")
        elif title == "GAME EXPIRED":
            self.lobby.set_status("EXPIRED")
        else:
            self.lobby.set_status("IDLE")
    
    def on_server_response(self, data):
        # 1. ALWAYS CAPTURE STATS (Useful for the lobby)
        if 'my_stats' in data: 
            ms = data['my_stats']
            w = ms.get('w', 0); l = ms.get('l', 0)
            self.stats_received_signal.emit(w, l)
            
            # Save safely
            d = load_game_data() or {}
            if "stats" not in d: d["stats"] = {}
            d["stats"]["w"] = w; d["stats"]["l"] = l
            save_game_data(d)
            
            if self.stack.currentWidget() == self.lobby:
                self.lobby.update_stats(w, l)

        # 2. IF WE ARE IN THE LOBBY: Handle Queue/Match Found
        status = data.get('status')
        if self.stack.currentWidget() == self.lobby:
            
            # --- FIX: Don't react to old game states if we just finished one ---
            if self.match_processed: 
                return
            # -----------------------------------------------------------------

            if status == 'queued': self.lobby.set_status("SEARCHING...")
            elif status == 'active' or status == 'matched':
                seed = data.get('seed')
                if seed: self.load_map_view(seed)
            return

        # 3. IF WE ARE IN GAME: Update Map Data Only
        # We DO NOT handle "won", "lost", or "opponent_left" here.
        # Those are handled by separate signals now.
        if hasattr(self, 'map') and (status == 'active' or status == 'matched'):
            self.map.connection_status = "VERSUS"
            
            server_traps = data.get("my_traps", [])
            self.process_trap_sync(server_traps)

            # Update Opponent Ghost
            opp = data.get('opponent_pos')
            if opp: self.map.opponent_pos = (opp[0], opp[1])
            
            # Update Opponent Info
            self.map.opponent_name = data.get('opponent_name', 'Unknown')
            if 'opponent_stats' in data: self.map.opponent_stats = data['opponent_stats']
            
            self.map.update()

    def process_trap_sync(self, server_clusters):
        """
        Compares server trap list with local list.
        If the server list is smaller, it means the opponent stepped on one!
        """
        # A. Detect Trigger (Trapper Notification)
        # If we had more clusters before than we do now, one was triggered/removed
        if len(self.last_trap_clusters) > len(server_clusters):
            # Only show if we are actively playing
            if hasattr(self, 'map') and not self.map.match_terminated:
                 ModernAlert(self, "SUCCESS!", "Opponent triggered your minefield!", "#2ecc71").exec()
        
        # Update memory for next check
        self.last_trap_clusters = server_clusters

        # B. Sync Map Visuals
        # Rebuild the set of active_traps based EXACTLY on what the server says
        if hasattr(self, 'map'):
            valid_trap_tiles = set()
            
            # Flatten the clusters (List of Lists) into a single set of coordinates
            for cluster in server_clusters:
                for coord in cluster:
                    # coord comes from JSON as [q, r], convert to tuple (q, r)
                    if isinstance(coord, list):
                        valid_trap_tiles.add(tuple(coord))
            
            # Add locally placed traps that haven't synced yet (prevent flickering)
            # (Optional optimization, but good for UI responsiveness)
            
            # OVERWRITE the map's active traps with the Server's Truth
            # This ensures that when a trap is gone from server, it's gone from UI.
            self.map.active_traps = valid_trap_tiles
    
    def load_map_view(self, seed):
        d = load_game_data() or {}
        self.currency = d.get("currency", 0) 
        
        saved_world = d.get("world", {})
        saved_seed = saved_world.get("seed")

        if saved_seed != seed:
            # A. Reset Position
            d["player_pos"] = [0, 0] # Always start at Origin
            
            d["world"] = {}
            
            # B. Reset Wager & Shop
            d["wager_active"] = False
            d["wager_progress"] = 0
            self.currency = 0; d["currency"] = 0; d["opponent_visible"] = False
            d["is_frozen"] = False; d["freeze_debt"] = 0
            d["is_trapped"] = False; d["trap_debt"] = 0
            d["is_buried"] = False; d["rock_debt"] = 0
            d["is_climbing"] = False; d["climb_debt"] = 0
            d["is_burned"] = False; d["burn_debt"] = 0
            d["is_disoriented"] = False; d["disorientation_debt"] = 0; d["lost_memory"] = []
            d["has_key"] = False

            d["radar_target"] = None
            d["ruin_active"] = False
            d["ruin_progress"] = 0
            d["current_ruin_location"] = None
            d["completed_ruins"] = []

            save_game_data(d)

        d["in_match"] = True; save_game_data(d)
        
        if hasattr(self, 'world') and self.world.seed == seed:
            if hasattr(self, 'map') and self.stack.indexOf(self.map) != -1: 
                self.stack.setCurrentWidget(self.map); 
                self.ctrl_bar.setVisible(True);
                return
        if saved_world and saved_world.get("seed") == seed: self.world = WorldMap.from_dict(saved_world)
        else: self.world = WorldMap(0, 1, seed=seed)
        
        self.currency = d.get("currency", 0)
        self.map = HexMapWidget(self.world, self.currency, self.worker, parent=self)
        self.map.player_pos = tuple(d.get("player_pos", self.world.start_pos))
        self.map.cold_stacks = d.get("cold_stacks", 0)
        self.map.is_frozen = d.get("is_frozen", False); self.map.freeze_debt = d.get("freeze_debt", 0)
        self.map.is_trapped = d.get("is_trapped", False); self.map.trap_debt = d.get("trap_debt", 0)
        self.map.is_buried = d.get("is_buried", False); self.map.rock_debt = d.get("rock_debt", 0) 
        self.map.is_climbing = d.get("is_climbing", False); self.map.climb_debt = d.get("climb_debt", 0)
        self.map.is_burned = d.get("is_burned", False); self.map.burn_debt = d.get("burn_debt", 0)
        self.map.is_disoriented = d.get("is_disoriented", False); self.map.disorientation_debt = d.get("disorientation_debt", 0); self.map.lost_memory = d.get("lost_memory", [])
        self.map.ruin_active = d.get("ruin_active", False)
        self.map.ruin_progress = d.get("ruin_progress", 0)
        self.map.trap_placed_signal.connect(self.on_trap_placed)
        self.map.has_key = d.get("has_key", False)
        self.map.opponent_visible = d.get("opponent_visible", False)
        self.map.wager_active = d.get("wager_active", False); self.map.wager_progress = d.get("wager_progress", 0)
        self.map.leave_match_clicked.connect(self.on_user_leave_click); self.map.match_ended_signal.connect(self.on_match_result); self.map.currency_updated.connect(self.sync); self.map.save_requested.connect(self.save)
        self.map.update_fog_of_war(); self.stack.addWidget(self.map); self.stack.setCurrentWidget(self.map); 
        
        self.ctrl_bar.setVisible(True)
        #CHAT HERE
        self.timer.stop()
        self.timer.start(2000)

    def on_user_leave_click(self): self.worker.do_leave(); self._end_game("DISCONNECTED", "You left the match.", "#95a5a6")
    def open_shop(self):
        # 1. Load Fresh Data
        d = load_game_data() or {}
        self.currency = d.get("currency", 0) 
        wager_is_active = d.get("wager_active", False) # <--- Get Status
        
        # 2. Pass status to Dialog
        s = ShopDialog(self, self.currency, wager_active=wager_is_active)
        
        if s.exec():
            code, cost = s.choice
            
            # Update local memory
            self.currency -= cost
            
            # Update Map UI
            if hasattr(self, 'map'):
                self.map.currency = self.currency
                self.map.update()
            
            # Update Disk
            d["currency"] = self.currency
            save_game_data(d)

            # Handle Items
            if hasattr(self, 'map'):
                if code == "recall": 
                    self.map.player_pos = self.world.start_pos
                    self.map.update_fog_of_war()
                    self.map.save_requested.emit()
                    self.worker.do_send_move(0, 0, False)
                    ModernAlert(self, "RECALL", "Teleported to Base.", "#9b59b6").exec()
                
                elif code == "trap": 
                    self.map.placing_trap = True 
                    ModernAlert(self, "TRAP ARMED", "Select a tile to place the stasis mine.", "#e74c3c").exec()
                
                elif code == "vision": 
                    self.map.opponent_visible = True
                    d["opponent_visible"] = True 
                    save_game_data(d)
                    self.map.update()
                    ModernAlert(self, "FLARE", "Opponent location revealed.", "#2ecc71").exec()
                
                elif code == "wager":
                    d["wager_active"] = True
                    d["wager_progress"] = 0
                    save_game_data(d)
                    if hasattr(self, 'map'): 
                        self.map.wager_active = True
                        self.map.wager_progress = 0
                        self.map.update()
                    ModernAlert(self, "WAGER PLACED", "Do your next 200 reviews!\nKeep retention > 90%.", "#9b59b6").exec()
                    
    def closeEvent(self, e): 
        if not self.switching_profile: self.save()
        mw.reset(); super().closeEvent(e)
    def save(self):
        # 1. Load existing data so we don't wipe other fields (like 'stats')
        d = load_game_data() or {}

        # 2. Update with current Dialog state
        d["uid"] = self.uid
        d["username"] = self.lobby.input_name.text()
        d["category"] = self.lobby.input_cat.currentText()

        # 3. If Map is open, OVERWRITE with the most accurate Map data
        if hasattr(self, 'map'):
            # AUTHORITY: The Map Widget has the real-time currency
            current_map_currency = self.map.currency
            d["currency"] = current_map_currency
            
            # Sync back to dialog memory so they stay matched
            self.currency = current_map_currency

            # --- Map Fields ---
            d["current_level"] = 1
            d["player_pos"] = list(self.map.player_pos)
            d["world"] = self.world.to_dict()
            d["opponent_visible"] = self.map.opponent_visible
            d["has_key"] = self.map.has_key

            # --- Status Effects ---
            d["ruin_active"] = getattr(self.map, 'ruin_active', False)
            d["ruin_progress"] = getattr(self.map, 'ruin_progress', 0)
            d["current_ruin_location"] = getattr(self.map, 'current_ruin_location', None)
            d["completed_ruins"] = getattr(self.map, 'completed_ruins', [])
            d["radar_targets"] = getattr(self.map, 'radar_targets', [])

            d["is_disoriented"] = getattr(self.map, 'is_disoriented', False)
            d["disorientation_debt"] = getattr(self.map, 'disorientation_debt', 0)
            d["lost_memory"] = getattr(self.map, 'lost_memory', [])

            d["is_frozen"] = getattr(self.map, 'is_frozen', False)
            d["freeze_debt"] = getattr(self.map, 'freeze_debt', 0)
            d["is_trapped"] = getattr(self.map, 'is_trapped', False)
            d["trap_debt"] = getattr(self.map, 'trap_debt', 0)
            d["is_buried"] = getattr(self.map, 'is_buried', False)
            d["rock_debt"] = getattr(self.map, 'rock_debt', 0)
            d["is_climbing"] = getattr(self.map, 'is_climbing', False)
            d["climb_debt"] = getattr(self.map, 'climb_debt', 0)
            d["is_burned"] = getattr(self.map, 'is_burned', False)
            d["burn_debt"] = getattr(self.map, 'burn_debt', 0)

            d["cold_stacks"] = getattr(self.map, 'cold_stacks', 0)
            d["wager_active"] = getattr(self.map, 'wager_active', False)
            d["wager_progress"] = getattr(self.map, 'wager_progress', 0)
        else:
            # If map isn't open, ensure we don't write 0 if we have a value in memory
            d["currency"] = self.currency

        # 4. Write back to disk safely
        save_game_data(d)

    def reset(self):
        p = get_save_path()
        if os.path.exists(p): os.remove(p)
        save_game_data({"uid": str(uuid.uuid4())})
        self.close(); showInfo("Factory Reset Complete. Please reopen.")
    def add_funds(self, a): self.currency += a; self.sync(self.currency); self.save()
    def sync(self, new_amount): 
        # 1. Update Memory (Dialog)
        self.currency = new_amount
        
        # 2. Update Visuals (Map)
        if hasattr(self, 'map'): 
            self.map.currency = new_amount 
            self.map.update()
            

    def open_help(self): HelpDialog(self).exec()

def show_realm_dialog(): d = RealmDialog(mw); d.exec()
action = QAction("Open Realm Battle", mw); action.triggered.connect(show_realm_dialog); mw.form.menuTools.addAction(action)

def render_dashboard(wager=False):
    d = load_game_data(); 
    if not d: d = {}
    c = d.get("currency", 0)
    pills = ""
    def make_pill(icon, text, bg, text_col="white"):
        return (f"<span style='background:{bg}; color:{text_col}; padding:5px 10px; border-radius:6px; font-size:9px; font-weight:800; margin:2px 3px; display:inline-block; vertical-align:middle; box-shadow:0 2px 4px rgba(0,0,0,0.1); text-transform:uppercase; letter-spacing:0.5px; border:1px solid rgba(255,255,255,0.2);'><span style='opacity:0.8; margin-right:3px;'>{icon}</span>{text}</span>")
    if d.get("wager_active"):
        prog = d.get("wager_progress", 0); corr = d.get("wager_correct", 0)
        curr_ret = (corr / prog * 100) if prog > 0 else 100.0
        pills += make_pill("🎲", f"WAGER {prog}/200 ({int(curr_ret)}%)", "#9b59b6", "#fff")
    if d.get("is_frozen"): pills += make_pill("❄", f"FROZEN ({d.get('freeze_debt',0)})", "#74b9ff", "#002b55")
    if d.get("is_burned"): pills += make_pill("🔥", f"BURNED ({d.get('burn_debt',0)})", "#ff7675", "#550000")
    if d.get("is_trapped"): pills += make_pill("☠", f"TRAPPED ({d.get('trap_debt',0)})", "#2d3436", "#fff")
    if d.get("is_buried"): pills += make_pill("⛰", f"BURIED ({d.get('rock_debt',0)})", "#636e72", "#fff") 
    if d.get("is_climbing"): pills += make_pill("▲", f"CLIMB ({d.get('climb_debt',0)})", "#ffeaa7", "#5c5000")
    if d.get("is_disoriented"): pills += make_pill("≋", f"{d['disorientation_debt']}", "#fab1a0")
    status_content = pills if pills else "<span style='opacity:0.6; font-size:10px; font-weight:700; letter-spacing:1.5px;'>FREE FROM STATUS EFFECTS</span>"
    status_bg = "rgba(0, 0, 0, 0.15)" if pills else "rgba(255, 255, 255, 0.1)" 
    return f"""<div style='background: linear-gradient(135deg, #0984e3 0%, #74b9ff 100%); color: white; border-radius: 20px; width: 92%; max-width: 500px; margin: 30px auto; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; box-shadow: 0 15px 35px -5px rgba(9, 132, 227, 0.4), 0 0 0 1px rgba(255,255,255,0.1) inset; position: relative; overflow: hidden; text-align: center;'><div style='position:absolute; top:0; left:0; right:0; height:1px; background:rgba(255,255,255,0.4);'></div><div style='background: {status_bg}; padding: 10px 15px; min-height: 25px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: center; align-items: center; flex-wrap: wrap;'>{status_content}</div><div style='padding: 25px 20px 30px 20px;'><div style='margin-bottom: 20px;'><div style='font-size: 42px; font-weight: 800; line-height: 1.0; letter-spacing: -1.5px; text-shadow: 0 4px 10px rgba(0,0,0,0.15);'>{c}</div><div style='font-size: 11px; text-transform: uppercase; letter-spacing: 2px; opacity: 0.7; margin-top: 5px; font-weight: 600;'>Realm Coins</div></div><button onclick='pycmd("open_realm")' style='background: white; color: #0984e3; border: none; padding: 12px 32px; border-radius: 12px; font-weight: 800; font-size: 12px; cursor: pointer; letter-spacing: 0.5px; box-shadow: 0 6px 15px rgba(0,0,0,0.15); transition: transform 0.1s, box-shadow 0.1s;'>ENTER REALM</button></div></div>"""

gui_hooks.deck_browser_will_render_content.append(lambda d, c: setattr(c, 'stats', c.stats + render_dashboard(False)))
gui_hooks.overview_will_render_content.append(lambda o, c: setattr(c, 'table', c.table + render_dashboard(True)))
def msg_handler(h, m, c):
    if m == "open_realm": RealmDialog(mw).exec(); return (True, None)
    return h
gui_hooks.webview_did_receive_js_message.append(msg_handler)

def append_reviewer_overlay(content, context):
    if not isinstance(context, aqt.reviewer.Reviewer): return
    d = load_game_data()
    if not d or not d.get("in_match", False): 
        return
    pills = generate_pills_html(d)
    html = f"""<div style="position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: rgba(30, 39, 46, 0.92); backdrop-filter: blur(4px); padding: 10px 16px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.1); display: flex; flex-direction: column; align-items: flex-end; font-family: sans-serif;">
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <div id="realm-coins" style="color: #f1c40f; font-weight: 900; font-size: 18px; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">{d.get('currency', 0)}</div>
            <div style="color: #bdc3c7; font-size: 10px; font-weight: 700; margin-left: 6px; letter-spacing: 0.5px;">COINS</div>
        </div>
        <div id="realm-pills-container" style="display: flex; flex-wrap: wrap; justify-content: flex-end;">{pills}</div>
    </div>"""
    content.body += html

gui_hooks.webview_will_set_content.append(append_reviewer_overlay)