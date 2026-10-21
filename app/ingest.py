import json
from config import config
import os
import glob
from app.vector_store import vector_store
from app.models import GuidelineEntry

def chunk_text(text, chunk_size=512, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
            
        # Find the next space to avoid splitting a word
        while end < len(text) and not text[end].isspace():
            end += 1
            
        chunks.append(text[start:end])
        start = end - overlap
        
        # Ensure new start also falls on a word boundary
        while start > 0 and not text[start-1].isspace():
            start -= 1
            
        if start >= end:
            break
            
    return chunks

def ingest_guidelines():
    data_dir = os.path.dirname(config.DATA_PATH)
    json_files = [
        path for path in glob.glob(os.path.join(data_dir, "*.json"))
        if os.path.basename(path) != os.path.basename(config.STORAGE_PATH)
    ]
    
    print(f"Found {len(json_files)} data files: {json_files}")
    
    guidelines = []
    for json_file in json_files:
        print(f"Loading data from {json_file}...")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                records = data.get("guidelines")
                if isinstance(records, list):
                    guidelines.extend(records)
        except Exception as exc:
            print(f"Skipping {json_file} due to read/parse error: {exc}")
    
    # Reset collection for fresh start
    vector_store.reset_collection()
    
    all_chunks = []
    all_ids = []
    all_metadatas = []
    total_processed = 0
    
    for entry in guidelines:
        guideline = GuidelineEntry(**entry)
        aliases_text = ", ".join(guideline.aliases) if guideline.aliases else ""
        
        # Combine content and key recommendations for indexing
        full_text = (
            f"Title: {guideline.title}\n"
            f"Domain: {guideline.domain}\n"
            f"Aliases: {aliases_text}\n"
            f"Content: {guideline.content}\n"
            f"Key Recommendations: {', '.join(guideline.key_recommendations)}"
        )
        
        # Increased chunk size for better context and fewer vectors
        chunks = chunk_text(full_text, chunk_size=1024, overlap=200)
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{guideline.id}_chunk_{i}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadatas.append({
                "guideline_id": guideline.id,
                "domain": guideline.domain,
                "title": guideline.title,
                "source": guideline.source,
                "category": guideline.category,
                "last_updated": guideline.last_updated,
                "aliases": guideline.aliases
            })
        
        total_processed += 1
        # Batch inserting into list to manage memory if needed, 
        # but the real bottleneck was the vector store encoding.
        if total_processed % 5000 == 0:
            print(f"Prepared {total_processed}/{len(guidelines)} entries...")

    if all_chunks:
        print(f"Inserting {len(all_chunks)} chunks into vector database...")
        # We now use the batch-aware add_documents
        vector_store.add_documents(
            documents=all_chunks,
            ids=all_ids,
            metadatas=all_metadatas,
            batch_size=1000 # Encoding batch size
        )
        print("Ingestion complete.")
        return len(all_chunks)
    
    print("No guidelines found to ingest.")
    return 0

if __name__ == "__main__":
    ingest_guidelines()
