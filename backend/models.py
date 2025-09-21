import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from .db import Base

def gen_uuid():
    return str(uuid.uuid4())

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=gen_uuid)
    filename = Column(String, nullable=False, unique=True)  # <— unique
    title = Column(String, nullable=True)
    path = Column(String, nullable=False)
    pages = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id"), index=True, nullable=False)
    chunk_index = Column(Integer, index=True)
    text = Column(Text, nullable=False)
    page = Column(Integer, default=0, nullable=False)
    start_char = Column(Integer, default=0, nullable=False)
    end_char = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        # prevents the same page region/text being stored twice for the same doc
        UniqueConstraint("document_id", "page", "start_char", "end_char", "text", name="uq_chunk_pos_text"),
    )

    document = relationship("Document", back_populates="chunks")

class FaissMap(Base):
    __tablename__ = "faiss_map"
    vector_id = Column(Integer, primary_key=True, autoincrement=False)  # faiss vector id
    chunk_id = Column(String, ForeignKey("chunks.id"), index=True, unique=True)  # <— unique
