import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

# --- APP INIT ---
app = FastAPI(title="Expense Tracker API")
templates = Jinja2Templates(directory="templates")

# --- SUPABASE CONFIG ---
# These will be pulled from Render's Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing! Add them to Render Environment Variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SCHEMAS ---
class TransactionCreate(BaseModel):
    date: Optional[datetime.date] = None
    t_type: str
    category: str
    amount: float

class TransactionOut(TransactionCreate):
    id: int
    user_id: str 

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AUTH DEPENDENCY ---
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No Authorization header found")
    
    try:
        # Expected format: "Bearer <JWT_TOKEN>"
        token = authorization.split(" ")[1]
        user_resp = supabase.auth.get_user(token)
        return user_resp.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.post("/api/transactions", response_model=TransactionOut)
def add_transaction(transaction: TransactionCreate, user=Depends(get_current_user)):
    txn_date = str(transaction.date or datetime.date.today())
    
    data = {
        "user_id": user.id,
        "date": txn_date,
        "t_type": transaction.t_type.capitalize(),
        "category": transaction.category,
        "amount": transaction.amount
    }
    
    response = supabase.table("transactions").insert(data).execute()
    return response.data[0]

@app.get("/api/transactions", response_model=List[TransactionOut])
def view_transactions(user=Depends(get_current_user)):
    response = supabase.table("transactions")\
        .select("*")\
        .eq("user_id", user.id)\
        .order("date", desc=True)\
        .execute()
    return response.data

@app.get("/api/transactions/summary")
def monthly_summary(user=Depends(get_current_user)):
    today = datetime.date.today()
    # Logic to get the start of the current month
    first_day = today.replace(day=1).isoformat()
    
    response = supabase.table("transactions")\
        .select("*")\
        .eq("user_id", user.id)\
        .gte("date", first_day)\
        .execute()
    
    txns = response.data
    income = sum(t['amount'] for t in txns if t['t_type'].lower() == "income")
    expense = sum(t['amount'] for t in txns if t['t_type'].lower() == "expense")
    
    categories = {}
    for t in txns:
        if t['t_type'].lower() == "expense":
            cat = t['category']
            categories[cat] = categories.get(cat, 0) + t['amount']
            
    return {
        "month": f"{today.month}/{today.year}",
        "total_income": income,
        "total_spent": expense,
        "balance": income - expense,
        "expense_by_category": categories
    }

@app.delete("/api/transactions")
def clear_transactions(user=Depends(get_current_user)):
    supabase.table("transactions").delete().eq("user_id", user.id).execute()
    return {"message": "Success"}
