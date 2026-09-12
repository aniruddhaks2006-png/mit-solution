# Contributing to MIT Solution

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this hackathon solution project.

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## How to Contribute

### Reporting Issues
1. **Check existing issues** – avoid duplicates
2. **Use a clear title** – describe the problem concisely
3. **Include details:**
   - Steps to reproduce
   - Expected vs. actual behavior
   - Environment (Python version, OS, browser if frontend)
   - Error logs or screenshots

### Submitting Changes

1. **Fork the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/mit-solution.git
   cd mit-solution
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Set up your environment**
   - **Problem 1 (Streamlit):**
     ```bash
     cd "health care/problem 1 solution"
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     pip install -r requirements.txt
     ```
   
   - **Problem 2 (FastAPI + React):**
     ```bash
     # Backend
     cd "health care/problem 2 solution/backend"
     python -m venv venv
     source venv/bin/activate
     pip install -r requirements.txt
     
     # Frontend (in another terminal)
     cd "health care/problem 2 solution/frontend"
     npm install
     ```

4. **Make your changes**
   - Keep commits atomic and descriptive
   - Follow existing code style
   - Add comments for complex logic
   - Update relevant documentation

5. **Test locally**
   - **Problem 1:** `streamlit run app.py`
   - **Problem 2 Backend:** `uvicorn main:app --reload`
   - **Problem 2 Frontend:** `npm run dev`

6. **Commit and push**
   ```bash
   git add .
   git commit -m "Fix: descriptive message (Problem 1/2)"
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Reference the issue it addresses (if applicable)
   - Describe what you changed and why
   - Note any new dependencies

## Development Guidelines

### Python Code
- Use Python 3.10+
- Follow PEP 8 style (use `black` for formatting if available)
- Add docstrings to functions/classes
- Test your changes

### React/Frontend Code
- Use modern JavaScript (ES6+)
- Keep components small and focused
- Use meaningful variable/component names
- Test across browsers (Chrome, Firefox, Safari)

### Documentation
- Update README files if you change functionality
- Comment non-obvious logic
- Keep examples working

## Project Structure

```
health care/
├── problem 1 solution/          # Medication Adherence (Streamlit)
│   ├── app.py                   # Main dashboard
│   ├── model.py                 # ML model logic
│   ├── feature_engineering.py   # Feature extraction
│   ├── data_generator.py        # Synthetic data
│   └── requirements.txt
│
└── problem 2 solution/          # Medicine Shortage (FastAPI + React)
    ├── backend/                 # FastAPI server
    │   ├── main.py              # App entry point
    │   ├── data_generator.py    # Synthetic facility data
    │   └── requirements.txt
    └── frontend/                # React + Vite
        ├── src/
        ├── vite.config.js
        └── package.json
```

## Questions?

Open an issue with the label `question` or `help wanted` and describe what you need assistance with.

---

**Thank you for contributing to this project!** 🙏
