"""Profile service for managing user profiles and dream summaries."""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date
import re

from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.user.profile_repo import ProfileRepository
from new_backend_ruminate.domain.user.profile import DreamSummary, UserProfile, EmotionalMetric, DreamTheme
from new_backend_ruminate.domain.user.preferences import UserPreferences
from new_backend_ruminate.domain.dream.entities.dream import Dream
from new_backend_ruminate.domain.dream.entities.segments import Segment
from new_backend_ruminate.domain.ports.llm import LLMService

logger = logging.getLogger(__name__)

# Archetype definitions
ARCHETYPES = {
    "starweaver": {
        "keywords": ["symbol", "pattern", "weave", "cosmic", "ancient", "wisdom"],
        "symbol": "🌟",
        "colors": ["5B2C6F", "FFD700"]
    },
    "moonwalker": {
        "keywords": ["fly", "travel", "journey", "path", "adventure", "explore"],
        "symbol": "🌙",
        "colors": ["C0C0C0", "191970"]
    },
    "soulkeeper": {
        "keywords": ["feel", "emotion", "heart", "soul", "deep", "love"],
        "symbol": "💫",
        "colors": ["008B8B", "FFB6C1"]
    },
    "timeseeker": {
        "keywords": ["past", "memory", "future", "time", "remember", "tomorrow"],
        "symbol": "⏳",
        "colors": ["FFBF00", "CD7F32"]
    },
    "shadowmender": {
        "keywords": ["dark", "fear", "shadow", "night", "hidden", "transform"],
        "symbol": "🌑",
        "colors": ["4B0082", "36454F"]
    },
    "lightbringer": {
        "keywords": ["light", "joy", "happy", "bright", "sun", "hope"],
        "symbol": "☀️",
        "colors": ["A8C3BC", "FFCCCB"]
    }
}


