import math
import re
from typing import List
from app.utils.logging import logger

class SimpleBM25:
    """A lightweight, dependency-free BM25 implementation for RAG."""
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0
        self.doc_lengths = []
        self.doc_freqs = []
        self.idf = {}
        self.chunks = []

    def _tokenize(self, text: str) -> List[str]:
        return [word for word in re.split(r'\W+', text.lower()) if word]

    def fit(self, chunks: List[str]):
        """Fit the BM25 model to a list of text chunks."""
        self.chunks = chunks
        self.corpus_size = len(chunks)
        self.doc_lengths = []
        self.doc_freqs = []
        self.idf = {}
        
        if self.corpus_size == 0:
            return

        nd = {}  # Word -> number of documents containing it
        total_len = 0
        
        for chunk in chunks:
            tokens = self._tokenize(chunk)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)
            
            # Term frequencies for this document
            freqs = {}
            for token in tokens:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)
            
            # Document frequencies
            for token in freqs.keys():
                nd[token] = nd.get(token, 0) + 1
                
        self.avg_doc_len = total_len / self.corpus_size
        
        # Calculate IDF
        for word, freq in nd.items():
            # BM25 IDF formula
            self.idf[word] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query: str) -> List[float]:
        """Get BM25 scores for a query against all chunks."""
        scores = [0.0] * self.corpus_size
        tokens = self._tokenize(query)
        
        if self.avg_doc_len == 0:
            return scores
            
        for i in range(self.corpus_size):
            score = 0.0
            freqs = self.doc_freqs[i]
            d_len = self.doc_lengths[i]
            for token in tokens:
                if token not in freqs:
                    continue
                tf = freqs[token]
                idf = self.idf.get(token, 0.0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * d_len / self.avg_doc_len)
                score += idf * (numerator / denominator)
            scores[i] = score
            
        return scores

    def get_top_k(self, query: str, k: int = 2) -> List[str]:
        """Return the top k chunks for a given query."""
        if not self.chunks:
            return []
            
        scores = self.get_scores(query)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        
        # Only return chunks that actually have a positive score
        results = []
        for idx in ranked_indices[:k]:
            if scores[idx] > 0:
                results.append(self.chunks[idx])
        return results
