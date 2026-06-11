# CobroPro — Código Completo

---
### FILE: services/api/app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .config import settings
from .routers import auth, customers, loans, visits, payments, reconciliation, reports, privacy, audit, cash, groups, tenants, users, branches, devices, keys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title=settings.APP_NAME)

# Configuración de CORS - DEBE estar antes de los routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",  # Por si acaso usas otro puerto
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/health")
def health():
    return {"ok": True, "app": settings.APP_NAME}

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(loans.router)
app.include_router(visits.router)
app.include_router(payments.router)
app.include_router(reconciliation.router)
app.include_router(reports.router)
app.include_router(privacy.router)
app.include_router(audit.router)
app.include_router(cash.router)
app.include_router(groups.router, prefix="/groups", tags=["groups"])
app.include_router(tenants.router)
app.include_router(users.router)
app.include_router(branches.router)
app.include_router(devices.router)
app.include_router(keys.router)
```

---
### FILE: services/api/app/config.py
```python
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"  # Ignorar variables extra en el .env que no estén definidas
    )
    
    APP_NAME: str = "CobroPro API"
    ENV: str = "local"
    JWT_SECRET: str = "change_me_now"
    JWT_ALG: str = "HS256"
    JWT_EXP_HOURS: int = 8
    DB_URI: str
    REDIS_URL: str
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    COUNTRY: str = "EC"
    CURRENCY: str = "USD"
    GOOGLE_CLIENT_ID: Optional[str] = None  # Opcional, para OAuth de Google
    GOOGLE_CLIENT_SECRET: Optional[str] = None  # Opcional, para OAuth de Google

settings = Settings()
```

---
### FILE: services/api/app/security.py
```python
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from .config import settings

def create_token(sub: str, role: str, tenant_id: Optional[int] = None):
    payload = {"sub": sub, "role": role, "exp": datetime.utcnow()+timedelta(hours=settings.JWT_EXP_HOURS)}
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
```

---
### FILE: services/api/app/database.py
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

engine = create_engine(
    settings.DB_URI, 
    future=True,
    pool_pre_ping=True,  # Verificar conexiones antes de usarlas
    pool_recycle=3600,   # Reciclar conexiones cada hora
    connect_args={"connect_timeout": 10}  # Timeout de 10 segundos
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---
### FILE: services/api/app/deps.py
```python
"""
Dependencias para autenticación y multi-tenant.
Proporciona funciones para obtener el usuario actual y su tenant_id.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
from jose import jwt, JWTError
from .database import get_db
from .models import User, Tenant
from .config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Obtiene el usuario actual desde el token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    
    # Asegurar que el tenant_id del token esté sincronizado
    tenant_id = payload.get("tenant_id")
    if tenant_id is not None:
        user.tenant_id = tenant_id
    
    return user

def get_current_tenant_id(current_user: User = Depends(get_current_user)) -> Optional[int]:
    """
    Obtiene el tenant_id del usuario actual.
    Retorna None si es SUPER_ADMIN.
    """
    if current_user.role == "SUPER_ADMIN":
        return None
    return current_user.tenant_id

def require_tenant(current_user: User = Depends(get_current_user)) -> int:
    """
    Requiere que el usuario tenga un tenant_id.
    Lanza error si es SUPER_ADMIN o no tiene tenant.
    """
    if current_user.role == "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta operación requiere un tenant específico"
        )
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no tiene tenant asignado"
        )
    return current_user.tenant_id

def get_tenant_filter(current_user: User = Depends(get_current_user)):
    """
    Retorna un diccionario con el filtro de tenant_id para queries.
    Si es SUPER_ADMIN, retorna None (sin filtro).
    """
    if current_user.role == "SUPER_ADMIN":
        return None  # SUPER_ADMIN puede ver todo
    return current_user.tenant_id
```

---
### FILE: services/api/app/models.py
```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, Date, Float, JSON, func, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from .database import Base

# Enums para roles y estados
class UserRole(PyEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    TENANT_ROOT = "TENANT_ROOT"
    TENANT_SUB_ADMIN = "TENANT_SUB_ADMIN"
    COLLECTOR = "COLLECTOR"

class TenantStatus(PyEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class LicensePlan(PyEnum):
    BASIC = "BASIC"
    PRO = "PRO"
    ELITE = "ELITE"

class DeviceStatus(PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"

# Modelo Tenant (La Empresa)
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    schema_name = Column(String(100), nullable=True)  # Para aislamiento futuro
    status = Column(String(20), server_default="ACTIVE")  # 'ACTIVE', 'INACTIVE'
    currency = Column(String(5), server_default="USD")  # Moneda de la empresa
    logo_url = Column(String(255), nullable=True)  # URL del logo
    country = Column(String(50), nullable=True)  # País de la empresa
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Modelo License (El Negocio Tuyo)
class License(Base):
    __tablename__ = "licenses"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    plan_type = Column(String(20), nullable=False)  # 'BASIC', 'PRO', 'ELITE'
    expiration_date = Column(Date, nullable=False)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Modelo Branch (Centro de Negocio)
class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    name = Column(String(120), nullable=False)
    location = Column(String(200), nullable=True)  # Ciudad/Dirección
    # Reglas de Negocio Configurables
    max_daily_loan = Column(Numeric(12,2), nullable=True)  # null = ilimitado
    max_expense_amount = Column(Numeric(12,2), nullable=True)
    days_late_yellow = Column(Integer, server_default="3")  # Días para alerta amarilla
    days_late_red = Column(Integer, server_default="7")  # Días para alerta roja
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Modelo Device (Seguridad Móvil)
class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Cobrador asignado
    imei = Column(String(20), unique=True, nullable=False)  # Identificador único del hardware
    alias = Column(String(100), nullable=True)  # Ej: "Samsung A50 de Pedro"
    status = Column(String(20), server_default="PENDING")  # 'PENDING', 'APPROVED', 'BLOCKED'
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relaciones
    user = relationship("User", foreign_keys=[user_id])

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)  # Centro de Negocio
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    parent_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relaciones
    branch = relationship("Branch", foreign_keys=[branch_id])

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(30), nullable=False)  # SUPER_ADMIN, TENANT_ROOT, TENANT_SUB_ADMIN, COLLECTOR
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)  # NULL solo para SUPER_ADMIN
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)  # Para collectors
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    doc_type = Column(String(20))
    doc_num = Column(String(64))
    name = Column(String(160), nullable=False)
    phone = Column(String(40))
    address = Column(String(240))
    lat = Column(Float)
    lng = Column(Float)
    consent = Column(Boolean, server_default="true")
    consent_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    currency = Column(String(4), server_default="USD")
    amount = Column(Numeric(12,2), nullable=False)
    term_days = Column(Integer, nullable=False)
    annual_rate = Column(Numeric(7,4), server_default="0")
    rate_period = Column(String(10), server_default="ANNUAL")
    payment_frequency = Column(String(20), server_default="DAILY")  # DAILY, WEEKLY, BIWEEKLY, MONTHLY
    disbursement_date = Column(Date, nullable=False)
    status = Column(String(20), server_default="ACTIVE")
    created_at = Column(DateTime, server_default=func.now())

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False)
    n = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    principal = Column(Numeric(12,2), nullable=False)
    interest = Column(Numeric(12,2), nullable=False)
    total = Column(Numeric(12,2), nullable=False)
    status = Column(String(20), server_default="PENDING")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    method = Column(String(20), server_default="CASH")
    amount = Column(Numeric(12,2), nullable=False)
    currency = Column(String(4), server_default="USD")
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), server_default="CONFIRMED")
    external_ref = Column(String(120))
    evidence_url = Column(String(240))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class CollectVisit(Base):
    __tablename__ = "collect_visits"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    ts = Column(DateTime, server_default=func.now())
    result = Column(String(20))
    notes = Column(Text)
    lat = Column(Float)
    lng = Column(Float)
    photo_url = Column(String(240))

class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    route_date = Column(Date)
    stops = Column(JSON)
    distance_km = Column(Numeric(12,3))
    eta_min = Column(Integer)

class Reconciliation(Base):
    __tablename__ = "reconciliations"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    close_date = Column(Date, server_default=func.text("CURRENT_DATE"))
    reported_total = Column(Numeric(12,2))
    delivered_total = Column(Numeric(12,2))
    diff = Column(Numeric(12,2))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)  # NULL para acciones de SUPER_ADMIN
    actor = Column(String(80))
    action = Column(String(40))
    entity = Column(String(40))
    entity_id = Column(Integer)
    payload_hash = Column(String(120))
    ip = Column(String(64))
    ts = Column(DateTime, server_default=func.now())

class CashMovement(Base):
    __tablename__ = "cash_movements"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    type = Column(String(20), nullable=False)  # 'OPENING', 'EXPENSE', 'WITHDRAWAL', 'INCOME'
    amount = Column(Numeric(12,2), nullable=False)
    description = Column(String(240), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

# Enums para AccessKey
class AccessKeyActionType(PyEnum):
    DELETE_PAYMENT = "DELETE_PAYMENT"
    OVERRIDE_LIMIT = "OVERRIDE_LIMIT"
    REFINANCE = "REFINANCE"
    OTHER = "OTHER"

class AccessKeyStatus(PyEnum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"

class AccessKey(Base):
    __tablename__ = "access_keys"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # Multi-tenant
    code = Column(String(6), nullable=False)  # Código numérico de 4 a 6 dígitos
    action_type = Column(String(30), nullable=False)  # DELETE_PAYMENT, OVERRIDE_LIMIT, REFINANCE, OTHER
    status = Column(String(20), server_default="ACTIVE")  # ACTIVE, USED, EXPIRED
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # Admin que genera
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Cobrador que usa (opcional)
    expires_at = Column(DateTime, nullable=False)  # Por defecto: 15 minutos de validez
    created_at = Column(DateTime, server_default=func.now())
    
    # Relaciones
    generator = relationship("User", foreign_keys=[generated_by])
    user = relationship("User", foreign_keys=[used_by])
```

---
### FILE: services/api/app/schemas.py
```python
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List

class LoginIn(BaseModel):
    username: str
    password: str

class LoginOut(BaseModel):
    token: str
    role: str
    tenant_id: Optional[int] = None

class GoogleAuthIn(BaseModel):
    id_token: str

# Schemas para Multi-Tenant
class TenantIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    schema_name: Optional[str] = Field(None, max_length=100)
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|INACTIVE)$")
    currency: Optional[str] = Field(default="USD", max_length=5)
    logo_url: Optional[str] = Field(None, max_length=255)
    country: Optional[str] = Field(None, max_length=50)

class TenantSetupIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    currency: str = Field(
        default="USD", 
        pattern="^(USD|COP|MXN|BRL|PEN|CLP|ARS|BOB|GTQ|HNL|NIO|CRC|PYG|UYU|DOP)$"
    )

class TenantOut(BaseModel):
    id: int
    name: str
    schema_name: Optional[str]
    status: str
    currency: str
    logo_url: Optional[str]
    country: Optional[str]
    created_at: datetime
    updated_at: datetime

# Schemas para Gestión de Usuarios/Colaboradores
class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=100)
    role: str = Field(pattern="^(TENANT_SUB_ADMIN|COLLECTOR)$")
    group_id: Optional[int] = None

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=80)
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    role: Optional[str] = Field(None, pattern="^(TENANT_SUB_ADMIN|COLLECTOR)$")
    group_id: Optional[int] = None
    is_active: Optional[bool] = None  # Para activar/desactivar usuarios

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    tenant_id: Optional[int]
    group_id: Optional[int]
    group_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class CustomerIn(BaseModel):
    group_id: int
    doc_type: str
    doc_num: str
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    consent: bool = True

class CustomerOut(BaseModel):
    id: int
    name: str
    doc_type: Optional[str]
    doc_num: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    group_id: int
    group_name: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class LoanIn(BaseModel):
    group_id: int
    customer_id: int
    amount: float = Field(gt=0)
    term_days: int = Field(gt=0)
    annual_rate: float = Field(ge=0)
    rate_period: Optional[str] = Field(default="ANNUAL", pattern="^(ANNUAL|MONTHLY|DAILY)$")
    payment_frequency: Optional[str] = Field(default="DAILY", pattern="^(DAILY|WEEKLY|BIWEEKLY|MONTHLY)$")
    disbursement_date: date

class PaymentOut(BaseModel):
    id: int
    amount: float
    payment_date: Optional[date] = None
    created_at: datetime
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class LoanOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    amount: float
    term_days: int
    annual_rate: float
    payment_frequency: str
    disbursement_date: date
    status: str
    interest: Optional[float] = None
    total: Optional[float] = None
    created_at: datetime
    collection_status: Optional[str] = None  # 'OK', 'WARNING', 'CRITICAL'
    arrears_amount: Optional[float] = None  # Monto en mora
    
    class Config:
        from_attributes = True

class LoanDetail(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    amount: float
    term_days: int
    annual_rate: float
    payment_frequency: str
    disbursement_date: date
    status: str
    interest: Optional[float] = None
    total: Optional[float] = None
    created_at: datetime
    payments: List[PaymentOut] = []
    total_paid: float = 0.0
    remaining_balance: float = 0.0
    
    class Config:
        from_attributes = True

class VisitIn(BaseModel):
    collector_id: int
    customer_id: int
    result: str
    notes: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class CashPaymentIn(BaseModel):
    schedule_id: int
    amount: float = Field(gt=0)
    notes: Optional[str] = None

class LoanPaymentIn(BaseModel):
    loan_id: int
    amount: float = Field(gt=0)
    payment_date: date
    notes: Optional[str] = None

class ReconciliationIn(BaseModel):
    collector_id: int
    reported_total: float
    delivered_total: float
    notes: Optional[str] = None

class CashMovementIn(BaseModel):
    type: str = Field(pattern="^(OPENING|EXPENSE|WITHDRAWAL|INCOME)$")
    amount: float = Field(gt=0)
    description: str = Field(min_length=1, max_length=240)

class CashMovementOut(BaseModel):
    id: int
    type: str
    amount: float
    description: str
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class CashSummaryOut(BaseModel):
    base_amount: float  # Suma de OPENING de hoy
    collected_amount: float  # Suma de payments de hoy
    expenses_amount: float  # Suma de EXPENSE de hoy
    balance: float  # Base + Recaudo - Gastos
    movements: List[CashMovementOut] = []  # Lista de movimientos de hoy

# Schemas para Centros de Negocio (Branch)
class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: Optional[str] = Field(None, max_length=200)
    max_daily_loan: Optional[float] = None  # null = ilimitado
    max_expense_amount: Optional[float] = None
    days_late_yellow: Optional[int] = Field(default=3, ge=1)
    days_late_red: Optional[int] = Field(default=7, ge=1)

class BranchOut(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    max_daily_loan: Optional[float] = None
    max_expense_amount: Optional[float] = None
    days_late_yellow: int
    days_late_red: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Schemas para Dispositivos (Device)
class DeviceIn(BaseModel):
    imei: str = Field(min_length=1, max_length=20)
    alias: Optional[str] = Field(None, max_length=100)
    user_id: Optional[int] = None  # Cobrador asignado

class DeviceOut(BaseModel):
    id: int
    imei: str
    alias: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None  # Nombre del cobrador
    status: str  # 'PENDING', 'APPROVED', 'BLOCKED'
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    branch_id: Optional[int] = None  # Centro de Negocio
    parent_id: Optional[int] = None

class GroupOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None  # Nombre del centro de negocio
    parent_id: Optional[int] = None
    
    class Config:
        from_attributes = True
```

---
### FILE: services/api/app/routers/auth.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from ..security import create_token
from ..database import get_db
from ..models import User, UserRole
from ..utils.hashing import verify_pwd, hash_pwd
from ..schemas import LoginIn, LoginOut, GoogleAuthIn
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username==body.username).first()
    if not u or not verify_pwd(body.password, u.password_hash):
        raise HTTPException(401, "bad credentials")
    
    token = create_token(sub=u.username, role=u.role, tenant_id=u.tenant_id)
    return {"token": token, "role": u.role, "tenant_id": u.tenant_id}

@router.post("/google", response_model=LoginOut)
def google_login(body: GoogleAuthIn, db: Session = Depends(get_db)):
    """
    Autenticación con Google OAuth.
    Recibe un id_token de Google, lo verifica y crea/actualiza el usuario.
    """
    try:
        # Verificar el token con Google
        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
        if not client_id:
            raise HTTPException(
                status_code=500, 
                detail="GOOGLE_CLIENT_ID no configurado. Configura la variable de entorno GOOGLE_CLIENT_ID en el archivo .env"
            )
        
        try:
            idinfo = id_token.verify_oauth2_token(
                body.id_token, 
                google_requests.Request(),
                client_id
            )
        except ValueError as ve:
            # Token inválido o expirado
            raise HTTPException(
                status_code=401, 
                detail=f"Token de Google inválido o expirado: {str(ve)}"
            )
        except Exception as ve:
            # Otros errores de verificación
            raise HTTPException(
                status_code=401, 
                detail=f"Error al verificar token de Google: {str(ve)}"
            )
        
        # Extraer información del usuario
        email = idinfo.get('email')
        if not email:
            raise HTTPException(
                status_code=400, 
                detail="No se pudo obtener el email de Google. Asegúrate de que tu cuenta de Google tenga un email asociado."
            )
        
        name = idinfo.get('name', email.split('@')[0] if email else 'Usuario')
        
        # Buscar si el usuario ya existe (usando email como username)
        user = db.query(User).filter(User.username == email).first()
        
        if user:
            # Usuario existente: generar token
            token = create_token(sub=user.username, role=user.role, tenant_id=user.tenant_id)
            return {"token": token, "role": user.role, "tenant_id": user.tenant_id}
        else:
            # Nuevo usuario: crear con rol TENANT_ROOT (sin tenant aún)
            new_user = User(
                username=email,
                password_hash=hash_pwd("google_oauth_no_password"),  # Password dummy, nunca se usará
                role=UserRole.TENANT_ROOT.value,
                tenant_id=None  # Se asignará en el onboarding
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            token = create_token(sub=new_user.username, role=new_user.role, tenant_id=None)
            return {"token": token, "role": new_user.role, "tenant_id": None}
            
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
    except Exception as e:
        # Log del error completo para debugging
        import logging
        logging.error(f"Error inesperado en Google OAuth: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno en autenticación con Google: {str(e)}"
        )
```

---
### FILE: services/api/app/routers/customers.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
import logging
from ..database import get_db
from ..models import Customer, Group
from ..schemas import CustomerIn, CustomerOut
from ..deps import require_tenant, get_current_user
from ..models import User

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])

@router.get("", response_model=List[CustomerOut])
def list_customers(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    skip: int = 0,
    limit: int = 100
):
    """
    Listar todos los clientes del tenant actual.
    Incluye el nombre del grupo (ruta) asignado.
    """
    # Obtener clientes del mismo tenant
    customers = db.query(Customer).filter(
        Customer.tenant_id == tenant_id
    ).offset(skip).limit(limit).all()
    
    # Enriquecer con información del grupo
    result = []
    for customer in customers:
        customer_dict = {
            "id": customer.id,
            "name": customer.name,
            "doc_type": customer.doc_type,
            "doc_num": customer.doc_num,
            "phone": customer.phone,
            "address": customer.address,
            "group_id": customer.group_id,
            "group_name": None,
            "created_at": customer.created_at
        }
        
        # Obtener nombre del grupo si existe
        if customer.group_id:
            group = db.query(Group).filter(Group.id == customer.group_id).first()
            if group:
                customer_dict["group_name"] = group.name
        
        result.append(CustomerOut(**customer_dict))
    
    return result

@router.post("")
def create_customer(
    body: CustomerIn, 
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Crear un nuevo cliente.
    Valida que el group_id exista y pertenezca al mismo tenant.
    """
    try:
        # Validar que el grupo existe y pertenece al mismo tenant
        group = db.query(Group).filter(
            Group.id == body.group_id,
            Group.tenant_id == tenant_id
        ).first()
        if not group:
            raise HTTPException(status_code=404, detail=f"La ruta con ID {body.group_id} no existe o no pertenece a tu organización")
        
        # Crear cliente con tenant_id del usuario actual
        customer_data = body.model_dump()
        customer_data['tenant_id'] = tenant_id
        c = Customer(**customer_data)
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"id": c.id}
    except HTTPException:
        raise
    except IntegrityError as e:
        logger.error(f"Error de integridad al crear cliente: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al crear el cliente. Verifica que los datos sean válidos.")
    except Exception as e:
        logger.error(f"Error al crear cliente: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear el cliente: {str(e)}")

