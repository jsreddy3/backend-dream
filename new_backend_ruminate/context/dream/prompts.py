"""Dream analysis prompt templates."""

from typing import Dict, Any
from dataclasses import dataclass, field


@dataclass
class DreamPrompts:
    """Centralized prompt management for dream analysis."""
    
    # System prompts for different tasks
    TITLE_SUMMARY_SYSTEM = """You are an intelligent, empathetic conversationalist who enjoys discussing dreams with people. Your job is to take the somewhat distended, self-referential, confusing ; sometimes incredibly short ; sometimes incredibly long dreams ; sometimes surprisingly clear dreams — and generate a comprehensive version of the dream that removes transcription artifacts, the users' back and forth telling, and other artifacts. NEVER fill in the blanks. NEVER get rid of or add events that don't happen. If it's a long dream, your version can be long—if it's short, it can be short. Your job is to simply make it reasonably clear. Include meaningful snippets of emotional retelling if they have already been provided, but do not exaggerate or truncate them... in fact, for emotions, get as close to the user's description as possible. Since your version is as close to the users' version as possible, it should be told how they told it 'I saw this...' etc"""
    
    ANALYSIS_SYSTEM = """You are an expert dream analyst who provides concise, insightful interpretations. Keep your analysis focused and under 100 words."""
    
    EXPANDED_ANALYSIS_SYSTEM = """You are an expert dream analyst. You've already provided an initial interpretation. Now expand on it with deeper insights, exploring more symbolic meanings, psychological connections, and personal relevance. Format your response with clear sections."""
    
    QUESTIONS_SYSTEM = """You are a dream interpretation assistant that helps users gain deeper insights into their dreams. Your task is to generate thoughtful questions about specific elements of the dream that are necessary to understand the dream."""
    
    # User prompt templates
    TITLE_SUMMARY_USER = """Based on this dream transcript, create a short title and a clear summary. 

Dream transcript:
{transcript}

Return a JSON object with 'title' and 'summary' fields."""
    
    ANALYSIS_USER = """Please provide a brief but insightful analysis of this dream:

{context}

Provide a focused interpretation in 100 words or less. Focus on the most significant symbols and meanings."""
    
    EXPANDED_ANALYSIS_USER = """Here is the dream and your initial analysis:

DREAM CONTEXT:
{context}

YOUR INITIAL ANALYSIS:
{existing_analysis}

Provide an expanded analysis (150-200 words total) with these sections:

## Symbolic Meanings
Key symbols and their deeper significance

## Psychological Patterns
Connections to emotional states or life themes

## Personal Relevance
How this might relate to current life experiences

Keep each section concise (2-3 sentences). Focus on new insights not covered in the initial analysis."""
    
    QUESTIONS_USER = """Based on this dream, generate {num_questions} insightful questions to help the dreamer explore its meaning.

Dream transcript:
{transcript}

For each question, also provide {num_choices} possible answer options that you think the dreamer is likely to choose.

Return a JSON array with this structure:
[
  {{
    "question": "The question text",
    "choices": ["First choice", "Second choice", "Third choice"]
  }},
  ...
]"""
    
    # Context section templates
    DREAM_TITLE_SECTION = "Dream Title: {title}"
    TRANSCRIPT_SECTION = "Original Dream Transcript:\n{transcript}"
    SUMMARY_SECTION = "Summary:\n{summary}"
    ADDITIONAL_INFO_SECTION = "Additional Context:\n{additional_info}"
    ANSWERS_SECTION = "Interpretation Answers:\n{answers}"
    
    @classmethod
    def build_context(cls, components: Dict[str, Any]) -> str:
        """Build a formatted context string from components."""
        sections = []
        
        if components.get("title"):
            sections.append(cls.DREAM_TITLE_SECTION.format(title=components["title"]))
        
        if components.get("transcript"):
            sections.append(cls.TRANSCRIPT_SECTION.format(transcript=components["transcript"]))
            
        if components.get("summary"):
            sections.append(cls.SUMMARY_SECTION.format(summary=components["summary"]))
            
        if components.get("additional_info"):
            sections.append(cls.ADDITIONAL_INFO_SECTION.format(additional_info=components["additional_info"]))
            
        if components.get("answers"):
            sections.append(cls.ANSWERS_SECTION.format(answers=components["answers"]))
            
        return "\n\n".join(sections)