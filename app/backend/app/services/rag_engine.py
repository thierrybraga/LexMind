"""
RAG Engine - Motor de Pesquisa Semântica Jurídica
"""

import logging
import os
from typing import List, Dict, Any, Optional
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Motor de Retrieval-Augmented Generation para documentos jurídicos
    
    Utiliza embeddings (SentenceTransformers) e busca vetorial (ChromaDB)
    para encontrar documentos relevantes.
    """
    
    def __init__(self):
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        self.initialized = False
        
    async def initialize(self):
        """Inicializa o RAG Engine"""
        if self.initialized:
            return
            
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            # Carregar modelo de embeddings
            logger.info(f"Carregando modelo de embeddings: {settings.EMBEDDING_MODEL}")
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL or "all-MiniLM-L6-v2")
            
            # Inicializar vector store (ChromaDB)
            db_path = settings.VECTOR_DB_PATH or "./chroma_db"
            logger.info(f"Inicializando vector store: {db_path}")
            
            if not os.path.exists(db_path):
                os.makedirs(db_path, exist_ok=True)
                
            self.chroma_client = chromadb.PersistentClient(path=db_path)
            
            # Criar ou obter coleção
            self.collection = self.chroma_client.get_or_create_collection(
                name="jurisprudencia",
                metadata={"hnsw:space": "cosine"}
            )
            
            self.initialized = True
            logger.info("✅ RAG Engine inicializado com sucesso (ChromaDB + SentenceTransformers)")
            
        except ImportError:
            logger.warning("Bibliotecas RAG (sentence-transformers, chromadb) não instaladas. RAG rodará em modo MOCK.")
            self.initialized = True
            return
            
        except Exception as e:
            logger.error(f"Erro ao inicializar RAG Engine: {e}")
            # Não dar raise para permitir que a aplicação suba mesmo sem RAG (graceful degradation)
            # Mas marcar como não inicializado para usar fallback se necessário
            # raise e

    async def embed_text(self, text: str) -> List[float]:
        """Gera embedding para texto"""
        if not self.initialized:
            await self.initialize()
        
        if not self.embedding_model:
            raise RuntimeError(
                "Modelo de embeddings não carregado. "
                "Verifique se sentence-transformers está instalado."
            )

        # Executar em thread pool para não bloquear o loop async
        import asyncio
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(None, self.embedding_model.encode, text)
        return embedding.tolist()

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Gera embeddings para múltiplos textos"""
        if not self.initialized:
            await self.initialize()

        if not self.embedding_model:
            raise RuntimeError(
                "Modelo de embeddings não carregado. "
                "Verifique se sentence-transformers está instalado."
            )

        import asyncio
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(None, self.embedding_model.encode, texts)
        return embeddings.tolist()
    
    async def search(
        self,
        query: str,
        tribunal: Optional[str] = None,
        area_direito: Optional[str] = None,
        tipo_fonte: Optional[str] = None,
        ano_inicio: Optional[int] = None,
        ano_fim: Optional[int] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Busca semântica em base jurídica
        """
        if not self.initialized:
            await self.initialize()
        
        # Gerar embedding da query
        query_embedding = await self.embed_text(query)
        
        if not self.collection:
            raise RuntimeError(
                "RAG Engine não inicializado: ChromaDB indisponível. "
                "Verifique se as bibliotecas sentence-transformers e chromadb estão instaladas "
                "e se o diretório de dados é acessível."
            )

        # Construir filtros de metadados
        where_clause = {}
        if tribunal:
            where_clause["tribunal"] = tribunal
        if area_direito:
            where_clause["area"] = area_direito

        # Se where_clause estiver vazio, passar None para o chromadb
        where_filter = where_clause if where_clause else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
        )

        # Formatar resultados
        formatted_results = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                document = results["documents"][0][i] if results["documents"] else ""
                distance = results["distances"][0][i] if results["distances"] else 0

                formatted_results.append({
                    "id": doc_id,
                    "score": 1 - distance,  # Converter distância para similaridade
                    "conteudo": document,
                    **metadata,
                })

        return formatted_results
    
    async def index_document(
        self,
        content: str = None,
        metadata: Dict[str, Any] = None,
        doc_id: Optional[str] = None,
        *,
        id: Optional[Any] = None,
        text: Optional[str] = None
    ) -> str:
        """
        Indexa documento na base vetorial

        Aceita tanto (content, metadata, doc_id) quanto (id=, text=, metadata=)
        """
        # Compatibilidade com chamada via keyword args
        if text is not None and content is None:
            content = text
        if id is not None and doc_id is None:
            doc_id = str(id)
        if metadata is None:
            metadata = {}
        if not self.initialized:
            await self.initialize()
        
        # Chunking semântico
        chunks = self._chunk_juridico(content)
        
        # Gerar embeddings
        embeddings = await self.embed_texts(chunks)
        
        # Inserir no vector store (ChromaDB)
        if self.collection and doc_id:
            try:
                # Gerar IDs únicos para cada chunk
                chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
                
                # Replicar metadados para cada chunk
                chunk_metadatas = [metadata.copy() for _ in range(len(chunks))]
                for i, meta in enumerate(chunk_metadatas):
                    meta["chunk_index"] = i
                    meta["parent_doc_id"] = doc_id
                
                self.collection.add(
                    documents=chunks,
                    embeddings=embeddings,
                    metadatas=chunk_metadatas,
                    ids=chunk_ids
                )
                logger.info(f"Documento {doc_id} indexado com sucesso ({len(chunks)} chunks)")
                return doc_id
            except Exception as e:
                logger.error(f"Erro ao indexar documento no ChromaDB: {e}")
                return "error_indexing"
        
        return doc_id or "doc_placeholder"
    
    def _chunk_juridico(self, text: str) -> List[str]:
        """
        Chunking semântico jurídico
        
        Divide por:
        - Tese jurídica
        - Ementa
        - Fundamento
        - Dispositivo
        """
        # Estratégia simplificada - em produção usar algo mais sofisticado
        chunks = []
        
        # Dividir por parágrafos
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) < settings.CHUNK_SIZE:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def delete_document(self, doc_id: str):
        """Remove documento da base vetorial"""
        if not self.initialized:
            await self.initialize()
        
        if self.collection:
            try:
                # Remover todos os chunks do documento
                self.collection.delete(
                    where={"parent_doc_id": doc_id}
                )
                logger.info(f"Documento {doc_id} removido do ChromaDB")
            except Exception as e:
                logger.error(f"Erro ao remover documento {doc_id}: {e}")


# Instância global
_rag_engine = None


async def get_rag_engine() -> RAGEngine:
    """Dependency para obter RAG Engine"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
        await _rag_engine.initialize()
    return _rag_engine