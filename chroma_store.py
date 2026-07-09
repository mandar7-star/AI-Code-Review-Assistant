import chromadb
from chromadb.utils import embedding_functions
import hashlib
import json
from typing import List, Dict

class CodePatternStore:
    def __init__(self):
        try:
            self.client = chromadb.PersistentClient(path="./chroma_db")
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self.collection = self.client.get_or_create_collection(
                name="code_patterns",
                embedding_function=self.embedding_fn
            )
            self._initialize_patterns()
            print("✓ ChromaDB initialized")
        except Exception as e:
            print(f"⚠️ ChromaDB error: {e}")
            self.collection = None
    
    def _initialize_patterns(self):
        if self.collection and self.collection.count() == 0:
            patterns = [
                {"id": "p1", "code": "password = 'hardcoded'", "issue": "Hardcoded credentials", "fix": "Use environment variables"},
                {"id": "p2", "code": "query = 'SELECT * FROM users WHERE id = ' + user_id", "issue": "SQL Injection", "fix": "Use parameterized queries"},
                {"id": "p3", "code": "os.system('rm -rf ' + filename)", "issue": "Command Injection", "fix": "Use subprocess with list arguments"},
                {"id": "p4", "code": "eval(user_input)", "issue": "Unsafe code execution", "fix": "Avoid eval, use safer alternatives"},
                {"id": "p5", "code": "for i in range(len(arr)):", "issue": "Inefficient loop", "fix": "Use enumerate(arr)"}
            ]
            try:
                self.collection.add(
                    ids=[p["id"] for p in patterns],
                    documents=[p["code"] for p in patterns],
                    metadatas=[{"issue": p["issue"], "fix": p["fix"]} for p in patterns]
                )
            except Exception as e:
                print(f"Error seeding patterns: {e}")
    
    def search_similar(self, code: str, language: str, n_results: int = 3) -> List[Dict]:
        if not self.collection:
            return []
        try:
            results = self.collection.query(query_texts=[code[:500]], n_results=n_results)
            similar = []
            if results and results.get('documents'):
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results.get('metadatas', [[]])[0][i] if results.get('metadatas') else {}
                    similar.append({
                        "code": doc,
                        "issue": metadata.get('issue', 'Unknown issue'),
                        "fix": metadata.get('fix', 'No fix suggested')
                    })
            return similar
        except Exception as e:
            print(f"Search error: {e}")
            return []