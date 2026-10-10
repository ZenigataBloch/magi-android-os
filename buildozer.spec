[app]

title = MAGI-OS
package.name = magios
package.domain = org.magi

source.dir = .
source.include_exts = py,ttf,otf,env,png,kv,txt
source.exclude_dirs = bin,tests,venv,__pycache__
source.exclude_patterns = fonts/NotoSerifJP-Bold.otf,subset.py,ui/gui.py,ui/boot.py,ui/fonts.py,ui/magi_map.py,ui/nerv.py,discord_magi.py,run_desktop.py
version = 0.1

requirements = python3,kivy,https://github.com/kivymd/KivyMD/archive/master.zip,materialyoucolor,exceptiongroup,asyncgui,asynckivy,pillow,requests,certifi,urllib3,idna,charset-normalizer,python-dotenv

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/magi.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #04060A

android.permissions = INTERNET
android.api = 35
android.ndk = 28c
android.archs = arm64-v8a
android.accept_sdk_license = True

# python-for-android recente (il branch master e' vecchio e senza supporto AAB)
p4a.fork = kivy
p4a.branch = develop

# per il debug serve solo l'APK
android.debug_artifact = apk
android.release_artifact = apk


[buildozer]

log_level = 2
warn_on_root = 1
