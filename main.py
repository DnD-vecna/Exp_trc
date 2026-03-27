import os
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


# Initialize FastAPI
app = FastAPI()

# Enable CORS so your frontend can talk to your backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://expense-trackerrr-f4nb.onrender.com", 
        "http://localhost:5500", 
        "http://127.0.0.1:5500"],  # For production, replace with your specific Render URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase Configuration
SUPABASE_URL = "https://pvsegoyevnivyfllqmuv.supabase.co"
# Use your Service Role Key if you want to bypass RLS, or Anon Key to respect it.
# Based on your setup, Anon Key is used.
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB2c2Vnb3lldm5pdnlmbGxxbXV2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzAzMjgsImV4cCI6MjA5MDA0NjMyOH0.88nQJAS2k3CVGqPXMCW41tDt3uFpiCfR2ONPJIkWVvE"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Data Model for Transactions
class Transaction(BaseModel):
    t_type: str
    category: str
    amount: float
    date: str
    user_id: Optional[str] = None

# --- ROUTES ---
# Add this route to serve your index.html as the home page
@app.get("/")
async def serve_home():
    return FileResponse("index.html")
    
@app.get("/")
def read_root():
    return {"status": "Backend is running"}

# GET all transactions for the logged-in user
@app.get("/api/transactions")
async def get_transactions(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    # We use the token to set the session so Supabase knows who is asking
    token = authorization.replace("Bearer ", "")
    supabase.postgrest.auth(token)
    
    try:
        response = supabase.table("transactions").select("*").order("date", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# POST a new transaction
@app.post("/api/transactions")
async def add_transaction(transaction: Transaction, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    token = authorization.replace("Bearer ", "")
    # Set auth context for the request
    supabase.postgrest.auth(token)

    # Prepare data for insertion
    data = {
        "t_type": transaction.t_type,
        "category": transaction.category,
        "amount": transaction.amount,
        "date": transaction.date,
        "user_id": transaction.user_id # This comes from the frontend fix we did earlier
    }

    try:
        response = supabase.table("transactions").insert(data).execute()
        return response.data
    except Exception as e:
        # This will catch the RLS error if user_id is missing or wrong
        raise HTTPException(status_code=400, detail=str(e))

# GET summary (Income, Expense, Balance)
@app.get("/api/transactions/summary")
async def get_summary(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    token = authorization.replace("Bearer ", "")
    supabase.postgrest.auth(token)

    try:
        response = supabase.table("transactions").select("*").execute()
        data = response.data
        
        total_income = sum(t['amount'] for t in data if t['t_type'] == 'Income')
        total_spent = sum(t['amount'] for t in data if t['t_type'] == 'Expense')
        
        return {
            "total_income": total_income,
            "total_spent": total_spent,
            "balance": total_income - total_spent
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# DELETE all transactions for the user
@app.delete("/api/transactions")
async def clear_transactions(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")

    token = authorization.replace("Bearer ", "")
    supabase.postgrest.auth(token)

    try:
        # In a real app, you'd filter by user_id here, 
        # but RLS policies usually handle this automatically if set up.
        # We'll perform a broad delete that RLS will restrict to the owner.
        response = supabase.table("transactions").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        return {"status": "success", "deleted": len(response.data)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Use port from environment (Render requirement)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
