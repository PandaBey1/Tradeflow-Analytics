from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import pandas as pd
import io
import os
from datetime import datetime
from logic import fetch_stock_data
from tickers import get_bist_tickers

app = FastAPI(title="Stock Momentum Explorer API")

# CORS Setup
origins = [
    "http://localhost:5173", # Vite default
    "http://localhost:3000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TickerRequest(BaseModel):
    tickers: List[str] = [] # Optional, defaults to empty list

class StockData(BaseModel):
    ticker: str
    period: str
    price: float
    change_1d: float
    change_3d: float
    change_5d: float
    change_7d: float
    rsi_daily: float
    ma5: float
    dist_ma5: float
    score: float
    signal: str

@app.get("/")
def read_root():
    return {"message": "Stock Momentum Explorer API is running"}

@app.post("/scan", response_model=List[StockData])
def scan_tickers(payload: TickerRequest):
    """
    Scans the provided list of tickers. 
    If 'tickers' list is empty, scans ALL BIST tickers (using cached logic).
    """
    try:
        target_tickers = payload.tickers
        if not target_tickers:
            # Use the BIST ALL list
            target_tickers = get_bist_tickers()
            print(f"No specific tickers provided. Scanning all {len(target_tickers)} BIST tickers...")
        
        # Logic handles caching internally
        data = fetch_stock_data(target_tickers, use_cache=True)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export")
def export_results(data: List[StockData]):
    """
    Receives the current table data and returns an Excel file.
    """
    try:
        # Convert Pydantic models to dicts
        records = [item.dict() for item in data]
        df = pd.DataFrame(records)
        
        # Create a BytesIO buffer to write the Excel file
        # We need to save to a temporary file or buffer.
        # FastAPI FileResponse works best with actual files or streams.
        # Let's save to a temp file for simplicity
        
        filename = f"momentum_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(os.getcwd(), filename)
        
        df.to_excel(filepath, index=False)
        
        return FileResponse(path=filepath, filename=filename, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
