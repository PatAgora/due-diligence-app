# Scrutinise Due Diligence Platform

A comprehensive financial crime due diligence workflow and reporting platform with integrated Transaction Review, AI SME assistance, and Quality Control modules.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Manual Setup](#manual-setup)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software

1. **Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)
   - Verify installation: `python --version` or `python3 --version`

2. **Node.js 16.x or higher and npm**
   - Download from [nodejs.org](https://nodejs.org/)
   - npm comes bundled with Node.js
   - Verify installation:
     ```bash
     node --version
     npm --version
     ```


### Optional but Recommended

- **Virtual Environment** (Python): Recommended for isolating dependencies
- **Code Editor**: VS Code, PyCharm, or any preferred IDE

## Project Structure

```
Development Modules/
├── Due Diligence/          # Main Flask backend application
│   ├── app.py              # Main Flask application
│   ├── utils.py            # Utility functions
│   ├── tx_review_ingest.py # Transaction Review ingestion logic
│   ├── templates/          # HTML templates (legacy)
│   └── scrutinise_workflow.db  # SQLite database (created on first run)
│
├── AI SME/                 # FastAPI backend for AI SME module
│   ├── app.py             # FastAPI application
│   ├── llm.py             # LLM integration (OpenAI/Ollama)
│   └── chroma_db/         # Vector database (created on first run)
│
├── frontend/               # React frontend application
│   ├── src/               # React source code
│   ├── public/            # Static assets
│   ├── package.json       # Node.js dependencies
│   └── vite.config.js     # Vite configuration
│
├── Transaction Review/     # Legacy Transaction Review module (reference)
│
├── initialize.py           # Automated initialization script
├── start_services.py       # Script to run all services
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Installation

### Quick Start (Automated)

The easiest way to set up the project is using the provided initialization script:

1. **Navigate to the project root directory:**

2. **Run the initialization script:**
   ```bash
   python initialize.py
   ```
   
   Or on Linux/Mac:
   ```bash
   python3 initialize.py
   ```

   This script will:
   - Check for Python and Node.js installations
   - Install Python dependencies from `requirements.txt`
   - Navigate to the `frontend` directory
   - Install Node.js dependencies via `npm install`

### Manual Installation

If you prefer to install dependencies manually:

#### 1. Install Python Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Install Node.js Dependencies

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Return to root directory
cd ..
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory or in the `Due Dilligence` directory with the following variables:

```env
# OpenAI API Key (required for AI SME)
OPENAI_API_KEY=your_openai_api_key_here

# Sumsub API Credentials (required for identity verification)
SUMSUB_APP_TOKEN=your_sumsub_app_token
SUMSUB_SECRET_KEY=your_sumsub_secret_key

# SendGrid API Key (required for 2FA emails)
SENDGRID_API_KEY=your_sendgrid_api_key

# Flask Secret Key (for session management)
SECRET_KEY=your_secret_key_here

# Database Path (optional, defaults to Due Diligence/scrutinise_workflow.db)
TX_DB=path/to/database.db
```

**Note:** The `.env` file should be added to `.gitignore` and never committed to version control.

### Database Setup

The SQLite database (`scrutinise_workflow.db`) will be created automatically on first run. If you need to initialize it manually or reset it, the application will create the necessary tables when it starts.

## Running the Application

### Quick Start (All Services)

To run all services (Due Diligence backend, AI SME backend, and Frontend) simultaneously:

```bash
python start_services.py
```

Or on Linux/Mac:
```bash
python3 start_services.py
```

This will start:
- **Due Diligence Flask Backend** on `http://localhost:5050`
- **AI SME FastAPI Backend** on `http://localhost:8000`
- **React Frontend** on `http://localhost:5173` (Vite default port)

Press `Ctrl+C` to stop all services.

### Running Services Individually

#### 1. Due Diligence Backend (Flask)

```bash
cd "Due Diligence"
python app.py
```

The backend will be available at `http://localhost:5050`

#### 2. AI SME Backend (FastAPI)

```bash
cd "AI SME"
python app.py
```

Or using uvicorn directly:
```bash
cd "AI SME"
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

#### 3. Frontend (React/Vite)

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173` (or the next available port)

### Accessing the Application

Once all services are running:

1. Open your web browser
2. Navigate to `http://localhost:5173`
3. You will be redirected to the login page
4. Use your credentials to log in

**Default Admin Account:**
- Email: `admin@scrutinise.co.uk`
- Password: (set during initial setup)

## Manual Setup

If you encounter issues with the automated scripts, you can set up manually:

### Step 1: Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### Step 2: Node.js Environment

```bash
cd frontend
npm install
cd ..
```

### Step 3: Database Initialization

The database will be created automatically when you first run the Flask application. No manual setup required.

### Step 4: Start Services

Start each service in separate terminal windows:

**Terminal 1 - Due Diligence:**
```bash
cd "Due Diligence"
python app.py
```

**Terminal 2 - AI SME:**
```bash
cd "AI SME"
python app.py
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm run dev
```

## Troubleshooting

### Common Issues

#### 1. Python/Node.js Not Found

**Error:** `python: command not found` or `npm: command not found`

**Solution:**
- Ensure Python and Node.js are installed and added to your system PATH
- On Windows, you may need to restart your terminal after installation
- Verify installation with `python --version` and `node --version`

#### 2. Port Already in Use

**Error:** `Address already in use` or `Port 5050/8000/5173 is already in use`

**Solution:**
- Stop any other services using these ports
- On Windows: `netstat -ano | findstr :5050` to find the process, then kill it
- On Linux/Mac: `lsof -i :5050` to find the process, then `kill -9 <PID>`
- Or change the port in the respective configuration files

#### 3. Module Not Found (Python)

**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
- Ensure you're in a virtual environment: `pip install -r requirements.txt`
- Verify the virtual environment is activated

#### 4. npm Install Fails

**Error:** `npm ERR!` during installation

**Solution:**
- Clear npm cache: `npm cache clean --force`
- Delete `node_modules` and `package-lock.json` in the frontend directory
- Run `npm install` again
- Ensure you have sufficient disk space

#### 5. Database Locked Error

**Error:** `sqlite3.OperationalError: database is locked`

**Solution:**
- Ensure only one instance of the Flask app is running
- Close any database viewers or tools accessing the database
- Restart the Flask application

#### 6. CORS Errors

**Error:** `CORS policy: No 'Access-Control-Allow-Origin' header`

**Solution:**
- Ensure all services are running
- Verify the frontend is making requests to the correct backend URLs
- Check that Flask-CORS is properly configured in `app.py`

#### 7. AI SME Not Working

**Error:** `OPENAI_API_KEY not set` or 401/403 errors

**Solution:**
- Ensure `.env` file exists in the `AI SME` directory
- Verify `OPENAI_API_KEY` is set correctly in the `.env` file
- Restart the AI SME backend after adding environment variables

#### 8. Login Redirects Back to Login

**Error:** After successful login, redirected back to login page

**Solution:**
- Clear browser cookies and localStorage
- Ensure session cookies are being set (check browser DevTools)
- Verify the backend is running and accessible
- Check browser console for JavaScript errors

### Getting Help

If you encounter issues not covered here:

1. Check the terminal/console output for error messages
2. Review the browser console (F12) for frontend errors
3. Verify all environment variables are set correctly
4. Ensure all prerequisites are installed and up to date
5. Check that all services are running on the correct ports

## Development Notes

### Database

- The application uses SQLite for data storage
- Database file: `Due Diligence/scrutinise_workflow.db`
- Tables are created automatically on first run
- **Important:** Always backup the database before making schema changes

### API Endpoints

- **Due Diligence Backend:** `http://localhost:5050`
- **AI SME Backend:** `http://localhost:8000`
- **Frontend:** `http://localhost:5173`

### Module Toggles

The application supports enabling/disabling modules:
- Due Diligence (core module)
- Transaction Review
- AI SME

Module settings can be configured by admin users in the Module Settings page.

## License

[Add your license information here]

## Support

For support and questions, please contact [your support email/contact information]

