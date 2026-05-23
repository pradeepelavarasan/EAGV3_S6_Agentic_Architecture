import hashlib
import json
import os
from pathlib import Path
from schemas import Artifact

ARTIFACTS_DIR = Path("state/artifacts")

def init_artifacts_dir():
    """Ensure the artifacts directory exists."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def put(blob: bytes, content_type: str, source: str, descriptor: str) -> str:
    """
    Hashes the blob, saves raw bytes to state/artifacts/<hash>.bin and metadata to <hash>.json.
    Returns art:<hash>.
    """
    init_artifacts_dir()
    
    # Generate SHA-256 hash prefix (16 chars)
    sha256_hash = hashlib.sha256(blob).hexdigest()[:16]
    art_id = f"art:{sha256_hash}"
    
    # Save raw bytes
    bin_path = ARTIFACTS_DIR / f"{sha256_hash}.bin"
    bin_path.write_bytes(blob)
    
    # Create Artifact metadata
    artifact_meta = Artifact(
        id=art_id,
        content_type=content_type,
        size_bytes=len(blob),
        source=source,
        descriptor=descriptor
    )
    
    # Save metadata
    json_path = ARTIFACTS_DIR / f"{sha256_hash}.json"
    json_path.write_text(artifact_meta.model_dump_json(indent=2), encoding="utf-8")
    
    return art_id

def get_bytes(art_id: str) -> bytes:
    """
    Retrieves the raw bytes for a given artifact ID.
    """
    if not art_id.startswith("art:"):
        raise ValueError(f"Invalid artifact ID format: {art_id}")
    
    sha256_hash = art_id[4:]
    bin_path = ARTIFACTS_DIR / f"{sha256_hash}.bin"
    
    if not bin_path.exists():
        raise FileNotFoundError(f"Artifact bytes not found: {bin_path}")
        
    return bin_path.read_bytes()

def get_metadata(art_id: str) -> Artifact:
    """
    Retrieves the metadata for a given artifact ID.
    """
    if not art_id.startswith("art:"):
        raise ValueError(f"Invalid artifact ID format: {art_id}")
        
    sha256_hash = art_id[4:]
    json_path = ARTIFACTS_DIR / f"{sha256_hash}.json"
    
    if not json_path.exists():
        raise FileNotFoundError(f"Artifact metadata not found: {json_path}")
        
    return Artifact.model_validate_json(json_path.read_text(encoding="utf-8"))
