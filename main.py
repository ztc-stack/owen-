# -*- coding: utf-8 -*-
"""
健食管家 FitnessDiet Manager
一款安卓端饮食 + 健身管理 App
功能：
  1. 拍照/选图估算一餐热量（百度AI图像识别，可手动录入兜底）
  2. 记录运动量，按 MET 公式估算消耗卡路里与减脂进度
  3. 设定减重目标，按每日热量预算/蛋白质目标给出引导与提醒
数据本地存储（SQLite），无需联网也能用（识别功能需联网）。
"""

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
# 常量与配置
# ---------------------------------------------------------------------------

# 百度 AI 图像识别（食物识别）配置 —— 在此填入你自己的 API Key
BAIDU_API_KEY = ""       # 例如 "xxxx.yyyyy"
BAIDU_SECRET_KEY = ""    # 例如 "zzzz"
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_FOOD_URL = "https://aip.baidubce.com/rest/2.0/image-classify/v1/dish"

# 用户基础信息（可在 App 内修改）
DEFAULT_PROFILE = {
    "gender": "male",        # male / female
    "age": 39,
    "height_cm": 178,
    "weight_kg": 78.5,
    "activity": 1.55,        # 活动系数：久坐1.2 / 轻度1.375 / 中度1.55 / 高强度1.725
    "target_weight_kg": 75.0,
    "target_date": "2027-01-09",   # 目标日期（3个月后）
}

# 常见食物热量库（kcal / 100g 或 /个），用于手动录入与识别兜底
FOOD_LIB = {
    "米饭": 116, "馒头": 223, "面条": 110, "粥": 46,
    "鸡蛋": 144, "鸡胸肉": 133, "牛肉": 125, "猪肉": 143,
    "鱼": 105, "虾": 93, "豆腐": 82, "西兰花": 36,
    "青菜": 25, "番茄": 20, "黄瓜": 16, "苹果": 53,
    "香蕉": 93, "橙子": 48, "牛奶": 54, "酸奶": 72,
    "豆浆": 31, "面包": 313, "蛋糕": 348, "薯条": 298,
    "汉堡": 295, "披萨": 235, "可乐": 43, "奶茶": 60,
}

# 运动 MET 值（代谢当量，kcal/kg/h）
EXERCISE_MET = {
    "步行": 3.5, "快走": 4.3, "慢跑": 7.0, "跑步": 9.8,
    "骑行": 6.8, "游泳": 8.0, "跳绳": 11.0, "HIIT": 8.0,
    "力量训练": 5.0, "瑜伽": 3.0, "羽毛球": 5.5, "篮球": 6.5,
    "足球": 7.0, "爬楼梯": 8.0, "椭圆机": 5.0, "划船机": 7.0,
}


# ---------------------------------------------------------------------------
# 数据库
# ---------------------------------------------------------------------------

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
        # 类型还原
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
# 计算逻辑
# ---------------------------------------------------------------------------

def calc_bmr(prof):
    """Mifflin-St Jeor 公式"""
    if prof["gender"] == "female":
        return 10 * prof["weight_kg"] + 6.25 * prof["height_cm"] - 5 * prof["age"] - 161
    return 10 * prof["weight_kg"] + 6.25 * prof["height_cm"] - 5 * prof["age"] + 5


def calc_tdee(prof):
    return calc_bmr(prof) * prof["activity"]


def calc_target_calories(prof):
    """按目标体重与目标日期推算每日热量预算（温和缺口，不极端）"""
    tdee = calc_tdee(prof)
    today = datetime.date.today()
    try:
        target_d = datetime.date.fromisoformat(str(prof["target_date"]))
    except Exception:
        target_d = today + datetime.timedelta(days=90)
    days = max((target_d - today).days, 1)
    need_loss = max(prof["weight_kg"] - prof["target_weight_kg"], 0.0)
    # 每公斤脂肪约 7700 kcal
    daily_deficit = need_loss * 7700 / days
    # 缺口上限不超过 TDEE 的 25%，避免极端
    daily_deficit = min(daily_deficit, tdee * 0.25)
    return tdee - daily_deficit, tdee, daily_deficit


