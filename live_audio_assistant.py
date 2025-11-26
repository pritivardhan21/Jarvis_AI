import os
import sys
import time
import json
import logging
import subprocess
import webbrowser
import urllib.parse
import datetime
import struct
import re
import ctypes
import shutil
import random

try:
    import pvporcupine
    import pyaudio
    import speech_recognition as sr
    import pyttsx3
    import psutil
    import keyboard
except Exception as e:
    print("Missing python packages. Install requirements. Error:", e)
    raise

try:
    from newsapi import NewsApiClient
except Exception:
    NewsApiClient = None

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ---------------------------
# CONFIG (edit as needed)
# ---------------------------
ACCESS_KEY = "vqUOYXsvM8E2Guo/nqQ4+ba4FFD2v5LxPE5FxyNo0ZOnJDsflKveFw=="
WAKE_WORDS = ["jarvis"]
MEMORY_FILE = "assistant_memory.json"
NEWSAPI_KEY = None
SPOTIFY_OPEN_IN_APP = True

# ---------------------------
# TTS engine
# ---------------------------
engine = pyttsx3.init()

def speak(text):
    if not text:
        return
    print("[Jarvis]:", text)
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logging.error("TTS error: %s", e)

# ---------------------------
# Utility helpers
# ---------------------------
def run_cmd(cmd_list, shell=False):
    try:
        proc = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell, text=True)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        logging.error("Command failed: %s", e)
        return 1, "", str(e)

# ---------------------------
# Memory helpers
# ---------------------------
def _load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error("Failed to load memory: %s", e)
        return []


def _save_memory(mem_list):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error("Failed to save memory: %s", e)


def remember_text(text):
    mem = _load_memory()
    entry = {"text": text, "timestamp": datetime.datetime.now().isoformat()}
    mem.append(entry)
    _save_memory(mem)
    speak("Okay, I have remembered that.")
    print("[Memory saved]", entry)


def list_memories():
    mem = _load_memory()
    if not mem:
        speak("You have no saved memories.")
        return
    speak(f"You have {len(mem)} memories. I'll list them now.")
    for i, e in enumerate(mem, 1):
        ts = e.get("timestamp", "")[:19].replace("T", " ")
        speak(f"{i}. {e.get('text')} (saved on {ts})")


def recall_by_keyword(keyword):
    keyword_lower = keyword.lower()
    mem = _load_memory()
    matches = [e for e in mem if keyword_lower in e.get("text", "").lower()]
    if not matches:
        speak(f"I couldn't find anything matching {keyword}.")
        return
    speak(f"I found {len(matches)} item(s) that match {keyword}:")
    for e in matches:
        ts = e.get("timestamp", "")[:19].replace("T", " ")
        speak(f"{e.get('text')} — saved on {ts}")


def forget_memory(query):
    mem = _load_memory()
    new_mem = [e for e in mem if query.lower() not in e.get("text", "").lower()]
    removed = len(mem) - len(new_mem)
    if removed == 0:
        speak("I couldn't find that memory to remove.")
    else:
        _save_memory(new_mem)
        speak(f"Removed {removed} memory item(s).")
        print(f"[Memory deleted] {removed} entries removed")

# ---------------------------
# Spotify helpers
# ---------------------------
def search_spotify(query):
    if not query:
        speak("Please tell me what to search on Spotify.")
        return
    q = urllib.parse.quote_plus(query)
    web_url = f"https://open.spotify.com/search/{q}"
    spotify_uri = f"spotify:search:{query}"
    speak(f"Searching Spotify for {query}")
    print("[Spotify] opening:", spotify_uri, "or", web_url)
    try:
        os.system(f"start {spotify_uri}")
        time.sleep(0.6)
        webbrowser.open(web_url)
    except Exception as e:
        logging.error("Spotify open error: %s", e)
        webbrowser.open(web_url)

