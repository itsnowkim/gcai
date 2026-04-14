from pydantic import BaseModel


class InitialIndexResult(BaseModel):
    repo_path: str
    scanned_files: int
    skipped_files: int
    upserted_nodes: int
    upserted_edges: int
    upserted_documents: int
