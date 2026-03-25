# 🎓 LectureLensAI — Smart Study Notes from Videos

LectureLensAI is an AI-powered system that transforms lecture videos into structured study materials using **Groq LLMs**, **LangChain pipelines**, and **FAISS-based retrieval**.

It processes raw video input into:

* 📄 Structured notes
* 🧠 Flashcards
* 💬 Context-aware Q&A chatbot with timestamps

---

## 🚀 Key Features

* 🎥 **Video → Text Pipeline**
  Extracts audio and transcribes it using Groq Whisper (`whisper-large-v3`) 

* 🧠 **Structured Notes Generation**
  Converts transcripts into clean, bullet-point notes with TL;DR summaries 

* 🗂️ **Flashcard Creation**
  Generates concept-focused Q&A flashcards from lecture content 

* 💬 **RAG-based Chatbot**
  Answers questions using FAISS + LangChain with timestamp grounding 

* 🔎 **Semantic Search (FAISS)**
  Retrieves most relevant lecture chunks for accurate answers

* ⚡ **High-Speed LLM Inference (Groq)**
  Uses Groq-hosted LLaMA models for ultra-fast responses

* 🧠 **Conversation Memory Compression**
  Summarizes chat history to maintain context efficiently 

---

## 🏗️ System Architecture

```
Video Input
   ↓
Audio Extraction (ffmpeg)
   ↓
Chunking (time-based)
   ↓
Groq Whisper Transcription
   ↓
Segmented Transcript (JSON)
   ↓
────────────────────────────────
↓                ↓            ↓
Notes         Flashcards     Chatbot
(Groq LLM)    (Groq LLM)     (LangChain + FAISS + Groq)
                               ↓
                        Context-aware Answers
```

---

## 🧠 Tech Stack

* **LLM Inference:** Groq (LLaMA models, Whisper)
* **Framework:** LangChain
* **Vector Store:** FAISS
* **Embeddings:** HuggingFace (`all-MiniLM-L6-v2`)
* **Backend:** Python (Flask)
* **Audio Processing:** ffmpeg

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/LectureLensAI.git
cd LectureLensAI
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup environment variables

Create a `.env` file:

```env
GROQ_API_KEY=your_api_key_here
```

---

## ▶️ Usage

### Run the application

```bash
python run.py
```

### CLI Examples

#### 1. Transcribe video

```bash
python -m app.services.audio path/to/video.mp4
```

#### 2. Generate notes

```bash
python -m app.services.notes data/audio/output.json
```

#### 3. Generate flashcards

```bash
python -m app.services.flashcards data/notes/notes.json
```

---

## 🔍 How It Works (Deep Dive)

### 🎧 1. Audio + Transcription

* Extracts WAV audio using ffmpeg
* Splits into chunks (default: 6 min)
* Transcribes using Groq Whisper
* Outputs timestamped segments JSON 

---

### 🧠 2. Notes Generation

* Processes transcript in chunks
* Uses Groq LLM (`llama-3.3-70b-versatile`)
* Outputs:

  * Titles
  * Bullet points
  * TL;DR summaries 

---

### 🗂️ 3. Flashcards

* Converts transcript/notes into Q&A pairs
* Supports multilingual (Hindi + English + Hinglish)
* Outputs structured JSON flashcards 

---

### 💬 4. Chatbot (RAG Pipeline)

**Pipeline:**

1. Chunk transcript → Documents
2. Create embeddings
3. Store in FAISS
4. Retrieve top-k relevant chunks
5. Generate answer using Groq LLM

**Advanced Features:**

* Query rewriting using chat history
* Timestamp-aware answers
* JSON output parsing
* Chat memory compression after multiple turns 

---

## 📂 Project Structure

```
app/
 ├── services/
 │   ├── audio.py        # Audio extraction + Whisper transcription
 │   ├── notes.py        # Notes generation (Groq)
 │   ├── flashcards.py   # Flashcard generation
 │   ├── chatbot.py      # RAG chatbot (FAISS + LangChain)
 │
data/
 ├── audio/
 ├── notes/
 ├── flashcards/

run.py
requirements.txt
```

---

## 🧩 Core Concepts Used

* **RAG (Retrieval-Augmented Generation)**
* **Vector Embeddings + Semantic Search**
* **Chunking for Long Context Handling**
* **LLM Prompt Engineering**
* **Conversation Memory Compression**

---

## 📌 Future Improvements

* 🌐 Multi-language transcription (auto-detect + translate)
* 📱 Mobile-friendly UI
* ☁️ Cloud deployment (Docker + AWS/GCP)
* 📊 Learning analytics dashboard
* 🎯 Personalized summaries
