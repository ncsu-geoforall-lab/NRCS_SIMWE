############################################################################
#
# MODULE:       g.ssurgo.query/rag/kb.py
# AUTHOR:       Corey T. White, GeoForAll Lab, NCSU
# PURPOSE:      Build/load SSURGO RAG knowledge base
# COPYRIGHT:    (C) 2025 Corey White and the GRASS Development Team
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

import os
import json
import sqlite3
import pathlib
from typing import List

# choose one of: chromadb or faiss
import chromadb
from chromadb.utils import embedding_functions


def _dump_sqlite_schema(sqlite_path):
    conn = sqlite3.connect(sqlite_path)
    c = conn.cursor()
    out = []
    for (tname,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        out.append(f"TABLE {tname}")
        for col in c.execute(f"PRAGMA table_info('{tname}')"):
            out.append(f"  COL {col[1]} type={col[2]} notnull={col[3]} pk={col[5]}")
        for fk in c.execute(f"PRAGMA foreign_key_list('{tname}')"):
            out.append(f"  FK ref={fk[2]} from={fk[3]} to={fk[4]}")
    conn.close()
    return "\n".join(out)


def _read_pdf_texts(pdf_paths: List[str]):
    # minimal: rely on your earlier uploads; many GRASS envs won’t have pdfminer.
    # If you prefer, pre-extract text externally and pass as .txt files.
    pdf_paths = pdf_paths if pdf_paths else pathlib.Path(__file__).parent / "data"
    texts = []
    for p in pdf_paths:
        if p.lower().endswith(".txt"):
            texts.append(open(p, "r", encoding="utf-8").read())
        else:
            # Expect pre-extracted text or ship pdfminer.six optionally
            try:
                from langchain_community.document_loaders import PDFMinerLoader

                loader = PDFMinerLoader(p)
                docs = loader.load()
                for d in docs:
                    texts.append(d.page_content)
            except Exception:
                # Fallback: include filename as marker
                texts.append(f"[PDF unavailable at runtime] {p}")
    return texts


def build_kb(sqlite_path, kb_dir, pdf_paths=None, use_sda=False):
    os.makedirs(kb_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=kb_dir)
    embed = (
        embedding_functions.DefaultEmbeddingFunction()
    )  # or OpenAIEmbeddingFunction(api_key=...)
    col = client.get_or_create_collection("ssurgo_kb", embedding_function=embed)

    docs = []
    if not use_sda and sqlite_path:
        docs.append({"id": "schema", "text": _dump_sqlite_schema(sqlite_path)})
    for i, txt in enumerate(_read_pdf_texts(pdf_paths or [])):
        docs.append({"id": f"pdf_{i}", "text": txt})

    # Chunk simple
    CHUNK = 1200
    OVER = 200
    items = []
    for d in docs:
        t = d["text"]
        i = 0
        k = 0
        while i < len(t):
            chunk = t[i : i + CHUNK]
            items.append((f"{d['id']}_{k}", chunk))
            i += CHUNK - OVER
            k += 1

    col.add(
        ids=[i[0] for i in items],
        documents=[i[1] for i in items],
        metadatas=[{} for _ in items],
    )
    with open(os.path.join(kb_dir, "kb_meta.json"), "w") as f:
        json.dump({"sqlite": sqlite_path, "pdfs": pdf_paths}, f)


def load_kb(kb_dir):
    client = chromadb.PersistentClient(path=kb_dir)
    col = client.get_collection("ssurgo_kb")
    return col


def search(kb, query, k=8):
    res = kb.query(query_texts=[query], n_results=k)
    return [doc for doc in (res["documents"][0] if res and res["documents"] else [])]
