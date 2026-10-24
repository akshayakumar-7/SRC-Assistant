# SRC Assistant

An AI-powered campus assistant designed to help SASTRA SRC Kumbakonam students find campus locations, explore facilities, and get answers through a simple web interface.

## Features

- Flask-based web application
- Campus location lookup using JSON data
- Alternative names and aliases for campus locations
- RapidFuzz-based approximate matching
- Groq-powered AI conversation
- Basic campus floor and route support
- Web-based chat interface

**Project status:** Under development. Some campus information and navigation features may be incomplete.

## Requirements

- Python 3.12
- Git
- A Groq API key for AI-powered responses

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/akshayakumar-7/SRC-Assistant.git
cd SRC-Assistant
```

### 2. Create a virtual environment

```bash
py -3.12 -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure your API key

Copy `.env.example` to a new file named `.env` in the project root.

On Windows Command Prompt, you can use:

```bat
copy .env.example .env
```

Open `.env` and enter your own Groq API key:

```dotenv
GROQ_API_KEY=your_own_groq_api_key
```

Get your key through the [Groq Console](https://console.groq.com/).

**Never upload or share your `.env` file or API key.** Each user should use their own key.

### 5. Run the application

```bash
python app.py
```

Open this address in your browser:

http://127.0.0.1:5000

## Project Structure

```text
SRC-Assistant/
├── app.py
├── locations.json
├── aliases.json
├── campus_graph.json
├── location_matching.py
├── navigation.py
├── navigation_names.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── templates/
└── static/
```

## Important Notes

- Campus information depends on the supplied JSON data.
- Some locations, aliases and navigation features may be incomplete.
- AI-generated answers may be inaccurate; verify important campus information.
- AI features require a valid Groq API key and are subject to provider limits.
- Never commit API keys, passwords or other secrets.

## Contributing

Suggestions, bug reports and improvements are welcome. Please test changes before submitting them, and never include private credentials in commits.

## Project Status

SRC Assistant is an ongoing student development project. Features, accuracy, navigation and documentation will continue to improve.