@router.get("/{cid}")
def get_customer(cid: int, db: Session = Depends(get_db)):
    """
    Obtener un cliente por ID.
    """
    c = db.get(Customer, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "address": c.address,
        "lat": c.lat,
        "lng": c.lng,
        "consent": c.consent,
        "group_id": c.group_id,
        "doc_type": c.doc_type,
        "doc_num": c.doc_num
    }

@router.put("/{cid}")
def update_customer(cid: int, body: CustomerIn, db: Session = Depends(get_db)):
    """
    Actualizar un cliente existente.
    Permite cambiar la ruta (group_id) y otros datos.
    """
    try:
        # Verificar que el cliente existe
        customer = db.get(Customer, cid)
        if not customer:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
        # Validar que el grupo existe (si se está cambiando)
        if body.group_id:
            group = db.query(Group).filter(Group.id == body.group_id).first()
            if not group:
                raise HTTPException(status_code=404, detail=f"La ruta con ID {body.group_id} no existe")
        
        # Actualizar campos
        customer.name = body.name
        customer.doc_type = body.doc_type
        customer.doc_num = body.doc_num
        customer.phone = body.phone
        customer.address = body.address
        customer.group_id = body.group_id
        customer.lat = body.lat
        customer.lng = body.lng
        customer.consent = body.consent
        
        db.commit()
        db.refresh(customer)
        
        return {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "address": customer.address,
            "lat": customer.lat,
            "lng": customer.lng,
            "consent": customer.consent,
            "group_id": customer.group_id,
            "doc_type": customer.doc_type,
            "doc_num": customer.doc_num
        }
    except HTTPException:
        raise
    except IntegrityError as e:
        logger.error(f"Error de integridad al actualizar cliente: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al actualizar el cliente. Verifica que los datos sean válidos.")
    except Exception as e:
        logger.error(f"Error al actualizar cliente: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar el cliente: {str(e)}")
