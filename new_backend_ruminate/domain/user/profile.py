"""User profile domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from uuid import UUID


@dataclass
class DreamSummary:
    """Incremental summary statistics for a user's dreams."""
    id: UUID
    user_id: UUID
    dream_count: int = 0
    total_duration_seconds: int = 0
    last_dream_date: Optional[date] = None
    dream_streak_days: int = 0
    theme_keywords: Dict[str, int] = field(default_factory=dict)  # keyword -> count
    emotion_counts: Dict[str, int] = field(default_factory=dict)  # emotion -> count
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def increment_dream_count(self) -> None:
        """Increment the dream count."""
        self.dream_count += 1
        self.updated_at = datetime.utcnow()

    def add_duration(self, seconds: int) -> None:
        """Add duration in seconds."""
        self.total_duration_seconds += seconds
        self.updated_at = datetime.utcnow()

    def update_last_dream_date(self, dream_date: date) -> None:
        """Update the last dream date and calculate streak."""
        if self.last_dream_date:
            days_diff = (dream_date - self.last_dream_date).days
            if days_diff == 1:
                self.dream_streak_days += 1
            elif days_diff > 1:
                self.dream_streak_days = 1
        else:
            self.dream_streak_days = 1
        
        self.last_dream_date = dream_date
        self.updated_at = datetime.utcnow()

    def add_theme_keywords(self, keywords: List[str]) -> None:
        """Add theme keywords to the count."""
        for keyword in keywords:
            normalized = keyword.lower().strip()
            self.theme_keywords[normalized] = self.theme_keywords.get(normalized, 0) + 1
        self.updated_at = datetime.utcnow()

    def add_emotion_counts(self, emotions: Dict[str, int]) -> None:
        """Add emotion counts."""
        for emotion, count in emotions.items():
            self.emotion_counts[emotion] = self.emotion_counts.get(emotion, 0) + count
        self.updated_at = datetime.utcnow()


@dataclass
class DreamTheme:
    """Represents a dream theme with percentage."""
    name: str
    percentage: int


@dataclass
class EmotionalMetric:
    """Represents an emotional metric."""
    name: str
    intensity: float  # 0.0 to 1.0
    color: str  # Hex color


@dataclass
class UserProfile:
    """User's dream profile with calculated insights."""
    id: UUID
    user_id: UUID
    archetype: Optional[str] = None
    archetype_confidence: Optional[float] = None  # 0.0 to 1.0
    archetype_metadata: Dict[str, Any] = field(default_factory=dict)
    emotional_landscape: List[EmotionalMetric] = field(default_factory=list)
    top_themes: List[DreamTheme] = field(default_factory=list)
    recent_symbols: List[str] = field(default_factory=list)
    calculation_version: int = 1
    last_calculated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def update_archetype(self, archetype: str, confidence: float, metadata: Dict[str, Any] = None) -> None:
        """Update the archetype with confidence score."""
        self.archetype = archetype
        self.archetype_confidence = confidence
        if metadata:
            self.archetype_metadata = metadata
        self.updated_at = datetime.utcnow()

    def set_emotional_landscape(self, metrics: List[EmotionalMetric]) -> None:
        """Set the emotional landscape."""
        self.emotional_landscape = metrics
        self.updated_at = datetime.utcnow()

    def set_top_themes(self, themes: List[DreamTheme]) -> None:
        """Set the top themes."""
        self.top_themes = themes
        self.updated_at = datetime.utcnow()

    def set_recent_symbols(self, symbols: List[str]) -> None:
        """Set recent symbols."""
        self.recent_symbols = symbols[:10]  # Limit to 10 symbols
        self.updated_at = datetime.utcnow()

    def mark_calculated(self) -> None:
        """Mark the profile as calculated."""
        self.last_calculated_at = datetime.utcnow()
        self.updated_at = self.last_calculated_at