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

# Archetype definitions with academic backing
ARCHETYPES = {
    "analytical": {
        "keywords": ["organize", "process", "structure", "practical", "clear", "daily", "routine"],
        "symbol": "🧠",
        "name": "Analytical Dreamer",
        "researcher": "Dr. Ernest Hartmann",
        "theory": "Thick-Boundary Dreaming Theory",
        "description": "Your dreams quietly process and organize your daily experiences, reflecting your practical approach to life."
    },
    "reflective": {
        "keywords": ["emotion", "relationship", "family", "feeling", "water", "heart", "process"],
        "symbol": "🌊",
        "name": "Reflective Dreamer",
        "researcher": "Dr. Rosalind Cartwright",
        "theory": "Dreams as Emotional Adaptation",
        "description": "Your dreams help you process emotional experiences, manage relationships, and build psychological resilience."
    },
    "introspective": {
        "keywords": ["symbol", "insight", "vivid", "meaning", "mystery", "deep", "spiritual"],
        "symbol": "🔍",
        "name": "Introspective Dreamer",
        "researcher": "Dr. Michael Schredl",
        "theory": "Dream Recall and Personality Research",
        "description": "You regularly experience vivid, symbolic dreams, revealing deep insights into your inner life."
    },
    "lucid": {
        "keywords": ["control", "aware", "fly", "conscious", "lucid", "direct", "intention"],
        "symbol": "🌀",
        "name": "Lucid Dreamer",
        "researcher": "Dr. Stephen LaBerge",
        "theory": "Lucid Dreaming and Metacognition",
        "description": "Your vivid, sometimes controllable dreams indicate exceptional self-awareness, imagination, and curiosity."
    },
    "creative": {
        "keywords": ["imagine", "create", "art", "fantasy", "nature", "adventure", "inspire"],
        "symbol": "🎨",
        "name": "Creative Dreamer",
        "researcher": "Dr. Ernest Hartmann",
        "theory": "Thin-Boundary Dreaming Theory",
        "description": "Your dreams overflow with imaginative and symbolic content, providing a wellspring for creative thought."
    },
    "resolving": {
        "keywords": ["solve", "problem", "chase", "work", "recurring", "unresolved", "challenge"],
        "symbol": "⚙️",
        "name": "Resolving Dreamer",
        "researcher": "Dr. G. William Domhoff",
        "theory": "Dreams as Problem-solving Mechanisms",
        "description": "Your dreams frequently revisit unresolved issues, helping you rehearse possibilities and solve problems."
    }
}

# Migration mapping from old to new archetypes
ARCHETYPE_MIGRATION = {
    "starweaver": "introspective",
    "moonwalker": "lucid",
    "soulkeeper": "reflective",
    "timeseeker": "resolving",
    "shadowmender": "resolving",
    "lightbringer": "creative"
}


