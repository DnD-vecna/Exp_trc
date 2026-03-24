from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request, FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, extract
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, ConfigDict
from typing import List
import datetime
import os

# --- APP INIT ---
app = FastAPI(title="Expense Tracker API")

# --- TEMPLATES ---
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Pass 'request' as a keyword argument (NOT inside the context dict)
    # This specifically fixes the "unhashable type: 'dict'" error
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )

# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./expenses.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String, unique=True, index=True)

class DBTransaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date)
    t_type = Column(String)
    category = Column(String)
    amount = Column(Float)

Base.metadata.create_all(bind=engine)

# --- SCHEMAS ---
class TransactionCreate(BaseModel):
    date: datetime.date = None
    t_type: str
    category: str
    amount: float

class TransactionOut(TransactionCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DB DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- USER DEPENDENCY ---
def get_current_user(x_user_uid: str = Header(...), db: Session = Depends(get_db)):
    if not x_user_uid:
        raise HTTPException(status_code=400, detail="UID Header missing")
    user = db.query(DBUser).filter(DBUser.uid == x_user_uid).first()
    if not user:
        user = DBUser(uid=x_user_uid)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

# --- ROUTES ---
@app.post("/api/auth")
def authenticate(user: DBUser = Depends(get_current_user)):
    return {"message": "Authenticated", "uid": user.uid}

@app.post("/api/transactions", response_model=TransactionOut)
def add_transaction(transaction: TransactionCreate, user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    txn_date = transaction.date or datetime.date.today()
    new_txn = DBTransaction(
        user_id=user.id,
        date=txn_date,
        t_type=transaction.t_type.capitalize(),
        category=transaction.category,
        amount=transaction.amount
    )
    db.add(new_txn)
    db.commit()
    db.refresh(new_txn)
    return new_txn

@app.get("/api/transactions", response_model=List[TransactionOut])
def view_transactions(user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(DBTransaction).filter(DBTransaction.user_id == user.id).order_by(DBTransaction.date.desc()).all()

@app.get("/api/transactions/summary")
def monthly_summary(user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.date.today()
    monthly_txns = db.query(DBTransaction).filter(
        DBTransaction.user_id == user.id,
        extract('year', DBTransaction.date) == today.year,
        extract('month', DBTransaction.date) == today.month
    ).all()
    income = sum(t.amount for t in monthly_txns if t.t_type == "Income")
    expense = sum(t.amount for t in monthly_txns if t.t_type == "Expense")
    categories = {}
    for t in monthly_txns:
        if t.t_type == "Expense":
            categories[t.category] = categories.get(t.category, 0) + t.amount
    return {
        "month": f"{today.month}/{today.year}",
        "total_income": income,
        "total_spent": expense,
        "balance": income - expense,
        "expense_by_category": categories
    }

@app.delete("/api/transactions")
def clear_transactions(user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(DBTransaction).filter(DBTransaction.user_id == user.id).delete()
    db.commit()
    return {"message": "All transactions cleared"}
