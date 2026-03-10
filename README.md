# Market Dashboard

A Python project that fetches real-time stock market data, processes it with pandas, and produces financial visualisations comparing different stocks. Built as a portfolio project for data/business analyst roles in Finance and FinTech.

## Features
- Fetches live historical stock data via the yfinance API
- Calculates daily returns and rolling averages using pandas
- Plots price history with trend overlay (matplotlib)
- Compares multiple tickers on a normalised performance chart

## Setup

1. Clone the repository
   git clone https://github.com/joakim-hersche/market-dashboard.git
   cd market-dashboard

2. Install dependencies
   pip install -r requirements.txt

3. Open the notebook
   jupyter notebook notebooks/01_data_exploration.ipynb

## Project Structure
market-dashboard/
├── notebooks/        # Jupyter notebooks
├── src/              # Python scripts (upcoming)
├── data/             # Local data files (gitignored)
├── requirements.txt
└── README.md

## Tech Stack
- Python 3.12
- pandas
- yfinance
- matplotlib

[![Live Demo](https://market-dashboardgit-p4ehquxxrncud3gzyvhbeq.streamlit.app)