# ---------------------------
# YouTube (Chrome) helper
# ---------------------------
def search_youtube_chrome(query):
    if not query:
        speak("Please tell me what to search on YouTube.")
        return
    query_enc = urllib.parse.quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={query_enc}"
    speak(f"Searching YouTube for {query}")
    print("[YouTube] URL:", url)
    possible = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    chrome_path = next((p for p in possible if os.path.exists(p)), None)
    try:
        if chrome_path:
            subprocess.Popen([chrome_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
    except Exception as e:
        logging.warning("Could not open Chrome directly: %s", e)
    webbrowser.open(url)

# ---- Conversation style helpers ----
_WAKE_IDLE_RESET = 300  
_wake_count = 0
_last_wake_time = 0.0

_ALTERNATE_GREETINGS = [
    "Yes? What can I do for you?",
    "Hey again — how can I help?",
    "I'm listening. What would you like?",
    "What's up? Ready when you are.",
    "Back again! Tell me what you need.",
    "I'm here. Say a command when you're ready.",
    "At your service. What's next?"
]

def _time_of_day_prefix():
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning! "
    if 12 <= hour < 17:
        return "Good afternoon! "
    if 17 <= hour < 22:
        return "Good evening! "
    return ""

def get_wake_greeting():
    global _wake_count, _last_wake_time
    now = time.time()
    if now - _last_wake_time > _WAKE_IDLE_RESET:
        _wake_count = 0

    if _wake_count == 0:
        greeting = _time_of_day_prefix() + "Hi! How can I help you?"
    else:
        greeting = random.choice(_ALTERNATE_GREETINGS)

    _wake_count += 1
    _last_wake_time = now
    return greeting

# ---------------------------
# Windows system controls
# ---------------------------

def enable_battery_saver(enable=True):
    val = "1" if enable else "0"
    rc, out, err = run_cmd(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "SUB_ENERGYSAVER", "ESV", val])
    if rc == 0:
        rc2, out2, err2 = run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"])
        if rc2 == 0:
            speak(f"{'Enabled' if enable else 'Disabled'} battery saver (attempted).")
            return True
    logging.warning("powercfg output: %s %s", out, err)
    speak("Tried to toggle battery saver, but it may require admin rights or isn't supported on this system.")
    return False


def set_dark_mode(enable=True):
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
            val = 0 if enable else 1
            winreg.SetValueEx(k, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
            winreg.SetValueEx(k, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "ImmersiveColorSet")
        speak(f"{'Enabled' if enable else 'Disabled'} dark mode. Some apps may need restart to apply.")
        return True
    except Exception as e:
        logging.error("set_dark_mode error: %s", e)
        speak("Couldn't change Windows theme settings. You may need to run as your user or restart.")
        return False


def set_brightness(percent):
    try:
        percent = max(0, min(100, int(percent)))
        ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{percent})"
        rc, out, err = run_cmd(["powershell", "-Command", ps_cmd])
        if rc == 0:
            speak(f"Brightness set to {percent} percent.")
            return True
        else:
            logging.warning("Brightness powershell error: %s", err)
            speak("Could not change brightness. It may require admin or unsupported driver.")
            return False
    except Exception as e:
        logging.error("set_brightness exception: %s", e)
        speak("Error while setting brightness.")
        return False

PYCAW_AVAILABLE = False
try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False


def toggle_mute(mute=None):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        nircmd_path = shutil.which("nircmd.exe") or os.path.join(script_dir, "nircmd.exe")

        if os.path.exists(nircmd_path):
            if mute is None:
                run_cmd([nircmd_path, "mutesysvolume", "2"])
                speak("Toggled mute.")
            else:
                run_cmd([nircmd_path, "mutesysvolume", "1" if mute else "0"])
                speak("Muted." if mute else "Unmuted.")
            return True

        if PYCAW_AVAILABLE:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            if mute is None:
                current = volume.GetMute()
                volume.SetMute(0 if current else 1, None)
                speak("Toggled mute.")
            else:
                volume.SetMute(1 if mute else 0, None)
                speak("Muted." if mute else "Unmuted.")
            return True

        speak("nircmd.exe not found and pycaw is not installed. Install nircmd (recommended) or run: python -m pip install pycaw comtypes")
        return False

    except Exception as e:
        logging.exception("toggle_mute exception:")
        speak("Failed to change volume mute state.")
        return False

# ---------------------------
# Network & Bluetooth
# ---------------------------

def connect_wifi(ssid, password=None):
    if not ssid:
        speak("Please provide the WiFi SSID.")
        return False
    try:
        rc, out, err = run_cmd(["netsh", "wlan", "connect", f"name={ssid}", f"ssid={ssid}"])
        if rc == 0:
            speak(f"Attempted to connect to {ssid}.")
            return True
        else:
            logging.warning("netsh wlan connect error: %s", err)
            speak("Auto-connection failed. If you provided a password, consider connecting once via Windows UI to create a profile.")
            return False
    except Exception as e:
        logging.error("connect_wifi error: %s", e)
        speak("Error trying to connect to WiFi.")
        return False


def open_bluetooth_settings():
    try:
        subprocess.Popen(["start", "ms-settings:bluetooth"], shell=True)
        speak("Opening Bluetooth settings. You can toggle Bluetooth there.")
        return True
    except Exception as e:
        logging.exception("open_bluetooth_settings error:")
        speak("Could not open Bluetooth settings automatically. Please open Action Center or Settings.")
        return False


def _run_powershell(cmd):
    try:
        completed = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except Exception as e:
        logging.exception("_run_powershell error:")
        return 1, "", str(e)


def _try_winrt_toggle(enable: bool):
    try:
        state = "On" if enable else "Off"
        ps = f'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction SilentlyContinue
$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetAwaiter().GetResult()
foreach ($r in $radios) {{
    if ($r.Kind -eq 'Bluetooth') {{
        $r.SetStateAsync('{state}') | Out-Null
    }}
}}
'''
        rc, out, err = _run_powershell(ps)
        if rc == 0:
            speak(f"Bluetooth turned {state.lower()}.")
            return True
        else:
            logging.warning("WinRT toggle returned non-zero: %s %s", out, err)
            return False
    except Exception as e:
        logging.exception("WinRT toggle exception:")
        return False


def _try_pnp_toggle(enable: bool):
    try:
        action = "Enable-PnpDevice" if enable else "Disable-PnpDevice"
        ps_cmd = f"Get-PnpDevice -Class Bluetooth | Where-Object {{$_.InstanceId -ne $null}} | ForEach-Object {{try {{ {action} -InstanceId $_.InstanceId -Confirm:$false -ErrorAction Stop }} catch {{ Write-Host 'ERR:' $_.Exception.Message; exit 2 }} }}; exit 0"
        rc, out, err = _run_powershell(ps_cmd)
        if rc == 0:
            speak(f"Bluetooth adapter {'enabled' if enable else 'disabled'}.")
            return True
        else:
            logging.warning("PnP toggle returned rc=%s out=%s err=%s", rc, out, err)
            return False
    except Exception as e:
        logging.exception("_try_pnp_toggle exception:")
        return False


def toggle_bluetooth(enable: bool):
    try:
        ok = _try_winrt_toggle(enable)
        if ok:
            return True
    except Exception:
        pass

    try:
        ok2 = _try_pnp_toggle(enable)
        if ok2:
            return True
    except Exception:
        pass

    speak("I couldn't toggle Bluetooth automatically. I'll open Bluetooth settings so you can toggle it manually.")
    return open_bluetooth_settings()

# ---------------------------
# Lock / Shutdown / Restart
# ---------------------------
def lock_system():
    try:
        ctypes.windll.user32.LockWorkStation()
        speak("Locked the system.")
        return True
    except Exception as e:
        logging.error("lock_system error: %s", e)
        speak("Could not lock the system.")
        return False


def shutdown_system(force=True):
    try:
        cmd = ["shutdown", "/s", "/t", "0"]
        if force:
            cmd = ["shutdown", "/s", "/f", "/t", "0"]
        run_cmd(cmd)
        speak("Shutting down now.")
        return True
    except Exception as e:
        logging.error("shutdown_system error: %s", e)
        speak("Could not shut down the system.")
        return False


def restart_system():
    try:
        run_cmd(["shutdown", "/r", "/t", "0"])
        speak("Restarting now.")
        return True
    except Exception as e:
        logging.error("restart_system error: %s", e)
        speak("Could not restart the system.")
        return False

# ---------------------------
# News & Weather placeholders
# ---------------------------
def get_news():
    if not NEWSAPI_KEY or NewsApiClient is None:
        speak("News is not configured. Set NEWSAPI_KEY in the script to enable news.")
        return
    try:
        newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
        today = datetime.date.today().isoformat()
        top = newsapi.get_everything(q='top', from_param=today, language='en', sort_by='relevancy', page_size=5)
        articles = top.get('articles', [])[:5]
        if articles:
            for a in articles:
                speak(a.get('title'))
        else:
            speak("No recent headlines found.")
    except Exception as e:
        logging.error("news error: %s", e)
        speak("Could not fetch news.")


def get_weather():
    speak("Weather function not configured. I can add OpenWeatherMap support if you provide an API key and city.")

# ---------------------------
# Speech recognition & Porcupine setup
# ---------------------------
try:
    porcupine = pvporcupine.create(access_key=ACCESS_KEY, keywords=WAKE_WORDS)
except Exception as e:
    logging.error("Porcupine init error: %s", e)
    speak("Could not initialize Porcupine. Check your ACCESS_KEY and keywords.")
    sys.exit(1)

pa = pyaudio.PyAudio()
audio_stream = None
try:
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )
except Exception as e:
    logging.error("Audio stream error: %s", e)
    speak("Could not open microphone stream.")
    sys.exit(1)


def recognize_speech(timeout=6, phrase_time_limit=6):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for command...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except Exception as e:
            logging.error("Microphone listen error: %s", e)
            return None
    try:
        command = recognizer.recognize_google(audio).lower()
        print("[Heard]:", command)
        return command
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that.")
    except sr.RequestError as e:
        logging.error("Speech recognition request error: %s", e)
        speak("Speech recognition service is not available.")
    return None

# Greeting behavior configuration
_wake_count = 0            
_last_wake_time = 0.0      
WAKE_IDLE_RESET = 300      

_ALTERNATE_GREETINGS = [
    "Yes? What can I do for you?",
    "Hey again — how can I help?",
    "I'm listening. What would you like?",
    "What's up? Ready when you are.",
    "Back again! Tell me what you need.",
    "I'm here. Say a command when you're ready.",
    "At your service. What's next?"
]

def get_wake_greeting():
    global _wake_count, _last_wake_time

    now = time.time()
    if now - _last_wake_time > WAKE_IDLE_RESET:
        _wake_count = 0

    if _wake_count == 0:
        greeting = "Hi! How can I help you?"
    else:
        greeting = random.choice(_ALTERNATE_GREETINGS)

    _wake_count += 1
    _last_wake_time = now
    return greeting

# ---------------------------
# Main loop
# ---------------------------
speak("Listening for wake word Jarvis...")

try:
    while True:
        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
        keyword_index = porcupine.process(pcm_unpacked)
        if keyword_index >= 0:
            print("Wake word detected!")
            speak(get_wake_greeting())
            command = recognize_speech()
            if not command:
                continue

            # ---------- MEMORY ----------
            if command.startswith("remember "):
                remember_text(command.replace("remember", "", 1).strip())
                continue
            if command.startswith("what did i tell you about ") or command.startswith("recall "):
                if "about" in command:
                    keyword = command.split("about",1)[1].strip()
                else:
                    keyword = command.replace("recall", "", 1).strip()
                recall_by_keyword(keyword)
                continue
            if command.strip() == "list memories":
                list_memories()
                continue
            if command.startswith("forget "):
                forget_memory(command.replace("forget", "", 1).strip())
                continue

            # ---------- SPOTIFY ----------
            if "search spotify for " in command:
                q = command.split("search spotify for",1)[1].strip()
                if q: search_spotify(q)
                continue
            if command.startswith("play ") and "on spotify" in command:
                q = command.split("play",1)[1].split("on spotify",1)[0].strip()
                if q: search_spotify(q)
                continue

            # ---------- YOUTUBE ----------
            if command.startswith("search youtube for "):
                q = command.replace("search youtube for", "", 1).strip()
                if q: search_youtube_chrome(q)
                continue
            if "search for" in command and "youtube" in command:
                try:
                    q = command.split("search for",1)[1].split("on youtube",1)[0].strip()
                    if q: search_youtube_chrome(q)
                except Exception:
                    speak("Please repeat the YouTube search query.")
                continue

            # ---------- SYSTEM CONTROLS (Windows) ----------
            if "turn on battery saver" in command or "enable battery saver" in command:
                enable_battery_saver(True); continue
            if "turn off battery saver" in command or "disable battery saver" in command:
                enable_battery_saver(False); continue

            if "turn on dark mode" in command or "enable dark mode" in command:
                set_dark_mode(True); continue
            if "turn off dark mode" in command or "disable dark mode" in command:
                set_dark_mode(False); continue

            if "increase brightness" in command:
                set_brightness(80); continue
            if "decrease brightness" in command:
                set_brightness(30); continue
            if "set brightness to" in command:
                m = re.search(r"(\d{1,3})", command)
                if m:
                    set_brightness(int(m.group(1)))
                else:
                    speak("Please state a percentage between 0 and 100.")
                continue

            if "mute" in command and "unmute" not in command:
                toggle_mute(True); continue
            if "unmute" in command:
                toggle_mute(False); continue
            if "toggle mute" in command or "mute toggle" in command:
                toggle_mute(None); continue

            if "connect to wifi" in command or "connect to wi-fi" in command:
                tokens = command.split()
                ssid = None; pwd = None
                if "wifi" in tokens:
                    try:
                        idx = tokens.index("wifi")
                        ssid = tokens[idx+1]
                    except Exception:
                        ssid = None
                if "password" in tokens:
                    try:
                        pidx = tokens.index("password")
                        pwd = tokens[pidx+1]
                    except Exception:
                        pwd = None
                if ssid:
                    connect_wifi(ssid, pwd)
                else:
                    speak("Please tell me the SSID to connect to.")
                continue

            if "turn bluetooth on" in command or "enable bluetooth" in command:
                toggle_bluetooth(True); continue
            if "turn bluetooth off" in command or "disable bluetooth" in command:
                toggle_bluetooth(False); continue

            if "lock the system" in command or "lock the computer" in command:
                lock_system(); continue

            if "shutdown the laptop" in command or "shut down" in command or "shutdown" in command:
                speak("Are you sure you want to shut down? Please say 'yes' to confirm or 'no' to cancel.")
                confirm = recognize_speech(timeout=5, phrase_time_limit=3)
                if confirm and "yes" in confirm:
                    shutdown_system()
                    break
                else:
                    speak("Shutdown cancelled.")
                continue

            if "restart the laptop" in command or "restart the computer" in command or "restart" in command:
                speak("Are you sure you want to restart? Please say 'yes' to confirm or 'no' to cancel.")
                confirm = recognize_speech(timeout=5, phrase_time_limit=3)
                if confirm and "yes" in confirm:
                    restart_system()
                    break
                else:
                    speak("Restart cancelled.")
                continue

            if command.startswith("open "):
                app = command.replace("open", "", 1).strip()
                if app:
                    os.system(f"start {app}")
                    speak(f"Opening {app}")
                continue

            if command.startswith("close "):
                app = command.replace("close", "", 1).strip()
                if app:
                    os.system(f"taskkill /IM {app}.exe /F")
                    speak(f"Closed {app} if it was running.")
                continue

            if "what time" in command or "what is the time" in command:
                now = datetime.datetime.now().strftime("%I:%M %p")
                speak(f"The time is {now}")
                continue

            if "what is the date" in command or "what is today's date" in command:
                today = datetime.date.today().strftime("%A, %B %d, %Y")
                speak(f"Today is {today}")
                continue

            if "tell me the news" in command or "news" in command:
                get_news()
                continue

            if "what is the weather" in command or "weather" in command:
                get_weather()
                continue

            speak("I did not understand that command.")

except KeyboardInterrupt:
    logging.info("KeyboardInterrupt - exiting")

finally:
    try:
        if audio_stream:
            audio_stream.close()
    except Exception:
        pass
    try:
        pa.terminate()
    except Exception:
        pass
    try:
        porcupine.delete()
    except Exception:
        pass
    speak("Assistant stopped.")
