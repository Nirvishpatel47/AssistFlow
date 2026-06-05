#python -m RAG.Vector_Store   
from Security.get_secretes import load_env_from_secret
from Security.Advance_Logger import logger
from RAG.Gemini_Api_connection import GeminiFunctions
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType
)

import uuid

QDRANT_URL = load_env_from_secret("QDRANT_URL")
QDRANT_API_KEY = load_env_from_secret("QDRANT_API_KEY")

COLLECTION_NAME = "documents"

VECTOR_SIZE = 3072


class VectorStore:
    def __init__(self):
        try:
            self.gemini = GeminiFunctions()

            self.client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY
            )

            self._create_collection_if_not_exists()

        except Exception as e:
            logger.error("VectorStore.__init__", e)

    def _create_collection_if_not_exists(self):
        try:
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if COLLECTION_NAME not in collection_names:
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created new collection: {COLLECTION_NAME}")

            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="user_id",
                field_schema=PayloadSchemaType.INTEGER,
            )

            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="document_id",
                field_schema=PayloadSchemaType.INTEGER,
            )

            logger.info("Verified and enforced user_id payload index in Qdrant.")

        except Exception as e:
            logger.error("VectorStore._create_collection_if_not_exists", e)

    async def add_vectors_batch(self, user_id: int, chunks: list[str], document_id: int = 0) -> bool:
        """
        Generates individual embeddings for document text chunks and inserts them as a batch.
        """
        try:
            if not chunks:
                return False

            points = []
            for chunk in chunks:
                if not chunk.strip():
                    continue
                    
                # Generate a vector for each isolated chunk segment
                vector = await self.gemini.generate_embeddings(chunk)

                points.append(
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector.tolist(),
                        payload={
                            "text": chunk, # Stores only this specific chunk context
                            "user_id": user_id,
                            "document_id": document_id
                        }
                    )
                )

            # Atomic upload of all points to your collection index
            if points:
                self.client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points
                )
                return True
            return False

        except Exception as e:
            logger.error("VectorStore.add_vectors_batch", e)
            return False

    async def search_vector(self, query: str, user_id: int, limit: int = 3):
        """
        Searches the collection using an isolated payload metadata filter for the explicit user.
        """
        try:
            vector = await self.gemini.generate_embeddings(query)
            if len(vector) == 0:
                return []

            # Hard filter restriction: Matches only records belonging to the authenticated user
            user_isolation_filter = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )

            results = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=vector.tolist(),
                query_filter=user_isolation_filter, # Restricts search space at the engine layer
                limit=limit
            )

            return [result.payload for result in results.points]
        except Exception as e:
            logger.error("VectorStore.search_vector", e)
            return []

    def delete_vectors_by_document_id(self, document_id: int, user_id: int) -> bool:
        """
        Deletes vector partitions by document ID while validating user ownership bounds.
        """
        try:
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="document_id",
                                match=MatchValue(value=document_id)
                            ),
                            FieldCondition(
                                key="user_id",
                                match=MatchValue(value=user_id) # Prevents unauthorized deletion cross-calls
                            )
                        ]
                    )
                )
            )
            return True
        except Exception as e:
            logger.error("VectorStore.delete_vectors_by_document_id", e)
            return False

Vector = VectorStore()

if __name__ == "__main__":

    results = Vector.delete_vectors_by_document_id(document_id=21, user_id=3)

    print(results)