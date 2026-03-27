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
@app.post("/api/transactions")
async def add_transaction(transaction: TransactionCreate, user=Depends(get_current_user)):
    try:
        payload = {
            "user_id": str(user.id),
            "date": str(transaction.date or datetime.date.today()),
            "t_type": transaction.t_type.capitalize(),
            "category": transaction.category,
            "amount": float(transaction.amount)
        }
        
        res = supabase.table("transactions").insert(payload).execute()
        
        if res.data:
            return res.data[0]
        
        raise HTTPException(status_code=400, detail="Database rejected the insert.")

    except Exception as e:
        print(f"DEBUG ADD ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
