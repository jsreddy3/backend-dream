from datetime import datetime
from uuid import uuid4, UUID as PYUUID
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column, DateTime, String, Text, Integer, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship
from new_backend_ruminate.infrastructure.db.meta import Base


class InterpretationQuestion(Base):
    __tablename__ = "interpretation_questions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dream_id = Column(UUID(as_uuid=True), ForeignKey("dreams.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_order = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    dream = relationship("Dream", back_populates="interpretation_questions")
    choices = relationship(
        "InterpretationChoice",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="InterpretationChoice.choice_order"
    )
    answers = relationship(
        "InterpretationAnswer",
        back_populates="question",
        cascade="all, delete-orphan"
    )


class InterpretationChoice(Base):
    __tablename__ = "interpretation_choices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("interpretation_questions.id", ondelete="CASCADE"), nullable=False)
    choice_text = Column(Text, nullable=False)
    choice_order = Column(Integer, nullable=False)
    is_custom = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    question = relationship("InterpretationQuestion", back_populates="choices")
    answers = relationship("InterpretationAnswer", back_populates="selected_choice")


class InterpretationAnswer(Base):
    __tablename__ = "interpretation_answers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("interpretation_questions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    selected_choice_id = Column(UUID(as_uuid=True), ForeignKey("interpretation_choices.id", ondelete="SET NULL"), nullable=True, index=True)
    custom_answer = Column(Text, nullable=True)
    answered_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    question = relationship("InterpretationQuestion", back_populates="answers")
    selected_choice = relationship("InterpretationChoice", back_populates="answers")
    user = relationship("User")