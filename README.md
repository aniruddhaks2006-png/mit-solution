# MIT Solution

Hackathon problem solutions.

## Structure

```
mit-solution
└── health care
    ├── problem 1 solution
    │   └── The Vanishing Dose                  medication adherence anomaly detection
    │       ├── app.py                         Streamlit dashboard
    │       ├── data_generator.py              synthetic patient cohort
    │       ├── feature_engineering.py         refill-interval + signal features
    │       ├── model.py                       rules + IsolationForest + confidence
    │       ├── requirements.txt
    │       ├── LICENSE                        MIT
    │       └── README.md
    └── problem 2 solution
        └── Medicine Shortage Early Warning System
            ├── backend/     FastAPI + pandas risk engine
            └── frontend/    React + Vite + Recharts dashboard
```

See `health care/problem 1 solution/README.md` for the full problem statement,
architecture, and run instructions (medication non-adherence / under-use and
over-use anomaly detection).