# *Jarvis_AI*

A smart, voice-activated desktop assistant built with Python.
 
 Under Development:
Jarvis_AI is still evolving. New features, improvements, and optimizations are being added regularly. Expect updates, refinements, and experimental features. Contributions & suggestions are welcome!
  
   # 1. Features:- 

  i) Voice Interaction
- Wake-word detection using Picovoice Porcupine
- Natural speech recognition using Google Speech API
- Dynamic and human-like conversational responses
- Time-based greetings + context-aware replies

  ii)  Memory System
- Save information: remember <text>
- Recall saved details
- Search memories by keyword
- Forget stored items

  iii)  Multimedia & Online Search
- Spotify search & playback
- YouTube search using Chrome
- Open apps, search Google, and automate browser tasks

  iv)  Windows System Controls
- Battery saver: ON/OFF
- Dark mode toggle
- Brightness control
- Mute / unmute / toggle volume
- Wi-Fi connect
- Bluetooth ON/OFF (with fallback to settings)
- Lock system
- Shutdown/restart (with confirmation)


   # 2. Additional Modules:-
- Basic News API support (optional)
- Weather placeholder module (expandable)


   # 3. Requirements:-
- Install required Python packages:
- pip install pvporcupine pyaudio speechrecognition pyttsx3 psutil keyboard pycaw comtypes
- Optional for news support:
    pip install newsapi-python
- You also need:
    A Picovoice ACCESS_KEY
    nircmd.exe (included) for controlling volume/mute

  
   # 4. Setup:-
- Add your Picovoice access key in the script:
- ACCESS_KEY = "<your_access_key>"
- Keep nircmd.exe in the same folder as the script.
- Run Jarvis using:
      python live_audio_assistant.py
- Then say “Jarvis” to activate the AI assistant.


   # 5. Project Structure:-
  
Jarvis_AI/
│── live_audio_assistant.py     # Main assistant logic
│── nircmd.exe                  # Audio control utility
│── 1.json / 2.0.py             # Additional files (in-progress)
│── assistant_memory.json       # Persistent memory storage
│── README.md


   # 6. Technologies Used:-
- Python 3.11+
- Picovoice Porcupine (wake word)
- SpeechRecognition
- pyttsx3 (TTS engine)
- Pycaw (fallback volume control)
- PowerShell automation
- Windows API & Registry config


   # 7. Future Improvements:-
- Planned / upcoming features:
- ChatGPT API integration
- Browser automation upgrade
- Music player mode
- Offline speech-to-text
- Better Bluetooth/Wi-Fi control support
- Modular command system
- Custom wake-word training
