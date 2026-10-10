# 健食管家（FitnessDiet Manager）

安卓端饮食 + 健身管理 App，基于 Python / Kivy 开发。

## 功能

1. **拍照估算热量**：上传/拍摄餐食照片，调用百度 AI 图像识别（菜品识别）识别出食物，弹出**可编辑份量确认表单**——你可逐项修改每样食物的份量（如"1碗""150g""半份"），App 按份量精确估算本餐热量；识别失败或未配置 Key 时可手动录入，内置常见食物热量库自动估算。
2. **运动消耗估算**：记录运动类型与时长，按 MET 代谢当量公式 `kcal = MET × 体重(kg) × 小时` 估算消耗卡路里，并汇总当日净摄入。
3. **目标引导与提醒**：设定目标体重与目标日期，自动计算 BMR、TDEE、每日热量预算（温和缺口，不极端）、蛋白质目标；首页实时显示"剩余可摄入"，引导每餐分配与运动安排。

数据全部本地存储（SQLite），无需注册账号。

## 项目结构

```
fitness-apk/
├── main.py                  # 应用主程序
├── buildozer.spec           # APK 打包配置
├── requirements.txt         # Python 依赖
├── icon.png                 # 应用图标（可选，自行放入）
└── .github/workflows/build.yml  # GitHub Actions 在线打包
```

## 一、先在电脑上预览（可选，Windows 即可）

```bash
pip install kivy plyer requests
python main.py
```

会弹出桌面窗口，可先体验功能。

## 二、打包成 APK

> ⚠️ 关键说明：APK 打包工具 **Buildozer 只能在 Linux 上运行**，Windows 原生无法直接打包。你有两条路：

### 方案 A：GitHub Actions 在线打包（推荐，无需装 Linux）

1. 把 `fitness-apk` 整个文件夹推到你的 GitHub 仓库（私有仓库即可）。
2. 打开仓库 **Actions** 页 → 左侧选 **Build APK** → 点 **Run workflow**。
3. 等约 15~30 分钟（首次会下载 Android SDK/NDK，较慢）。
4. 构建完成后，在本次运行的 **Artifacts** 里下载 `fitness-apk.zip`，里面就是 `.apk` 文件。
5. 把 APK 传到手机安装（需允许"安装未知来源应用"）。

### 方案 B：本机装 WSL 后用 Buildozer 打包

1. 以管理员运行 PowerShell，安装 WSL：
   ```powershell
   wsl --install -d Ubuntu
   ```
   （装完重启电脑）
2. 进入 Ubuntu，安装依赖并打包：
   ```bash
   sudo apt update
   sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config \
     zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   pip3 install --upgrade pip buildozer cython
   cd /mnt/d/你的路径/fitness-apk
   yes | buildozer android debug
   ```
3. 生成的 APK 在 `bin/` 目录下。

## 三、配置百度 AI 食物识别（可选但推荐）

1. 打开 [百度智能云](https://console.bce.baidu.com/) → 图像识别 → 创建应用，开通"菜品识别"。
2. 拿到 **API Key** 和 **Secret Key**。
3. 打开 `main.py`，在文件顶部填入：

   ```python
   BAIDU_API_KEY = "你的APIKey"
   BAIDU_SECRET_KEY = "你的SecretKey"
   ```

4. 重新打包。不配置也能用（手动录入 + 内置食物库估算）。

## 四、使用提示

- 首页：今日摄入/消耗/净摄入/剩余可摄入一目了然。
- 记饮食：拍照识别或手动录入，选餐次后保存。
- 记运动：选运动类型 + 时长，自动算消耗。
- 目标：修改个人资料（性别/年龄/身高/体重/目标），自动重算热量预算；可每日记录体重跟踪进度。
- 记录：按日期查询历史饮食与运动。

## 免责声明

热量与运动消耗均为估算值，仅供参考；健康与减重建议不替代医生或专业营养师意见。
