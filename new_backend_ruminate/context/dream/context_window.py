"""Dream context window data structure."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class DreamContextWindow:
    """Container for all dream context components."""
    
    # Core dream data
    dream_id: str
    user_id: str
    transcript: str
    
    # Optional metadata
    title: Optional[str] = None
    summary: Optional[str] = None
    additional_info: Optional[str] = None
    created_at: Optional[datetime] = None
    
    # Analysis components
    existing_analysis: Optional[str] = None
    existing_analysis_metadata: Optional[Dict[str, Any]] = None
    
    # Interpretation data
    interpretation_answers: Optional[List[Dict[str, Any]]] = None
    
    # Generation task info
    task_type: str = "analysis"  # "title_summary", "analysis", "expanded_analysis", "questions"
    
    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_llm_messages(self, system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
        """Convert context window to LLM-ready messages."""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def get_context_components(self) -> Dict[str, Any]:
        """Get all non-null context components for building prompts."""
        components = {
            "transcript": self.transcript,
            "title": self.title or "Untitled",
        }
        
        if self.summary:
            components["summary"] = self.summary
            
        if self.additional_info:
            components["additional_info"] = self.additional_info
            
        if self.interpretation_answers:
            # Format interpretation answers
            formatted_answers = []
            for answer in self.interpretation_answers:
                q_text = answer.get("question_text", "")
                a_text = answer.get("answer_text", answer.get("custom_answer", ""))
                if q_text and a_text:
                    formatted_answers.append(f"Q: {q_text}\nA: {a_text}")
            if formatted_answers:
                components["answers"] = "\n\n".join(formatted_answers)
                
        if self.existing_analysis and self.task_type == "expanded_analysis":
            components["existing_analysis"] = self.existing_analysis
            
        return components
    
    def estimate_tokens(self) -> int:
        """Rough estimate of token count for context management."""
        # Simple estimation: ~4 characters per token
        total_chars = len(self.transcript or "")
        total_chars += len(self.title or "")
        total_chars += len(self.summary or "")
        total_chars += len(self.additional_info or "")
        total_chars += len(self.existing_analysis or "")
        
        if self.interpretation_answers:
            for answer in self.interpretation_answers:
                total_chars += len(answer.get("question_text", ""))
                total_chars += len(answer.get("answer_text", ""))
                
        return total_chars // 4