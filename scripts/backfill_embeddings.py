"""Backfill embeddings for all outputs that don't have one yet."""

import asyncio
import asyncpg
from sentence_transformers import SentenceTransformer


async def main():
    conn = await asyncpg.connect("postgresql://zetesis:zetesis_dev@localhost:5432/zetesis")

    rows = await conn.fetch(
        "SELECT id, content FROM outputs WHERE embedding IS NULL"
    )
    print(f"Found {len(rows)} outputs without embeddings")

    if not rows:
        await conn.close()
        return

    model = SentenceTransformer("all-MiniLM-L6-v2")
    contents = [row["content"] for row in rows]
    embeddings = model.encode(contents, show_progress_bar=True)

    for row, emb in zip(rows, embeddings):
        emb_str = "[" + ",".join(str(x) for x in emb.tolist()) + "]"
        await conn.execute(
            "UPDATE outputs SET embedding = $1::vector WHERE id = $2",
            emb_str,
            row["id"],
        )
        print(f"  Updated {row['id']}")

    count = await conn.fetchval(
        "SELECT count(*) FROM outputs WHERE embedding IS NOT NULL"
    )
    print(f"\nDone. {count} outputs now have embeddings.")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
