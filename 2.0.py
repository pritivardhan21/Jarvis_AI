import pvporcupine
import pyaudio
import struct
import speech_recognition as sr
import webbrowser
import os
import pyttsx3
import datetime
import keyboard
import requests
import json
import psutil
import subprocess
import logging
import time
from newsapi import NewsApiClient
import sqlite3

# Initialize text-to-speech engine
engine = pyttsx3.init()

def speak(text):
    """ Function to make the assistant speak """
    engine.say(text)
    engine.runAndWait()

# Database for memory storage
conn = sqlite3.connect("assistant_memory.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT)''')
conn.commit()

def remember(key, value):
    cursor.execute("INSERT OR REPLACE INTO memory (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    speak(f"I will remember that {key} is {value}.")

def recall(key):
    cursor.execute("SELECT value FROM memory WHERE key = ?", (key,))
    result = cursor.fetchone()
    if result:
        speak(f"{key} is {result[0]}.")
        return result[0]
    return None

# Your Picovoice access key
ACCESS_KEY = "vqUOYXsvM8E2Guo/nqQ4+ba4FFD2v5LxPE5FxyNo0ZOnJDsflKveFw=="  # Replace with your actual access key

# Define wake word
WAKE_WORDS = ["alexa"]  # Choose a valid keyword from Picovoice

# Initialize Porcupine
porcupine = pvporcupine.create(access_key=ACCESS_KEY, keywords=WAKE_WORDS)

# Set up audio stream
pa = pyaudio.PyAudio()
audio_stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

def recognize_speech():
    """ Function to recognize speech after wake word detection """
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for command...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio).lower()
        print(f"Recognized: {command}")
        return command
    except sr.UnknownValueError:
        print("Could not understand audio.")
        speak("Sorry, I didn't catch that.")
    except sr.RequestError:
        print("Speech Recognition service is down.")
        speak("Speech recognition service is down.")
    return None

def execute_command(command):
    """ Executes specific tasks based on voice commands """
    if "open youtube" in command:
        webbrowser.open("https://www.youtube.com")
        speak("Opening YouTube.")
    elif "open google" in command:
        webbrowser.open("https://www.google.com")
        speak("Opening Google.")
    elif "open notepad" in command:
        os.system("notepad")
        speak("Opening Notepad.")
    elif "open calculator" in command:
        os.system("calc")
        speak("Opening Calculator.")
    elif "what time is it" in command:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {current_time}.")
    elif "what is today's date" in command:
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        speak(f"Today's date is {current_date}.")
    elif "shutdown" in command:
        speak("Shutting down the system.")
        os.system("shutdown /s /t 1")
    elif "restart" in command:
        speak("Restarting the system.")
        os.system("shutdown /r /t 1")
    else:
        speak("I'm not sure how to do that.")

print("Listening for wake word: alexa...")
speak("Listening for wake word alexa")

last_active_time = time.time()
active_duration = 120  # Assistant remains active for 2 minutes after wake word detection

try:
    while True:
        if time.time() - last_active_time > active_duration:
            print("Listening for wake word: alexa...")
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
            keyword_index = porcupine.process(pcm_unpacked)
            if keyword_index >= 0:
                print("Wake word detected!")
                speak("Hi!! How can I help you?")
                last_active_time = time.time()

        command = recognize_speech()
        if command:
            last_active_time = time.time()
            if "remember that" in command:
                parts = command.replace("remember that", "").strip().split(" is ")
                if len(parts) == 2:
                    key, value = parts
                    remember(key.strip(), value.strip())
            elif "what is" in command:
                key = command.replace("what is", "").strip()
                result = recall(key)
                if not result:
                    speak("I don't remember that.")
            else:
                execute_command(command)

except KeyboardInterrupt:
    print("Stopping assistant...")
    speak("Stopping assistant")

finally:
    audio_stream.close()
    pa.terminate()
    porcupine.delete()
    conn.close()
