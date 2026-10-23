---
name: rag-vector-db
description: RAG pipeline design, vector database integration, and embedding workflows
version: 1.0.0
activation: ["*.py", "vector_store/", "embeddings/"]
tags: [rag, vector-db, embeddings, langchain, llm, chroma, pinecone, weaviate]
requires_profile: full
---

# RAG and Vector Database Engineering Skill

## RAG Pipeline Steps
1. **Chunk** documents (sentence, paragraph, or semantic chunking).
2. **Embed** chunks using a consistent embedding model.
3. **Store** in vector DB (Chroma, Pinecone, Weaviate, pgvector).
4. **Retrieve** top-k chunks by cosine similarity.
5. **Generate** with LLM using retrieved context.

## Implementation
1. Install: `install_dependencies(manager="pip", package="langchain chromadb openai")`
2. Test retrieval quality with a gold standard Q&A set.
3. Monitor chunk relevance scores.
4. Tune chunk size and overlap.

## Evaluation
- Measure recall@k: did the correct chunk appear in top k?
- Measure answer faithfulness: does the answer follow from the context?
- Use `ragas` or `ARES` for automated evaluation.
