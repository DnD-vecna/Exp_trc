import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI(title = "Expense Tracker APII")
templates = Jinja2Templates(directory="templates")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- AUTH ----------
# ---------- AUTH ----------
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No Authorization header")

    try:
        # Expecting "Bearer <token>"
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        # Use the GLOBAL client to get the user
        # This validates the JWT with Supabase Auth
        res = supabase.auth.get_user(token)
        
        if not res.user:
            raise HTTPException(status_code=401, detail="Invalid user")

        return res.user

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth error: {str(e)}")

# ---------- ROUTES ----------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Change this line:
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"request": request}
    )

# ADD TRANSACTION
@app.post("/api/transactions") # Removed response_model temporarily to debug
async def add_transaction(transaction: TransactionCreate, user=Depends(get_current_user)):
    try:
        # We manually build the dict to ensure NO hidden 'id' or 'None' values are sent
        payload = {
            "user_id": str(user.id),
            "date": str(transaction.date or datetime.date.today()),
            "t_type": transaction.t_type.capitalize(),
            "category": transaction.category,
            "amount": float(transaction.amount)
        }
        
        print(f"DEBUG: Sending to Supabase -> {payload}")
        
        res = supabase.table("transactions").insert(payload).execute()
        
        if not res.data:
            print(f"DEBUG: Supabase returned empty data: {res}")
            raise HTTPException(status_code=400, detail="Insert failed - no data returned")
            
        return res.data[0]

    except Exception as e:
        print(f"CRITICAL DATABASE ERROR: {str(e)}")
        # This sends the ACTUAL error message to your browser console
        raise HTTPException(status_code=500, detail=str(e))

# GET TRANSACTIONS
@app.get("/api/transactions", response_model=List[TransactionOut])
def get_transactions(user=Depends(get_current_user)):
    # Use the global supabase client
    res = supabase.table("transactions")\
        .select("*")\
        .eq("user_id", user.id)\
        .order("date", desc=True)\
        .execute()

    return res.data

# SUMMARY
@app.get("/api/transactions/summary")
def summary(user=Depends(get_current_user)):

    today = datetime.date.today()
    first_day = today.replace(day=1).isoformat()

    res = supabase.table("transactions")\
        .select("*")\
        .eq("user_id", user.id)\
        .gte("date", first_day)\
        .execute()

    txns = res.data

    income = sum(t["amount"] for t in txns if t["t_type"].lower() == "income")
    expense = sum(t["amount"] for t in txns if t["t_type"].lower() == "expense")

    return {
        "total_income": income,
        "total_spent": expense,
        "balance": income - expense
    }

# DELETE
@app.delete("/api/transactions")
def delete_all(user=Depends(get_current_user)):

    supabase.table("transactions").delete().eq("user_id", user.id).execute()

    return {"message": "Deleted"}
