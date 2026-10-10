# -*- coding: utf-8 -*-
"""
鍋ラ绠″ FitnessDiet Manager
涓€娆惧畨鍗撶楗 + 鍋ヨ韩绠＄悊 App
鍔熻兘锛?  1. 鎷嶇収/閫夊浘浼扮畻涓€椁愮儹閲忥紙鐧惧害AI鍥惧儚璇嗗埆锛屽彲鎵嬪姩褰曞叆鍏滃簳锛?  2. 璁板綍杩愬姩閲忥紝鎸?MET 鍏紡浼扮畻娑堣€楀崱璺噷涓庡噺鑴傝繘搴?  3. 璁惧畾鍑忛噸鐩爣锛屾寜姣忔棩鐑噺棰勭畻/铔嬬櫧璐ㄧ洰鏍囩粰鍑哄紩瀵间笌鎻愰啋
鏁版嵁鏈湴瀛樺偍锛圫QLite锛夛紝鏃犻渶鑱旂綉涔熻兘鐢紙璇嗗埆鍔熻兘闇€鑱旂綉锛夈€?"""

import os
import json
import sqlite3
import datetime
import threading
import urllib.request
import urllib.parse

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.image import Image as KivyImage
from kivy.uix.spinner import Spinner
from kivy.core.window import Window
from kivy.utils import platform

try:
    from plyer import filechooser
    HAS_PLYER = True
except Exception:
    HAS_PLYER = False

# ---------------------------------------------------------------------------
# 甯搁噺涓庨厤缃?# ---------------------------------------------------------------------------

# 鐧惧害 AI 鍥惧儚璇嗗埆锛堥鐗╄瘑鍒級閰嶇疆 鈥斺€?鍦ㄦ濉叆浣犺嚜宸辩殑 API Key
BAIDU_API_KEY = ""       # 渚嬪 "xxxx.yyyyy"
BAIDU_SECRET_KEY = ""    # 渚嬪 "zzzz"
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_FOOD_URL = "https://aip.baidubce.com/rest/2.0/image-classify/v1/dish"

# 鐢ㄦ埛鍩虹淇℃伅锛堝彲鍦?App 鍐呬慨鏀癸級
DEFAULT_PROFILE = {
    "gender": "male",        # male / female
    "age": 39,
    "height_cm": 178,
    "weight_kg": 78.5,
    "activity": 1.55,        # 娲诲姩绯绘暟锛氫箙鍧?.2 / 杞诲害1.375 / 涓害1.55 / 楂樺己搴?.725
    "target_weight_kg": 75.0,
    "target_date": "2027-01-09",   # 鐩爣鏃ユ湡锛?涓湀鍚庯級
}

# 甯歌椋熺墿鐑噺搴擄紙kcal / 100g 鎴?/涓級锛岀敤浜庢墜鍔ㄥ綍鍏ヤ笌璇嗗埆鍏滃簳
FOOD_LIB = {
    "绫抽キ": 116, "棣掑ご": 223, "闈㈡潯": 110, "绮?: 46,
    "楦¤泲": 144, "楦¤兏鑲?: 133, "鐗涜倝": 125, "鐚倝": 143,
    "楸?: 105, "铏?: 93, "璞嗚厫": 82, "瑗垮叞鑺?: 36,
    "闈掕彍": 25, "鐣寗": 20, "榛勭摐": 16, "鑻规灉": 53,
    "棣欒晧": 93, "姗欏瓙": 48, "鐗涘ザ": 54, "閰稿ザ": 72,
    "璞嗘祮": 31, "闈㈠寘": 313, "铔嬬硶": 348, "钖潯": 298,
    "姹夊牎": 295, "鎶惃": 235, "鍙箰": 43, "濂惰尪": 60,
}

# 杩愬姩 MET 鍊硷紙浠ｈ阿褰撻噺锛宬cal/kg/h锛?EXERCISE_MET = {
    "姝ヨ": 3.5, "蹇蛋": 4.3, "鎱㈣窇": 7.0, "璺戞": 9.8,
    "楠戣": 6.8, "娓告吵": 8.0, "璺崇怀": 11.0, "HIIT": 8.0,
    "鍔涢噺璁粌": 5.0, "鐟滀冀": 3.0, "缇芥瘺鐞?: 5.5, "绡悆": 6.5,
    "瓒崇悆": 7.0, "鐖ゼ姊?: 8.0, "妞渾鏈?: 5.0, "鍒掕埞鏈?: 7.0,
}


# ---------------------------------------------------------------------------
# 鏁版嵁搴?# ---------------------------------------------------------------------------

