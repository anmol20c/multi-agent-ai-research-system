# 🧠 ResearchMind – Multi-Agent AI Research System

An AI-powered research automation system that uses multiple specialized AI agents to search, extract, write, and evaluate research reports automatically.

🌐 **Live Demo:** https://multi-agent-ai-research-system-htfrzaylpdfsnwbdrqnarx.streamlit.app/

## 🚀 Overview

ResearchMind is a multi-agent research application built using LangChain, Groq LLMs, and Streamlit. It automates the research workflow by assigning different tasks to specialized AI agents, from gathering information to generating and reviewing a structured research report.

## ✨ Key Features

- 🔍 **Search Agent:** Finds relevant and recent information from the web.
- 📄 **Reader Agent:** Scrapes selected URLs and extracts detailed content.
- ✍️ **Writer Chain:** Generates structured research reports.
- 🧐 **Critic Chain:** Evaluates reports, provides scores, identifies strengths, and suggests improvements.
- 📊 **Interactive Dashboard:** Displays research results, pipeline progress, and agent activity.
- 📥 **Report Download:** Download generated research reports in Markdown format.
- 🎨 **Custom UI:** Dark and light themes with an interactive Streamlit interface.
- 📚 **Research History:** Stores previous research sessions.

## 🏗️ System Architecture

User Input (Research Topic)  
↓  
Search Agent – Web Search  
↓  
Reader Agent – URL Scraping  
↓  
Writer Chain – Report Generation  
↓  
Critic Chain – Report Evaluation  
↓  
Final Research Report + Feedback

## 🛠️ Tech Stack

- **Programming Language:** Python
- **LLM Framework:** LangChain
- **LLM Provider:** Groq
- **AI Models:** Groq-supported LLM
- **Frontend:** Streamlit
- **Web Search & Extraction:** Custom Search and Scraping Tools
- **Environment Management:** Python dotenv
- **Deployment:** Streamlit Community Cloud
- **Version Control:** Git & GitHub

## 📂 Project Structure

```text
multi-agent-ai-research-system/
│
├── agents.py           # AI agents and LLM chains
├── pipeline.py         # Main research workflow
├── tools.py            # Web search and scraping tools
├── app.py              # Streamlit application
├── test_model.py       # Model testing
├── requirements.txt    # Project dependencies
├── .env                # API keys (not uploaded)
├── .gitignore          # Ignored files
└── research_history/   # Saved research sessions
```

## ⚙️ Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/anmol20c/multi-agent-ai-research-system.git
cd multi-agent-ai-research-system
```

### 2. Create a virtual environment

```bash
uv venv
```

### 3. Activate the environment (Windows)

```bash
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
uv sync
```

If using requirements.txt instead:

```bash
uv pip install -r requirements.txt
```

### 5. Configure API key

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_api_key
```

### 6. Run the application

```bash
uv run streamlit run app.py
```

## 📸 Application Preview

Add screenshots of your Streamlit dashboard here.

## 🎯 Project Objective

The objective of ResearchMind is to demonstrate how multiple specialized AI agents can collaborate to automate complex research tasks, reduce manual effort, and generate structured, AI-assisted research reports.

## 👩‍💻 Author

**Anmol Choudhary**

- [GitHub](https://github.com/anmol20c)
- [LinkedIn](https://www.linkedin.com/in/anmol-choudhary-08002528a/)
- [Portfolio](https://relaxed-frangipane-0157d6.netlify.app/)

---

⭐ If you find this project interesting, consider giving it a star!