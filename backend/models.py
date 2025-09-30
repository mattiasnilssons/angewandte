# backend/models.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from .db import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())



class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id"), index=True)
    chunk_index = Column(Integer, index=True)
    text = Column(Text, nullable=False)
    page = Column(Integer, default=0)
    start_char = Column(Integer, default=0)
    end_char = Column(Integer, default=0)

    document = relationship("Document", back_populates="chunks")


class FaissMap(Base):
    __tablename__ = "faiss_map"
    vector_id = Column(Integer, primary_key=True, autoincrement=False)  # faiss id
    chunk_id = Column(String, ForeignKey("chunks.id"), index=True)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=gen_uuid)
    filename = Column(String, nullable=False)
    title = Column(String, nullable=True)
    author = Column(String, nullable=True)        # just a column
    year = Column(Integer, nullable=True)         # just a column
    meta_json = Column(Text, nullable=True)       # raw/extra metadata as JSON
    path = Column(String, nullable=False)
    pages = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # used to detect duplicates
    sha256 = Column(String, unique=True, index=True, nullable=True)

    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )

