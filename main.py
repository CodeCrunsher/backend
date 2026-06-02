import os
import sqlite3
import requests
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Load the new Groq key
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SYS_PROMPT = "You are Oracle (Barbara Gordon) operating the Batcomputer in the year 2089. You are Batman's tactical overwatch. Respond to his messages concisely, professionally, and with a dark, cyberpunk, tactical tone. Keep responses under 3 sentences. Do not break character."

app = FastAPI(title="Batcomputer API - Project Titan")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "batcomputer.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Keeping all your original tables safe!
    c.execute('''CREATE TABLE IF NOT EXISTS missions 
                 (id INTEGER PRIMARY KEY, title TEXT, description TEXT, priority TEXT, is_completed BOOLEAN)''')
    c.execute('''CREATE TABLE IF NOT EXISTS equipment 
                 (id INTEGER PRIMARY KEY, name TEXT, status TEXT, integrity_level INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY, sender TEXT, content TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

class MessageCreate(BaseModel):
    content: str
    sender: str = "Batman"

@app.get("/messages")
def get_messages():
    conn = get_db()
    messages = conn.execute("SELECT * FROM messages ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(m) for m in messages]

@app.post("/messages")
def send_message(msg: MessageCreate):
    conn = get_db()
    timestamp = datetime.now().isoformat()
    
    # 1. Save Batman's Message
    conn.execute("INSERT INTO messages (sender, content, timestamp) VALUES (?, ?, ?)",
                 (msg.sender, msg.content, timestamp))
    conn.commit()
    
    # 2. Get AI Response using GROQ
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": SYS_PROMPT},
                {"role": "user", "content": msg.content}
            ]
        }
        
        # Hit Groq's servers
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        # Extract the reply
        data = response.json()
        oracle_reply = data["choices"][0]["message"]["content"].strip()
        
    except Exception as e:
        print(f"🚨 GROQ API ERROR: {e}", flush=True)
        oracle_reply = "Comms error. Uplink degraded."
        
    # 3. Save Oracle's Reply
    reply_timestamp = datetime.now().isoformat()
    conn.execute("INSERT INTO messages (sender, content, timestamp) VALUES (?, ?, ?)",
                 ("Oracle", oracle_reply, reply_timestamp))
    conn.commit()
    conn.close()
    
    # 4. Return response to Android
    return {"aiResponse": oracle_reply}