```

---
### FILE: services/api/app/routers/loans.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
from sqlalchemy import desc, func
from datetime import timedelta, date
from typing import List
import logging
from ..database import get_db
from ..models import Loan, Schedule, Customer, Group, Payment, User
from ..schemas import LoanIn, LoanOut, LoanDetail, PaymentOut
from ..deps import get_current_user, require_tenant

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/loans", tags=["loans"])

# CONFIGURACIÓN DEL MODELO DE NEGOCIO
# Días que dura el ciclo estándar para la tasa ingresada.
# Ejemplo: Si la tasa es 20% y STANDARD_CYCLE_DAYS es 20, la tasa diaria es 1%.
# Si en el futuro esto cambia a 30, solo se edita esta línea.
STANDARD_CYCLE_DAYS = 20

# Validar constante al inicio
if STANDARD_CYCLE_DAYS <= 0:
    raise ValueError("STANDARD_CYCLE_DAYS debe ser mayor a 0")

@router.get("/{loan_id}", response_model=LoanDetail)
def get_loan_detail(loan_id: int, db: Session = Depends(get_db)):
    """
    Obtiene el detalle completo de un préstamo incluyendo su historial de pagos.
    """
    try:
        # 1. Obtener el préstamo
        loan = db.get(Loan, loan_id)
        if not loan:
            raise HTTPException(status_code=404, detail=f"El Préstamo ID {loan_id} no existe")
        
        # 2. Obtener el cliente
        customer = db.get(Customer, loan.customer_id)
        customer_name = customer.name if customer else "Cliente Desconocido"
        
        # 3. Obtener el schedule para calcular interés y total
        schedule = db.query(Schedule).filter(Schedule.loan_id == loan.id).first()
        interest = float(schedule.interest) if schedule else None
        total = float(schedule.total) if schedule else None
        
        # 4. Obtener todos los pagos del préstamo (a través del schedule)
        payments = []
        total_paid = 0.0
        
        if schedule:
            # Obtener pagos ordenados por fecha (más recientes primero)
            payment_list = db.query(Payment)\
                .filter(Payment.schedule_id == schedule.id)\
                .order_by(Payment.created_at.desc())\
                .all()
            
            # Calcular total pagado
            total_paid = float(db.query(func.sum(Payment.amount))
                .filter(Payment.schedule_id == schedule.id)
                .scalar() or 0.0)
            
            # Convertir a PaymentOut
            payments = [
                PaymentOut(
                    id=p.id,
                    amount=float(p.amount),
                    payment_date=None,  # El modelo Payment no tiene payment_date, usamos created_at
                    created_at=p.created_at,
                    notes=p.notes
                )
                for p in payment_list
            ]
        
        # 5. Calcular saldo pendiente
        remaining_balance = (total - total_paid) if total else 0.0
        remaining_balance = max(0.0, remaining_balance)
        
        # 6. Construir respuesta
        loan_detail = LoanDetail(
            id=loan.id,
            customer_id=loan.customer_id,
            customer_name=customer_name,
            amount=float(loan.amount),
            term_days=loan.term_days,
            annual_rate=float(loan.annual_rate),
            payment_frequency=loan.payment_frequency or "DAILY",
            disbursement_date=loan.disbursement_date,
            status=loan.status,
            interest=interest,
            total=total,
            created_at=loan.created_at,
            payments=payments,
            total_paid=round(total_paid, 2),
            remaining_balance=round(remaining_balance, 2)
        )
        
        logger.info(f"Detalle de préstamo {loan_id} obtenido: {len(payments)} pagos")
        return loan_detail
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener detalle del préstamo {loan_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al obtener el detalle del préstamo"
        )

@router.get("", response_model=List[LoanOut])
def list_loans(db: Session = Depends(get_db)):
    """
    Obtiene la lista de préstamos con información del cliente.
    Ordenados por fecha de creación descendente (más recientes primero).
    """
    try:
        # Query optimizada: obtener préstamos con join a customers
        loans = db.query(Loan, Customer)\
            .join(Customer, Loan.customer_id == Customer.id)\
            .order_by(desc(Loan.created_at))\
            .all()
        
        # Obtener todos los schedules de una vez para evitar N+1 queries
        loan_ids = [loan.id for loan, _ in loans]
        schedules = {}
        if loan_ids:
            schedule_list = db.query(Schedule)\
                .filter(Schedule.loan_id.in_(loan_ids))\
                .all()
            # Agrupar por loan_id (tomar el primero si hay múltiples)
            for schedule in schedule_list:
                if schedule.loan_id not in schedules:
                    schedules[schedule.loan_id] = schedule
        
        # Obtener todos los pagos de una vez para calcular total_paid
        total_paid_by_loan = {}
        if loan_ids:
            schedule_ids = [s.id for s in schedules.values()]
            if schedule_ids:
                payment_totals = db.query(
                    Payment.schedule_id,
                    func.sum(Payment.amount).label('total_paid')
                ).filter(
                    Payment.schedule_id.in_(schedule_ids)
                ).group_by(Payment.schedule_id).all()
                
                # Mapear schedule_id -> loan_id -> total_paid
                schedule_to_loan = {s.id: s.loan_id for s in schedules.values()}
                for schedule_id, total_paid in payment_totals:
                    loan_id = schedule_to_loan.get(schedule_id)
                    if loan_id:
                        total_paid_by_loan[loan_id] = float(total_paid) or 0.0
        
        # Fecha actual para calcular días transcurridos
        today = date.today()
        
        result = []
        for loan, customer in loans:
            # Obtener el schedule asociado
            schedule = schedules.get(loan.id)
            
            # Calcular interés y total desde el schedule si existe
            interest = float(schedule.interest) if schedule else None
            total = float(schedule.total) if schedule else None
            
            # Calcular estado de cobro (solo para préstamos activos)
            collection_status = None
            arrears_amount = None
            
            if loan.status == "ACTIVE" and total and schedule:
                # Obtener total pagado
                total_paid = total_paid_by_loan.get(loan.id, 0.0)
                
                # Calcular días transcurridos desde el desembolso
                days_elapsed = (today - loan.disbursement_date).days
                days_elapsed = max(0, days_elapsed)  # No permitir días negativos
                
                # Calcular cuota diaria esperada
                daily_quota = total / loan.term_days
                
                # Calcular monto esperado pagado hasta hoy
                expected_paid = daily_quota * days_elapsed
                
                # Calcular diferencia (monto en mora)
                arrears = expected_paid - total_paid
                
                # Determinar estado de cobro
                if arrears <= 0:
                    # Al día o adelantado
                    collection_status = "OK"
                    arrears_amount = 0.0
                elif arrears < (daily_quota * 3):
                    # Atraso leve (menos de 3 días)
                    collection_status = "WARNING"
                    arrears_amount = round(arrears, 2)
                else:
                    # Mora crítica (3 días o más)
                    collection_status = "CRITICAL"
                    arrears_amount = round(arrears, 2)
            
            result.append(LoanOut(
                id=loan.id,
                customer_id=loan.customer_id,
                customer_name=customer.name if customer else "Cliente Desconocido",
                amount=float(loan.amount),
                term_days=loan.term_days,
                annual_rate=float(loan.annual_rate),
                payment_frequency=loan.payment_frequency or "DAILY",
                disbursement_date=loan.disbursement_date,
                status=loan.status,
                interest=interest,
                total=total,
                created_at=loan.created_at,
                collection_status=collection_status,
                arrears_amount=arrears_amount
            ))
        
        logger.info(f"Listados {len(result)} préstamos")
        return result
    
    except Exception as e:
        logger.error(f"Error al listar préstamos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al obtener la lista de préstamos"
        )

@router.post("")
def create_loan(loan_in: LoanIn, db: Session = Depends(get_db)):
    """
    Crea un préstamo usando el modelo 'Gota a Gota' (Interés Simple Proporcional).
    """
    try:
        # 1. Validar Cliente
        customer = db.get(Customer, loan_in.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"El Cliente ID {loan_in.customer_id} no existe")
        
        # 2. Validar Group (CRÍTICO - Evita IntegrityError)
        group = db.get(Group, loan_in.group_id)
        if not group:
            raise HTTPException(status_code=404, detail=f"El Group ID {loan_in.group_id} no existe")
        
        # 3. DEFINICIÓN DE VARIABLES (Mapeo claro de inputs)
        try:
            capital = float(loan_in.amount)
            tasa_ciclo_porcentaje = float(loan_in.annual_rate)
            dias_reales = float(loan_in.term_days)
        except (ValueError, TypeError) as e:
            logger.error(f"Error de conversión de tipos: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error en valores numéricos: {str(e)}")
        
        # Validar valores razonables
        if capital <= 0:
            raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
        if dias_reales <= 0:
            raise HTTPException(status_code=400, detail="Los días deben ser mayor a 0")
        if tasa_ciclo_porcentaje < 0:
            raise HTTPException(status_code=400, detail="La tasa no puede ser negativa")
        
        dias_base = STANDARD_CYCLE_DAYS
        
        # 4. LÓGICA DE CÁLCULO (Modelo Optimizado)
        
        # Paso A: Calcular Tasa Diaria (% por día)
        # Ejemplo: 20 / 20 = 1% diario
        if dias_base == 0:
            raise HTTPException(status_code=500, detail="Error de configuración: STANDARD_CYCLE_DAYS no puede ser 0")
        
        tasa_diaria_porcentaje = tasa_ciclo_porcentaje / dias_base
        
        # Paso B: Calcular Interés Total
        # Ejemplo: 80 * (1 / 100) * 30 = 24.0
        interes_total = capital * (tasa_diaria_porcentaje / 100.0) * dias_reales
        
        # Paso C: Totales
        interes_total = round(interes_total, 2)
        total_pagar = round(capital + interes_total, 2)
        
        # 5. FECHAS
        fecha_desembolso = loan_in.disbursement_date
        try:
            fecha_vencimiento = fecha_desembolso + timedelta(days=int(dias_reales))
        except (ValueError, OverflowError) as e:
            logger.error(f"Error al calcular fecha de vencimiento: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error en el cálculo de fechas: {str(e)}")

        # 6. Asegurar rate_period y payment_frequency tienen valores por defecto
        loan_data = loan_in.model_dump()
        if not loan_data.get('rate_period'):
            loan_data['rate_period'] = 'DAILY'
        if not loan_data.get('payment_frequency'):
            loan_data['payment_frequency'] = 'DAILY'
        
        # 7. GUARDAR EN BASE DE DATOS (CON MANEJO DE ERRORES)
        try:
            loan = Loan(**loan_data)
            db.add(loan)
            db.flush()
            
            # 8. Generar Schedule
            sched = Schedule(loan_id=loan.id, n=1, due_date=fecha_vencimiento, 
                           principal=loan.amount, interest=interes_total, total=total_pagar)
            
            db.add(sched)
            db.commit()
            
            logger.info(f"Préstamo creado exitosamente: ID {loan.id}, Cliente {loan.customer_id}")
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"IntegrityError al crear préstamo: {str(e)}")
            # Detectar el tipo de violación de Foreign Key
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            if "foreign key constraint" in error_msg.lower() or "FOREIGN KEY" in error_msg:
                raise HTTPException(
                    status_code=400, 
                    detail="Error de integridad: Verifica que el Group ID y Customer ID existan en la base de datos."
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Error de integridad de datos: {error_msg}"
                )
        except (OperationalError, DatabaseError) as e:
            db.rollback()
            logger.error(f"Error de base de datos al crear préstamo: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="Error de conexión con la base de datos. Por favor, intenta nuevamente."
            )
        
        return {
            "loan_id": loan.id, 
            "schedule_id": sched.id, 
            "total": total_pagar, 
            "due_date": str(fecha_vencimiento)
        }
    
    except HTTPException:
        # Re-lanzar HTTPException sin modificar (ya tiene el status_code y detail correctos)
        raise
    except ValueError as e:
        logger.error(f"Error de validación: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error de validación: {str(e)}")
    except Exception as e:
        # Capturar cualquier otro error inesperado
        logger.error(f"Error inesperado al crear préstamo: {str(e)}", exc_info=True)
        try:
            db.rollback()
        except:
            pass  # Si no hay transacción activa, ignorar
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor. Por favor, contacta al administrador."
        )

@router.post("/{loan_id}/renew")
def renew_loan(
    loan_id: int,
    loan_in: LoanIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Renueva un préstamo activo creando un nuevo préstamo y liquidando el saldo del anterior.
    """
    try:
        # 1. Obtener el préstamo original
        old_loan = db.get(Loan, loan_id)
        if not old_loan:
            raise HTTPException(status_code=404, detail=f"El Préstamo ID {loan_id} no existe")
        
        # 2. Verificar que el préstamo esté activo
        if old_loan.status != "ACTIVE":
            raise HTTPException(
                status_code=400,
                detail=f"El préstamo debe estar ACTIVE para renovarlo. Estado actual: {old_loan.status}"
            )
        
        # 3. Obtener tenant_id
        tenant_id = require_tenant(current_user)
        if old_loan.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para renovar este préstamo"
            )
        
        # 4. Calcular saldo pendiente del préstamo viejo
        schedule_old = db.query(Schedule).filter(Schedule.loan_id == old_loan.id).first()
        if not schedule_old:
            raise HTTPException(
                status_code=400,
                detail="El préstamo no tiene un schedule asociado"
            )
        
        total_pagar_viejo = float(schedule_old.total)
        
        # Obtener total pagado del préstamo viejo
        total_pagado_viejo = db.query(func.sum(Payment.amount)).filter(
            Payment.schedule_id == schedule_old.id
        ).scalar() or 0.0
        total_pagado_viejo = float(total_pagado_viejo)
        
        saldo_pendiente = total_pagar_viejo - total_pagado_viejo
        
        # 5. Validar que el nuevo monto sea mayor que el saldo pendiente
        nuevo_monto = float(loan_in.amount)
        if nuevo_monto <= saldo_pendiente:
            raise HTTPException(
                status_code=400,
                detail=f"El nuevo monto (${nuevo_monto:.2f}) debe ser mayor que el saldo pendiente (${saldo_pendiente:.2f})"
            )
        
        # 6. Validar que el cliente sea el mismo
        if loan_in.customer_id != old_loan.customer_id:
            raise HTTPException(
                status_code=400,
                detail="El cliente del nuevo préstamo debe ser el mismo que el préstamo original"
            )
        
        # 7. Crear el nuevo préstamo (reutilizar lógica de create_loan)
        try:
            capital = nuevo_monto
            tasa_ciclo_porcentaje = float(loan_in.annual_rate)
            dias_reales = float(loan_in.term_days)
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"Error en valores numéricos: {str(e)}")
        
        if capital <= 0 or dias_reales <= 0 or tasa_ciclo_porcentaje < 0:
            raise HTTPException(status_code=400, detail="Valores inválidos para el nuevo préstamo")
        
        dias_base = STANDARD_CYCLE_DAYS
        tasa_diaria_porcentaje = tasa_ciclo_porcentaje / dias_base
        interes_total = capital * (tasa_diaria_porcentaje / 100.0) * dias_reales
        interes_total = round(interes_total, 2)
        total_pagar_nuevo = round(capital + interes_total, 2)
        
        fecha_desembolso = loan_in.disbursement_date
        fecha_vencimiento = fecha_desembolso + timedelta(days=int(dias_reales))
        
        # Preparar datos del nuevo préstamo
        loan_data = loan_in.model_dump()
        if not loan_data.get('rate_period'):
            loan_data['rate_period'] = 'DAILY'
        if not loan_data.get('payment_frequency'):
            loan_data['payment_frequency'] = 'DAILY'
        
        # Asegurar que el nuevo préstamo tenga el mismo tenant_id
        loan_data['tenant_id'] = tenant_id
        
        # 8. TRANSACCIÓN: Crear nuevo préstamo y liquidar el viejo
        try:
            # Crear nuevo préstamo
            new_loan = Loan(**loan_data)
            db.add(new_loan)
            db.flush()
            
            # Crear schedule del nuevo préstamo
            new_schedule = Schedule(
                loan_id=new_loan.id,
                n=1,
                due_date=fecha_vencimiento,
                principal=new_loan.amount,
                interest=interes_total,
                total=total_pagar_nuevo
            )
            db.add(new_schedule)
            db.flush()
            
            # Liquidar el préstamo viejo: crear pago especial
            # Necesitamos un collector_id - usar el usuario actual o buscar un admin
            collector = db.query(User).filter(
                User.tenant_id == tenant_id,
                User.role.in_(["TENANT_ROOT", "TENANT_SUB_ADMIN", "COLLECTOR"])
            ).first()
            
            if not collector:
                raise HTTPException(
                    status_code=400,
                    detail="No se encontró un usuario válido para registrar el pago de renovación"
                )
            
            renewal_payment = Payment(
                tenant_id=tenant_id,
                schedule_id=schedule_old.id,
                method="RENEWAL",
                amount=saldo_pendiente,
                collector_id=collector.id,
                status="CONFIRMED",
                notes=f"Pago de renovación - Préstamo renovado por préstamo #{new_loan.id}"
            )
            db.add(renewal_payment)
            
            # Cambiar estado del préstamo viejo a RENEWED
            old_loan.status = "RENEWED"
            
            db.commit()
            
            # Calcular dinero a entregar al cliente
            dinero_entregar = nuevo_monto - saldo_pendiente
            
            logger.info(
                f"Préstamo {loan_id} renovado exitosamente. "
                f"Nuevo préstamo: {new_loan.id}. "
                f"Saldo liquidado: ${saldo_pendiente:.2f}. "
                f"Dinero a entregar: ${dinero_entregar:.2f}"
            )
            
            return {
                "old_loan_id": loan_id,
                "new_loan_id": new_loan.id,
                "old_balance_paid": round(saldo_pendiente, 2),
                "new_loan_total": round(total_pagar_nuevo, 2),
                "cash_to_deliver": round(dinero_entregar, 2),
                "message": "Préstamo renovado exitosamente"
            }
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"IntegrityError al renovar préstamo: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error de integridad al crear el nuevo préstamo"
            )
        except (OperationalError, DatabaseError) as e:
            db.rollback()
            logger.error(f"Error de base de datos al renovar préstamo: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="Error de conexión con la base de datos"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado al renovar préstamo: {str(e)}", exc_info=True)
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al renovar el préstamo"
        )
```

