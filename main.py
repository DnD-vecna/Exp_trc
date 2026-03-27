import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI(title="Expense Tracker API")
templates = Jinja2Templates(directory="templates")

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
import os
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional

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
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Supabase Environment Variables are missing!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- MODELS ----------
class TransactionCreate(BaseModel):
    date: Optional[datetime.date] = None
    t_type: str
    category: str
    amount: float

class TransactionOut(BaseModel):
    id: Optional[int] = None
    user_id: Optional[str] = None
    date: Optional[datetime.date] = None
    t_type: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://expense-trackerrr-f4nb.onrender.com", 
        "http://localhost:5500", 
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- AUTH HELPER ----------
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No Authorization header")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        res = supabase.auth.get_user(token)
        if not res.user:
            raise HTTPException(status_code=401, detail="Invalid user session")

        return res.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# ---------- ROUTES ----------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"request": request}
    )

# ADD TRANSACTION
@app.post("/add-transaction")
async def add_transaction(amount: float, category: str, t_type: str):
    # 1. Get the authenticated user's ID
    user_res = supabase.auth.get_user()
    if not user_res.user:
        return {"error": "Unauthorized"}
    
    uid = user_res.user.id

    # 2. Prepare the data payload including the user_id
    new_transaction = {
        "user_id": uid, # This matches the column in your screenshot
        "amount": amount,
        "category": category,
        "t_type": t_type,
        "date": "2026-03-27" # Or use datetime.now()
    }

    # 3. Execute the insert
    try:
        result = supabase.table("transactions").insert(new_transaction).execute()
        return result
    except Exception as e:
        return {"error": str(e)}

# GET TRANSACTIONS
@app.get("/api/transactions", response_model=List[TransactionOut])
async def get_transactions(user=Depends(get_current_user)):
    try:
        res = supabase.table("transactions")\
            .select("*")\
            .eq("user_id", user.id)\
            .order("date", desc=True)\
            .execute()
        return res.data
    except Exception as e:
        print(f"DEBUG GET ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# SUMMARY
@app.get("/api/transactions/summary")
async def summary(user=Depends(get_current_user)):
    try:
        today = datetime.date.today()
        first_day = today.replace(day=1).isoformat()

        res = supabase.table("transactions")\
            .select("*")\
            .eq("user_id", user.id)\
            .gte("date", first_day)\
            .execute()

        txns = res.data or []
        
        # Consistent case comparison
        income = sum(t["amount"] for t in txns if t["t_type"].lower() == "income")
        expense = sum(t["amount"] for t in txns if t["t_type"].lower() == "expense")

        return {
            "total_income": round(income, 2),
            "total_spent": round(expense, 2),
            "balance": round(income - expense, 2)
        }
    except Exception as e:
        print(f"DEBUG SUMMARY ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# DELETE
@app.delete("/api/transactions")
async def delete_all(user=Depends(get_current_user)):
    try:
        supabase.table("transactions").delete().eq("user_id", user.id).execute()
        return {"message": "All transactions deleted"}
    except Exception as e:
        print(f"DEBUG DELETE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
