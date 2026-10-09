"""Print the knowledge base completeness report: `python -m hort_ia.knowledge`."""

from .loader import completeness_report, load_knowledge_base

print(completeness_report(load_knowledge_base()))
