from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(120), nullable=False, index=True)
    manufacturer = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    search_mode = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)

    images = relationship("ImageResult", back_populates="product", cascade="all, delete-orphan")
    logs = relationship("SearchLog", back_populates="product", cascade="all, delete-orphan")


class ImageResult(Base, TimestampMixin):
    __tablename__ = "image_results"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    is_selected = Column(Boolean, default=False)

    product = relationship("Product", back_populates="images")


class SearchLog(Base, TimestampMixin):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    provider = Column(String(50), nullable=False)
    request_payload = Column(Text, nullable=True)
    response_payload = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    product = relationship("Product", back_populates="logs")
