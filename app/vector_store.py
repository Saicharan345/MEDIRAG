import os
import pickle
import numpy as np
import re
import math
from collections import Counter
from config import config

class SimpleVectorStore:
    def __init__(self):
        self.index_path = os.path.join(config.CHROMA_DB_PATH, "index.pkl")
        self.documents = []
        self.ids = []
        self.metadatas = []
        
        # BM25 Parameters
        self.k1 = 1.5
        self.b = 0.75
        self.corpus_size = 0
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        
        # We don't use real embeddings anymore due to environment hangs
        # This is a BM25 TF-IDF fallback implementation
        
        if not os.path.exists(config.CHROMA_DB_PATH):
            os.makedirs(config.CHROMA_DB_PATH)
            
        self.load()

    def _tokenize(self, text):
        return re.findall(r'\w+', text.lower())

    def _build_bm25(self):
        self.corpus_size = len(self.documents)
        if self.corpus_size == 0:
            return
            
        self.doc_freqs = []
        self.doc_len = []
        self.idf = {}
        
        df = Counter()
        total_len = 0
        
        print("Building BM25 index...")
        for doc in self.documents:
            tokens = self._tokenize(doc)
            length = len(tokens)
            self.doc_len.append(length)
            total_len += length
            
            frequencies = dict(Counter(tokens))
            self.doc_freqs.append(frequencies)
            for word in frequencies.keys():
                df[word] += 1
                
        self.avgdl = total_len / self.corpus_size
        
        for word, freq in df.items():
            # BM25 IDF formula
            self.idf[word] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def add_documents(self, documents, ids, metadatas, batch_size=500):
        print(f"Adding {len(documents)} documents to BM25 index...")
        self.documents.extend(documents)
        self.ids.extend(ids)
        self.metadatas.extend(metadatas)
        self._build_bm25()
        self.save()
        print("Indexing complete.")

    def query(self, query_text, n_results=5, domain_filter=None):
        if not self.documents:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            
        print(f"Performing BM25 search for: '{query_text}'")
        query_tokens = self._tokenize(query_text)
        
        scores = np.zeros(self.corpus_size)
        doc_len = np.array(self.doc_len)
        
        for q in query_tokens:
            if q not in self.idf:
                continue
            
            # Fetch frequency of query term q in all documents
            q_freq = np.array([doc.get(q, 0) for doc in self.doc_freqs])
            
            # Calculate BM25 score for this term across all docs
            scores += (self.idf[q] * q_freq * (self.k1 + 1) /
                       (q_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)))
        
        # Apply domain filter and title boosts
        for i in range(self.corpus_size):
            if domain_filter and self.metadatas[i].get('domain') != domain_filter:
                scores[i] = -1.0
                continue
                
            title = self.metadatas[i].get('title', '').lower()
            for token in query_tokens:
                if token in title:
                    scores[i] += self.idf.get(token, 1.0) * 1.5 # Boost based on term rarity
                    
        # Get top N indices
        indices = np.argsort(scores)[::-1]
        top_indices = [idx for idx in indices if scores[idx] > 0][:n_results]
        
        if not top_indices:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        return {
            "documents": [[self.documents[i] for i in top_indices]],
            "metadatas": [[self.metadatas[i] for i in top_indices]],
            "distances": [[float(scores[i]) for i in top_indices]]
        }

    def reset_collection(self):
        self.documents = []
        self.ids = []
        self.metadatas = []
        self._build_bm25()
        if os.path.exists(self.index_path):
            os.remove(self.index_path)

    def save(self):
        data = {
            "documents": self.documents,
            "ids": self.ids,
            "metadatas": self.metadatas
        }
        with open(self.index_path, 'wb') as f:
            pickle.dump(data, f)

    def load(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'rb') as f:
                    data = pickle.load(f)
                    self.documents = data.get("documents", [])
                    self.ids = data.get("ids", [])
                    self.metadatas = data.get("metadatas", [])
                self._build_bm25()
            except Exception as e:
                print(f"Error loading index: {e}")

    def get_count(self):
        return len(self.documents)

    def get_domains(self):
        domains = {meta.get("domain") for meta in self.metadatas if meta.get("domain")}
        return sorted(domains)

vector_store = SimpleVectorStore()