def calc_protein_target(prof):
    """减脂期蛋白质目标：1.6~2.0 g/kg 体重"""
    return round(prof["weight_kg"] * 1.8, 1)


def calc_exercise_kcal(met, minutes, weight_kg):
    """MET 公式：kcal = MET * 体重(kg) * 小时数"""
    return round(met * weight_kg * (minutes / 60.0), 1)


def estimate_food_kcal(food_name, grams=100):
    """按食物库估算热量"""
    for k, v in FOOD_LIB.items():
        if k in food_name:
            return round(v * grams / 100.0, 1)
    return None


# ---------------------------------------------------------------------------
# 百度 AI 食物识别
# ---------------------------------------------------------------------------

# 百度 access_token 有效期约 30 天，缓存到内存避免每次识别都重新换取
_BAIDU_TOKEN_CACHE = {"token": None, "expires_at": 0}


class BaiduError(Exception):
    """百度识别业务错误，message 为可直接展示给用户的中文提示"""
    pass


def baidu_token(force=False):
    """获取百度 access_token（带缓存，token 过期前 1 天自动刷新）"""
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
        raise BaiduError("网络异常，无法连接百度服务：%s" % e)

    if "access_token" not in data:
        err = data.get("error_description") or data.get("error") or "未知错误"
        raise BaiduError("获取百度授权失败：%s（请检查 API Key / Secret Key 是否正确）" % err)

    expires_in = int(data.get("expires_in", 2592000))
    _BAIDU_TOKEN_CACHE["token"] = data["access_token"]
    # 提前 1 天过期，避免临界失效
    _BAIDU_TOKEN_CACHE["expires_at"] = now + expires_in - 86400
    return _BAIDU_TOKEN_CACHE["token"]


def recognize_food(image_path):
    """调用百度图像识别-菜品识别，返回 [(菜名, 置信度), ...]

    抛出 BaiduError（中文提示）或 RuntimeError（未配置 Key）。
    """
    if not (BAIDU_API_KEY and BAIDU_SECRET_KEY):
        raise RuntimeError("未配置百度API Key")

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
        raise BaiduError("网络异常，识别失败：%s" % e)

    # 百度返回错误码时分类处理
    if "error_code" in data:
        code = data["error_code"]
        if code in (110, 111):          # token 失效/过期
            try:
                token = baidu_token(force=True)   # 强制刷新后重试一次
                req = urllib.request.Request(
                    BAIDU_FOOD_URL + "?access_token=" + token, data=body,
                    headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read().decode())
                if "error_code" in data:
                    raise BaiduError("识别服务异常（%s）：%s" % (data["error_code"], data.get("error_msg", "")))
            except BaiduError:
                raise
            except Exception as e:
                raise BaiduError("网络异常，识别失败：%s" % e)
        elif code == 17:                # QPS 超限
            raise BaiduError("请求过于频繁（免费版每秒限 2 次），请稍后再试")
        elif code == 18:                # 配额耗尽
            raise BaiduError("本月免费识别额度已用完，请到百度智能云查看配额")
        elif code == 4:                 # 请求超限
            raise BaiduError("今日识别次数已达上限，请明天再试")
        else:
            raise BaiduError("识别失败（%s）：%s" % (code, data.get("error_msg", "")))

    results = []
    for item in data.get("result", []):
        results.append((item.get("name", ""), item.get("probability", 0)))
    return results


# 份量单位换算：把"碗/个/份/盘"等口语份量折算成克（用于热量估算）
PORTION_TO_GRAMS = {
    "碗": 200, "小碗": 150, "大碗": 300, "盘": 250, "碟": 150,
    "份": 200, "个": 100, "只": 100, "片": 30, "块": 50,
    "勺": 20, "杯": 250, "瓶": 330, "盒": 250, "串": 80,
}


