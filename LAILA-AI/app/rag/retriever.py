import asyncio, json
import numpy as np
import faiss
from app.database import database as db
from app.rag.loader import extract


def chunk_sections(sections):
    chunks = []
    for page, location, text in sections:
        text = text.replace("\x00", "").strip()
        for start in range(0, len(text), 900):
            part = text[start : start + 1100]
            if part.strip():
                chunks.append({"page": page, "location": location, "content": part})
    if len(chunks) > 2000:
        raise ValueError("Document exceeds 2,000 chunks. Split it into smaller files.")
    return chunks


async def index_document(doc_id, provider, model):
    documents = db.rows("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not documents:
        raise ValueError("Document not found.")
    db.run("UPDATE documents SET status='processing',error=NULL WHERE id=?", (doc_id,))
    try:
        chunks = await asyncio.to_thread(
            lambda: chunk_sections(extract(documents[0]["path"]))
        )
        vectors = []
        for start in range(0, len(chunks), 24):
            vectors.extend(
                await provider.embed(
                    model, [x["content"] for x in chunks[start : start + 24]]
                )
            )
        if len(vectors) != len(chunks):
            raise ValueError("Embedding count mismatch.")
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or not np.isfinite(matrix).all():
            raise ValueError("Invalid embeddings.")
        with db.connect() as con:
            con.execute("DELETE FROM document_chunks WHERE document_id=?", (doc_id,))
            for chunk, vector in zip(chunks, vectors):
                con.execute(
                    "INSERT INTO document_chunks VALUES(?,?,?,?,?,?)",
                    (
                        db.uid(),
                        doc_id,
                        chunk["page"],
                        chunk["location"],
                        chunk["content"],
                        json.dumps(vector),
                    ),
                )
            con.execute(
                "UPDATE documents SET status='indexed',embedding_model=?,error=NULL WHERE id=?",
                (model, doc_id),
            )
        return len(chunks)
    except Exception as e:
        db.run(
            "UPDATE documents SET status='error',error=? WHERE id=?",
            (str(e)[:300], doc_id),
        )
        raise


async def search(query, provider, model, document_ids=None, limit=5):
    sql = "SELECT c.*, d.filename FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE d.status='indexed' AND d.embedding_model=?"
    args = [model]
    if document_ids:
        sql += " AND d.id IN (" + ",".join("?" for _ in document_ids) + ")"
        args += document_ids
    chunks = db.rows(sql, args)
    if not chunks:
        return []
    vector = (await provider.embed(model, [query]))[0]

    # SQLite is the durable source of vectors; FAISS is rebuilt in memory, avoiding unsafe index deserialization.
    def retrieve():
        matrix = np.array([json.loads(x["embedding"]) for x in chunks], dtype="float32")
        q = np.array([vector], dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] != q.shape[1]:
            raise ValueError("Embedding dimensions changed. Reindex your documents.")
        faiss.normalize_L2(matrix)
        faiss.normalize_L2(q)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        scores, indices = index.search(q, min(limit, len(chunks)))
        result = []
        for score, i in zip(scores[0], indices[0]):
            x = chunks[int(i)]
            result.append(
                {
                    k: x[k]
                    for k in (
                        "id",
                        "document_id",
                        "filename",
                        "page",
                        "location",
                        "content",
                    )
                }
                | {"score": float(score), "label": f"S{len(result)+1}"}
            )
        return result

    return await asyncio.to_thread(retrieve)