---
### FILE: services/api/app/routers/payments.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
import logging
from ..database import get_db
from ..models import Payment, Schedule, User, Loan
from ..schemas import CashPaymentIn, LoanPaymentIn
from ..security import settings # Importamos settings si fuera necesario, o dependencias de auth futuras

# Configurar logging
logger = logging.getLogger(__name__)

# NOTA: En un futuro, aquí inyectaremos al usuario actual para obtener el collector_id real.
# Por ahora, lo simularemos o lo recibiremos (idealmente debería venir del token).

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/cash")
def payment_cash(body: CashPaymentIn, db: Session = Depends(get_db)):
    # VALIDACIÓN: Verificar que el schedule existe
    sched = db.get(Schedule, body.schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # CORRECCIÓN: Necesitamos un collector_id. 
    # Como aun no tenemos login activo en el frontend, asignaremos al admin (ID 1) temporalmente
    # o buscaremos un usuario cobrador por defecto.
    # En producción, esto viene del token del usuario logueado (current_user.id).
    collector = db.query(User).first() # Usamos el primer usuario encontrado como cobrador temporal
    if not collector:
        raise HTTPException(status_code=400, detail="No collectors available")

    p = Payment(
        schedule_id=body.schedule_id, 
        amount=body.amount,
        collector_id=collector.id # <--- CORRECCIÓN: Agregado collector_id
    )
    db.add(p); db.flush()
    
    # CORRECCIÓN LÓGICA: Calcular lo pagado sumando pagos SOLO de este schedule
    paid_amount = db.query(func.sum(Payment.amount))\
        .filter(Payment.schedule_id == body.schedule_id)\
        .scalar() or 0.0
    
    # Convertir a float para comparar
    total_due = float(sched.total)
    paid_float = float(paid_amount)

    if paid_float >= total_due:
        sched.status = "PAID"
        db.add(sched)
    
    db.commit()
    return {"id": p.id, "status": "CONFIRMED", "new_balance": round(total_due - paid_float, 2)}

@router.post("")
def create_payment(payment_in: LoanPaymentIn, db: Session = Depends(get_db)):
    """
    Registra un pago (abono) a un préstamo.
    Actualiza el saldo pendiente y cambia el estado a PAID si el saldo llega a 0.
    """
    try:
        # 1. Validar que el préstamo existe
        loan = db.get(Loan, payment_in.loan_id)
        if not loan:
            raise HTTPException(status_code=404, detail=f"El Préstamo ID {payment_in.loan_id} no existe")
        
        # 2. Obtener el schedule asociado al préstamo
        schedule = db.query(Schedule).filter(Schedule.loan_id == loan.id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail=f"No se encontró el schedule para el préstamo ID {payment_in.loan_id}")
        
        # 3. Obtener un collector (usuario cobrador) - temporalmente el primero disponible
        collector = db.query(User).first()
        if not collector:
            raise HTTPException(status_code=400, detail="No hay usuarios cobradores disponibles")
        
        # 4. Calcular el total pagado hasta ahora (suma de todos los pagos del schedule)
        total_paid = db.query(func.sum(Payment.amount))\
            .filter(Payment.schedule_id == schedule.id)\
            .scalar() or 0.0
        
        total_paid = float(total_paid)
        total_due = float(schedule.total)
        remaining_balance = total_due - total_paid
        
        # 5. Validar que el monto del pago no exceda el saldo pendiente
        if payment_in.amount > remaining_balance:
            raise HTTPException(
                status_code=400, 
                detail=f"El monto del pago (${payment_in.amount:.2f}) excede el saldo pendiente (${remaining_balance:.2f})"
            )
        
        # 6. Registrar el pago
        try:
            payment = Payment(
                schedule_id=schedule.id,
                amount=payment_in.amount,
                collector_id=collector.id,
                method="CASH",
                notes=payment_in.notes
            )
            db.add(payment)
            db.flush()
            
            # 7. Actualizar el saldo pagado
            new_total_paid = total_paid + payment_in.amount
            new_balance = total_due - new_total_paid
            
            # 8. Actualizar el estado del schedule y del préstamo
            if new_total_paid >= total_due:
                # Pago completo
                schedule.status = "PAID"
                loan.status = "PAID"
                db.add(schedule)
                db.add(loan)
                logger.info(f"Préstamo {loan.id} pagado completamente")
            else:
                # Pago parcial
                schedule.status = "PARTIAL"
                db.add(schedule)
                logger.info(f"Pago parcial registrado para préstamo {loan.id}: ${payment_in.amount:.2f}")
            
            db.commit()
            
            return {
                "id": payment.id,
                "loan_id": loan.id,
                "amount": payment_in.amount,
                "total_paid": round(new_total_paid, 2),
                "remaining_balance": round(max(0, new_balance), 2),
                "loan_status": loan.status,
                "message": "Pago registrado exitosamente"
            }
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"IntegrityError al registrar pago: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Error al registrar el pago. Verifica los datos."
            )
        except (OperationalError, DatabaseError) as e:
            db.rollback()
            logger.error(f"Error de base de datos al registrar pago: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="Error de conexión con la base de datos. Intenta nuevamente."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado al registrar pago: {str(e)}", exc_info=True)
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al registrar el pago"
        )
```

---
### FILE: services/api/app/routers/visits.py
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import CollectVisit
from ..schemas import VisitIn

router = APIRouter(prefix="/collections", tags=["collections"])

@router.post("/visit")
def collection_visit(body: VisitIn, db: Session = Depends(get_db)):
    v = CollectVisit(**body.model_dump())
    db.add(v); db.commit(); db.refresh(v)
    return {"id": v.id}
```

---
### FILE: services/api/app/routers/cash.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
import logging
from ..database import get_db
from ..models import CashMovement, Payment, User
from ..schemas import CashMovementIn, CashMovementOut, CashSummaryOut

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cash", tags=["cash"])

@router.post("/movement", response_model=CashMovementOut)
def create_cash_movement(
    movement_in: CashMovementIn,
    db: Session = Depends(get_db)
):
    """
    Registra un movimiento de caja (Base Inicial, Gasto, Retiro o Ingreso Extra).
    """
    try:
        # Obtener el usuario actual (temporalmente el primero disponible)
        # TODO: En producción, esto debe venir del token JWT del usuario autenticado
        user = db.query(User).first()
        if not user:
            raise HTTPException(status_code=400, detail="No hay usuarios disponibles en el sistema")
        
        # Validar que el tipo sea válido
        valid_types = ['OPENING', 'EXPENSE', 'WITHDRAWAL', 'INCOME']
        if movement_in.type not in valid_types:
            raise HTTPException(
                status_code=422,
                detail=f"Tipo de movimiento inválido. Debe ser uno de: {', '.join(valid_types)}"
            )
        
        # Crear el movimiento
        movement = CashMovement(
            type=movement_in.type,
            amount=movement_in.amount,
            description=movement_in.description,
            user_id=user.id
        )
        
        db.add(movement)
        db.commit()
        db.refresh(movement)
        
        return movement
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear movimiento de caja: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar el movimiento: {str(e)}")

@router.get("/summary", response_model=CashSummaryOut)
def get_cash_summary(db: Session = Depends(get_db)):
    """
    Obtiene el resumen de caja del día actual:
    - Base del Día: Suma de movimientos tipo 'OPENING' de hoy
    - Recaudo: Suma de todos los pagos de préstamos de hoy
    - Gastos: Suma de movimientos tipo 'EXPENSE' de hoy
    - En Caja (Balance): Base + Recaudo - Gastos
    """
    try:
        today = date.today()
        
        # 1. Base del Día: Suma de movimientos OPENING de hoy
        base_amount = db.query(func.sum(CashMovement.amount)).filter(
            func.date(CashMovement.created_at) == today,
            CashMovement.type == 'OPENING'
        ).scalar() or 0.0
        base_amount = float(base_amount)
        
        # 2. Recaudo: Suma de pagos de préstamos de hoy
        collected_amount = db.query(func.sum(Payment.amount)).filter(
            func.date(Payment.created_at) == today
        ).scalar() or 0.0
        collected_amount = float(collected_amount)
        
        # 3. Gastos: Suma de movimientos EXPENSE de hoy
        expenses_amount = db.query(func.sum(CashMovement.amount)).filter(
            func.date(CashMovement.created_at) == today,
            CashMovement.type == 'EXPENSE'
        ).scalar() or 0.0
        expenses_amount = float(expenses_amount)
        
        # 4. Balance: Base + Recaudo - Gastos
        balance = base_amount + collected_amount - expenses_amount
        
        # 5. Obtener todos los movimientos de hoy (para la tabla)
        movements = db.query(CashMovement).filter(
            func.date(CashMovement.created_at) == today
        ).order_by(CashMovement.created_at.desc()).all()
        
        return CashSummaryOut(
            base_amount=round(base_amount, 2),
            collected_amount=round(collected_amount, 2),
            expenses_amount=round(expenses_amount, 2),
            balance=round(balance, 2),
            movements=movements
        )
    
    except Exception as e:
        logger.error(f"Error al obtener resumen de caja: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener el resumen de caja: {str(e)}")
```

---
### FILE: services/api/app/routers/reconciliation.py
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Reconciliation
from ..schemas import ReconciliationIn

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

@router.post("/close-day")
def close_day(body: ReconciliationIn, db: Session = Depends(get_db)):
    diff = round(float(body.reported_total) - float(body.delivered_total), 2)
    r = Reconciliation(collector_id=body.collector_id, 
                     reported_total=body.reported_total, 
                     delivered_total=body.delivered_total, 
                     diff=diff, notes=body.notes)
    
    db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "diff": float(diff)}
```

