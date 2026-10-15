# AGENTS.md

## Project Overview

Help Desk & Ticket Management System with ML-based ticket resolution time prediction.

## Commands

### Running the Application
- Start the development server: `python app.py`
- The app runs on `http://127.0.0.1:5000`

### ML Model Training
- Train/retrain the ML model: `python -m ml.train_resolution_model`
- The training script fetches resolved tickets from the database, preprocesses text features, trains a GradientBoostingRegressor with TF-IDF, evaluates performance, and deploys the model if it improves over the existing version.
- Minimum training data: 5 resolved tickets with `resolved_at` set

### ML Model Management
- View and manage the ML model: `http://127.0.0.1:5000/ml-model` (Super Admin only)
- View prediction history: `http://127.0.0.1:5000/ml-predictions` (Super Admin only)
- Retrain model: POST to `/ml-model/retrain` (Super Admin only)

### Linting and Type Checking
- Syntax check: `python -c "import ast; [ast.parse(open(f).read()) for f in [...]]"`
- Compile check: `python -m py_compile <file>`
- Type checking: `npx pyright` (requires Node.js)

### Testing
- All tests run through Flask test client: `python -m pytest` or custom test scripts
- ML integration tests: use venv Python at `venv\Scripts\python.exe`

### Dependencies
- Python 3.12
- Flask
- scikit-learn, numpy, pandas, scipy (for ML)
- SQLAlchemy + psycopg2 (for PostgreSQL)

### Environment
- Virtual environment: `venv/`
- Config: `.env` file for database URL and other settings
- Templates: Jinja2 templates in `templates/`
