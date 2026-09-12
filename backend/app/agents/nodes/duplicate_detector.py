"""Duplicate Complaint Detection: generates sentence embeddings and finds similar committed complaints via pgvector."""
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Lazy-load the model to avoid slowing startup
_model = None


def _get_model():
    """Lazy-loads sentence-transformers model (downloads ~90MB on first call, cached thereafter)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("sentence-transformers model loaded: all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed; duplicate detection unavailable.")
    return _model


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generates a 384-dimensional embedding vector for the given text.
    Returns None if sentence-transformers is unavailable.
    """
    if not text or not text.strip():
        return None
    model = _get_model()
    if model is None:
        return None
    try:
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None


async def find_similar_complaints(
    db,
    embedding: List[float],
    exclude_id: Optional[str] = None,
    threshold: float = 0.82,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Performs pgvector cosine similarity search against committed complaints.

    Args:
        db: AsyncSession instance
        embedding: 384-dim query vector
        exclude_id: Complaint ID to exclude (the complaint being checked)
        threshold: Minimum cosine similarity (0-1). Default 0.82.
        limit: Maximum number of results to return

    Returns:
        List of dicts with complaint id, summary, category, severity, similarity score
    """
    try:
        from sqlalchemy import text as sql_text

        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

        query_str = """
            SELECT
                id,
                customer_name,
                product_name,
                batch_lot_number,
                complaint_category,
                severity_suggested,
                complaint_summary,
                complaint_date,
                1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM complaints
            WHERE
                embedding IS NOT NULL
                AND status = 'committed'
                AND (:exclude_id IS NULL OR id != :exclude_id)
                AND 1 - (embedding <=> CAST(:query_vec AS vector)) >= :threshold
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :limit
        """

        result = await db.execute(
            sql_text(query_str),
            {
                "query_vec": vec_str,
                "exclude_id": exclude_id,
                "threshold": threshold,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        return [
            {
                "id": row.id,
                "customer_name": row.customer_name,
                "product_name": row.product_name,
                "batch_lot_number": row.batch_lot_number,
                "complaint_category": row.complaint_category,
                "severity_suggested": row.severity_suggested,
                "complaint_summary": row.complaint_summary,
                "complaint_date": str(row.complaint_date) if row.complaint_date else None,
                "similarity": round(float(row.similarity), 3),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Duplicate similarity search failed: {e}")
        return []