class ProfileService:
    """Service for managing user profiles and dream summaries."""
    
    def __init__(
        self,
        profile_repo: ProfileRepository,
        analysis_llm: Optional[LLMService] = None,
    ):
        self._repo = profile_repo
        self._llm = analysis_llm
    
    # ─────────────────── Dream Summary Methods ─────────────────────
    
    async def update_dream_summary_on_completion(
        self,
        user_id: UUID,
        dream: Dream,
        session: AsyncSession
    ) -> DreamSummary:
        """Update dream summary when a dream is completed."""
        summary = await self._repo.get_or_create_dream_summary(user_id, session)
        
        # Increment dream count
        summary.increment_dream_count()
        
        # Calculate and add duration
        total_duration = sum(s.duration or 0 for s in dream.segments if s.duration)
        if total_duration > 0:
            summary.add_duration(int(total_duration))
        
        # Update last dream date
        summary.update_last_dream_date(dream.created_at.date())
        
        # Extract and add theme keywords
        if dream.title or dream.summary:
            keywords = self._extract_keywords(f"{dream.title or ''} {dream.summary or ''}")
            summary.add_theme_keywords(keywords)
        
        # Save updated summary
        return await self._repo.update_dream_summary(summary, session)
    
    async def get_dream_summary(self, user_id: UUID, session: AsyncSession) -> Optional[DreamSummary]:
        """Get dream summary for a user."""
        return await self._repo.get_dream_summary(user_id, session)
    
    # ─────────────────── User Profile Methods ─────────────────────
    
    async def get_user_profile(self, user_id: UUID, session: AsyncSession) -> Optional[UserProfile]:
        """Get user profile, creating if needed."""
        profile = await self._repo.get_user_profile(user_id, session)
        if not profile:
            # Get summary to check if we have data to calculate from
            summary = await self._repo.get_dream_summary(user_id, session)
            if summary and summary.dream_count > 0:
                # Create and calculate profile
                profile = await self._repo.get_or_create_user_profile(user_id, session)
                await self.calculate_profile(user_id, session)
                profile = await self._repo.get_user_profile(user_id, session)
        
        return profile
    
    async def calculate_profile(
        self,
        user_id: UUID,
        session: AsyncSession,
        force: bool = False
    ) -> UserProfile:
        """Calculate or recalculate user profile based on dream summary."""
        profile = await self._repo.get_or_create_user_profile(user_id, session)
        
        # Check if recalculation is needed
        if not force and profile.last_calculated_at:
            # Only recalculate if it's been more than 24 hours
            from datetime import timezone
            hours_since = (datetime.now(timezone.utc) - profile.last_calculated_at).total_seconds() / 3600
            if hours_since < 24:
                logger.info(f"Profile for user {user_id} is fresh (calculated {hours_since:.1f} hours ago)")
                return profile
        
        logger.info(f"Calculating profile for user {user_id}")
        
        # Get dream summary
        summary = await self._repo.get_dream_summary(user_id, session)
        if not summary or summary.dream_count == 0:
            logger.warning(f"No dreams found for user {user_id}")
            return profile
        
        # Calculate archetype
        archetype, confidence = self._calculate_archetype(summary.theme_keywords)
        if archetype:
            profile.update_archetype(
                archetype=archetype,
                confidence=confidence,
                metadata={"keywords_analyzed": len(summary.theme_keywords)}
            )
        
        # Calculate emotional landscape
        emotional_metrics = self._calculate_emotional_landscape(summary.emotion_counts)
        profile.set_emotional_landscape(emotional_metrics)
        
        # Calculate top themes
        top_themes = self._calculate_top_themes(summary.theme_keywords)
        profile.set_top_themes(top_themes)
        
        # Generate recent symbols (placeholder - could be enhanced with AI)
        symbols = self._generate_symbols(archetype)
        profile.set_recent_symbols(symbols)
        
        # Mark as calculated
        profile.mark_calculated()
        
        # Save updated profile
        return await self._repo.update_user_profile(profile, session)
    
    # ─────────────────── Private Helper Methods ─────────────────────
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Convert to lowercase and split
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common words (simple stop words)
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'you', 'your', 'yours',
            'he', 'him', 'his', 'she', 'her', 'hers', 'it', 'its', 'they', 'them',
            'their', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
            'am', 'is', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had',
            'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but',
            'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for',
            'with', 'about', 'against', 'between', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in',
            'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
        }
        
        # Filter keywords
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        
        return keywords
    
    def _calculate_archetype(self, theme_keywords: Dict[str, int]) -> tuple[Optional[str], float]:
        """Calculate archetype based on theme keywords."""
        if not theme_keywords:
            return "starweaver", 0.85  # Default with good confidence
        
        # Calculate scores for each archetype
        archetype_scores = {}
        total_keywords = sum(theme_keywords.values())
        
        for archetype_name, archetype_data in ARCHETYPES.items():
            score = 0
            for keyword in archetype_data["keywords"]:
                # Check for exact match or substring
                for theme_keyword, count in theme_keywords.items():
                    if keyword in theme_keyword or theme_keyword in keyword:
                        score += count
            
            archetype_scores[archetype_name] = score
        
        # Find the best matching archetype
        if not any(archetype_scores.values()):
            return "starweaver", 0.85  # Default with good confidence
        
        best_archetype = max(archetype_scores, key=archetype_scores.get)
        best_score = archetype_scores[best_archetype]
        
        # Calculate confidence (ratio of matching keywords to total)
        # Map the raw score (0-1) to our desired range (0.80-0.95)
        raw_confidence = min(best_score / (total_keywords * 0.1), 1.0)
        confidence = 0.80 + (raw_confidence * 0.15)  # Maps 0->0.80, 1->0.95
        
        return best_archetype, confidence
    
    def _calculate_emotional_landscape(self, emotion_counts: Dict[str, int]) -> List[EmotionalMetric]:
        """Calculate emotional landscape from emotion counts."""
        # Default emotions if none tracked
        if not emotion_counts:
            return [
                EmotionalMetric(name="Joy", intensity=0.7, color="FFD700"),
                EmotionalMetric(name="Wonder", intensity=0.5, color="87CEEB"),
                EmotionalMetric(name="Peace", intensity=0.3, color="98FB98")
            ]
        
        # Normalize emotion counts to intensities (0-1)
        total = sum(emotion_counts.values())
        metrics = []
        
        # Color mapping for common emotions
        emotion_colors = {
            "joy": "FFD700",
            "wonder": "87CEEB",
            "peace": "98FB98",
            "fear": "8B4513",
            "sadness": "4682B4",
            "anger": "DC143C",
            "love": "FF69B4",
            "excitement": "FF6347"
        }
        
        for emotion, count in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            intensity = count / total
            color = emotion_colors.get(emotion.lower(), "808080")  # Default gray
            
            metrics.append(EmotionalMetric(
                name=emotion.capitalize(),
                intensity=intensity,
                color=color
            ))
        
        return metrics
    
    def _calculate_top_themes(self, theme_keywords: Dict[str, int]) -> List[DreamTheme]:
        """Calculate top themes from keywords."""
        if not theme_keywords:
            return []
        
        # Group related keywords into themes
        theme_groups = {
            "Adventure": ["journey", "travel", "explore", "adventure", "discover", "quest"],
            "Family": ["family", "mother", "father", "sister", "brother", "child", "parent"],
            "Mystery": ["unknown", "hidden", "secret", "mystery", "puzzle", "strange"],
            "Nature": ["water", "ocean", "forest", "mountain", "tree", "animal", "earth"],
            "Flying": ["fly", "flying", "float", "soar", "wing", "air", "sky"],
            "Work": ["work", "job", "office", "boss", "colleague", "meeting", "project"],
            "School": ["school", "class", "teacher", "student", "exam", "test", "study"],
            "Home": ["home", "house", "room", "door", "window", "bed", "kitchen"]
        }
        
        # Calculate theme scores
        theme_scores = {}
        total_score = 0
        
        for theme_name, theme_words in theme_groups.items():
            score = 0
            for keyword, count in theme_keywords.items():
                for theme_word in theme_words:
                    if theme_word in keyword or keyword in theme_word:
                        score += count
                        break
            
            if score > 0:
                theme_scores[theme_name] = score
                total_score += score
        
        # Convert to percentages
        themes = []
        for theme_name, score in sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)[:3]:
            percentage = int((score / total_score) * 100) if total_score > 0 else 0
            themes.append(DreamTheme(name=theme_name, percentage=percentage))
        
        return themes
    
    def _generate_symbols(self, archetype: Optional[str]) -> List[str]:
        """Generate symbols based on archetype."""
        # Base symbols pool
        base_symbols = ["🌊", "💎", "🦋", "🌙", "⭐", "🔥", "🌺", "🦅", "🗝️", "🌈",
                       "🌸", "🦁", "🌿", "⚡", "🦉", "🏔️", "🌅", "🌌", "🦚", "🔮"]
        
        # Archetype-specific symbols
        archetype_symbols = {
            "starweaver": ["🌟", "✨", "🌠", "🪐", "🌌"],
            "moonwalker": ["🌙", "🚀", "🗺️", "🧭", "🌍"],
            "soulkeeper": ["💫", "💖", "🫂", "💭", "🎭"],
            "timeseeker": ["⏳", "⏰", "📅", "🔄", "⌛"],
            "shadowmender": ["🌑", "🌘", "🕯️", "🦇", "🌚"],
            "lightbringer": ["☀️", "💡", "🌞", "🌻", "🌤️"]
        }
        
        # Get archetype-specific symbols if available
        if archetype and archetype in archetype_symbols:
            specific = archetype_symbols[archetype]
            # Mix specific and random base symbols
            import random
            symbols = specific[:2] + random.sample(base_symbols, 3)
            return symbols[:5]
        
        # Return random symbols if no archetype
        import random
        return random.sample(base_symbols, 5)
    
    # ─────────────────── User Preferences Methods ─────────────────────
    
    async def get_user_preferences(self, user_id: UUID, session: AsyncSession) -> Optional[UserPreferences]:
        """Get user preferences."""
        return await self._repo.get_user_preferences(user_id, session)
    
    async def create_user_preferences(
        self,
        user_id: UUID,
        preferences_data: dict,
        session: AsyncSession
    ) -> UserPreferences:
        """Create user preferences from data dict."""
        from uuid import uuid4
        
        # Create preferences object with explicit defaults
        preferences = UserPreferences(
            id=uuid4(),
            user_id=user_id,
            common_dream_themes=preferences_data.get('common_dream_themes', []),
            interests=preferences_data.get('interests', []),
            reminder_enabled=preferences_data.get('reminder_enabled', True),
            reminder_frequency=preferences_data.get('reminder_frequency', 'daily'),
            reminder_days=preferences_data.get('reminder_days', []),
            personality_traits=preferences_data.get('personality_traits', {}),
            onboarding_completed=preferences_data.get('onboarding_completed', False),
            **{k: v for k, v in preferences_data.items() if k not in ['common_dream_themes', 'interests', 'reminder_enabled', 'reminder_frequency', 'reminder_days', 'personality_traits', 'onboarding_completed']}
        )
        return await self._repo.create_user_preferences(preferences, session)
    
    async def update_user_preferences(
        self,
        user_id: UUID,
        preferences_data: dict,
        session: AsyncSession
    ) -> Optional[UserPreferences]:
        """Update user preferences with partial data."""
        # Get existing preferences
        preferences = await self._repo.get_user_preferences(user_id, session)
        if not preferences:
            # Create new if doesn't exist
            return await self.create_user_preferences(user_id, preferences_data, session)
        
        # Update only provided fields
        for key, value in preferences_data.items():
            if hasattr(preferences, key) and value is not None:
                setattr(preferences, key, value)
        
        # Update timestamp
        from datetime import timezone
        preferences.updated_at = datetime.now(timezone.utc)
        
        return await self._repo.update_user_preferences(preferences, session)
    
    async def suggest_initial_archetype(self, preferences: UserPreferences) -> tuple[str, float]:
        """Suggest archetype based on onboarding preferences."""
        # Score each archetype based on preferences
        scores = {}
        
        # Primary goal mapping
        goal_archetypes = {
            "self_discovery": ["starweaver", "timeseeker"],
            "creativity": ["starweaver", "moonwalker"],
            "problem_solving": ["timeseeker", "moonwalker"],
            "emotional_healing": ["soulkeeper", "shadowmender"],
            "lucid_dreaming": ["moonwalker", "lightbringer"]
        }
        
        # Initialize scores
        for archetype in ARCHETYPES:
            scores[archetype] = 0
        
        # Score based on primary goal
        if preferences.primary_goal and preferences.primary_goal in goal_archetypes:
            for archetype in goal_archetypes[preferences.primary_goal]:
                scores[archetype] += 3
        
        # Score based on dream themes
        if preferences.common_dream_themes:
            theme_mappings = {
                "flying": ["moonwalker", "lightbringer"],
                "water": ["soulkeeper", "timeseeker"],
                "darkness": ["shadowmender"],
                "light": ["lightbringer", "starweaver"],
                "family": ["soulkeeper"],
                "mystery": ["timeseeker", "shadowmender"],
                "adventure": ["moonwalker"],
                "emotions": ["soulkeeper", "shadowmender"]
            }
            
            for theme in preferences.common_dream_themes:
                theme_lower = theme.lower()
                for mapped_theme, archetypes in theme_mappings.items():
                    if mapped_theme in theme_lower:
                        for archetype in archetypes:
                            scores[archetype] += 1
        
        # Score based on dream recall and vividness
        if preferences.dream_recall_frequency in ["often", "always"]:
            scores["starweaver"] += 1
        elif preferences.dream_recall_frequency in ["never", "rarely"]:
            scores["shadowmender"] += 1
        
        if preferences.dream_vividness in ["vivid", "very_vivid"]:
            scores["lightbringer"] += 1
            scores["moonwalker"] += 1
        
        # Find best match
        if not any(scores.values()):
            return "starweaver", 0.85  # Default with good confidence
        
        best_archetype = max(scores, key=scores.get)
        best_score = scores[best_archetype]
        
        # Calculate confidence (normalize to 0.80-0.95 range)
        max_possible_score = 10  # Adjust based on scoring logic
        raw_confidence = min(best_score / max_possible_score, 1.0)
        # Map raw score (0-1) to confidence range (0.80-0.95)
        confidence = 0.80 + (raw_confidence * 0.15)
        
        return best_archetype, confidence