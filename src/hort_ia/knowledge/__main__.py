"""Print the knowledge base completeness report: `python -m hortia.knowledge`."""

from .loader import completeness_report, load_knowledge_base

print(completeness_report(load_knowledge_base()))
