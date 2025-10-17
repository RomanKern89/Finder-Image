from datetime import timedelta
from io import BytesIO
from typing import List

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    get_user_by_username,
    verify_password,
)
from .config import get_settings
from .database import SessionLocal, engine
from .models import Base, ImageResult, Product, SearchLog, User
from .schemas import (
    BatchSearchRequest,
    ChangeCredentialsRequest,
    LogEntry,
    ProductCreate,
    ProductDetail,
    ProductRead,
    SearchRequest,
    SelectImageRequest,
    Token,
    UserRead,
)
from .search import SearchError, search_with_google, search_with_openai


settings = get_settings()

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def ensure_admin_user() -> None:
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == "admin").first()
        if not user:
            session.add(
                User(
                    username="admin",
                    password_hash=get_password_hash("admin"),
                )
            )
            session.commit()
    finally:
        session.close()


@app.get("/", response_class=HTMLResponse)
def serve_home() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.post("/api/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    session = SessionLocal()
    try:
        user = get_user_by_username(session, form_data.username)
        if not user or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
        access_token = create_access_token(data={"sub": user.username}, expires_delta=timedelta(minutes=settings.access_token_expire_minutes))
        return Token(access_token=access_token)
    finally:
        session.close()


@app.get("/api/me", response_model=UserRead)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/api/change-credentials", response_model=UserRead)
def change_credentials(payload: ChangeCredentialsRequest, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        if not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        if session.query(User).filter(User.username == payload.new_username, User.id != current_user.id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
        current_user.username = payload.new_username
        current_user.password_hash = get_password_hash(payload.new_password)
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        return current_user
    finally:
        session.close()


@app.get("/api/products", response_model=List[ProductRead])
def list_products(current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        products = session.query(Product).order_by(Product.created_at.desc()).all()
        return products
    finally:
        session.close()


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        list(product.images)
        return product
    finally:
        session.close()


@app.post("/api/products", response_model=ProductRead)
def create_product(payload: ProductCreate, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        product = Product(
            sku=payload.sku,
            manufacturer=payload.manufacturer,
            title=payload.title,
            search_mode=payload.search_mode,
            status="pending",
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        return product
    finally:
        session.close()


@app.post("/api/products/import", response_model=List[ProductRead])
def import_products(
    mode: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if mode not in {"google", "openai"}:
        raise HTTPException(status_code=400, detail="Unsupported search mode")
    content = file.file.read()
    try:
        df = pd.read_excel(BytesIO(content))
    except Exception as exc:  # pragma: no cover - Excel parsing errors
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {exc}")

    normalized_columns = {col.lower(): col for col in df.columns}
    sku_column = next((normalized_columns[col] for col in normalized_columns if col in {"sku", "артикул"}), None)
    manufacturer_column = next((normalized_columns[col] for col in normalized_columns if col in {"manufacturer", "производитель"}), None)
    if not sku_column or not manufacturer_column:
        raise HTTPException(status_code=400, detail="Excel file must contain sku and manufacturer columns")

    session = SessionLocal()
    created_products: List[Product] = []
    try:
        for _, row in df.iterrows():
            sku = str(row[sku_column]).strip()
            manufacturer = str(row[manufacturer_column]).strip()
            if not sku or sku.lower() == "nan" or not manufacturer or manufacturer.lower() == "nan":
                continue
            product = Product(
                sku=sku,
                manufacturer=manufacturer,
                search_mode=mode,
                status="pending",
            )
            session.add(product)
            created_products.append(product)
        session.commit()
        for product in created_products:
            session.refresh(product)
        return created_products
    finally:
        session.close()


def _apply_results(session: Session, product: Product, provider: str, results: List[dict]):
    session.query(ImageResult).filter(ImageResult.product_id == product.id).delete()
    for item in results:
        image = ImageResult(
            product_id=product.id,
            provider=provider,
            image_url=item.get("image_url"),
            thumbnail_url=item.get("thumbnail_url"),
            is_selected=False,
        )
        session.add(image)
    product.status = "completed"
    product.search_mode = provider
    session.add(product)
    session.commit()


@app.post("/api/products/{product_id}/search", response_model=ProductDetail)
def search_product(product_id: int, payload: SearchRequest, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product.status = "searching"
        session.add(product)
        session.commit()
        try:
            if payload.mode == "google":
                results = search_with_google(session, product, payload.query_override)
            elif payload.mode == "openai":
                results = search_with_openai(session, product, payload.query_override)
            else:
                raise HTTPException(status_code=400, detail="Unknown search mode")
        except SearchError as exc:
            product.status = "failed"
            session.add(product)
            session.commit()
            raise HTTPException(status_code=502, detail=str(exc))

        _apply_results(session, product, payload.mode, results)
        session.refresh(product)
        list(product.images)
        return product
    finally:
        session.close()


@app.post("/api/products/batch-search", response_model=List[ProductDetail])
def batch_search(payload: BatchSearchRequest, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    updated_products: List[Product] = []
    try:
        for product_id in payload.product_ids:
            product = session.query(Product).filter(Product.id == product_id).first()
            if not product:
                continue
            product.status = "searching"
            session.add(product)
            session.commit()
            try:
                if payload.mode == "google":
                    results = search_with_google(session, product, payload.query_override)
                elif payload.mode == "openai":
                    results = search_with_openai(session, product, payload.query_override)
                else:
                    raise HTTPException(status_code=400, detail="Unknown search mode")
            except SearchError:
                product.status = "failed"
                session.add(product)
                session.commit()
                continue
            _apply_results(session, product, payload.mode, results)
            session.refresh(product)
            list(product.images)
            updated_products.append(product)
        return updated_products
    finally:
        session.close()


@app.post("/api/products/{product_id}/select-image", response_model=ProductDetail)
def select_image(product_id: int, payload: SelectImageRequest, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        image = session.query(ImageResult).filter(ImageResult.id == payload.image_id, ImageResult.product_id == product_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")
        session.query(ImageResult).filter(ImageResult.product_id == product_id).update({"is_selected": False})
        image.is_selected = True
        session.add(image)
        session.commit()
        session.refresh(product)
        list(product.images)
        return product
    finally:
        session.close()


@app.get("/api/products/{product_id}/logs", response_model=List[LogEntry])
def get_logs(product_id: int, current_user: User = Depends(get_current_user)):
    session = SessionLocal()
    try:
        logs = (
            session.query(SearchLog)
            .filter(SearchLog.product_id == product_id)
            .order_by(SearchLog.created_at.desc())
            .all()
        )
        return logs
    finally:
        session.close()
