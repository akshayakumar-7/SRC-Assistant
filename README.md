# SRC Assistant

An AI-powered campus assistant designed to help SRC Kumbakonam students find campus locations, explore facilities, and get answers through a simple web interface.

## Features

- Flask-based web application
- Campus location lookup using JSON data
- Alternative names and aliases for campus locations
- RapidFuzz-based approximate matching
- Groq-powered AI conversation
- Basic campus floor and route support
- Web-based chat interface

*Note: Features and campus data are still under development.*

## Requirements

- Python 3.12 recommended
- Git
- A Groq API key for AI-powered responses

## Installation

### 1. Clone the repository

```bash
git clone YOUR_REPOSITORY_URL
cd YOUR_REPOSITORY_FOLDER
```

Replace the example values with the repository URL and folder name.

### 2. Create a virtual environment

```bash
py -3.12 -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure the API key

Create a file named `.env` in the project root.

Add your own key:

```env
GROQ_API_KEY=your_own_groq_api_key
```

Never publish your `.env` file or share your private API key.

### 5. Run the application

```bash
python app.py
```

Open the local address displayed in the terminal, usually:

http://127.0.0.1:5000

## Project Structure

```text
SRC-Assistant/
├── app.py
├── locations.json
├── aliases.json
├── campus_graph.json
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   ├── landing.html
│   └── index.html
└── static/
    └── frontend assets
```

The structure above is illustrative. Check the actual repository for the complete list of files.

## Important Notes

- Campus information depends on the supplied JSON data.
- Some locations, aliases and navigation features may be incomplete.
- AI-generated answers are not a substitute for verified campus records.
- AI features require a valid API key and may be subject to the provider's usage limits.
- Do not commit API keys, passwords, or other secrets.

## Contributing

Contributions, bug reports, and suggestions are welcome. Please test changes before submitting them and avoid including private credentials in commits.

## Project Status

SRC Assistant is an ongoing student development project. Features, accuracy, navigation and documentation will continue to improve.