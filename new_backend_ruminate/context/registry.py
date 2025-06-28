from typing import Dict
from new_backend_ruminate.context.protocols import Retriever, Renderer
from new_backend_ruminate.context.renderers.default import plain_renderer

retriever_registry: Dict[str, Retriever] = {}
renderer_registry:  Dict[str, Renderer]  = {}

def register_retriever(tag: str, retriever: Retriever) -> None:
    retriever_registry[tag] = retriever

def register_renderer(key: str, renderer: Renderer) -> None:
    renderer_registry[key] = renderer

def ensure_default(key: str) -> None:
    if key not in renderer_registry:
        renderer_registry[key] = plain_renderer
