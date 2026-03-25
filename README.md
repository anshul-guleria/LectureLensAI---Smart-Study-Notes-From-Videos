# 🎓 LectureLensAI — Smart Study Notes from Videos

LectureLensAI is an AI-powered web application that transforms lecture videos into structured study materials. It automatically extracts key concepts, generates concise notes, creates flashcards, and enables interactive learning through a chatbot.

---

## 🚀 Features

* 🎥 **Video Processing**
  Upload or provide a lecture video to extract meaningful content.

* 🧠 **AI-Generated Notes**
  Converts lecture content into well-structured, easy-to-read notes.

* 🗂️ **Flashcard Generation**
  Automatically creates flashcards for revision and self-testing.

* 💬 **Interactive Chatbot**
  Ask questions about the lecture and get intelligent responses.

* 📄 **PDF Export**
  Export generated notes into downloadable PDF format.

* ⚡ **Caching System**
  Stores processed data to improve performance and avoid reprocessing.

---

## 🏗️ Project Structure

```
LectureLensAI/
│
├── app/
│   ├── routes/           # API and frontend routes
│   ├── services/         # Core logic (audio, notes, chatbot, etc.)
│   ├── templates/        # HTML templates
│   ├── static/           # CSS & JS files
│   └── utils/            # Helper functions and caching
│
├── data/cache/           # Cached outputs (notes, flashcards, segments)
├── run.py                # Application entry point
├── requirements.txt      # Dependencies
└── README.md
```

---

## ⚙️ Installation

1. **Clone the repository**

```bash
git clone https://github.com/your-username/LectureLensAI.git
cd LectureLensAI
```

2. **Create a virtual environment (recommended)**

```bash
python -m venv venv
source venv/bin/activate     # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Application

```bash
python run.py
```

Then open your browser and go to:

```
http://127.0.0.1:5000/
```

---

## 🧩 How It Works

1. **Video Input**
   The system loads and processes the lecture video.

2. **Audio Extraction**
   Extracts audio from the video for transcription.

3. **Content Processing Pipeline**

   * Segments lecture content
   * Generates summaries and structured notes
   * Creates flashcards

4. **User Interaction**

   * View notes and flashcards
   * Ask questions via chatbot
   * Export results as PDF

---

## 📦 Key Modules

* `video_loader.py` → Handles video input
* `audio.py` → Extracts and processes audio
* `notes.py` → Generates structured notes
* `flashcards.py` → Creates flashcards
* `chatbot.py` → Handles Q&A interaction
* `pipeline.py` → Orchestrates the full workflow
* `pdf_export.py` → Exports notes as PDF

---

## 🛠️ Tech Stack

* **Backend:** Python (Flask)
* **Frontend:** HTML, CSS, JavaScript
* **AI Processing:** NLP-based summarization & generation
* **Storage:** Local caching system

---

## 📌 Future Improvements

* 🔍 Better summarization accuracy
* 🌐 Multi-language support
* ☁️ Cloud deployment support
* 🎯 Personalized learning insights