class DB:
    def __init__(self):
        self.conn = sqlite3.connect(self.db_path())
        self.init()

    @staticmethod
    def db_path():
        if platform == "android":
            from android.storage import app_storage_dir
            d = app_storage_dir()
        else:
            d = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(d, "fitness.db")

    def init(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS meals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, time TEXT, meal_type TEXT,
            desc TEXT, kcal REAL, protein REAL, fat REAL, carb REAL,
            photo TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS exercises(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, time TEXT, ex_type TEXT, minutes REAL,
            kcal REAL, note TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS profile(
            key TEXT PRIMARY KEY, value TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS weights(
            date TEXT PRIMARY KEY, weight REAL)""")
        self.conn.commit()

    # ---- profile ----
    def get_profile(self):
        prof = dict(DEFAULT_PROFILE)
        for row in self.conn.execute("SELECT key,value FROM profile"):
            prof[row[0]] = row[1]
        # 绫诲瀷杩樺師
        for k in ("age", "height_cm", "weight_kg", "activity", "target_weight_kg"):
            try:
                prof[k] = float(prof[k])
            except Exception:
                prof[k] = DEFAULT_PROFILE[k]
        return prof

    def save_profile(self, prof):
        for k, v in prof.items():
            self.conn.execute(
                "INSERT OR REPLACE INTO profile(key,value) VALUES(?,?)", (k, str(v)))
        self.conn.commit()

    # ---- meals ----
    def add_meal(self, m):
        self.conn.execute(
            "INSERT INTO meals(date,time,meal_type,desc,kcal,protein,fat,carb,photo)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (m["date"], m["time"], m["meal_type"], m["desc"], m["kcal"],
             m["protein"], m["fat"], m["carb"], m.get("photo", "")))
        self.conn.commit()

    def meals_by_date(self, date):
        return self.conn.execute(
            "SELECT * FROM meals WHERE date=? ORDER BY time", (date,)).fetchall()

    # ---- exercises ----
    def add_exercise(self, e):
        self.conn.execute(
            "INSERT INTO exercises(date,time,ex_type,minutes,kcal,note)"
            " VALUES(?,?,?,?,?,?)",
            (e["date"], e["time"], e["ex_type"], e["minutes"], e["kcal"], e.get("note", "")))
        self.conn.commit()

    def exercises_by_date(self, date):
        return self.conn.execute(
            "SELECT * FROM exercises WHERE date=? ORDER BY time", (date,)).fetchall()

    # ---- weights ----
    def set_weight(self, date, w):
        self.conn.execute(
            "INSERT OR REPLACE INTO weights(date,weight) VALUES(?,?)", (date, w))
        self.conn.commit()

    def latest_weight(self):
        row = self.conn.execute(
            "SELECT date,weight FROM weights ORDER BY date DESC LIMIT 1").fetchone()
        return row


# ---------------------------------------------------------------------------
# 璁＄畻閫昏緫
# ---------------------------------------------------------------------------

def calc_bmr(prof):
    """Mifflin-St Jeor 鍏紡"""
    if prof["gender"] == "female":
        return 10 * prof["weight_kg"] + 6.25 * prof["height_cm"] - 5 * prof["age"] - 161
    return 10 * prof["weight_kg"] + 6.25 * prof["height_cm"] - 5 * prof["age"] + 5


def calc_tdee(prof):
    return calc_bmr(prof) * prof["activity"]


def calc_target_calories(prof):
    """鎸夌洰鏍囦綋閲嶄笌鐩爣鏃ユ湡鎺ㄧ畻姣忔棩鐑噺棰勭畻锛堟俯鍜岀己鍙ｏ紝涓嶆瀬绔級"""
    tdee = calc_tdee(prof)
    today = datetime.date.today()
    try:
        target_d = datetime.date.fromisoformat(str(prof["target_date"]))
    except Exception:
        target_d = today + datetime.timedelta(days=90)
    days = max((target_d - today).days, 1)
    need_loss = max(prof["weight_kg"] - prof["target_weight_kg"], 0.0)
    # 姣忓叕鏂よ剛鑲害 7700 kcal
    daily_deficit = need_loss * 7700 / days
    # 缂哄彛涓婇檺涓嶈秴杩?TDEE 鐨?25%锛岄伩鍏嶆瀬绔?    daily_deficit = min(daily_deficit, tdee * 0.25)
    return tdee - daily_deficit, tdee, daily_deficit


def calc_protein_target(prof):
    """鍑忚剛鏈熻泲鐧借川鐩爣锛?.6~2.0 g/kg 浣撻噸"""
    return round(prof["weight_kg"] * 1.8, 1)


def calc_exercise_kcal(met, minutes, weight_kg):
    """MET 鍏紡锛歬cal = MET * 浣撻噸(kg) * 灏忔椂鏁?""
    return round(met * weight_kg * (minutes / 60.0), 1)


def estimate_food_kcal(food_name, grams=100):
    """鎸夐鐗╁簱浼扮畻鐑噺"""
    for k, v in FOOD_LIB.items():
        if k in food_name:
            return round(v * grams / 100.0, 1)
    return None


# ---------------------------------------------------------------------------
# 鐧惧害 AI 椋熺墿璇嗗埆
# ---------------------------------------------------------------------------

# 鐧惧害 access_token 鏈夋晥鏈熺害 30 澶╋紝缂撳瓨鍒板唴瀛橀伩鍏嶆瘡娆¤瘑鍒兘閲嶆柊鎹㈠彇
_BAIDU_TOKEN_CACHE = {"token": None, "expires_at": 0}


class BaiduError(Exception):
    """鐧惧害璇嗗埆涓氬姟閿欒锛宮essage 涓哄彲鐩存帴灞曠ず缁欑敤鎴风殑涓枃鎻愮ず"""
    pass


def baidu_token(force=False):
    """鑾峰彇鐧惧害 access_token锛堝甫缂撳瓨锛宼oken 杩囨湡鍓?1 澶╄嚜鍔ㄥ埛鏂帮級"""
    import time
    now = time.time()
    if not force and _BAIDU_TOKEN_CACHE["token"] and now < _BAIDU_TOKEN_CACHE["expires_at"]:
        return _BAIDU_TOKEN_CACHE["token"]

    params = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": BAIDU_API_KEY,
        "client_secret": BAIDU_SECRET_KEY,
    })
    req = urllib.request.Request(BAIDU_TOKEN_URL + "?" + params)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        raise BaiduError("缃戠粶寮傚父锛屾棤娉曡繛鎺ョ櫨搴︽湇鍔★細%s" % e)

    if "access_token" not in data:
        err = data.get("error_description") or data.get("error") or "鏈煡閿欒"
        raise BaiduError("鑾峰彇鐧惧害鎺堟潈澶辫触锛?s锛堣妫€鏌?API Key / Secret Key 鏄惁姝ｇ‘锛? % err)

    expires_in = int(data.get("expires_in", 2592000))
    _BAIDU_TOKEN_CACHE["token"] = data["access_token"]
    # 鎻愬墠 1 澶╄繃鏈燂紝閬垮厤涓寸晫澶辨晥
    _BAIDU_TOKEN_CACHE["expires_at"] = now + expires_in - 86400
    return _BAIDU_TOKEN_CACHE["token"]


def recognize_food(image_path):
    """璋冪敤鐧惧害鍥惧儚璇嗗埆-鑿滃搧璇嗗埆锛岃繑鍥?[(鑿滃悕, 缃俊搴?, ...]

    鎶涘嚭 BaiduError锛堜腑鏂囨彁绀猴級鎴?RuntimeError锛堟湭閰嶇疆 Key锛夈€?    """
    if not (BAIDU_API_KEY and BAIDU_SECRET_KEY):
        raise RuntimeError("鏈厤缃櫨搴PI Key")

    token = baidu_token()
    with open(image_path, "rb") as f:
        img = f.read()

    boundary = "----fitboundary"
    body = (
        "--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.jpg\""
        "\r\nContent-Type: application/octet-stream\r\n\r\n" % boundary
    ).encode() + img + ("\r\n--%s--\r\n" % boundary).encode()

    req = urllib.request.Request(
        BAIDU_FOOD_URL + "?access_token=" + token, data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})

    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        raise BaiduError("缃戠粶寮傚父锛岃瘑鍒け璐ワ細%s" % e)

    # 鐧惧害杩斿洖閿欒鐮佹椂鍒嗙被澶勭悊
    if "error_code" in data:
        code = data["error_code"]
        if code in (110, 111):          # token 澶辨晥/杩囨湡
            try:
                token = baidu_token(force=True)   # 寮哄埗鍒锋柊鍚庨噸璇曚竴娆?                req = urllib.request.Request(
                    BAIDU_FOOD_URL + "?access_token=" + token, data=body,
                    headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read().decode())
                if "error_code" in data:
                    raise BaiduError("璇嗗埆鏈嶅姟寮傚父锛?s锛夛細%s" % (data["error_code"], data.get("error_msg", "")))
            except BaiduError:
                raise
            except Exception as e:
                raise BaiduError("缃戠粶寮傚父锛岃瘑鍒け璐ワ細%s" % e)
        elif code == 17:                # QPS 瓒呴檺
            raise BaiduError("璇锋眰杩囦簬棰戠箒锛堝厤璐圭増姣忕闄?2 娆★級锛岃绋嶅悗鍐嶈瘯")
        elif code == 18:                # 閰嶉鑰楀敖
            raise BaiduError("鏈湀鍏嶈垂璇嗗埆棰濆害宸茬敤瀹岋紝璇峰埌鐧惧害鏅鸿兘浜戞煡鐪嬮厤棰?)
        elif code == 4:                 # 璇锋眰瓒呴檺
            raise BaiduError("浠婃棩璇嗗埆娆℃暟宸茶揪涓婇檺锛岃鏄庡ぉ鍐嶈瘯")
        else:
            raise BaiduError("璇嗗埆澶辫触锛?s锛夛細%s" % (code, data.get("error_msg", "")))

    results = []
    for item in data.get("result", []):
        results.append((item.get("name", ""), item.get("probability", 0)))
    return results


# 浠介噺鍗曚綅鎹㈢畻锛氭妸"纰?涓?浠?鐩?绛夊彛璇唤閲忔姌绠楁垚鍏嬶紙鐢ㄤ簬鐑噺浼扮畻锛?PORTION_TO_GRAMS = {
    "纰?: 200, "灏忕": 150, "澶х": 300, "鐩?: 250, "纰?: 150,
    "浠?: 200, "涓?: 100, "鍙?: 100, "鐗?: 30, "鍧?: 50,
    "鍕?: 20, "鏉?: 250, "鐡?: 330, "鐩?: 250, "涓?: 80,
}


