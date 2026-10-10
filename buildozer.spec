[app]

# 应用名（显示在手机桌面）
title = 健食管家

# 包名（唯一标识，建议改成你自己的域名倒写）
package.name = fitnessdiet
package.domain = com.example

# 版本
version = 1.0.0

# 源码入口
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,db

# 图标（可选，放到项目根目录 icon.png）

# 支持的架构（arm64-v8a 覆盖绝大多数现代手机）
android.archs = arm64-v8a

# Android SDK/NDK 版本（buildozer 会自动下载）
android.api = 33
android.minapi = 21
android.ndk = 25b

# 权限：相机（拍照）、读写存储（选图）
android.permissions = CAMERA, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, INTERNET

# 需要的 Python 依赖
requirements = python3,kivy==2.3.1,plyer,requests

# 日志
android.logcat_filters =

# 屏幕方向
orientation = portrait

# 应用分类
presplash.filename =
presplash.color = #F5F5F2

[buildozer]

# 日志级别
log_level = 2

# 警告级别
warn_on_root = 1