def parse_portion(amount_text):
    """解析份量文本，返回 (克数, 单位)。如 1碗 -> (200, 碗)；150g -> (150, g)"""
    amount_text = (amount_text or "").strip()
    if not amount_text:
        return 100, "g"   # 默认 100g
    # 支持 "150g" / "150克" / "1碗" / "半碗" / "2个"
    import re
    m = re.match(r"^([\d.]+)\s*(g|克)?$", amount_text)
    if m:
        return float(m.group(1)), "g"
    m = re.match(r"^(半|一|两|[一二三四五六七八九十\d.]+)\s*(碗|小碗|大碗|盘|碟|份|个|只|片|块|勺|杯|瓶|盒|串)$", amount_text)
    if m:
        num_word, unit = m.group(1), m.group(2)
        num_map = {"半": 0.5, "一": 1, "两": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        n = num_map.get(num_word, float(num_word) if num_word.replace(".", "").isdigit() else 1)
        grams = PORTION_TO_GRAMS.get(unit, 100) * n
        return grams, unit
    return 100, "g"


def estimate_food_kcal_by_amount(food_name, amount_text="100g"):
    """按份量估算食物热量：返回 (kcal, 克数, 单位)"""
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

        self.add_widget(TabbedPanelItem(text="首页", content=self.build_home()))
        self.add_widget(TabbedPanelItem(text="记饮食", content=self.build_meal()))
        self.add_widget(TabbedPanelItem(text="记运动", content=self.build_exercise()))
        self.add_widget(TabbedPanelItem(text="目标", content=self.build_goal()))
        self.add_widget(TabbedPanelItem(text="记录", content=self.build_history()))

    # ---------- 通用组件 ----------
    @staticmethod
    def hline():
        return Label(text="-" * 60, size_hint_y=None, height=20)

    @staticmethod
    def section(title):
        return Label(text="[b]%s[/b]" % title, markup=True,
                     size_hint_y=None, height=34, color=(0.2, 0.7, 0.4, 1))

    # ---------- 首页 ----------
    def build_home(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        scroll = ScrollView()
        inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=8)
        inner.bind(minimum_height=inner.setter("height"))
        self.home_label = Label(size_hint_y=None, markup=True, halign="left",
                                valign="top", text_size=(Window.width - 60, None))
        self.home_label.bind(texture_size=lambda *a: setattr(
            self.home_label, "height", self.home_label.texture_size[1]))
        btn_refresh = Button(text="刷新今日概览", size_hint_y=None, height=48)
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
        w_str = "%s %.1f kg" % (lw[0], lw[1]) if lw else "未记录"

        txt = (
            "[b]今日 %s[/b]\n\n"
            "🍚 已摄入：%.0f kcal（%d 餐）\n"
            "🏃 已消耗：%.0f kcal（%d 次运动）\n"
            "⚖️ 净摄入：%.0f kcal\n\n"
            "🎯 今日热量预算：%.0f kcal（TDEE %.0f，缺口 %.0f）\n"
            "🥩 蛋白质：%.1f / %.1f g\n"
            "📉 剩余可摄入：%.0f kcal\n\n"
            "⚖️ 最新体重：%s\n"
            "目标：%.1f kg（%s）"
        ) % (today, intake, len(meals), burn, len(exes), net,
             target_cal, tdee, deficit, protein, protein_target, remain,
             w_str, prof["target_weight_kg"], prof["target_date"])
        self.home_label.text = txt

    # ---------- 记饮食 ----------
    def build_meal(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        box.add_widget(self.section("拍照估算热量"))

        row1 = BoxLayout(size_hint_y=None, height=48, spacing=8)
        btn_photo = Button(text="📷 拍照/选图")
        btn_photo.bind(on_release=lambda *a: self.pick_photo())
        btn_manual = Button(text="✍️ 手动录入")
        btn_manual.bind(on_release=lambda *a: self.manual_meal_popup())
        row1.add_widget(btn_photo)
        row1.add_widget(btn_manual)
        box.add_widget(row1)

        self.photo_preview = KivyImage(size_hint_y=None, height=180, allow_stretch=True,
                                       keep_ratio=True)
        box.add_widget(self.photo_preview)

        self.meal_result = Label(text="识别结果将显示在这里", size_hint_y=None,
                                 height=120, markup=True, halign="left",
                                 valign="top", text_size=(Window.width - 60, None))
        self.meal_result.bind(texture_size=lambda *a: setattr(
            self.meal_result, "height", self.meal_result.texture_size[1]))
        box.add_widget(self.meal_result)

        row2 = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.meal_spinner = Spinner(text="午餐", values=("早餐", "午餐", "加餐", "晚餐", "夜宵"))
        row2.add_widget(self.meal_spinner)
        box.add_widget(row2)
        return box

    def pick_photo(self):
        if not HAS_PLYER:
            self.toast("当前环境不支持选图，请用手动录入")
            return
        try:
            filechooser.open_file(on_selection=self.on_photo_selected,
                                  filters=[("Images", "*.png", "*.jpg", "*.jpeg")])
        except Exception as e:
            self.toast("选图失败：%s" % e)

    def on_photo_selected(self, selection):
        if not selection:
            return
        path = selection[0]
        self.current_photo = path
        try:
            self.photo_preview.source = path
        except Exception:
            pass
        self.meal_result.text = "正在识别食物…"
        threading.Thread(target=self._recognize_thread, args=(path,), daemon=True).start()

    def _recognize_thread(self, path):
        try:
            foods = recognize_food(path)
            if not foods:
                self._set_meal_result("未能识别出食物，请手动录入。")
                return
            # 保存识别结果，供确认表单使用
            self._last_foods = foods
            lines = []
            for name, prob in foods[:5]:
                kcal = estimate_food_kcal(name)
                if kcal:
                    lines.append("%s（%.0f%%）≈ %.0f kcal/100g" % (name, prob * 100, kcal))
                else:
                    lines.append("%s（%.0f%%）— 未收录，请手动录入" % (name, prob * 100))
            self._set_meal_result(
                "识别到：\n" + "\n".join(lines) +
                "\n\n[b]点击下方「确认份量」逐项核对后保存[/b]")
            # 弹出可编辑的份量确认表单
            self._show_confirm_popup(foods)
        except BaiduError as e:
            self._set_meal_result("识别失败：%s\n请手动录入。" % e)
        except RuntimeError as e:
            self._set_meal_result("识别失败：%s\n请手动录入。" % e)
        except Exception as e:
            self._set_meal_result("识别失败：%s\n请手动录入。" % e)

    def _show_confirm_popup(self, foods):
        """弹出可编辑份量的确认表单，逐项核对后保存"""
        content = BoxLayout(orientation="vertical", spacing=6, padding=10)
        tip = Label(text="请核对每样食物的份量（可修改），将按份量精确估算热量",
                    size_hint_y=None, height=30, color=(0.3, 0.3, 0.3, 1))
        content.add_widget(tip)

        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(cols=3, size_hint_y=None, spacing=6, row_default_height=44)
        grid.bind(minimum_height=grid.setter("height"))

        # 表头
        grid.add_widget(Label(text="食物", bold=True))
        grid.add_widget(Label(text="份量", bold=True))
        grid.add_widget(Label(text="热量kcal", bold=True))

        self._food_inputs = []
        total = 0.0
        for name, prob in foods[:5]:
            kcal_per_100 = estimate_food_kcal(name)
            grid.add_widget(Label(text="%s" % name))
            ti = TextInput(text="100g", multiline=False, hint_text="如 1碗/150g")
            grid.add_widget(ti)
            if kcal_per_100:
                lbl = Label(text="%.0f/100g" % kcal_per_100)
                total += kcal_per_100
            else:
                lbl = Label(text="未收录", color=(0.8, 0.3, 0.3, 1))
            grid.add_widget(lbl)
            self._food_inputs.append({"name": name, "ti": ti, "kcal_per_100": kcal_per_100})

        scroll.add_widget(grid)
        content.add_widget(scroll)

        self._confirm_total = Label(text="合计：约 %.0f kcal" % total,
                                    size_hint_y=None, height=34, bold=True)
        content.add_widget(self._confirm_total)

        popup = Popup(title="确认份量", content=content, size_hint=(0.95, 0.85))
        self._confirm_popup = popup

        def recalc(*a):
            tot = 0.0
            for item in self._food_inputs:
                if item["kcal_per_100"] is None:
                    continue
                grams, _ = parse_portion(item["ti"].text)
                tot += item["kcal_per_100"] * grams / 100.0
            self._confirm_total.text = "合计：约 %.0f kcal" % tot

        def ok(*a):
            # 按用户填写的份量精确计算并保存
            desc_parts = []
            total_kcal = 0.0
            for item in self._food_inputs:
                if item["kcal_per_100"] is None:
                    desc_parts.append("%s(未收录)" % item["name"])
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
        b_ok = Button(text="✅ 保存这餐")
        b_ok.bind(on_release=ok)
        b_cancel = Button(text="取消")
        b_cancel.bind(on_release=lambda *a: popup.dismiss())
        btns.add_widget(b_ok)
        btns.add_widget(b_cancel)
        content.add_widget(btns)

        # 份量变化时实时重算合计
        for item in self._food_inputs:
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
        ti_desc = TextInput(hint_text="食物描述，如：米饭1碗+鸡胸肉150g+西兰花", multiline=False)
        ti_kcal = TextInput(hint_text="热量 kcal（可留空自动估算）", multiline=False,
                            input_filter="float")
        content.add_widget(ti_desc)
        content.add_widget(ti_kcal)
        popup = Popup(title="手动录入饮食", content=content, size_hint=(0.9, 0.5))

        def ok(*a):
            desc = ti_desc.text.strip()
            if not desc:
                self.toast("请输入食物描述")
                return
            kcal = None
            if ti_kcal.text:
                kcal = float(ti_kcal.text)
            else:
                # 尝试按食物库估算
                est = 0.0
                for k, v in FOOD_LIB.items():
                    if k in desc:
                        est += v
                kcal = est if est > 0 else 300.0
            self._save_meal(desc, kcal, protein=kcal * 0.045, fat=kcal * 0.035,
                            carb=kcal * 0.055)
            popup.dismiss()

        btns = BoxLayout(size_hint_y=None, height=48, spacing=8)
        b_ok = Button(text="保存")
        b_ok.bind(on_release=ok)
        b_cancel = Button(text="取消")
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
        self.toast("已记录：%.0f kcal" % kcal)
        self.refresh_home()

    # ---------- 记运动 ----------
    def build_exercise(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        box.add_widget(self.section("记录运动"))
        row1 = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.ex_spinner = Spinner(text="慢跑", values=sorted(EXERCISE_MET.keys()))
        self.ex_min = TextInput(hint_text="时长(分钟)", multiline=False, input_filter="float")
        row1.add_widget(self.ex_spinner)
        row1.add_widget(self.ex_min)
        box.add_widget(row1)
        self.ex_note = TextInput(hint_text="备注（可选）", multiline=False, size_hint_y=None, height=44)
        box.add_widget(self.ex_note)
        self.ex_result = Label(text="", size_hint_y=None, height=60, markup=True)
        box.add_widget(self.ex_result)
        btn = Button(text="✅ 保存运动", size_hint_y=None, height=48)
        btn.bind(on_release=lambda *a: self.save_exercise())
        box.add_widget(btn)
        return box

    def save_exercise(self):
        prof = self.db.get_profile()
        try:
            minutes = float(self.ex_min.text)
        except Exception:
            self.toast("请输入有效时长")
            return
        met = EXERCISE_MET[self.ex_spinner.text]
        kcal = calc_exercise_kcal(met, minutes, prof["weight_kg"])
        now = datetime.datetime.now()
        self.db.add_exercise({
            "date": now.date().isoformat(), "time": now.strftime("%H:%M"),
            "ex_type": self.ex_spinner.text, "minutes": minutes,
            "kcal": kcal, "note": self.ex_note.text,
        })
        self.ex_result.text = "[b]%s %s 分钟 ≈ %.0f kcal[/b]" % (
            self.ex_spinner.text, minutes, kcal)
        self.toast("已记录运动 %.0f kcal" % kcal)
        self.refresh_home()

    # ---------- 目标 ----------
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

        inner.add_widget(self.section("我的目标"))
        inner.add_widget(self.goal_label)

        inner.add_widget(self.section("修改资料"))
        grid = GridLayout(cols=2, size_hint_y=None, height=320, spacing=6)
        fields = [
            ("性别", "gender"), ("年龄", "age"), ("身高cm", "height_cm"),
            ("当前体重kg", "weight_kg"), ("目标体重kg", "target_weight_kg"),
            ("目标日期", "target_date"),
        ]
        self.inputs = {}
        for label, key in fields:
            grid.add_widget(Label(text=label))
            ti = TextInput(text=str(prof[key]), multiline=False)
            self.inputs[key] = ti
            grid.add_widget(ti)
        inner.add_widget(grid)

        btn_save = Button(text="💾 保存资料并重算", size_hint_y=None, height=48)
        btn_save.bind(on_release=lambda *a: self.save_goal())
        inner.add_widget(btn_save)

        btn_weight = Button(text="⚖️ 记录今日体重", size_hint_y=None, height=48)
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
        w_str = "%s %.1f kg" % (lw[0], lw[1]) if lw else "未记录"
        self.goal_label.text = (
            "基础代谢 BMR：%.0f kcal\n"
            "每日消耗 TDEE：%.0f kcal\n"
            "每日热量预算：%.0f kcal（缺口 %.0f）\n"
            "蛋白质目标：%.1f g/天\n\n"
            "当前体重：%.1f kg\n"
            "最新记录：%s\n"
            "目标体重：%.1f kg（%s）\n\n"
            "[b]引导[/b]：\n"
            "• 每餐控制在预算的 1/3 左右\n"
            "• 优先高蛋白、高纤维食物\n"
            "• 每天 30 分钟以上中强度运动\n"
            "• 每周减重 0.5~1 kg 为宜，勿极端节食"
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
            self.toast("输入有误，请检查数字")
            return
        self.db.save_profile(prof)
        self.toast("已保存并重算目标")
        self.refresh_goal()
        self.refresh_home()

    def weight_popup(self):
        content = BoxLayout(orientation="vertical", spacing=8, padding=10)
        ti = TextInput(hint_text="今日体重 kg", multiline=False, input_filter="float")
        content.add_widget(ti)
        popup = Popup(title="记录体重", content=content, size_hint=(0.9, 0.4))
        def ok(*a):
            try:
                w = float(ti.text)
            except Exception:
                self.toast("请输入有效体重")
                return
            self.db.set_weight(datetime.date.today().isoformat(), w)
            self.toast("已记录 %.1f kg" % w)
            popup.dismiss()
            self.refresh_goal()
            self.refresh_home()
        btns = BoxLayout(size_hint_y=None, height=48, spacing=8)
        b1 = Button(text="保存"); b1.bind(on_release=ok)
        b2 = Button(text="取消"); b2.bind(on_release=lambda *a: popup.dismiss())
        btns.add_widget(b1); btns.add_widget(b2)
        content.add_widget(btns)
        popup.open()

    # ---------- 记录 ----------
    def build_history(self):
        box = BoxLayout(orientation="vertical", padding=12, spacing=8)
        box.add_widget(self.section("历史记录"))
        row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.hist_date = TextInput(text=datetime.date.today().isoformat(),
                                   multiline=False)
        btn = Button(text="查询")
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
        lines = ["[b]%s[/b]" % date, "", "🍚 饮食："]
        mi = sum(m[5] for m in meals)
        for m in meals:
            lines.append("  %s %s｜%s｜%.0f kcal" % (m[2], m[3], m[4], m[5]))
        lines.append("  小计：%.0f kcal" % mi)
        lines.append("", "🏃 运动：")
        ei = sum(e[5] for e in exes)
        for e in exes:
            lines.append("  %s %s｜%.0f min｜%.0f kcal" % (e[2], e[3], e[4], e[5]))
        lines.append("  小计：%.0f kcal" % ei)
        lines.append("", "⚖️ 净摄入：%.0f kcal" % (mi - ei))
        self.hist_label.text = "\n".join(lines)

    # ---------- 工具 ----------
    def toast(self, msg):
        popup = Popup(title="提示", content=Label(text=msg),
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
