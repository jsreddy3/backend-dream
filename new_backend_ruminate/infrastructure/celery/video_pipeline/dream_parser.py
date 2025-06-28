import json
from typing import Tuple
from openai import AsyncOpenAI

from .config import CONFIG, OPENAI_API_KEY
from .models import ScenesData, Scene

SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "dream_summary": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_id": {"type": "integer"},
                    "summary": {"type": "string"},
                    "visual_prompt": {"type": "string"},
                    "voiceover_script": {"type": "string"},
                    "duration_sec": {"type": "integer"}
                },
                "required": ["scene_id", "summary", "visual_prompt", "voiceover_script", "duration_sec"],
                "additionalProperties": False
            },
            "minItems": 3,
            "maxItems": 6
        }
    },
    "required": ["dream_summary", "scenes"],
    "additionalProperties": False
}

async def parse_dream(dream_text: str) -> Tuple[ScenesData, float]:
    config = CONFIG["pipeline"]["scene_parsing"]
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""Convert this dream description into {config['min_scenes']}-{config['max_scenes']} distinct visual scenes for a video.
Each scene should have:
- A unique scene_id (starting from 1)
- A brief summary
- A detailed visual_prompt for image generation (focus on visual elements, colors, composition)
- A voiceover_script that narrates this part of the dream
- Duration in seconds (typically {config['scene_duration_seconds']} seconds)

IMPORTANT: The voiceover scripts should flow together as a cohesive narrative that tells the progression of the dream smoothly. They should capture what it felt like to experience the dream, creating a continuous story rather than disjointed descriptions. Keep the voiceover concise but evocative.

Also provide a brief dream_summary (1-2 sentences) that captures the essence of the entire dream.

Dream description:
{dream_text}"""
    
    response = await client.chat.completions.create(
        model=config["model"],
        response_format={"type": "json_schema", "json_schema": {"name": "scenes", "schema": SCENE_SCHEMA}},
        messages=[
            {"role": "system", "content": "You are a storyboard artist creating visual scenes from dream descriptions."},
            {"role": "user", "content": prompt}
        ]
    )
    
    # Calculate cost based on model
    if config["model"] == "gpt-4o-mini":
        cost = (response.usage.prompt_tokens * 0.15 + response.usage.completion_tokens * 0.60) / 1_000_000
    else:
        cost = (response.usage.prompt_tokens * 5.00 + response.usage.completion_tokens * 15.00) / 1_000_000
    
    result = json.loads(response.choices[0].message.content)
    
    scenes_data = ScenesData(
        dream_summary=result["dream_summary"],
        scenes=[Scene(**scene) for scene in result["scenes"]],
        total_duration_sec=sum(scene["duration_sec"] for scene in result["scenes"])
    )
    
    return scenes_data, cost