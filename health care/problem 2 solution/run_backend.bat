@echo off
cd backend
python -m pip install -r requirements.txt
python data_generator.py
uvicorn main:app --reload
