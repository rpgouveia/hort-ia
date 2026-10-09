"""Hort.IA agronomic knowledge base."""

from .loader import completeness_report, get_knowledge_base, load_knowledge_base
from .models import KnowledgeBase

__all__ = ["KnowledgeBase", "completeness_report", "get_knowledge_base", "load_knowledge_base"]
