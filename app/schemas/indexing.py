from pydantic import BaseModel


class InitialIndexVerificationResult(BaseModel):
    verified_nodes: int
    verified_edges: int
    verified_documents: int


class InitialIndexResult(BaseModel):
    repo_path: str
    scanned_files: int
    skipped_files: int
    upserted_nodes: int
    upserted_edges: int
    upserted_documents: int
    verified_nodes: int
    verified_edges: int
    verified_documents: int
