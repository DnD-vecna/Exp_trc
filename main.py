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

class TransactionOut(TransactionCreate):
    id: int
    user_id: str

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
@app.post("/api/transactions", response_model=TransactionOut)
def add_transaction(transaction: TransactionCreate, user=Depends(get_current_user)):

    data = {
        "user_id": user.id,
        "date": str(transaction.date or datetime.date.today()),
        "t_type": transaction.t_type.capitalize(),
        "category": transaction.category,
        "amount": transaction.amount
    }

    res = supabase.table("transactions").insert(data).execute()

    if not res.data:
        raise HTTPException(status_code=400, detail="Insert failed")

    return res.data[0]

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