---
### FILE: services/api/app/routers/reports.py
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
import logging
from ..database import get_db
from ..models import Payment, CollectVisit, Schedule, Loan, Customer, User

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/daily-collection")
def daily_collection(date: str, collector_id: int, db: Session = Depends(get_db)):
    rows = db.query(Payment).filter(func.date(Payment.created_at)==date, Payment.collector_id==collector_id).all()
    total = sum([float(r.amount) for r in rows])
    return {"date": date, "collector_id": collector_id, "count": len(rows), "total": round(total,2)}

@router.get("/aging")
def aging(db: Session = Depends(get_db)):
    # Simple: agrupa por días de mora (requiere due_date y status)
    return {"buckets": ["0-7","8-15","16-30","31+"], "data": []} # placeholder estructurado

@router.get("/dashboard-stats")
def dashboard_stats(db: Session = Depends(get_db)):
    """
    Obtiene las métricas principales para el dashboard:
    - total_customers: Conteo total de clientes
    - active_portfolio: Suma del saldo pendiente de préstamos activos
    - collected_today: Suma de pagos registrados hoy
    - total_arrears: Suma de mora de todos los préstamos activos
    - expected_today: Recaudo Pretendido (suma de cuotas diarias de préstamos activos)
    - compliance_rate: Porcentaje de cumplimiento (collected_today / expected_today * 100)
    """
    try:
        # 1. Total de clientes
        total_customers = db.query(func.count(Customer.id)).scalar() or 0
        
        # 2. Cartera Activa (saldo pendiente de préstamos activos)
        active_loans = db.query(Loan).filter(Loan.status == "ACTIVE").all()
        active_portfolio = 0.0
        total_arrears = 0.0
        expected_today = 0.0  # Recaudo Pretendido (meta del día)
        
        if active_loans:
            loan_ids = [loan.id for loan in active_loans]
            
            # Obtener schedules de préstamos activos
            schedules = {}
            schedule_list = db.query(Schedule).filter(Schedule.loan_id.in_(loan_ids)).all()
            for schedule in schedule_list:
                if schedule.loan_id not in schedules:
                    schedules[schedule.loan_id] = schedule
            
            # Obtener total pagado por préstamo
            schedule_ids = [s.id for s in schedules.values()]
            total_paid_by_loan = {}
            if schedule_ids:
                payment_totals = db.query(
                    Payment.schedule_id,
                    func.sum(Payment.amount).label('total_paid')
                ).filter(
                    Payment.schedule_id.in_(schedule_ids)
                ).group_by(Payment.schedule_id).all()
                
                schedule_to_loan = {s.id: s.loan_id for s in schedules.values()}
                for schedule_id, total_paid in payment_totals:
                    loan_id = schedule_to_loan.get(schedule_id)
                    if loan_id:
                        total_paid_by_loan[loan_id] = float(total_paid) or 0.0
            
            # Calcular cartera activa, mora total y recaudo pretendido
            today = date.today()
            for loan in active_loans:
                schedule = schedules.get(loan.id)
                if schedule:
                    total = float(schedule.total)
                    total_paid = total_paid_by_loan.get(loan.id, 0.0)
                    
                    # Saldo pendiente (cartera activa)
                    remaining_balance = total - total_paid
                    if remaining_balance > 0:
                        active_portfolio += remaining_balance
                    
                    # Calcular mora
                    days_elapsed = (today - loan.disbursement_date).days
                    days_elapsed = max(0, days_elapsed)
                    
                    daily_quota = total / loan.term_days
                    expected_paid = daily_quota * days_elapsed
                    arrears = expected_paid - total_paid
                    
                    if arrears > 0:
                        total_arrears += arrears
                    
                    # Recaudo Pretendido: suma de cuotas diarias de préstamos activos
                    # Fórmula: (Monto + Interés) / Días de Plazo
                    # El schedule.total ya incluye principal + interés
                    expected_today += daily_quota
                else:
                    # Si no hay schedule, usar solo el monto del préstamo
                    daily_quota = float(loan.amount) / loan.term_days
                    expected_today += daily_quota
        
        # 3. Recaudo de hoy
        today = date.today()
        # Nota: El modelo Payment usa created_at (DateTime), no payment_date
        # Buscamos pagos creados hoy
        collected_today = db.query(func.sum(Payment.amount)).filter(
            func.date(Payment.created_at) == today
        ).scalar() or 0.0
        collected_today = float(collected_today)
        
        # 4. Porcentaje de Cumplimiento
        compliance_rate = 0.0
        if expected_today > 0:
            compliance_rate = (collected_today / expected_today) * 100
        
        return {
            "total_customers": total_customers,
            "active_portfolio": round(active_portfolio, 2),
            "collected_today": round(collected_today, 2),
            "total_arrears": round(total_arrears, 2),
            "expected_today": round(expected_today, 2),
            "compliance_rate": round(compliance_rate, 2)
        }
    
    except Exception as e:
        logger.error(f"Error al calcular métricas del dashboard: {str(e)}", exc_info=True)
        # Retornar valores por defecto en caso de error
        return {
            "total_customers": 0,
            "active_portfolio": 0.0,
            "collected_today": 0.0,
            "total_arrears": 0.0,
            "expected_today": 0.0,
            "compliance_rate": 0.0
        }

@router.get("/daily-detail")
def daily_detail(report_date: str, db: Session = Depends(get_db)):
    """
    Obtiene el detalle de todos los pagos recibidos en una fecha específica.
    Incluye información del cliente, préstamo y cobrador.
    """
    try:
        # Parsear la fecha
        try:
            target_date = date.fromisoformat(report_date)
        except ValueError:
            return {"error": "Formato de fecha inválido. Use YYYY-MM-DD"}
        
        # Query optimizada: obtener pagos con joins a schedule, loan, customer y user
        payments = db.query(
            Payment,
            Loan,
            Customer,
            User
        ).join(
            Schedule, Payment.schedule_id == Schedule.id
        ).join(
            Loan, Schedule.loan_id == Loan.id
        ).join(
            Customer, Loan.customer_id == Customer.id
        ).join(
            User, Payment.collector_id == User.id
        ).filter(
            func.date(Payment.created_at) == target_date
        ).order_by(
            Payment.created_at.asc()
        ).all()
        
        # Calcular total recaudado
        total_collected = sum([float(p.amount) for p, _, _, _ in payments])
        
        # Construir respuesta
        details = []
        for payment, loan, customer, collector in payments:
            # Formatear hora (ya está en UTC desde la BD, mantenerlo así para que el frontend lo convierta)
            # El frontend se encargará de convertir UTC a hora local
            payment_time = payment.created_at.strftime("%H:%M:%S") if payment.created_at else ""
            
            details.append({
                "id": payment.id,
                "time": payment_time,
                "customer_name": customer.name if customer else "Cliente Desconocido",
                "loan_id": loan.id if loan else None,
                "amount": float(payment.amount),
                "collector_name": collector.username if collector else "Cobrador Desconocido",
                "notes": payment.notes or ""
            })
        
        return {
            "date": report_date,
            "total_collected": round(total_collected, 2),
            "count": len(details),
            "details": details
        }
    
    except Exception as e:
        logger.error(f"Error al obtener detalle diario: {str(e)}", exc_info=True)
        return {
            "error": "Error al obtener el detalle del reporte",
            "date": report_date,
            "total_collected": 0.0,
            "count": 0,
            "details": []
        }
```

---
### FILE: services/api/app/routers/devices.py
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from ..database import get_db
from ..models import Device, User, UserRole
from ..schemas import DeviceIn, DeviceOut
from ..deps import get_current_user, require_tenant

router = APIRouter(prefix="/devices", tags=["devices"])

@router.get("/", response_model=List[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = None
):
    """
    Listar todos los dispositivos del tenant actual.
    Filtro opcional por estado: PENDING, APPROVED, BLOCKED
    Solo TENANT_ROOT y TENANT_SUB_ADMIN pueden ver dispositivos.
    """
    if current_user.role not in [UserRole.TENANT_ROOT.value, UserRole.TENANT_SUB_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver dispositivos."
        )
    
    query = db.query(Device).filter(Device.tenant_id == tenant_id)
    
    if status_filter:
        if status_filter not in ['PENDING', 'APPROVED', 'BLOCKED']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Estado inválido. Debe ser: PENDING, APPROVED o BLOCKED"
            )
        query = query.filter(Device.status == status_filter)
    
    devices = query.options(joinedload(Device.user)).all()
    
    # Construir respuesta con nombre de usuario
    result = []
    for device in devices:
        device_dict = {
            "id": device.id,
            "imei": device.imei,
            "alias": device.alias,
            "user_id": device.user_id,
            "username": device.user.username if device.user else None,
            "status": device.status,
            "last_login": device.last_login,
            "created_at": device.created_at,
            "updated_at": device.updated_at
        }
        result.append(DeviceOut(**device_dict))
    
    return result

@router.post("/", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def register_device(
    device_in: DeviceIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Registrar un nuevo dispositivo.
    Puede ser llamado desde la app móvil.
    El dispositivo se crea con estado PENDING hasta que sea aprobado.
    """
    # Verificar que el IMEI no esté duplicado
    existing = db.query(Device).filter(Device.imei == device_in.imei).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un dispositivo con ese IMEI."
        )
    
    # Si se asigna un usuario, verificar que pertenezca al mismo tenant
    if device_in.user_id:
        user = db.query(User).filter(
            User.id == device_in.user_id,
            User.tenant_id == tenant_id
        ).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario asignado no pertenece a tu organización."
            )
    
    device = Device(
        tenant_id=tenant_id,
        imei=device_in.imei,
        alias=device_in.alias,
        user_id=device_in.user_id or current_user.id,
        status="PENDING"
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    
    # Obtener nombre de usuario si existe
    username = None
    if device.user_id:
        user = db.query(User).filter(User.id == device.user_id).first()
        username = user.username if user else None
    
    device_dict = {
        "id": device.id,
        "imei": device.imei,
        "alias": device.alias,
        "user_id": device.user_id,
        "username": username,
        "status": device.status,
        "last_login": device.last_login,
        "created_at": device.created_at,
        "updated_at": device.updated_at
    }
    return DeviceOut(**device_dict)

@router.post("/{device_id}/approve", response_model=DeviceOut)
def approve_device(
    device_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Aprobar un dispositivo pendiente.
    Solo TENANT_ROOT y TENANT_SUB_ADMIN pueden aprobar dispositivos.
    """
    if current_user.role not in [UserRole.TENANT_ROOT.value, UserRole.TENANT_SUB_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para aprobar dispositivos."
        )
    
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo no encontrado."
        )
    
    if device.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El dispositivo ya está {device.status}. Solo se pueden aprobar dispositivos PENDING."
        )
    
    device.status = "APPROVED"
    db.commit()
    db.refresh(device)
    
    # Obtener nombre de usuario
    username = None
    if device.user_id:
        user = db.query(User).filter(User.id == device.user_id).first()
        username = user.username if user else None
    
    device_dict = {
        "id": device.id,
        "imei": device.imei,
        "alias": device.alias,
        "user_id": device.user_id,
        "username": username,
        "status": device.status,
        "last_login": device.last_login,
        "created_at": device.created_at,
        "updated_at": device.updated_at
    }
    return DeviceOut(**device_dict)

@router.post("/{device_id}/block", response_model=DeviceOut)
def block_device(
    device_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Bloquear un dispositivo (por seguridad).
    Solo TENANT_ROOT y TENANT_SUB_ADMIN pueden bloquear dispositivos.
    """
    if current_user.role not in [UserRole.TENANT_ROOT.value, UserRole.TENANT_SUB_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para bloquear dispositivos."
        )
    
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo no encontrado."
        )
    
    device.status = "BLOCKED"
    db.commit()
    db.refresh(device)
    
    # Obtener nombre de usuario
    username = None
    if device.user_id:
        user = db.query(User).filter(User.id == device.user_id).first()
        username = user.username if user else None
    
    device_dict = {
        "id": device.id,
        "imei": device.imei,
        "alias": device.alias,
        "user_id": device.user_id,
        "username": username,
        "status": device.status,
        "last_login": device.last_login,
        "created_at": device.created_at,
        "updated_at": device.updated_at
    }
    return DeviceOut(**device_dict)

@router.post("/{device_id}/unblock", response_model=DeviceOut)
def unblock_device(
    device_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Desbloquear un dispositivo.
    Solo TENANT_ROOT y TENANT_SUB_ADMIN pueden desbloquear dispositivos.
    """
    if current_user.role not in [UserRole.TENANT_ROOT.value, UserRole.TENANT_SUB_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para desbloquear dispositivos."
        )
    
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.tenant_id == tenant_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo no encontrado."
        )
    
    if device.status != "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El dispositivo está {device.status}. Solo se pueden desbloquear dispositivos BLOCKED."
        )
    
    device.status = "APPROVED"
    db.commit()
    db.refresh(device)
    
    # Obtener nombre de usuario
    username = None
    if device.user_id:
        user = db.query(User).filter(User.id == device.user_id).first()
        username = user.username if user else None
    
    device_dict = {
        "id": device.id,
        "imei": device.imei,
        "alias": device.alias,
        "user_id": device.user_id,
        "username": username,
        "status": device.status,
        "last_login": device.last_login,
        "created_at": device.created_at,
        "updated_at": device.updated_at
    }
    return DeviceOut(**device_dict)
```

