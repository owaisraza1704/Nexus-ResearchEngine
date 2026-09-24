from app.retrieval.vector_search import RetrievedChunk


def citation_display(source_name: str, chunk: RetrievedChunk) -> str:
    """Display Docling's existing provenance without inventing page or section numbers."""
    pages = sorted(
        {
            provenance["page_no"]
            for item in chunk.locator.get("doc_items", [])
            for provenance in item.get("prov", [])
            if provenance.get("page_no") is not None
        }
    )
    if pages:
        return f"{source_name}, page(s) {', '.join(str(page) for page in pages)}"
    headings = chunk.locator.get("headings", [])
    if headings:
        return f"{source_name}, {' > '.join(headings)}, chunk {chunk.sequence + 1}"
    return f"{source_name}, chunk {chunk.sequence + 1}"