def parse_portion(amount_text):
    """瑙ｆ瀽浠介噺鏂囨湰锛岃繑鍥?(鍏嬫暟, 鍗曚綅)銆傚 1纰?-> (200, 纰?锛?50g -> (150, g)"""
    amount_text = (amount_text or "").strip()
    if not amount_text:
        return 100, "g"   # 榛樿 100g
    # 鏀寔 "150g" / "150鍏? / "1纰? / "鍗婄" / "2涓?
    import re
    m = re.match(r"^([\d.]+)\s*(g|鍏??$", amount_text)
    if m:
        return float(m.group(1)), "g"
    m = re.match(r"^(鍗妡涓€|涓[涓€浜屼笁鍥涗簲鍏竷鍏節鍗乗d.]+)\s*(纰梶灏忕|澶х|鐩榺纰焲浠絴涓獆鍙獆鐗噟鍧梶鍕簗鏉瘄鐡秥鐩抾涓?$", amount_text)
    if m:
        num_word, unit = m.group(1), m.group(2)
        num_map = {"鍗?: 0.5, "涓€": 1, "涓?: 2, "涓?: 3, "鍥?: 4, "浜?: 5,
                   "鍏?: 6, "涓?: 7, "鍏?: 8, "涔?: 9, "鍗?: 10}
        n = num_map.get(num_word, float(num_word) if num_word.replace(".", "").isdigit() else 1)
        grams = PORTION_TO_GRAMS.get(unit, 100) * n
        return grams, unit
    return 100, "g"


def estimate_food_kcal_by_amount(food_name, amount_text="100g"):
    """鎸変唤閲忎及绠楅鐗╃儹閲忥細杩斿洖 (kcal, 鍏嬫暟, 鍗曚綅)"""
    grams, unit = parse_portion(amount_text)
    kcal_per_100 = estimate_food_kcal(food_name)
    if kcal_per_100 is None:
        return None, grams, unit
    return round(kcal_per_100 * grams / 100.0, 1), grams, unit
# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class Root(TabbedPanel):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.do_default_tab = False
        self.tab_pos = "top_mid"
        self.db = DB()
        self.current_photo = None

        self.add_widget(TabbedPanelItem(text="棣栭〉", content=self.build_home()))
        self.add_widget(TabbedPanelItem(text="璁伴ギ椋?, content=self.build_meal()))
        self.add_widget(TabbedPanelItem(text="璁拌繍鍔?, content=self.build_exercise()))
        self.add_widget(TabbedPanelItem(text="鐩爣", content=self.build_goal()))
        self.add_widget(TabbedPanelItem(text="璁板綍", content=self.build_history()))

    # ---------- 閫氱敤缁勪欢 ----------
    @staticmethod
    def hline():
        return Label(text="-" * 60, size_hint_y=None, height=20)

    @staticmethod
    def section(title):
        return Label(text="[b]%s[/b]" % title, markup=True,
                     size_hint_y=None, height=34, color=(0.2, 0.7, 0.4, 1))

    # ---------- 棣栭〉 ----------
    def build_home(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        scroll = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=8)
        inner.bind(minimum_height=inner.setter("height"))
        self.home_label = Label(size_hint_y=None, markup=True, halign="left",
                                valign="top", text_size=(Window.width - 60, None))
        self.home_label.bind(texture_size=lambda *a: setattr(
            self.home_label, "height", self.home_label.texture_size[1]))
        btn_refresh = Button(text="鍒锋柊浠婃棩姒傝", size_hint_y=None, height=48)
        btn_refresh.bind(on_release=lambda *a: self.refresh_home())
        inner.add_widget(self.home_label)
        inner.add_widget(btn_refresh)
        scroll.add_widget(inner)
        box.add_widget(scroll)
        return box

    def refresh_home(self):
        prof = self.db.get_profile()
        today = datetime.date.today().isoformat()
        meals = self.db.meals_by_date(today)
        exes = self.db.exercises_by_date(today)
        intake = sum(m[5] for m in meals)
        burn = sum(e[5] for e in exes)
        target_cal, tdee, deficit = calc_target_calories(prof)
        protein_target = calc_protein_target(prof)
        protein = sum(m[6] for m in meals)
        net = intake - burn
        remain = target_cal - net

        lw = self.db.latest_weight()
        w_str = "%s %.1f kg" % (lw[0], lw[1]) if lw else "鏈褰?

        txt = (
            "[b]浠婃棩 %s[/b]\n\n"
            "馃崥 宸叉憚鍏ワ細%.0f kcal锛?d 椁愶級\n"
            "馃弮 宸叉秷鑰楋細%.0f kcal锛?d 娆¤繍鍔級\n"
            "鈿栵笍 鍑€鎽勫叆锛?.0f kcal\n\n"
            "馃幆 浠婃棩鐑噺棰勭畻锛?.0f kcal锛圱DEE %.0f锛岀己鍙?%.0f锛塡n"
            "馃ォ 铔嬬櫧璐細%.1f / %.1f g\n"
            "馃搲 鍓╀綑鍙憚鍏ワ細%.0f kcal\n\n"
            "鈿栵笍 鏈€鏂颁綋閲嶏細%s\n"
            "鐩爣锛?.1f kg锛?s锛?
        ) % (today, intake, len(meals), burn, len(exes), net,
             target_cal, tdee, deficit, protein, protein_target, remain,
             w_str, prof["target_weight_kg"], prof["target_date"])
        self.home_label.text = txt

    # ---------- 璁伴ギ椋?----------
    def build_meal(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        box.add_widget(self.section("鎷嶇収浼扮畻鐑噺"))

        row1 = BoxLayout(size_hint_y=None, height=48, spacing=8)
        btn_photo = Button(text="馃摲 鎷嶇収/閫夊浘")
        btn_photo.bind(on_release=lambda *a: self.pick_photo())
        btn_manual = Button(text="鉁嶏笍 鎵嬪姩褰曞叆")
        btn_manual.bind(on_release=lambda *a: self.manual_meal_popup())
        row1.add_widget(btn_photo)
        row1.add_widget(btn_manual)
        box.add_widget(row1)

        self.photo_preview = KivyImage(size_hint_y=None, height=180, allow_stretch=True,
                                       keep_ratio=True)
        box.add_widget(self.photo_preview)

        self.meal_result = Label(text="璇嗗埆缁撴灉灏嗘樉绀哄湪杩欓噷", size_hint_y=None,
                                 height=120, markup=True, halign="left",
                                 valign="top", text_size=(Window.width - 60, None))
        self.meal_result.bind(texture_size=lambda *a: setattr(
            self.meal_result, "height", self.meal_result.texture_size[1]))
        box.add_widget(self.meal_result)

        row2 = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.meal_spinner = Spinner(text="鍗堥", values=("鏃╅", "鍗堥", "鍔犻", "鏅氶", "澶滃"))
        row2.add_widget(self.meal_spinner)
        box.add_widget(row2)
        return box

    def pick_photo(self):
        if not HAS_PLYER:
            self.toast("褰撳墠鐜涓嶆敮鎸侀€夊浘锛岃鐢ㄦ墜鍔ㄥ綍鍏?)
            return
        try:
            filechooser.open_file(on_selection=self.on_photo_selected,
                                  filters=[("Images", "*.png", "*.jpg", "*.jpeg")])
        except Exception as e:
            self.toast("閫夊浘澶辫触锛?s" % e)

    def on_photo_selected(self, selection):
        if not selection:
            return
        path = selection[0]
        self.current_photo = path
        try:
            self.photo_preview.source = path
        except Exception:
            pass
        self.meal_result.text = "姝ｅ湪璇嗗埆椋熺墿鈥?
        threading.Thread(target=self._recognize_thread, args=(path,), daemon=True).start()

    def _recognize_thread(self, path):
        try:
            foods = recognize_food(path)
            if not foods:
                self._set_meal_result("鏈兘璇嗗埆鍑洪鐗╋紝璇锋墜鍔ㄥ綍鍏ャ€?)
                return
            # 淇濆瓨璇嗗埆缁撴灉锛屼緵纭琛ㄥ崟浣跨敤
            self._last_foods = foods
            lines = []
            for name, prob in foods[:5]:
                kcal = estimate_food_kcal(name)
                if kcal:
                    lines.append("%s锛?.0f%%锛夆増 %.0f kcal/100g" % (name, prob * 100, kcal))
                else:
                    lines.append("%s锛?.0f%%锛夆€?鏈敹褰曪紝璇锋墜鍔ㄥ綍鍏? % (name, prob * 100))
            self._set_meal_result(
                "璇嗗埆鍒帮細\n" + "\n".join(lines) +
                "\n\n[b]鐐瑰嚮涓嬫柟銆岀‘璁や唤閲忋€嶉€愰」鏍稿鍚庝繚瀛榌/b]")
            # 寮瑰嚭鍙紪杈戠殑浠介噺纭琛ㄥ崟
            self._show_confirm_popup(foods)
        except BaiduError as e:
            self._set_meal_result("璇嗗埆澶辫触锛?s\n璇锋墜鍔ㄥ綍鍏ャ€? % e)
        except RuntimeError as e:
            self._set_meal_result("璇嗗埆澶辫触锛?s\n璇锋墜鍔ㄥ綍鍏ャ€? % e)
        except Exception as e:
            self._set_meal_result("璇嗗埆澶辫触锛?s\n璇锋墜鍔ㄥ綍鍏ャ€? % e)

    def _show_confirm_popup(self, foods):
        """寮瑰嚭鍙紪杈戜唤閲忕殑纭琛ㄥ崟锛岄€愰」鏍稿鍚庝繚瀛?""
        content = BoxLayout(orientation="vertical", spacing=6, padding=10)
        tip = Label(text="璇锋牳瀵规瘡鏍烽鐗╃殑浠介噺锛堝彲淇敼锛夛紝灏嗘寜浠介噺绮剧‘浼扮畻鐑噺",
                    size_hint_y=None, height=30, color=(0.3, 0.3, 0.3, 1))
        content.add_widget(tip)

        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(cols=3, size_hint_y=None, spacing=6, row_default_height=44)
        grid.bind(minimum_height=grid.setter("height"))

        # 琛ㄥご
        grid.add_widget(Label(text="椋熺墿", bold=True))
        grid.add_widget(Label(text="浠介噺", bold=True))
        grid.add_widget(Label(text="鐑噺kcal", bold=True))

        self._food_inputs = []
        total = 0.0
        for name, prob in foods[:5]:
            kcal_per_100 = estimate_food_kcal(name)
            grid.add_widget(Label(text="%s" % name))
            ti = TextInput(text="100g", multiline=False, hint_text="濡?1纰?150g")
            grid.add_widget(ti)
            if kcal_per_100:
                lbl = Label(text="%.0f/100g" % kcal_per_100)
                total += kcal_per_100
            else:
                lbl = Label(text="鏈敹褰?, color=(0.8, 0.3, 0.3, 1))
            grid.add_widget(lbl)
            self._food_inputs.append({"name": name, "ti": ti, "kcal_per_100": kcal_per_100})

        scroll.add_widget(grid)
        content.add_widget(scroll)

        self._confirm_total = Label(text="鍚堣锛氱害 %.0f kcal" % total,
                                    size_hint_y=None, height=34, bold=True)
        content.add_widget(self._confirm_total)

        popup = Popup(title="纭浠介噺", content=content, size_hint=(0.95, 0.85))
        self._confirm_popup = popup

        def recalc(*a):
            tot = 0.0
            for item in self._food_inputs:
                if item["kcal_per_100"] is None:
                    continue
                grams, _ = parse_portion(item["ti"].text)
                tot += item["kcal_per_100"] * grams / 100.0
            self._confirm_total.text = "鍚堣锛氱害 %.0f kcal" % tot

        def ok(*a):
            # 鎸夌敤鎴峰～鍐欑殑浠介噺绮剧‘璁＄畻骞朵繚瀛?            desc_parts = []
            total_kcal = 0.0
            for item in self._food_inputs:
                if item["kcal_per_100"] is None:
                    desc_parts.append("%s(鏈敹褰?" % item["name"])
                    continue
                grams, unit = parse_portion(item["ti"].text)
                kcal = item["kcal_per_100"] * grams / 100.0
                total_kcal += kcal
                desc_parts.append("%s%s(%dg)" % (item["name"], item["ti"].text.strip() or "100g", grams))
            desc = "+".join(desc_parts)
            self._save_meal(desc, total_kcal,
                            protein=total_kcal * 0.048, fat=total_kcal * 0.036,
                            carb=total_kcal * 0.052, photo=self.current_photo)
            popup.dismiss()

        btns = BoxLayout(size_hint_y=None, height=50, spacing=8)
        b_ok = Button(text="鉁?淇濆瓨杩欓")
        b_ok.bind(on_release=ok)
        b_cancel = Button(text="鍙栨秷")
        b_cancel.bind(on_release=lambda *a: popup.dismiss())
        btns.add_widget(b_ok)
        btns.add_widget(b_cancel)
        content.add_widget(btns)

        # 浠介噺鍙樺寲鏃跺疄鏃堕噸绠楀悎璁?        for item in self._food_inputs:
            item["ti"].bind(text=recalc)

        popup.open()

    def _set_meal_result(self, text):
        def upd():
            self.meal_result.text = text
        try:
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: upd(), 0)
        except Exception:
            upd()

    def manual_meal_popup(self):
        content = BoxLayout(orientation="vertical", spacing=8, padding=10)
        ti_desc = TextInput(hint_text="椋熺墿鎻忚堪锛屽锛氱背楗?纰?楦¤兏鑲?50g+瑗垮叞鑺?, multiline=False)
        ti_kcal = TextInput(hint_text="鐑噺 kcal锛堝彲鐣欑┖鑷姩浼扮畻锛?, multiline=False,
                            input_filter="float")
        content.add_widget(ti_desc)
        content.add_widget(ti_kcal)
        popup = Popup(title="鎵嬪姩褰曞叆楗", content=content, size_hint=(0.9, 0.5))

        def ok(*a):
            desc = ti_desc.text.strip()
            if not desc:
                self.toast("璇疯緭鍏ラ鐗╂弿杩?)
                return
            kcal = None
            if ti_kcal.text:
                kcal = float(ti_kcal.text)
            else:
                # 灏濊瘯鎸夐鐗╁簱浼扮畻
                est = 0.0
                for k, v in FOOD_LIB.items():
                    if k in desc:
                        est += v
                kcal = est if est > 0 else 300.0
            self._save_meal(desc, kcal, protein=kcal * 0.045, fat=kcal * 0.035,
                            carb=kcal * 0.055)
            popup.dismiss()

        btns = BoxLayout(size_hint_y=None, height=48, spacing=8)
        b_ok = Button(text="淇濆瓨")
        b_ok.bind(on_release=ok)
        b_cancel = Button(text="鍙栨秷")
        b_cancel.bind(on_release=lambda *a: popup.dismiss())
        btns.add_widget(b_ok)
        btns.add_widget(b_cancel)
        content.add_widget(btns)
        popup.open()

    def _save_meal(self, desc, kcal, protein, fat, carb, photo=""):
        now = datetime.datetime.now()
        self.db.add_meal({
            "date": now.date().isoformat(),
            "time": now.strftime("%H:%M"),
            "meal_type": self.meal_spinner.text,
            "desc": desc, "kcal": kcal, "protein": protein,
            "fat": fat, "carb": carb, "photo": photo,
        })
        self.toast("宸茶褰曪細%.0f kcal" % kcal)
        self.refresh_home()

    # ---------- 璁拌繍鍔?----------
    def build_exercise(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        box.add_widget(self.section("璁板綍杩愬姩"))
        row1 = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.ex_spinner = Spinner(text="鎱㈣窇", values=sorted(EXERCISE_MET.keys()))
        self.ex_min = TextInput(hint_text="鏃堕暱(鍒嗛挓)", multiline=False, input_filter="float")
        row1.add_widget(self.ex_spinner)
        row1.add_widget(self.ex_min)
        box.add_widget(row1)
        self.ex_note = TextInput(hint_text="澶囨敞锛堝彲閫夛級", multiline=False, size_hint_y=None, height=44)
        box.add_widget(self.ex_note)
        self.ex_result = Label(text="", size_hint_y=None, height=60, markup=True)
        box.add_widget(self.ex_result)
        btn = Button(text="鉁?淇濆瓨杩愬姩", size_hint_y=None, height=48)
        btn.bind(on_release=lambda *a: self.save_exercise())
        box.add_widget(btn)
        return box

    def save_exercise(self):
        prof = self.db.get_profile()
        try:
            minutes = float(self.ex_min.text)
        except Exception:
            self.toast("璇疯緭鍏ユ湁鏁堟椂闀?)
            return
        met = EXERCISE_MET[self.ex_spinner.text]
        kcal = calc_exercise_kcal(met, minutes, prof["weight_kg"])
        now = datetime.datetime.now()
        self.db.add_exercise({
            "date": now.date().isoformat(), "time": now.strftime("%H:%M"),
            "ex_type": self.ex_spinner.text, "minutes": minutes,
            "kcal": kcal, "note": self.ex_note.text,
        })
        self.ex_result.text = "[b]%s %s 鍒嗛挓 鈮?%.0f kcal[/b]" % (
            self.ex_spinner.text, minutes, kcal)
        self.toast("宸茶褰曡繍鍔?%.0f kcal" % kcal)
        self.refresh_home()

    # ---------- 鐩爣 ----------
    def build_goal(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        scroll = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=8)
        inner.bind(minimum_height=inner.setter("height"))

        prof = self.db.get_profile()
        self.goal_label = Label(size_hint_y=None, markup=True, halign="left",
                                valign="top", text_size=(Window.width - 60, None))
        self.goal_label.bind(texture_size=lambda *a: setattr(
            self.goal_label, "height", self.goal_label.texture_size[1]))

        inner.add_widget(self.section("鎴戠殑鐩爣"))
        inner.add_widget(self.goal_label)

        inner.add_widget(self.section("淇敼璧勬枡"))
        grid = GridLayout(cols=2, size_hint_y=None, height=320, spacing=6)
        fields = [
            ("鎬у埆", "gender"), ("骞撮緞", "age"), ("韬珮cm", "height_cm"),
            ("褰撳墠浣撻噸kg", "weight_kg"), ("鐩爣浣撻噸kg", "target_weight_kg"),
            ("鐩爣鏃ユ湡", "target_date"),
        ]
        self.inputs = {}
        for label, key in fields:
            grid.add_widget(Label(text=label))
            ti = TextInput(text=str(prof[key]), multiline=False)
            self.inputs[key] = ti
            grid.add_widget(ti)
        inner.add_widget(grid)

        btn_save = Button(text="馃捑 淇濆瓨璧勬枡骞堕噸绠?, size_hint_y=None, height=48)
        btn_save.bind(on_release=lambda *a: self.save_goal())
        inner.add_widget(btn_save)

        btn_weight = Button(text="鈿栵笍 璁板綍浠婃棩浣撻噸", size_hint_y=None, height=48)
        btn_weight.bind(on_release=lambda *a: self.weight_popup())
        inner.add_widget(btn_weight)

        scroll.add_widget(inner)
        box.add_widget(scroll)
        return box

    def refresh_goal(self):
        prof = self.db.get_profile()
        target_cal, tdee, deficit = calc_target_calories(prof)
        protein = calc_protein_target(prof)
        bmr = calc_bmr(prof)
        lw = self.db.latest_weight()
        w_str = "%s %.1f kg" % (lw[0], lw[1]) if lw else "鏈褰?
        self.goal_label.text = (
            "鍩虹浠ｈ阿 BMR锛?.0f kcal\n"
            "姣忔棩娑堣€?TDEE锛?.0f kcal\n"
            "姣忔棩鐑噺棰勭畻锛?.0f kcal锛堢己鍙?%.0f锛塡n"
            "铔嬬櫧璐ㄧ洰鏍囷細%.1f g/澶‐n\n"
            "褰撳墠浣撻噸锛?.1f kg\n"
            "鏈€鏂拌褰曪細%s\n"
            "鐩爣浣撻噸锛?.1f kg锛?s锛塡n\n"
            "[b]寮曞[/b]锛歕n"
            "鈥?姣忛鎺у埗鍦ㄩ绠楃殑 1/3 宸﹀彸\n"
            "鈥?浼樺厛楂樿泲鐧姐€侀珮绾ょ淮椋熺墿\n"
            "鈥?姣忓ぉ 30 鍒嗛挓浠ヤ笂涓己搴﹁繍鍔╘n"
            "鈥?姣忓懆鍑忛噸 0.5~1 kg 涓哄疁锛屽嬁鏋佺鑺傞"
        ) % (bmr, tdee, target_cal, deficit, protein,
             prof["weight_kg"], w_str, prof["target_weight_kg"], prof["target_date"])

    def save_goal(self):
        prof = self.db.get_profile()
        try:
            prof["gender"] = self.inputs["gender"].text.strip() or "male"
            prof["age"] = float(self.inputs["age"].text)
            prof["height_cm"] = float(self.inputs["height_cm"].text)
            prof["weight_kg"] = float(self.inputs["weight_kg"].text)
            prof["target_weight_kg"] = float(self.inputs["target_weight_kg"].text)
            prof["target_date"] = self.inputs["target_date"].text.strip()
        except Exception:
            self.toast("杈撳叆鏈夎锛岃妫€鏌ユ暟瀛?)
            return
        self.db.save_profile(prof)
        self.toast("宸蹭繚瀛樺苟閲嶇畻鐩爣")
        self.refresh_goal()
        self.refresh_home()

    def weight_popup(self):
        content = BoxLayout(orientation="vertical", spacing=8, padding=10)
        ti = TextInput(hint_text="浠婃棩浣撻噸 kg", multiline=False, input_filter="float")
        content.add_widget(ti)
        popup = Popup(title="璁板綍浣撻噸", content=content, size_hint=(0.9, 0.4))
        def ok(*a):
            try:
                w = float(ti.text)
            except Exception:
                self.toast("璇疯緭鍏ユ湁鏁堜綋閲?)
                return
            self.db.set_weight(datetime.date.today().isoformat(), w)
            self.toast("宸茶褰?%.1f kg" % w)
            popup.dismiss()
            self.refresh_goal()
            self.refresh_home()
        btns = BoxLayout(size_hint_y=None, height=48, spacing=8)
        b1 = Button(text="淇濆瓨"); b1.bind(on_release=ok)
        b2 = Button(text="鍙栨秷"); b2.bind(on_release=lambda *a: popup.dismiss())
        btns.add_widget(b1); btns.add_widget(b2)
        content.add_widget(btns)
        popup.open()

    # ---------- 璁板綍 ----------
    def build_history(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        box.add_widget(self.section("鍘嗗彶璁板綍"))
        row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.hist_date = TextInput(text=datetime.date.today().isoformat(),
                                   multiline=False)
        btn = Button(text="鏌ヨ")
        btn.bind(on_release=lambda *a: self.show_history())
        row.add_widget(self.hist_date)
        row.add_widget(btn)
        box.add_widget(row)
        scroll = ScrollView()
        self.hist_label = Label(size_hint_y=None, markup=True, halign="left",
                                valign="top", text_size=(Window.width - 60, None))
        self.hist_label.bind(texture_size=lambda *a: setattr(
            self.hist_label, "height", self.hist_label.texture_size[1]))
        scroll.add_widget(self.hist_label)
        box.add_widget(scroll)
        return box

    def show_history(self):
        date = self.hist_date.text.strip()
        meals = self.db.meals_by_date(date)
        exes = self.db.exercises_by_date(date)
        lines = ["[b]%s[/b]" % date, "", "馃崥 楗锛?]
        mi = sum(m[5] for m in meals)
        for m in meals:
            lines.append("  %s %s锝?s锝?.0f kcal" % (m[2], m[3], m[4], m[5]))
        lines.append("  灏忚锛?.0f kcal" % mi)
        lines.append("", "馃弮 杩愬姩锛?)
        ei = sum(e[5] for e in exes)
        for e in exes:
            lines.append("  %s %s锝?.0f min锝?.0f kcal" % (e[2], e[3], e[4], e[5]))
        lines.append("  灏忚锛?.0f kcal" % ei)
        lines.append("", "鈿栵笍 鍑€鎽勫叆锛?.0f kcal" % (mi - ei))
        self.hist_label.text = "\n".join(lines)

    # ---------- 宸ュ叿 ----------
    def toast(self, msg):
        popup = Popup(title="鎻愮ず", content=Label(text=msg),
                      size_hint=(0.8, 0.3))
        popup.open()


class FitnessApp(App):
    def build(self):
        Window.clearcolor = (0.96, 0.96, 0.95, 1)
        root = Root()
        root.refresh_home()
        root.refresh_goal()
        return root


if __name__ == "__main__":
    FitnessApp().run()