---
### FILE: services/api/app/routers/keys.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import random
import logging
from ..database import get_db
from ..models import AccessKey, User
from ..deps import get_current_user, require_tenant
from pydantic import BaseModel
from typing import Optional, List

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/keys", tags=["keys"])

# Schemas
class GenerateKeyRequest(BaseModel):
    action_type: str  # DELETE_PAYMENT, OVERRIDE_LIMIT, REFINANCE, OTHER

class ValidateKeyRequest(BaseModel):
    code: str

class AccessKeyResponse(BaseModel):
    id: int
    code: str
    action_type: str
    status: str
    generated_by: int
    generator_username: Optional[str] = None
    used_by: Optional[int] = None
    user_username: Optional[str] = None
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/generate")
def generate_key(
    body: GenerateKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Genera una llave de seguridad (código numérico de 4 dígitos).
    Solo usuarios con rol de Admin pueden generar llaves.
    """
    # Verificar que el usuario es Admin
    if current_user.role not in ["SUPER_ADMIN", "TENANT_ROOT", "TENANT_SUB_ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail="Solo administradores pueden generar llaves de seguridad"
        )
    
    # Obtener tenant_id
    tenant_id = require_tenant(current_user)
    
    # Validar action_type
    valid_actions = ["DELETE_PAYMENT", "OVERRIDE_LIMIT", "REFINANCE", "OTHER"]
    if body.action_type not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"action_type debe ser uno de: {', '.join(valid_actions)}"
        )
    
    # Generar código único de 4 dígitos para hoy
    today = datetime.now().date()
    max_attempts = 100
    code = None
    
    for _ in range(max_attempts):
        # Generar código de 4 dígitos
        candidate_code = str(random.randint(1000, 9999))
        
        # Verificar que no exista una llave activa con este código para el tenant hoy
        existing = db.query(AccessKey).filter(
            and_(
                AccessKey.tenant_id == tenant_id,
                AccessKey.code == candidate_code,
                func.date(AccessKey.created_at) == today,
                AccessKey.status == "ACTIVE"
            )
        ).first()
        
        if not existing:
            code = candidate_code
            break
    
    if not code:
        raise HTTPException(
            status_code=500,
            detail="No se pudo generar un código único después de varios intentos"
        )
    
    # Crear la llave con expiración de 15 minutos
    expires_at = datetime.now() + timedelta(minutes=15)
    
    access_key = AccessKey(
        tenant_id=tenant_id,
        code=code,
        action_type=body.action_type,
        status="ACTIVE",
        generated_by=current_user.id,
        expires_at=expires_at
    )
    
    db.add(access_key)
    db.commit()
    db.refresh(access_key)
    
    logger.info(f"Llave generada: {code} por usuario {current_user.username} para acción {body.action_type}")
    
    return {
        "code": code,
        "action_type": body.action_type,
        "expires_at": expires_at.isoformat(),
        "id": access_key.id
    }

@router.get("")
def list_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista las llaves generadas hoy para auditoría.
    Solo usuarios con rol de Admin pueden ver las llaves.
    """
    # Verificar que el usuario es Admin
    if current_user.role not in ["SUPER_ADMIN", "TENANT_ROOT", "TENANT_SUB_ADMIN"]:
        raise HTTPException(
            status_code=403,
            detail="Solo administradores pueden ver las llaves de seguridad"
        )
    
    # Obtener tenant_id
    tenant_id = require_tenant(current_user)
    
    # Obtener llaves generadas hoy
    today = datetime.now().date()
    keys = db.query(AccessKey).filter(
        and_(
            AccessKey.tenant_id == tenant_id,
            func.date(AccessKey.created_at) == today
        )
    ).order_by(AccessKey.created_at.desc()).all()
    
    # Verificar y actualizar llaves expiradas
    now = datetime.now()
    for key in keys:
        if key.status == "ACTIVE" and key.expires_at < now:
            key.status = "EXPIRED"
    
    db.commit()
    
    # Construir respuesta con información de usuarios
    result = []
    for key in keys:
        generator = db.query(User).filter(User.id == key.generated_by).first()
        user = None
        if key.used_by:
            user = db.query(User).filter(User.id == key.used_by).first()
        
        result.append({
            "id": key.id,
            "code": key.code,
            "action_type": key.action_type,
            "status": key.status,
            "generated_by": key.generated_by,
            "generator_username": generator.username if generator else None,
            "used_by": key.used_by,
            "user_username": user.username if user else None,
            "expires_at": key.expires_at.isoformat(),
            "created_at": key.created_at.isoformat()
        })
    
    return result

@router.post("/validate")
def validate_key(
    body: ValidateKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Valida un código de llave de seguridad.
    Verifica que existe, es del tenant correcto, no ha expirado y está ACTIVE.
    Si pasa, lo marca como USED.
    """
    # Obtener tenant_id
    tenant_id = require_tenant(current_user)
    
    # Buscar la llave
    key = db.query(AccessKey).filter(
        and_(
            AccessKey.code == body.code,
            AccessKey.tenant_id == tenant_id
        )
    ).first()
    
    if not key:
        raise HTTPException(
            status_code=404,
            detail="Código de llave no encontrado"
        )
    
    # Verificar que no haya expirado
    now = datetime.now()
    if key.expires_at < now:
        key.status = "EXPIRED"
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="La llave ha expirado"
        )
    
    # Verificar que esté activa
    if key.status != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail=f"La llave ya fue utilizada o está {key.status.lower()}"
        )
    
    # Marcar como usada
    key.status = "USED"
    key.used_by = current_user.id
    db.commit()
    
    logger.info(f"Llave {body.code} validada y marcada como usada por usuario {current_user.username}")
    
    return {
        "valid": True,
        "action_type": key.action_type,
        "message": "Llave validada correctamente"
    }
```

---
### FILE: services/api/app/routers/groups.py
```python
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
from sqlalchemy import func
import logging
from ..database import get_db
from ..models import Group, Customer, Loan, Schedule, Payment, Branch
from ..schemas import GroupIn, GroupOut
from ..deps import get_current_user, require_tenant
from ..models import User, UserRole

# Configurar logging
logger = logging.getLogger(__name__)

# Usamos el router sin prefijo aquí porque ya se define en main.py como /groups
router = APIRouter()

@router.get("/", response_model=List[GroupOut])
def read_groups(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener lista de rutas (grupos) del tenant actual.
    Incluye el nombre del centro de negocio (branch).
    """
    try:
        logger.info(f"Usuario: {current_user.username}, Role: {current_user.role}, Tenant ID: {tenant_id}")
        logger.info(f"Obteniendo grupos para tenant_id={tenant_id}, skip={skip}, limit={limit}")
        
        # Obtener grupos sin joinedload para evitar problemas con branch_id NULL
        groups = db.query(Group).filter(
            Group.tenant_id == tenant_id
        ).offset(skip).limit(limit).all()
        
        logger.info(f"Encontrados {len(groups)} grupos para tenant_id={tenant_id}")
        
        # Si no hay grupos, retornar lista vacía (no es un error)
        if not groups:
            logger.info(f"No hay grupos para tenant_id={tenant_id}")
            return []
        
        # Obtener todos los branch_ids únicos de una vez (optimización)
        branch_ids = [g.branch_id for g in groups if g.branch_id]
        branches = {}
        if branch_ids:
            branch_list = db.query(Branch).filter(Branch.id.in_(branch_ids)).all()
            branches = {b.id: b.name for b in branch_list}
            logger.debug(f"Encontrados {len(branches)} branches para los grupos")
        
        # Construir respuesta con nombre de branch
        result = []
        validation_errors = []
        for group in groups:
            try:
                group_dict = {
                    "id": group.id,
                    "name": group.name,
                    "description": group.description,
                    "branch_id": group.branch_id,
                    "branch_name": branches.get(group.branch_id) if group.branch_id else None,
                    "parent_id": group.parent_id
                }
                # Validar con Pydantic antes de agregar
                group_out = GroupOut(**group_dict)
                result.append(group_out)
            except Exception as e:
                error_msg = f"Error al procesar grupo ID {group.id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                validation_errors.append(error_msg)
                # Continuar con el siguiente grupo en lugar de fallar todo
                continue
        
        # Si hay errores de validación pero al menos algunos grupos se procesaron, loguear advertencia
        if validation_errors and result:
            logger.warning(f"Se procesaron {len(result)} grupos de {len(groups)}. Errores: {validation_errors}")
        elif validation_errors and not result:
            # Si todos los grupos fallaron, lanzar error
            logger.error(f"Todos los grupos fallaron la validación. Errores: {validation_errors}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al procesar los grupos: {validation_errors[0] if validation_errors else 'Error desconocido'}"
            )
        
        logger.info(f"Retornando {len(result)} grupos válidos")
        return result
        
    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error inesperado al obtener grupos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al cargar las rutas"
        )

@router.post("/", response_model=GroupOut)
def create_group(
    group_in: GroupIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Crear una nueva ruta (grupo).
    Si no se especifica branch_id, se asigna al primer centro de negocio del tenant.
    Si no hay branches, se permite crear la ruta sin branch (branch_id = None).
    """
    try:
        logger.info(f"Creando grupo '{group_in.name}' para tenant_id={tenant_id}")
        
        # Verificar si ya existe en el mismo tenant (case-insensitive)
        existing_group = db.query(Group).filter(
            Group.tenant_id == tenant_id,
            func.lower(Group.name) == func.lower(group_in.name.strip())
        ).first()
        if existing_group:
            logger.warning(f"Intento de crear grupo duplicado: '{group_in.name}' para tenant_id={tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una ruta con ese nombre"
            )
        
        # Si no se especifica branch_id, intentar obtener el primer centro de negocio del tenant
        # Si no hay branches, se permite crear la ruta sin branch (branch_id = None)
        branch_id = group_in.branch_id
        if not branch_id:
            first_branch = db.query(Branch).filter(Branch.tenant_id == tenant_id).first()
            if first_branch:
                branch_id = first_branch.id
                logger.debug(f"Asignando branch_id={branch_id} automáticamente")
            else:
                logger.info(f"No hay branches disponibles para tenant_id={tenant_id}, creando grupo sin branch")
        else:
            # Verificar que el branch pertenezca al mismo tenant
            branch = db.query(Branch).filter(
                Branch.id == branch_id,
                Branch.tenant_id == tenant_id
            ).first()
            if not branch:
                logger.warning(f"Branch_id={branch_id} no pertenece a tenant_id={tenant_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El centro de negocio especificado no pertenece a tu organización."
                )

        # Crear grupo (branch_id puede ser None)
        db_group = Group(
            tenant_id=tenant_id,
            branch_id=branch_id,
            name=group_in.name.strip(),
            description=group_in.description.strip() if group_in.description else None
        ) 
        db.add(db_group)
        db.flush()  # Para obtener el ID sin commit
        
        # Obtener nombre del branch si existe
        branch_name = None
        if branch_id:
            branch = db.query(Branch).filter(Branch.id == branch_id).first()
            branch_name = branch.name if branch else None
        
        db.commit()
        db.refresh(db_group)
        
        logger.info(f"Grupo creado exitosamente: ID={db_group.id}, nombre='{db_group.name}'")
        
        group_dict = {
            "id": db_group.id,
            "name": db_group.name,
            "description": db_group.description,
            "branch_id": db_group.branch_id,
            "branch_name": branch_name,
            "parent_id": db_group.parent_id
        }
        return GroupOut(**group_dict)
        
    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error de integridad al crear grupo: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error de integridad: posible duplicado o violación de restricción"
        )
    except (OperationalError, DatabaseError) as e:
        db.rollback()
        logger.error(f"Error de base de datos al crear grupo: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error de conexión con la base de datos"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al crear grupo: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al crear la ruta"
        )

@router.get("/{group_id}/customers")
def get_group_customers(
    group_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener clientes de una ruta (grupo) con sus coordenadas y saldo pendiente.
    Devuelve lista vacía si no hay clientes, NO lanza error 404.
    Valida que el grupo pertenezca al tenant del usuario.
    """
    try:
        logger.info(f"Obteniendo clientes del grupo {group_id} para tenant_id={tenant_id}")
        
        # Verificar que el grupo existe y pertenece al tenant
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.tenant_id == tenant_id
        ).first()
        if not group:
            logger.warning(f"Grupo {group_id} no encontrado o no pertenece a tenant_id={tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ruta no encontrada"
            )
        
        # Obtener clientes del grupo con coordenadas
        customers = db.query(Customer).filter(Customer.group_id == group_id).all()
        
        logger.info(f"Encontrados {len(customers)} clientes para grupo {group_id}")
        
        # Si no hay clientes, devolver lista vacía (NO error)
        if not customers:
            return {
                "group_id": group_id,
                "group_name": group.name,
                "customers": []
            }
        
        # Para cada cliente, calcular saldo pendiente
        customers_data = []
        for customer in customers:
            try:
                # Calcular saldo pendiente de préstamos activos
                active_loans = db.query(Loan).filter(
                    Loan.customer_id == customer.id,
                    Loan.status == "ACTIVE"
                ).all()
                
                total_balance = 0.0
                for loan in active_loans:
                    # Obtener schedule del préstamo
                    schedule = db.query(Schedule).filter(Schedule.loan_id == loan.id).first()
                    if schedule:
                        # Calcular total pagado
                        total_paid = db.query(func.sum(Payment.amount)).join(
                            Schedule, Payment.schedule_id == Schedule.id
                        ).filter(
                            Schedule.loan_id == loan.id
                        ).scalar() or 0.0
                        
                        # Saldo pendiente
                        total_due = float(schedule.total)
                        remaining = total_due - float(total_paid)
                        total_balance += remaining if remaining > 0 else 0.0
                
                # Usar coordenadas dummy si no existen (Quito, Ecuador)
                lat = customer.lat if customer.lat else -0.1807 + (customer.id % 10) * 0.01
                lng = customer.lng if customer.lng else -78.4678 + (customer.id % 10) * 0.01
                
                customers_data.append({
                    "id": customer.id,
                    "name": customer.name,
                    "address": customer.address or "Sin dirección",
                    "lat": lat,
                    "lng": lng,
                    "balance": round(total_balance, 2)
                })
            except Exception as e:
                logger.error(f"Error al procesar cliente ID {customer.id}: {str(e)}", exc_info=True)
                # Continuar con el siguiente cliente
                continue
        
        return {
            "group_id": group_id,
            "group_name": group.name,
            "customers": customers_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado al obtener clientes del grupo {group_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al cargar los clientes de la ruta"
        )
```

---
### FILE: services/api/app/routers/branches.py
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import Branch, Tenant
from ..schemas import BranchIn, BranchOut
from ..deps import get_current_user, require_tenant
from ..models import User, UserRole

router = APIRouter(prefix="/branches", tags=["branches"])

@router.get("/", response_model=List[BranchOut])
def list_branches(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Listar todos los centros de negocio del tenant actual.
    Solo TENANT_ROOT y TENANT_SUB_ADMIN pueden ver centros de negocio.
    """
    if current_user.role not in [UserRole.TENANT_ROOT.value, UserRole.TENANT_SUB_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver centros de negocio."
        )
    
    branches = db.query(Branch).filter(Branch.tenant_id == tenant_id).all()
    return branches

@router.post("/", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
def create_branch(
    branch_in: BranchIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Crear un nuevo centro de negocio.
    Solo TENANT_ROOT puede crear centros de negocio.
    """
    if current_user.role != UserRole.TENANT_ROOT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el dueño de la empresa puede crear centros de negocio."
        )
    
    # Verificar que el nombre no esté duplicado en el mismo tenant
    existing = db.query(Branch).filter(
        Branch.tenant_id == tenant_id,
        Branch.name == branch_in.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un centro de negocio con ese nombre."
        )
    
    branch = Branch(
        tenant_id=tenant_id,
        name=branch_in.name,
        location=branch_in.location,
        max_daily_loan=branch_in.max_daily_loan,
        max_expense_amount=branch_in.max_expense_amount,
        days_late_yellow=branch_in.days_late_yellow or 3,
        days_late_red=branch_in.days_late_red or 7
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch

@router.get("/{branch_id}", response_model=BranchOut)
def get_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener un centro de negocio por ID.
    """
    if current_user.role not in [UserRole.TENANT_ROOT.value, UserRole.TENANT_SUB_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver centros de negocio."
        )
    
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.tenant_id == tenant_id
    ).first()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Centro de negocio no encontrado."
        )
    
    return branch

@router.put("/{branch_id}", response_model=BranchOut)
def update_branch(
    branch_id: int,
    branch_in: BranchIn,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Actualizar un centro de negocio.
    Solo TENANT_ROOT puede actualizar centros de negocio.
    """
    if current_user.role != UserRole.TENANT_ROOT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el dueño de la empresa puede actualizar centros de negocio."
        )
    
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.tenant_id == tenant_id
    ).first()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Centro de negocio no encontrado."
        )
    
    # Verificar que el nombre no esté duplicado (si se cambió)
    if branch_in.name != branch.name:
        existing = db.query(Branch).filter(
            Branch.tenant_id == tenant_id,
            Branch.name == branch_in.name,
            Branch.id != branch_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un centro de negocio con ese nombre."
            )
    
    # Actualizar campos
    branch.name = branch_in.name
    branch.location = branch_in.location
    branch.max_daily_loan = branch_in.max_daily_loan
    branch.max_expense_amount = branch_in.max_expense_amount
    if branch_in.days_late_yellow is not None:
        branch.days_late_yellow = branch_in.days_late_yellow
    if branch_in.days_late_red is not None:
        branch.days_late_red = branch_in.days_late_red
    
    db.commit()
    db.refresh(branch)
    return branch

@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(require_tenant),
    current_user: User = Depends(get_current_user)
):
    """
    Eliminar un centro de negocio.
    Solo TENANT_ROOT puede eliminar centros de negocio.
    Nota: No se puede eliminar si tiene rutas asignadas.
    """
    if current_user.role != UserRole.TENANT_ROOT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el dueño de la empresa puede eliminar centros de negocio."
        )
    
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.tenant_id == tenant_id
    ).first()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Centro de negocio no encontrado."
        )
    
    # Verificar que no tenga rutas asignadas
    from ..models import Group
    groups_count = db.query(Group).filter(Group.branch_id == branch_id).count()
    if groups_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el centro de negocio porque tiene {groups_count} ruta(s) asignada(s)."
        )
    
    db.delete(branch)
    db.commit()
    return None
```

---
### FILE: services/api/app/routers/users.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import User, Group, UserRole
from ..schemas import UserIn, UserOut, UserUpdate
from ..deps import get_current_user, require_tenant
from ..utils.hashing import hash_pwd

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant)
):
    """
    Listar todos los usuarios que pertenecen al mismo tenant_id que el solicitante.
    Solo TENANT_ROOT puede ver todos los usuarios de su tenant.
    """
    # Verificar que el usuario tenga permisos (TENANT_ROOT o TENANT_SUB_ADMIN)
    if current_user.role not in [UserRole.TENANT_ROOT.value, UserRole.TENANT_SUB_ADMIN.value]:
        raise HTTPException(403, "No tienes permisos para ver usuarios")
    
    # Obtener usuarios del mismo tenant
    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    
    # Enriquecer con información del grupo
    result = []
    for user in users:
        user_dict = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "group_id": user.group_id,
            "group_name": None,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        
        # Obtener nombre del grupo si existe
        if user.group_id:
            group = db.query(Group).filter(Group.id == user.group_id).first()
            if group:
                user_dict["group_name"] = group.name
        
        result.append(UserOut(**user_dict))
    
    return result