class ProfileService:
    """Service for managing user profiles and dream summaries."""
    
    # Expose migration mapping for API use
    ARCHETYPE_MIGRATION = ARCHETYPE_MIGRATION
    
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
        
        # If user has no dreams but has an archetype from onboarding, keep it
        if (not summary or summary.dream_count == 0) and profile.archetype:
            logger.info(f"User {user_id} has initial archetype '{profile.archetype}' from onboarding, keeping it")
            return profile
        
        if not summary or summary.dream_count == 0:
            logger.warning(f"No dreams found for user {user_id}")
            return profile
        
        # Calculate archetype based on dreams
        archetype, confidence = self._calculate_archetype(summary.theme_keywords)
        if archetype:
            # If this is the first real calculation (replacing onboarding archetype)
            # we might want to blend the confidence or notify the user
            metadata = {
                "keywords_analyzed": len(summary.theme_keywords),
                "dream_count": summary.dream_count
            }
            if profile.archetype and profile.archetype_metadata.get("source") == "onboarding":
                metadata["previous_source"] = "onboarding"
                metadata["previous_archetype"] = profile.archetype
            
            profile.update_archetype(
                archetype=archetype,
                confidence=confidence,
                metadata=metadata
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
    
    async def save_initial_archetype(
        self,
        user_id: UUID,
        archetype: str,
        confidence: float,
        session: AsyncSession
    ) -> UserProfile:
        """Save the initial archetype from onboarding."""
        # Get or create profile
        profile = await self._repo.get_or_create_user_profile(user_id, session)
        
        # Only update if no archetype exists (preserve existing archetypes)
        if not profile.archetype:
            profile.update_archetype(
                archetype=archetype,
                confidence=confidence,
                metadata={"source": "onboarding"}
            )
            profile.mark_calculated()
            
            # Save the profile
            profile = await self._repo.update_user_profile(profile, session)
            logger.info(f"Saved initial archetype '{archetype}' for user {user_id}")
        else:
            logger.info(f"User {user_id} already has archetype '{profile.archetype}', skipping update")
        
        return profile
    
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
        
        # Primary goal mapping (3 points)
        goal_archetypes = {
            "self_discovery": ["introspective", "analytical"],  # Split between practical and deep
            "creativity": ["creative", "introspective"],
            "problem_solving": ["resolving", "analytical"],
            "emotional_healing": ["reflective", "resolving"],
            "lucid_dreaming": ["lucid", "creative"]
        }
        
        # Initialize scores
        for archetype in ARCHETYPES:
            scores[archetype] = 0
        
        # Score based on primary goal (3 points)
        if preferences.primary_goal and preferences.primary_goal in goal_archetypes:
            for archetype in goal_archetypes[preferences.primary_goal]:
                scores[archetype] += 3
        
        # Score based on dream recall frequency (2 points)
        recall_mappings = {
            "never": ["analytical"],
            "rarely": ["analytical", "resolving"],
            "sometimes": ["reflective", "resolving"],
            "often": ["introspective", "creative", "lucid"],
            "always": ["introspective", "lucid"]
        }
        
        if preferences.dream_recall_frequency and preferences.dream_recall_frequency in recall_mappings:
            for archetype in recall_mappings[preferences.dream_recall_frequency]:
                scores[archetype] += 2
        
        # Score based on dream vividness (2 points)
        vividness_mappings = {
            "vague": ["analytical"],
            "moderate": ["reflective", "resolving", "analytical"],
            "vivid": ["introspective", "creative", "reflective"],
            "very_vivid": ["lucid", "creative", "introspective"]
        }
        
        if preferences.dream_vividness and preferences.dream_vividness in vividness_mappings:
            for archetype in vividness_mappings[preferences.dream_vividness]:
                scores[archetype] += 2
        
        # Score based on dream themes (1 point each, max 3 counted)
        if preferences.common_dream_themes:
            theme_mappings = {
                "flying": ["lucid", "creative"],
                "falling": ["resolving"],
                "being_chased": ["resolving"],
                "water": ["reflective", "introspective"],
                "animals": ["creative", "reflective"],
                "family": ["reflective"],
                "work": ["analytical", "resolving"],
                "school": ["analytical", "resolving"],
                "death": ["introspective", "resolving"],
                "food": ["analytical"],
                "vehicles": ["analytical"],
                "buildings": ["analytical"],
                "nature": ["creative", "introspective"],
                "supernatural": ["introspective", "creative"],
                "adventure": ["creative", "lucid"],
                "romance": ["reflective"]
            }
            
            theme_count = 0
            for theme in preferences.common_dream_themes[:3]:  # Max 3 themes
                theme_lower = theme.lower()
                if theme_lower in theme_mappings:
                    for archetype in theme_mappings[theme_lower]:
                        scores[archetype] += 1
                    theme_count += 1
        
        # Score based on interests (1 point each, max 2 counted)
        if preferences.interests:
            interest_mappings = {
                "lucid_dreaming": ["lucid"],
                "symbolism": ["introspective", "creative"],
                "emotional_processing": ["reflective"],
                "creativity": ["creative"],
                "problem_solving": ["resolving", "analytical"],
                "spiritual_growth": ["introspective"],
                "memory_enhancement": ["analytical"],
                "nightmare_resolution": ["resolving"],
                "prophetic_dreams": ["introspective"]
            }
            
            interest_count = 0
            for interest in preferences.interests[:2]:  # Max 2 interests
                if interest in interest_mappings:
                    for archetype in interest_mappings[interest]:
                        scores[archetype] += 1
                    interest_count += 1
        
        # Find best match
        if not any(scores.values()):
            return "analytical", 0.80  # Default with base confidence
        
        # If tied, use priority order
        max_score = max(scores.values())
        tied_archetypes = [arch for arch, score in scores.items() if score == max_score]
        
        if len(tied_archetypes) > 1:
            # Priority order: introspective > creative > reflective > lucid > resolving > analytical
            priority = ["introspective", "creative", "reflective", "lucid", "resolving", "analytical"]
            for arch in priority:
                if arch in tied_archetypes:
                    best_archetype = arch
                    break
        else:
            best_archetype = max(scores, key=scores.get)
        
        best_score = scores[best_archetype]
        
        # Calculate confidence (normalize to 0.80-0.95 range)
        max_possible_score = 12  # 3 (goal) + 2 (recall) + 2 (vividness) + 3 (themes) + 2 (interests)
        raw_confidence = min(best_score / max_possible_score, 1.0)
        # Map raw score (0-1) to confidence range (0.80-0.95)
        confidence = 0.80 + (raw_confidence * 0.15)
        
        return best_archetype, confidence