@router.post("", response_model=UserOut)
def create_user(
    body: UserIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant)
):
    """
    Crear un nuevo colaborador.
    Solo TENANT_ROOT puede crear usuarios.
    """
    # Solo TENANT_ROOT puede crear usuarios
    if current_user.role != UserRole.TENANT_ROOT.value:
        raise HTTPException(403, "Solo el dueño puede crear colaboradores")
    
    # Verificar que el username no exista
    existing_user = db.query(User).filter(User.username == body.username).first()
    if existing_user:
        raise HTTPException(400, "El nombre de usuario ya existe")
    
    # Validar que el group_id pertenezca al mismo tenant si se proporciona
    if body.group_id:
        group = db.query(Group).filter(
            Group.id == body.group_id,
            Group.tenant_id == tenant_id
        ).first()
        if not group:
            raise HTTPException(400, "La ruta especificada no existe o no pertenece a tu empresa")
    
    # Crear el nuevo usuario
    new_user = User(
        username=body.username,
        password_hash=hash_pwd(body.password),
        role=body.role,
        tenant_id=tenant_id,  # Asignar automáticamente el tenant_id del creador
        group_id=body.group_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Obtener nombre del grupo si existe
    group_name = None
    if new_user.group_id:
        group = db.query(Group).filter(Group.id == new_user.group_id).first()
        if group:
            group_name = group.name
    
    return UserOut(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role,
        tenant_id=new_user.tenant_id,
        group_id=new_user.group_id,
        group_name=group_name,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at
    )

@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant)
):
    """
    Editar usuario (Cambiar ruta, cambiar estado, resetear password).
    Solo TENANT_ROOT puede editar usuarios.
    """
    # Solo TENANT_ROOT puede editar usuarios
    if current_user.role != UserRole.TENANT_ROOT.value:
        raise HTTPException(403, "Solo el dueño puede editar colaboradores")
    
    # Buscar el usuario
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    
    # No permitir editar SUPER_ADMIN o TENANT_ROOT
    if user.role in [UserRole.SUPER_ADMIN.value, UserRole.TENANT_ROOT.value]:
        raise HTTPException(403, "No se puede editar este tipo de usuario")
    
    # Actualizar campos si se proporcionan
    if body.username is not None:
        # Verificar que el nuevo username no exista (excepto si es el mismo usuario)
        existing = db.query(User).filter(
            User.username == body.username,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(400, "El nombre de usuario ya existe")
        user.username = body.username
    
    if body.password is not None:
        user.password_hash = hash_pwd(body.password)
    
    if body.role is not None:
        user.role = body.role
    
    if body.group_id is not None:
        # Validar que el group_id pertenezca al mismo tenant
        if body.group_id == 0:  # Permitir desasignar grupo
            user.group_id = None
        else:
            group = db.query(Group).filter(
                Group.id == body.group_id,
                Group.tenant_id == tenant_id
            ).first()
            if not group:
                raise HTTPException(400, "La ruta especificada no existe o no pertenece a tu empresa")
            user.group_id = body.group_id
    
    # Nota: is_active no está en el modelo User actualmente
    # Si necesitas esta funcionalidad, deberías agregar una columna is_active al modelo
    
    db.commit()
    db.refresh(user)
    
    # Obtener nombre del grupo si existe
    group_name = None
    if user.group_id:
        group = db.query(Group).filter(Group.id == user.group_id).first()
        if group:
            group_name = group.name
    
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        tenant_id=user.tenant_id,
        group_id=user.group_id,
        group_name=group_name,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant)
):
    """
    Eliminar un usuario (soft delete o hard delete).
    Solo TENANT_ROOT puede eliminar usuarios.
    """
    # Solo TENANT_ROOT puede eliminar usuarios
    if current_user.role != UserRole.TENANT_ROOT.value:
        raise HTTPException(403, "Solo el dueño puede eliminar colaboradores")
    
    # Buscar el usuario
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    
    # No permitir eliminar SUPER_ADMIN, TENANT_ROOT o al mismo usuario
    if user.role in [UserRole.SUPER_ADMIN.value, UserRole.TENANT_ROOT.value]:
        raise HTTPException(403, "No se puede eliminar este tipo de usuario")
    
    if user.id == current_user.id:
        raise HTTPException(400, "No puedes eliminarte a ti mismo")
    
    db.delete(user)
    db.commit()
    
    return {"message": "Usuario eliminado correctamente"}
```

---
### FILE: services/api/app/routers/tenants.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, timedelta
from ..database import get_db
from ..models import Tenant, License, User, Group, Branch, UserRole
from ..schemas import TenantSetupIn, TenantOut, LoginOut
from ..deps import get_current_user
from ..security import create_token

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post("/setup", response_model=LoginOut)
def setup_tenant(
    body: TenantSetupIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuevo Tenant, una License DEMO (15 días) y asigna el tenant_id al usuario actual.
    Solo usuarios sin tenant pueden ejecutar esto.
    Retorna un nuevo token con el tenant_id actualizado.
    """
    # Verificar que el usuario no tenga tenant ya asignado
    if current_user.tenant_id is not None:
        raise HTTPException(400, "El usuario ya tiene un tenant asignado")
    
    # Verificar que el usuario tenga rol TENANT_ROOT
    if current_user.role != UserRole.TENANT_ROOT.value:
        raise HTTPException(403, "Solo usuarios TENANT_ROOT pueden crear tenants")
    
    try:
        # Crear el Tenant
        tenant = Tenant(
            name=body.company_name,
            status="ACTIVE",
            currency=body.currency  # Guardar la moneda seleccionada
        )
        db.add(tenant)
        db.flush()  # Para obtener el ID sin hacer commit
        
        # Crear la License DEMO (15 días)
        expiration_date = date.today() + timedelta(days=15)
        license = License(
            tenant_id=tenant.id,
            plan_type="BASIC",  # Plan DEMO
            expiration_date=expiration_date,
            is_active=True
        )
        db.add(license)
        
        # Crear un centro de negocio por defecto "Centro Principal"
        default_branch = Branch(
            tenant_id=tenant.id,
            name="Centro Principal",
            location="Sede Principal",
            days_late_yellow=3,
            days_late_red=7
        )
        db.add(default_branch)
        db.flush()  # Para obtener el ID
        
        # Crear un grupo por defecto "Sucursal Principal" asociado al centro
        default_group = Group(
            tenant_id=tenant.id,
            branch_id=default_branch.id,
            name="Sucursal Principal",
            description="Grupo por defecto"
        )
        db.add(default_group)
        
        # Asignar el tenant_id al usuario
        current_user.tenant_id = tenant.id
        db.add(current_user)
        
        # Commit de todo
        db.commit()
        db.refresh(current_user)
        
        # Generar nuevo token con el tenant_id actualizado
        token = create_token(sub=current_user.username, role=current_user.role, tenant_id=tenant.id)
        
        return {
            "token": token,
            "role": current_user.role,
            "tenant_id": tenant.id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al crear tenant: {str(e)}")

@router.get("/me", response_model=TenantOut)
def get_my_tenant(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el tenant del usuario actual.
    """
    if current_user.tenant_id is None:
        raise HTTPException(404, "El usuario no tiene tenant asignado")
    
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Tenant no encontrado")
    
    return tenant
```

---
### FILE: services/api/app/routers/audit.py
```python
from fastapi import APIRouter
router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/trace")
def trace(entity: str, entity_id: int):
    return {"entity": entity, "entity_id": entity_id, "events": []}
```

---
### FILE: services/api/app/routers/privacy.py
```python
from fastapi import APIRouter
router = APIRouter(prefix="/privacy", tags=["privacy"])

@router.post("/consent")
def save_consent():
    return {"ok": True}
```

---
### FILE: services/api/app/utils/hashing.py
```python
from passlib.hash import bcrypt

def hash_pwd(s: str) -> str:
    return bcrypt.hash(s)

def verify_pwd(s: str, h: str) -> bool:
    return bcrypt.verify(s, h)
```

---
### FILE: services/api/app/utils/audit.py
```python
import hashlib, json

def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```

---
### FILE: apps/web-admin/src/pages/_app.tsx
```typescript
import type { AppProps } from 'next/app';
import { GoogleOAuthProvider } from '@react-oauth/google';
import '../styles/globals.css';

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

export default function App({ Component, pageProps }: AppProps) {
  // Solo renderizar el provider si hay un Client ID válido
  if (!GOOGLE_CLIENT_ID || GOOGLE_CLIENT_ID.trim() === '') {
    if (process.env.NODE_ENV === 'development') {
      console.warn('NEXT_PUBLIC_GOOGLE_CLIENT_ID no está configurado. Google OAuth no estará disponible.');
    }
    return <Component {...pageProps} />;
  }

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <Component {...pageProps} />
    </GoogleOAuthProvider>
  );
}
```

---
### FILE: apps/web-admin/src/pages/index.tsx
```typescript
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { api } from '../lib/api';

interface Metrics {
  total_customers: number;
  active_portfolio: number;
  collected_today: number;
  total_arrears: number;
  expected_today: number;
  compliance_rate: number;
}

export default function Dashboard() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<Metrics>({
    total_customers: 0,
    active_portfolio: 0.0,
    collected_today: 0.0,
    total_arrears: 0.0,
    expected_today: 0.0,
    compliance_rate: 0.0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        setLoading(true);
        setError('');
        const response = await api.get('/reports/dashboard-stats');
        setMetrics(response.data);
      } catch (err: any) {
        console.error('Error loading metrics:', err);
        setError('Error al cargar las métricas');
        // Mantener valores por defecto en caso de error
        setMetrics({
          total_customers: 0,
          active_portfolio: 0.0,
          collected_today: 0.0,
          total_arrears: 0.0,
          expected_today: 0.0,
          compliance_rate: 0.0,
        });
      } finally {
        setLoading(false);
      }
    };

    loadMetrics();
  }, []);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-EC', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  // Función para obtener el color de la barra de progreso
  const getProgressColor = (rate: number) => {
    if (rate < 50) return 'bg-red-500';
    if (rate < 80) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const kpiCards = [
    {
      title: 'Total Clientes',
      value: loading ? '...' : metrics.total_customers.toLocaleString('es-EC'),
      icon: '👥',
      bgColor: 'bg-blue-500',
      textColor: 'text-blue-600',
    },
    {
      title: 'Cartera Activa',
      value: loading ? '...' : formatCurrency(metrics.active_portfolio),
      icon: '💰',
      bgColor: 'bg-green-500',
      textColor: 'text-green-600',
    },
    {
      title: 'Desempeño Diario',
      value: loading ? '...' : formatCurrency(metrics.collected_today),
      subtitle: loading ? '...' : `de ${formatCurrency(metrics.expected_today)}`,
      icon: '💵',
      bgColor: 'bg-emerald-500',
      textColor: 'text-emerald-600',
      showProgress: true,
      complianceRate: metrics.compliance_rate,
    },
    {
      title: 'Mora Total',
      value: loading ? '...' : formatCurrency(metrics.total_arrears),
      icon: '🚨',
      bgColor: 'bg-red-500',
      textColor: metrics.total_arrears > 0 ? 'text-red-600' : 'text-gray-600',
    },
  ];

  return (
    <Layout>
      <div className="space-y-6">
        {error && (
          <div className="bg-red-50 border-2 border-red-300 text-red-700 px-4 py-3 rounded-lg text-sm font-medium">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Grid de Tarjetas KPI */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {kpiCards.map((card, index) => (
            <div
              key={index}
              className="bg-white rounded-xl shadow-md border border-gray-200 p-6 hover:shadow-lg transition-all duration-200"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-600 mb-2">{card.title}</p>
                  <p className={`text-3xl font-bold ${card.textColor}`}>
                    {card.value}
                  </p>
                  {card.subtitle && (
                    <p className="text-sm text-gray-500 mt-1">{card.subtitle}</p>
                  )}
                  {/* Barra de Progreso para Desempeño Diario */}
                  {card.showProgress && !loading && (
                    <div className="mt-4">
                      <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
                        <div
                          className={`h-3 rounded-full transition-all duration-500 ${getProgressColor(card.complianceRate || 0)}`}
                          style={{
                            width: `${Math.min(card.complianceRate || 0, 100)}%`
                          }}
                        />
                      </div>
                      <p className="text-xs font-medium text-gray-600">
                        {card.complianceRate?.toFixed(1) || 0}% de la meta
                      </p>
                    </div>
                  )}
                </div>
                <div className={`w-16 h-16 ${card.bgColor} rounded-xl flex items-center justify-center text-3xl shadow-md`}>
                  {card.icon}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Accesos Rápidos */}
        <div className="bg-white rounded-xl shadow-md border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Accesos Rápidos</h2>
          <div className="flex flex-wrap gap-4">
            <button
              onClick={() => router.push('/customers/create')}
              className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors shadow-md hover:shadow-lg flex items-center gap-2"
            >
              <span className="text-xl">+</span>
              <span>Registrar Cliente</span>
            </button>
            <button
              onClick={() => router.push('/loans/create')}
              className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors shadow-md hover:shadow-lg flex items-center gap-2"
            >
              <span className="text-xl">+</span>
              <span>Crear Préstamo</span>
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
```

---
### FILE: apps/web-admin/src/pages/login.tsx
```typescript
import { useState } from 'react';
import { useRouter } from 'next/router';
import { GoogleLogin } from '@react-oauth/google';
import { api, setAuthToken } from '../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  
  // Verificar si Google OAuth está disponible
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const isGoogleOAuthAvailable = googleClientId && googleClientId.trim() !== '';

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/auth/login', { username, password });
      setAuthToken(res.data.token);
      // Redirigir según si tiene tenant o no
      if (res.data.tenant_id) {
        router.push('/');
      } else {
        router.push('/onboarding');
      }
    } catch (err) {
      setError('Credenciales incorrectas o error de conexión');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse: any) => {
    setGoogleLoading(true);
    setError('');
    try {
      // Obtener el id_token del response
      const idToken = credentialResponse.credential;
      if (!idToken) {
        throw new Error('No se recibió token de Google');
      }

      // Llamar al backend
      const res = await api.post('/auth/google', { id_token: idToken });
      setAuthToken(res.data.token);
      
      // Redirigir según si tiene tenant o no
      if (res.data.tenant_id) {
        router.push('/');
      } else {
        router.push('/onboarding');
      }
    } catch (err: any) {
      // Mejorar el manejo de errores para mostrar detalles
      const errorMessage = err.response?.data?.detail || 
                          err.response?.data?.message || 
                          err.message || 
                          'Error al autenticar con Google';
      setError(errorMessage);
      console.error('Error en Google OAuth:', err); // Para debugging
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError('Error al iniciar sesión con Google');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">CobroPro</h1>
            <p className="text-gray-600">Panel de Administración</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Usuario
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-colors"
                placeholder="Ingresa tu usuario"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-colors"
                placeholder="Ingresa tu contraseña"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading || googleLoading}
              className="w-full px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors shadow-sm hover:shadow-md"
            >
              {loading ? 'Iniciando sesión...' : 'Ingresar'}
            </button>
          </form>

          {isGoogleOAuthAvailable && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white text-gray-500">O</span>
                </div>
              </div>

              <div className="mt-4 flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  useOneTap={false}
                  theme="outline"
                  size="large"
                  text="signin_with"
                  shape="rectangular"
                  width="100%"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

---
### FILE: apps/web-admin/src/lib/api.ts
```typescript
import axios, { AxiosError } from 'axios';
import Cookies from 'js-cookie';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000, // 10 segundos de timeout
});

// Interceptor de request: agregar token JWT
api.interceptors.request.use(
  (config) => {
    const token = Cookies.get('token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor de response: manejar errores de autenticación
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    // Log detallado para debugging
    if (process.env.NODE_ENV === 'development') {
      console.log('API Error Interceptor:', {
        hasResponse: !!error.response,
        hasRequest: !!error.request,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        message: error.message
      });
    }
    
    // Si es un error 401 (No autorizado), redirigir al login
    if (error.response?.status === 401) {
      Cookies.remove('token');
      // Solo redirigir si no estamos ya en la página de login
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const setAuthToken = (token: string) => {
  Cookies.set('token', token, { expires: 1/3 }); // 8 horas
};

export const logout = () => {
  Cookies.remove('token');
  window.location.href = '/login';
};
```

---
### FILE: ops/docker/docker-compose.yml
```yaml
version: "3.9"

services:
  db:
    image: postgres:16
    container_name: cobropro_db
    environment:
      POSTGRES_DB: cobropro
      POSTGRES_USER: cobropro
      POSTGRES_PASSWORD: cobropro
    ports: ["5432:5432"]
    volumes: [dbdata:/var/lib/postgresql/data]

  redis:
    image: redis:7
    container_name: cobropro_redis
    ports: ["6379:6379"]

  minio:
    image: minio/minio:latest
    container_name: cobropro_minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: adminadmin
    ports: ["9000:9000","9001:9001"]
    volumes: [miniodata:/data]

  api:
    build: ../../services/api
    container_name: cobropro_api
    env_file: ../../services/api/.env.example
    depends_on: [db, redis, minio]
    ports: ["8000:8000"]

  routing:
    build: ../../services/routing
    container_name: cobropro_routing
    env_file: ../../services/routing/.env.example
    depends_on: []
    ports: ["7000:7000"]

volumes:
  dbdata:
  miniodata:
```
