"""
services/company_graph_store.py - Company Graph Storage Service

Unified storage interface for Company Graph data with MongoDB (primary) and SQLite (fallback) backends.
Provides CRUD operations for all Company Graph entities.

Usage:
    from services.company_graph_store import get_company_graph_store
    store = get_company_graph_store()
    # Create a company
    company = await store.create_company(company)
    # Get a company graph
    graph = await store.get_company_graph(company_id)
"""

from __future__ import annotations
from typing import Any, List, Optional, Dict
from datetime import datetime
import logging
import os
import json
import secrets

from bson import ObjectId

# Import Company Graph models
from models.company_graph import (
    Company,
    CompanyGraph,
    CompanyGraphSnapshot,
    Website,
    Repo,
    BusinessSystem,
    DetectedSystem,
    Specialist,
    Workflow,
    KnowledgeItem,
    Connector,
    ApprovalPolicy,
)

log = logging.getLogger("company_graph.store")

# Configuration
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "mongodb").lower()
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "agency_core")
MONGO_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SELECTION_TIMEOUT_MS", "2000"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", "agency_core.db")


class CompanyGraphStore:
    """
    Unified storage interface for Company Graph data.
    Supports both MongoDB (primary) and SQLite (fallback) backends through a common interface.
    All operations are async.
    """

    def __init__(self, backend: str | None = None):
        """
        Initialize the store with a specific backend.
        Args:
            backend: 'mongodb' or 'sqlite'. Defaults to STORAGE_BACKEND env var.
        """
        raw_backend = backend or STORAGE_BACKEND
        # Normalise "mongo" alias → "mongodb"
        self.backend = "mongodb" if raw_backend in {"mongo", "mongodb"} else raw_backend
        self._mongodb_store: MongoDBStore | None = None
        self._sqlite_store: SQLiteStore | None = None

        if self.backend == "mongodb":
            self._mongodb_store = MongoDBStore()
            log.info(f"Company Graph Store initialized with MongoDB backend: {MONGO_URL}")
        elif self.backend == "sqlite":
            self._sqlite_store = SQLiteStore()
            log.info(f"Company Graph Store initialized with SQLite backend: {SQLITE_PATH}")
        else:
            raise ValueError(f"Unsupported storage backend: {self.backend!r}. Use 'mongodb' or 'sqlite'.")

    # =========================================================================
    # COMPANY OPERATIONS
    # =========================================================================

    async def create_company(self, company: Company) -> Company:
        """Create a new company."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_company(company)
        else:
            return await self._sqlite_store.create_company(company)

    async def get_company(self, company_id: str) -> Company | None:
        """Get a company by ID."""
        if self.backend == "mongodb":
            return await self._mongodb_store.get_company(company_id)
        else:
            return await self._sqlite_store.get_company(company_id)

    async def update_company(self, company: Company) -> Company:
        """Update a company."""
        if self.backend == "mongodb":
            return await self._mongodb_store.update_company(company)
        else:
            return await self._sqlite_store.update_company(company)

    async def delete_company(self, company_id: str) -> bool:
        """Delete a company and all its associated data."""
        if self.backend == "mongodb":
            return await self._mongodb_store.delete_company(company_id)
        else:
            return await self._sqlite_store.delete_company(company_id)

    async def list_companies(
        self,
        owner_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None
    ) -> List[Company]:
        """List companies with optional filtering."""
        if self.backend == "mongodb":
            return await self._mongodb_store.list_companies(owner_id, limit, offset, search)
        else:
            return await self._sqlite_store.list_companies(owner_id, limit, offset, search)

    # =========================================================================
    # COMPANY GRAPH OPERATIONS
    # =========================================================================

    async def create_company_graph(self, graph: CompanyGraph) -> CompanyGraph:
        """Create a new company graph."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_company_graph(graph)
        else:
            return await self._sqlite_store.create_company_graph(graph)

    async def get_company_graph(self, company_id: str) -> CompanyGraph | None:
        """Get the complete company graph for a company."""
        if self.backend == "mongodb":
            return await self._mongodb_store.get_company_graph(company_id)
        else:
            return await self._sqlite_store.get_company_graph(company_id)

    async def update_company_graph(self, graph: CompanyGraph) -> CompanyGraph:
        """Update a company graph."""
        if self.backend == "mongodb":
            return await self._mongodb_store.update_company_graph(graph)
        else:
            return await self._sqlite_store.update_company_graph(graph)

    async def delete_company_graph(self, graph_id: str) -> bool:
        """Delete a company graph."""
        if self.backend == "mongodb":
            return await self._mongodb_store.delete_company_graph(graph_id)
        else:
            return await self._sqlite_store.delete_company_graph(graph_id)

    async def create_graph_snapshot(self, snapshot: CompanyGraphSnapshot) -> CompanyGraphSnapshot:
        """Create a snapshot of a company graph."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_graph_snapshot(snapshot)
        else:
            return await self._sqlite_store.create_graph_snapshot(snapshot)

    async def list_graph_snapshots(
        self, company_id: str, limit: int = 10, offset: int = 0
    ) -> List[CompanyGraphSnapshot]:
        """List snapshots for a company graph."""
        if self.backend == "mongodb":
            return await self._mongodb_store.list_graph_snapshots(company_id, limit, offset)
        else:
            return await self._sqlite_store.list_graph_snapshots(company_id, limit, offset)

    # =========================================================================
    # WEBSITE OPERATIONS
    # =========================================================================

    async def create_website(self, website: Website, company_id: str) -> Website:
        """Create a new website. ``company_id`` is stored alongside the record
        (the ``Website`` model itself does not carry it), so the website can be
        retrieved via ``list_websites(company_id)``."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_website(website, company_id)
        else:
            return await self._sqlite_store.create_website(website, company_id)

    async def get_website(self, website_id: str) -> Website | None:
        """Get a website by ID."""
        if self.backend == "mongodb":
            return await self._mongodb_store.get_website(website_id)
        else:
            return await self._sqlite_store.get_website(website_id)

    async def update_website(self, website: Website, company_id: str | None = None) -> Website:
        """Update a website. When ``company_id`` is omitted the existing
        company association is preserved."""
        if self.backend == "mongodb":
            return await self._mongodb_store.update_website(website, company_id)
        else:
            return await self._sqlite_store.update_website(website, company_id)

    async def delete_website(self, website_id: str) -> bool:
        """Delete a website."""
        if self.backend == "mongodb":
            return await self._mongodb_store.delete_website(website_id)
        else:
            return await self._sqlite_store.delete_website(website_id)

    async def list_websites(
        self, company_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> List[Website]:
        """List websites with optional filtering."""
        if self.backend == "mongodb":
            return await self._mongodb_store.list_websites(company_id, limit, offset)
        else:
            return await self._sqlite_store.list_websites(company_id, limit, offset)

    # =========================================================================
    # DETECTED SYSTEM OPERATIONS
    # =========================================================================

    async def create_detected_system(
        self, system: "DetectedSystem", company_id: str
    ) -> "DetectedSystem":
        """Persist a detected system for a company."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_detected_system(system, company_id)
        else:
            return await self._sqlite_store.create_detected_system(system, company_id)

    async def list_detected_systems(
        self, company_id: str, system_type: str | None = None
    ) -> List["DetectedSystem"]:
        """List detected systems for a company, optionally filtered by type."""
        if self.backend == "mongodb":
            return await self._mongodb_store.list_detected_systems(company_id, system_type)
        else:
            return await self._sqlite_store.list_detected_systems(company_id, system_type)

    # =========================================================================
    # REPOSITORY OPERATIONS
    # =========================================================================

    async def create_repo(self, repo: Repo) -> Repo:
        """Create a new repository."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_repo(repo)
        else:
            return await self._sqlite_store.create_repo(repo)

    async def get_repo(self, repo_id: str) -> Repo | None:
        """Get a repository by ID."""
        if self.backend == "mongodb":
            return await self._mongodb_store.get_repo(repo_id)
        else:
            return await self._sqlite_store.get_repo(repo_id)

    async def update_repo(self, repo: Repo) -> Repo:
        """Update a repository."""
        if self.backend == "mongodb":
            return await self._mongodb_store.update_repo(repo)
        else:
            return await self._sqlite_store.update_repo(repo)

    async def delete_repo(self, repo_id: str) -> bool:
        """Delete a repository."""
        if self.backend == "mongodb":
            return await self._mongodb_store.delete_repo(repo_id)
        else:
            return await self._sqlite_store.delete_repo(repo_id)

    async def list_repos(
        self, company_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> List[Repo]:
        """List repositories with optional filtering."""
        if self.backend == "mongodb":
            return await self._mongodb_store.list_repos(company_id, limit, offset)
        else:
            return await self._sqlite_store.list_repos(company_id, limit, offset)

    # =========================================================================
    # SPECIALIST OPERATIONS
    # =========================================================================

    async def create_specialist(self, specialist: Specialist) -> Specialist:
        """Create a new specialist."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_specialist(specialist)
        else:
            return await self._sqlite_store.create_specialist(specialist)

    async def get_specialist(self, specialist_id: str) -> Specialist | None:
        """Get a specialist by ID."""
        if self.backend == "mongodb":
            return await self._mongodb_store.get_specialist(specialist_id)
        else:
            return await self._sqlite_store.get_specialist(specialist_id)

    async def update_specialist(self, specialist: Specialist) -> Specialist:
        """Update a specialist."""
        if self.backend == "mongodb":
            return await self._mongodb_store.update_specialist(specialist)
        else:
            return await self._sqlite_store.update_specialist(specialist)

    async def delete_specialist(self, specialist_id: str) -> bool:
        """Delete a specialist."""
        if self.backend == "mongodb":
            return await self._mongodb_store.delete_specialist(specialist_id)
        else:
            return await self._sqlite_store.delete_specialist(specialist_id)

    async def list_specialists(
        self,
        company_id: str | None = None,
        family: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Specialist]:
        """List specialists with optional filtering."""
        if self.backend == "mongodb":
            return await self._mongodb_store.list_specialists(company_id, family, status, limit, offset)
        else:
            return await self._sqlite_store.list_specialists(company_id, family, status, limit, offset)

    # =========================================================================
    # KNOWLEDGE OPERATIONS
    # =========================================================================

    async def create_knowledge_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Create a new knowledge item."""
        if self.backend == "mongodb":
            return await self._mongodb_store.create_knowledge_item(item)
        else:
            return await self._sqlite_store.create_knowledge_item(item)

    async def get_knowledge_item(self, item_id: str) -> KnowledgeItem | None:
        """Get a knowledge item by ID."""
        if self.backend == "mongodb":
            return await self._mongodb_store.get_knowledge_item(item_id)
        else:
            return await self._sqlite_store.get_knowledge_item(item_id)

    async def update_knowledge_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Update a knowledge item."""
        if self.backend == "mongodb":
            return await self._mongodb_store.update_knowledge_item(item)
        else:
            return await self._sqlite_store.update_knowledge_item(item)

    async def delete_knowledge_item(self, item_id: str) -> bool:
        """Delete a knowledge item."""
        if self.backend == "mongodb":
            return await self._mongodb_store.delete_knowledge_item(item_id)
        else:
            return await self._sqlite_store.delete_knowledge_item(item_id)

    async def search_knowledge(
        self,
        query: str | None = None,
        company_id: str | None = None,
        tags: List[str] | None = None,
        knowledge_type: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeItem]:
        """Search knowledge items."""
        if self.backend == "mongodb":
            return await self._mongodb_store.search_knowledge(query, company_id, tags, knowledge_type, limit, offset)
        else:
            return await self._sqlite_store.search_knowledge(query, company_id, tags, knowledge_type, limit, offset)


# =============================================================================
# MONGODB STORE IMPLEMENTATION
# =============================================================================

class MongoDBStore:
    """
    MongoDB implementation of the Company Graph store.
    Uses Motor (async MongoDB driver) for async operations.
    """

    def __init__(self):
        self._client = None
        self._db = None

    def _get_db(self):
        """Get or create the MongoDB database connection."""
        if self._db is None:
            from motor.motor_asyncio import AsyncIOMotorClient
            self._client = AsyncIOMotorClient(
                MONGO_URL, serverSelectionTimeoutMS=MONGO_SELECTION_TIMEOUT_MS
            )
            self._db = self._client[DB_NAME]
            log.info(f"MongoDB connection established to {MONGO_URL}/{DB_NAME}")
        return self._db

    def _to_object_id(self, id_str: str) -> ObjectId:
        """Convert string ID to ObjectId."""
        try:
            return ObjectId(id_str)
        except Exception:
            raise ValueError(f"Invalid ObjectId: {id_str}")

    def _to_str(self, obj_id: ObjectId) -> str:
        """Convert ObjectId to string."""
        return str(obj_id)

    def _prepare_doc(self, model) -> dict:
        """Prepare a Pydantic model for MongoDB storage."""
        doc = model.model_dump(exclude={"id"})
        if hasattr(model, "id") and model.id:
            doc["_id"] = self._to_object_id(model.id)
        return doc

    @staticmethod
    def _strip_unknown(doc: dict, model_class: type) -> dict:
        """Drop persisted bookkeeping keys a strict (``extra="forbid"``) model
        does not declare — e.g. the ``graph_id`` reference written onto the
        company document by :meth:`create_company_graph`, or a leftover ``_id`` —
        so a round-tripped MongoDB document still validates instead of raising
        ``ValidationError`` (which surfaced as a 500 on ``POST /api/company``)."""
        cfg = getattr(model_class, "model_config", {}) or {}
        if cfg.get("extra") == "forbid":
            allowed = set(getattr(model_class, "model_fields", {}) or {})
            if allowed:
                return {k: v for k, v in doc.items() if k in allowed}
        return doc

    def _prepare_result(self, doc: dict, model_class: type) -> Any | None:
        """Prepare a MongoDB document for Pydantic model."""
        if not doc:
            return None
        doc = dict(doc)
        doc["id"] = self._to_str(doc["_id"])
        doc.pop("_id", None)
        return model_class.model_validate(self._strip_unknown(doc, model_class))

    # Company Operations
    async def create_company(self, company: Company) -> Company:
        """Create a new company in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(company)
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        company = company.model_copy(update={"id": self._to_str(doc["_id"])})
        await db.companies.insert_one(doc)
        log.debug(f"Created company: {company.id}")
        return company

    async def get_company(self, company_id: str) -> Company | None:
        """Get a company by ID from MongoDB."""
        db = self._get_db()
        doc = await db.companies.find_one({"_id": self._to_object_id(company_id)})
        return self._prepare_result(doc, Company)

    async def update_company(self, company: Company) -> Company:
        """Update a company in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(company)
        doc["updated_at"] = datetime.utcnow().isoformat()
        await db.companies.update_one(
            {"_id": self._to_object_id(company.id)},
            {"$set": doc}
        )
        log.debug(f"Updated company: {company.id}")
        return company

    async def delete_company(self, company_id: str) -> bool:
        """Delete a company and all associated data from MongoDB."""
        db = self._get_db()
        object_id = self._to_object_id(company_id)
        # Delete all associated data
        await db.company_graphs.delete_many({"company_id": company_id})
        await db.websites.delete_many({"company_id": company_id})
        await db.repos.delete_many({"company_id": company_id})
        await db.business_systems.delete_many({"company_id": company_id})
        await db.detected_systems.delete_many({"company_id": company_id})
        await db.specialists.delete_many({"company_id": company_id})
        await db.workflows.delete_many({"company_id": company_id})
        await db.knowledge_items.delete_many({"company_id": company_id})
        await db.connectors.delete_many({"company_id": company_id})
        await db.approval_policies.delete_many({"company_id": company_id})
        # Delete the company
        result = await db.companies.delete_one({"_id": object_id})
        if result.deleted_count > 0:
            log.info(f"Deleted company and all associated data: {company_id}")
        return result.deleted_count > 0

    async def list_companies(
        self, owner_id: str | None = None, limit: int = 100, offset: int = 0, search: str | None = None
    ) -> List[Company]:
        """List companies from MongoDB."""
        db = self._get_db()
        query = {}
        if owner_id:
            query["owner_id"] = owner_id
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"domain": {"$regex": search, "$options": "i"}}
            ]
        cursor = db.companies.find(query).skip(offset).limit(limit)
        companies = []
        async for doc in cursor:
            companies.append(self._prepare_result(doc, Company))
        return companies

    # Company Graph Operations
    async def create_company_graph(self, graph: CompanyGraph) -> CompanyGraph:
        """Create a new company graph in MongoDB."""
        db = self._get_db()
        graph_doc = self._prepare_doc(graph)
        if "_id" not in graph_doc:
            graph_doc["_id"] = ObjectId()
        graph = graph.model_copy(update={"id": self._to_str(graph_doc["_id"])})
        await db.company_graphs.insert_one(graph_doc)
        # Update company with graph reference
        await db.companies.update_one(
            {"_id": self._to_object_id(graph.company_id)},
            {
                "$set": {
                    "graph_id": graph.id,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
        log.debug(f"Created company graph: {graph.id}")
        return graph

    async def get_company_graph(self, company_id: str) -> CompanyGraph | None:
        """Get the complete company graph for a company from MongoDB."""
        db = self._get_db()
        # Get the graph document
        graph_doc = await db.company_graphs.find_one({"company_id": company_id})
        if not graph_doc:
            return None
        graph_doc["id"] = self._to_str(graph_doc["_id"])
        # Get all related entities
        websites = []
        async for doc in db.websites.find({"company_id": company_id}):
            websites.append(self._prepare_result(doc, Website))
        repos = []
        async for doc in db.repos.find({"company_id": company_id}):
            repos.append(self._prepare_result(doc, Repo))
        systems = []
        async for doc in db.business_systems.find({"company_id": company_id}):
            systems.append(self._prepare_result(doc, BusinessSystem))
        specialists = []
        async for doc in db.specialists.find({"company_id": company_id}):
            specialists.append(self._prepare_result(doc, Specialist))
        workflows = []
        async for doc in db.workflows.find({"company_id": company_id}):
            workflows.append(self._prepare_result(doc, Workflow))
        knowledge = []
        async for doc in db.knowledge_items.find({"company_id": company_id}):
            knowledge.append(self._prepare_result(doc, KnowledgeItem))
        connectors = []
        async for doc in db.connectors.find({"company_id": company_id}):
            connectors.append(self._prepare_result(doc, Connector))
        approval_policies = []
        async for doc in db.approval_policies.find({"company_id": company_id}):
            approval_policies.append(self._prepare_result(doc, ApprovalPolicy))
        detected_systems = []
        async for doc in db.detected_systems.find({"company_id": company_id}):
            detected_systems.append(self._prepare_result(doc, DetectedSystem))
        # Build the complete graph
        graph_doc["websites"] = websites
        graph_doc["repos"] = repos
        graph_doc["systems"] = systems
        graph_doc["specialists"] = specialists
        graph_doc["workflows"] = workflows
        graph_doc["knowledge"] = knowledge
        graph_doc["connectors"] = connectors
        graph_doc["approval_policies"] = approval_policies
        graph_doc["detected_systems"] = detected_systems
        # Get the company
        company = await self.get_company(company_id)
        graph_doc.pop("_id", None)
        graph_doc["company"] = company
        return CompanyGraph.model_validate(self._strip_unknown(graph_doc, CompanyGraph))

    async def update_company_graph(self, graph: CompanyGraph) -> CompanyGraph:
        """Update a company graph in MongoDB."""
        db = self._get_db()
        graph_doc = self._prepare_doc(graph)
        graph_doc["updated_at"] = datetime.utcnow().isoformat()
        await db.company_graphs.update_one(
            {"_id": self._to_object_id(graph.id)},
            {"$set": graph_doc}
        )
        log.debug(f"Updated company graph: {graph.id}")
        return graph

    async def delete_company_graph(self, graph_id: str) -> bool:
        """Delete a company graph from MongoDB."""
        db = self._get_db()
        result = await db.company_graphs.delete_one({"_id": self._to_object_id(graph_id)})
        return result.deleted_count > 0

    async def create_graph_snapshot(self, snapshot: CompanyGraphSnapshot) -> CompanyGraphSnapshot:
        """Create a snapshot of a company graph in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(snapshot)
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        snapshot = snapshot.model_copy(update={"id": self._to_str(doc["_id"])})
        await db.company_graph_snapshots.insert_one(doc)
        log.debug(f"Created graph snapshot: {snapshot.id}")
        return snapshot

    async def list_graph_snapshots(
        self, company_id: str, limit: int = 10, offset: int = 0
    ) -> List[CompanyGraphSnapshot]:
        """List snapshots for a company graph from MongoDB."""
        db = self._get_db()
        cursor = db.company_graph_snapshots.find({"company_id": company_id}).sort("created_at", -1).skip(offset).limit(limit)
        snapshots = []
        async for doc in cursor:
            snapshots.append(self._prepare_result(doc, CompanyGraphSnapshot))
        return snapshots

    # Website Operations
    async def create_website(self, website: Website, company_id: str) -> Website:
        """Create a new website in MongoDB. ``company_id`` is written onto the
        document (the model doesn't carry it) so ``list_websites`` can filter on
        it; ``_prepare_result`` strips it back off on read."""
        db = self._get_db()
        doc = self._prepare_doc(website)
        doc["company_id"] = company_id
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        website = website.model_copy(update={"id": self._to_str(doc["_id"])})
        await db.websites.insert_one(doc)
        log.debug(f"Created website: {website.id}")
        return website

    async def get_website(self, website_id: str) -> Website | None:
        """Get a website by ID from MongoDB."""
        db = self._get_db()
        doc = await db.websites.find_one({"_id": self._to_object_id(website_id)})
        return self._prepare_result(doc, Website)

    async def update_website(self, website: Website, company_id: str | None = None) -> Website:
        """Update a website in MongoDB. The company association is only rewritten
        when ``company_id`` is supplied (otherwise it is left untouched)."""
        db = self._get_db()
        doc = self._prepare_doc(website)
        doc["updated_at"] = datetime.utcnow().isoformat()
        if company_id is not None:
            doc["company_id"] = company_id
        await db.websites.update_one(
            {"_id": self._to_object_id(website.id)},
            {"$set": doc}
        )
        log.debug(f"Updated website: {website.id}")
        return website

    async def delete_website(self, website_id: str) -> bool:
        """Delete a website from MongoDB."""
        db = self._get_db()
        result = await db.websites.delete_one({"_id": self._to_object_id(website_id)})
        return result.deleted_count > 0

    async def list_websites(
        self, company_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> List[Website]:
        """List websites from MongoDB."""
        db = self._get_db()
        query = {}
        if company_id:
            query["company_id"] = company_id
        cursor = db.websites.find(query).skip(offset).limit(limit)
        websites = []
        async for doc in cursor:
            websites.append(self._prepare_result(doc, Website))
        return websites

    # Detected System Operations
    async def create_detected_system(self, system: DetectedSystem, company_id: str) -> DetectedSystem:
        """Persist a detected system in MongoDB (company_id is stored on the doc,
        since DetectedSystem itself doesn't carry it)."""
        db = self._get_db()
        doc = self._prepare_doc(system)
        doc["company_id"] = company_id
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        system = system.model_copy(update={"id": self._to_str(doc["_id"])})
        await db.detected_systems.insert_one(doc)
        log.debug(f"Created detected system: {system.name} ({system.system_type})")
        return system

    async def list_detected_systems(
        self, company_id: str, system_type: str | None = None
    ) -> List[DetectedSystem]:
        """List detected systems for a company from MongoDB."""
        db = self._get_db()
        query = {"company_id": company_id}
        if system_type:
            query["system_type"] = system_type
        systems = []
        async for doc in db.detected_systems.find(query):
            # _prepare_result strips the persisted company_id (DetectedSystem is extra="forbid")
            systems.append(self._prepare_result(doc, DetectedSystem))
        return systems

    # Repo Operations
    async def create_repo(self, repo: Repo) -> Repo:
        """Create a new repository in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(repo)
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        repo = repo.model_copy(update={"id": self._to_str(doc["_id"])})
        await db.repos.insert_one(doc)
        log.debug(f"Created repo: {repo.id}")
        return repo

    async def get_repo(self, repo_id: str) -> Repo | None:
        """Get a repository by ID from MongoDB."""
        db = self._get_db()
        doc = await db.repos.find_one({"_id": self._to_object_id(repo_id)})
        return self._prepare_result(doc, Repo)

    async def update_repo(self, repo: Repo) -> Repo:
        """Update a repository in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(repo)
        doc["updated_at"] = datetime.utcnow().isoformat()
        await db.repos.update_one(
            {"_id": self._to_object_id(repo.id)},
            {"$set": doc}
        )
        log.debug(f"Updated repo: {repo.id}")
        return repo

    async def delete_repo(self, repo_id: str) -> bool:
        """Delete a repository from MongoDB."""
        db = self._get_db()
        result = await db.repos.delete_one({"_id": self._to_object_id(repo_id)})
        return result.deleted_count > 0

    async def list_repos(
        self, company_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> List[Repo]:
        """List repositories from MongoDB."""
        db = self._get_db()
        query = {}
        if company_id:
            query["company_id"] = company_id
        cursor = db.repos.find(query).skip(offset).limit(limit)
        repos = []
        async for doc in cursor:
            repos.append(self._prepare_result(doc, Repo))
        return repos

    # Specialist Operations
    async def create_specialist(self, specialist: Specialist) -> Specialist:
        """Create a new specialist in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(specialist)
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        specialist = specialist.model_copy(update={"id": self._to_str(doc["_id"])})
        await db.specialists.insert_one(doc)
        log.debug(f"Created specialist: {specialist.id}")
        return specialist

    async def get_specialist(self, specialist_id: str) -> Specialist | None:
        """Get a specialist by ID from MongoDB."""
        db = self._get_db()
        doc = await db.specialists.find_one({"_id": self._to_object_id(specialist_id)})
        return self._prepare_result(doc, Specialist)

    async def update_specialist(self, specialist: Specialist) -> Specialist:
        """Update a specialist in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(specialist)
        doc["updated_at"] = datetime.utcnow().isoformat()
        await db.specialists.update_one(
            {"_id": self._to_object_id(specialist.id)},
            {"$set": doc}
        )
        log.debug(f"Updated specialist: {specialist.id}")
        return specialist

    async def delete_specialist(self, specialist_id: str) -> bool:
        """Delete a specialist from MongoDB."""
        db = self._get_db()
        result = await db.specialists.delete_one({"_id": self._to_object_id(specialist_id)})
        return result.deleted_count > 0

    async def list_specialists(
        self,
        company_id: str | None = None,
        family: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Specialist]:
        """List specialists from MongoDB."""
        db = self._get_db()
        query = {}
        if company_id:
            query["company_id"] = company_id
        if family:
            query["family"] = family
        if status:
            query["status"] = status
        cursor = db.specialists.find(query).skip(offset).limit(limit)
        specialists = []
        async for doc in cursor:
            specialists.append(self._prepare_result(doc, Specialist))
        return specialists

    # Knowledge Operations
    async def create_knowledge_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Create a new knowledge item in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(item)
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        item = item.model_copy(update={"id": self._to_str(doc["_id"])})
        await db.knowledge_items.insert_one(doc)
        log.debug(f"Created knowledge item: {item.id}")
        return item

    async def get_knowledge_item(self, item_id: str) -> KnowledgeItem | None:
        """Get a knowledge item by ID from MongoDB."""
        db = self._get_db()
        doc = await db.knowledge_items.find_one({"_id": self._to_object_id(item_id)})
        return self._prepare_result(doc, KnowledgeItem)

    async def update_knowledge_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Update a knowledge item in MongoDB."""
        db = self._get_db()
        doc = self._prepare_doc(item)
        doc["updated_at"] = datetime.utcnow().isoformat()
        await db.knowledge_items.update_one(
            {"_id": self._to_object_id(item.id)},
            {"$set": doc}
        )
        log.debug(f"Updated knowledge item: {item.id}")
        return item

    async def delete_knowledge_item(self, item_id: str) -> bool:
        """Delete a knowledge item from MongoDB."""
        db = self._get_db()
        result = await db.knowledge_items.delete_one({"_id": self._to_object_id(item_id)})
        return result.deleted_count > 0

    async def search_knowledge(
        self,
        query: str | None = None,
        company_id: str | None = None,
        tags: List[str] | None = None,
        knowledge_type: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeItem]:
        """Search knowledge items in MongoDB."""
        db = self._get_db()
        query_filter = {}
        if company_id:
            query_filter["company_id"] = company_id
        if knowledge_type:
            query_filter["knowledge_type"] = knowledge_type
        if tags:
            query_filter["tags"] = {"$in": tags}
        if query:
            query_filter["$or"] = [
                {"title": {"$regex": query, "$options": "i"}},
                {"content": {"$regex": query, "$options": "i"}}
            ]
        cursor = db.knowledge_items.find(query_filter).skip(offset).limit(limit)
        items = []
        async for doc in cursor:
            items.append(self._prepare_result(doc, KnowledgeItem))
        return items


# =============================================================================
# SQLITE STORE IMPLEMENTATION (Fallback)
# =============================================================================

class SQLiteStore:
    """
    SQLite implementation of the Company Graph store (fallback).
    Uses aiosqlite for async SQLite operations.
    """

    def __init__(self):
        self._db_path = SQLITE_PATH
        self._connection = None
        self._initialized = False

    async def _get_connection(self):
        """Get or create the SQLite connection."""
        if self._connection is None:
            import aiosqlite
            self._connection = await aiosqlite.connect(self._db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._initialize_schema()
            self._initialized = True
        return self._connection

    async def _initialize_schema(self):
        """Initialize the database schema."""
        if self._initialized:
            return
        conn = await self._get_connection()
        
        # Create companies table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                business_category TEXT NOT NULL DEFAULT 'other',
                description TEXT NOT NULL DEFAULT '',
                tagline TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                onboarding_status TEXT NOT NULL DEFAULT 'not_started',
                onboarding_progress REAL NOT NULL DEFAULT 0.0,
                owner_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create company_graphs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS company_graphs (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1.0',
                is_complete INTEGER NOT NULL DEFAULT 0,
                completeness_score REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Create websites table. Like detected_systems, the full Website model
        # (including nested inferred_stack / detected_systems) is stored as a JSON
        # blob in ``data`` so scan results round-trip; id/company_id/url are also
        # columned for querying.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS websites (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                url TEXT NOT NULL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                scan_status TEXT,
                scan_error TEXT,
                last_scanned TEXT,
                data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Create repos table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS repos (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                url TEXT NOT NULL,
                provider TEXT NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                is_private INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                last_scanned TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Create specialists table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS specialists (
                id TEXT PRIMARY KEY,
                company_id TEXT,
                name TEXT NOT NULL,
                family TEXT NOT NULL,
                capabilities TEXT NOT NULL DEFAULT '[]',
                tools TEXT NOT NULL DEFAULT '[]',
                model_preference TEXT,
                runtime TEXT,
                system_types TEXT NOT NULL DEFAULT '[]',
                bound_skills TEXT NOT NULL DEFAULT '[]',
                is_provisioned INTEGER NOT NULL DEFAULT 0,
                provisioned_at TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Create knowledge_items table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                title TEXT NOT NULL,
                knowledge_type TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Create detected_systems table. DetectedSystem has rich nested fields
        # (evidence, configuration, …) so the full model is stored as a JSON blob;
        # id/company_id/system_type are also columned for querying.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS detected_systems (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                system_type TEXT,
                name TEXT,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Create indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_owner ON companies(owner_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_websites_company ON websites(company_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_repos_company ON repos(company_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_specialists_company ON specialists(company_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_company ON knowledge_items(company_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_detected_systems_company ON detected_systems(company_id)")

        # Migration: add the websites.data JSON-blob column to pre-existing DBs
        # created before scan results were persisted. Check the schema first so a
        # locked / read-only / corrupt DB surfaces instead of being swallowed.
        cursor = await conn.execute("PRAGMA table_info(websites)")
        columns = {row[1] for row in await cursor.fetchall()}  # row[1] == column name
        if "data" not in columns:
            await conn.execute("ALTER TABLE websites ADD COLUMN data TEXT")

        # Migration: add bound_skills column to pre-existing specialists tables
        cursor = await conn.execute("PRAGMA table_info(specialists)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "bound_skills" not in columns:
            await conn.execute("ALTER TABLE specialists ADD COLUMN bound_skills TEXT NOT NULL DEFAULT '[]'")

        await conn.commit()
        log.info(f"SQLite schema initialized at {self._db_path}")

    def _prepare_doc(self, model) -> dict:
        """Prepare a Pydantic model for SQLite storage."""
        doc = model.model_dump()
        for key, value in doc.items():
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, list):
                # default=str so nested datetimes (e.g. in detected_systems) serialize
                doc[key] = json.dumps(value, default=str)
            elif isinstance(value, dict):
                doc[key] = json.dumps(value, default=str)
        return doc

    def _prepare_result(self, row, model_class) -> Any | None:
        """Prepare a SQLite row for Pydantic model."""
        if not row:
            return None
        doc = dict(row)
        for key, value in doc.items():
            if isinstance(value, str):
                if value.startswith('[') or value.startswith('{'):
                    try:
                        doc[key] = json.loads(value)
                    except json.JSONDecodeError:
                        pass
        return model_class.model_validate(doc)

    # Company Operations
    async def create_company(self, company: Company) -> Company:
        """Create a new company in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(company)
        await conn.execute("""
            INSERT INTO companies (id, name, domain, business_category, description, tagline, 
                                   owner_id, is_active, onboarding_status, onboarding_progress, 
                                   created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc["id"], doc["name"], doc["domain"], doc["business_category"],
            doc["description"], doc["tagline"], doc.get("owner_id"),
            1 if doc.get("is_active", True) else 0,
            doc.get("onboarding_status", "not_started"),
            doc.get("onboarding_progress", 0.0),
            doc["created_at"], doc["updated_at"]
        ))
        await conn.commit()
        log.debug(f"Created company: {company.id}")
        return company

    async def get_company(self, company_id: str) -> Company | None:
        """Get a company by ID from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        )
        row = await cursor.fetchone()
        return self._prepare_result(row, Company)

    async def update_company(self, company: Company) -> Company:
        """Update a company in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(company)
        await conn.execute("""
            UPDATE companies 
            SET name = ?, domain = ?, business_category = ?, description = ?, tagline = ?,
                owner_id = ?, is_active = ?, onboarding_status = ?, onboarding_progress = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            doc["name"], doc["domain"], doc["business_category"], doc["description"],
            doc["tagline"], doc.get("owner_id"),
            1 if doc.get("is_active", True) else 0,
            doc.get("onboarding_status", "not_started"),
            doc.get("onboarding_progress", 0.0),
            doc["updated_at"], doc["id"]
        ))
        await conn.commit()
        log.debug(f"Updated company: {company.id}")
        return company

    async def delete_company(self, company_id: str) -> bool:
        """Delete a company and all associated data from SQLite."""
        conn = await self._get_connection()
        # Delete all associated data
        await conn.execute("DELETE FROM company_graphs WHERE company_id = ?", (company_id,))
        await conn.execute("DELETE FROM websites WHERE company_id = ?", (company_id,))
        await conn.execute("DELETE FROM repos WHERE company_id = ?", (company_id,))
        await conn.execute("DELETE FROM detected_systems WHERE company_id = ?", (company_id,))
        await conn.execute("DELETE FROM specialists WHERE company_id = ?", (company_id,))
        await conn.execute("DELETE FROM knowledge_items WHERE company_id = ?", (company_id,))
        # Delete the company
        cursor = await conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        await conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            log.info(f"Deleted company and all associated data: {company_id}")
        return deleted

    async def list_companies(
        self, owner_id: str | None = None, limit: int = 100, offset: int = 0, search: str | None = None
    ) -> List[Company]:
        """List companies from SQLite."""
        conn = await self._get_connection()
        query = "SELECT * FROM companies"
        params = []
        if owner_id or search:
            conditions = []
            if owner_id:
                conditions.append("owner_id = ?")
                params.append(owner_id)
            if search:
                conditions.append("(name LIKE ? OR domain LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            query += " WHERE " + " AND ".join(conditions)
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await conn.execute(query, tuple(params))
        companies = []
        async for row in cursor:
            companies.append(self._prepare_result(row, Company))
        return companies

    # Website Operations
    @staticmethod
    def _website_from_row(row) -> Website | None:
        """Reconstruct a Website from a SQLite row, preferring the full JSON
        blob (which preserves inferred_stack / detected_systems) and falling
        back to the scalar columns only for rows written before the blob
        existed. A *present but corrupt* blob is treated as corruption (logged
        and surfaced as None) — never silently downgraded to the scalar columns,
        which would drop detected_systems and reintroduce the zero-specialist
        regression."""
        if not row:
            return None
        d = dict(row)
        blob = d.get("data")
        if blob:
            try:
                return Website.model_validate_json(blob)
            except Exception as exc:
                log.error(f"Website blob decode failed for {d.get('id')}: {exc}")
                return None
        return Website(
            id=d["id"], url=d["url"], is_primary=bool(d.get("is_primary")),
            scan_status=d.get("scan_status"), scan_error=d.get("scan_error"),
            last_scanned=d.get("last_scanned"),
            created_at=d["created_at"], updated_at=d["updated_at"],
        )

    async def create_website(self, website: Website, company_id: str) -> Website:
        """Create a new website in SQLite. The full model is stored in ``data``
        so scan results survive the round-trip; ``company_id`` is columned for
        filtering (the Website model itself doesn't carry it)."""
        conn = await self._get_connection()
        doc = self._prepare_doc(website)
        await conn.execute("""
            INSERT INTO websites (id, company_id, url, is_primary, scan_status,
                                  scan_error, last_scanned, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc["id"], company_id, doc["url"],
            1 if doc.get("is_primary", False) else 0,
            doc.get("scan_status"), doc.get("scan_error"),
            doc.get("last_scanned"), website.model_dump_json(),
            doc["created_at"], doc["updated_at"]
        ))
        await conn.commit()
        log.debug(f"Created website: {website.id}")
        return website

    async def get_website(self, website_id: str) -> Website | None:
        """Get a website by ID from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT * FROM websites WHERE id = ?", (website_id,)
        )
        row = await cursor.fetchone()
        return self._website_from_row(row)

    async def update_website(self, website: Website, company_id: str | None = None) -> Website:
        """Update a website in SQLite. When ``company_id`` is omitted the existing
        company association is preserved (via COALESCE)."""
        conn = await self._get_connection()
        doc = self._prepare_doc(website)
        await conn.execute("""
            UPDATE websites
            SET company_id = COALESCE(?, company_id), url = ?, is_primary = ?, scan_status = ?,
                scan_error = ?, last_scanned = ?, data = ?, updated_at = ?
            WHERE id = ?
        """, (
            company_id, doc["url"],
            1 if doc.get("is_primary", False) else 0,
            doc.get("scan_status"), doc.get("scan_error"),
            doc.get("last_scanned"), website.model_dump_json(),
            doc["updated_at"], doc["id"]
        ))
        await conn.commit()
        log.debug(f"Updated website: {website.id}")
        return website

    async def delete_website(self, website_id: str) -> bool:
        """Delete a website from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute("DELETE FROM websites WHERE id = ?", (website_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def list_websites(
        self, company_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> List[Website]:
        """List websites from SQLite."""
        conn = await self._get_connection()
        query = "SELECT * FROM websites"
        params = []
        if company_id:
            query += " WHERE company_id = ?"
            params.append(company_id)
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await conn.execute(query, tuple(params))
        websites = []
        async for row in cursor:
            website = self._website_from_row(row)
            if website is not None:
                websites.append(website)
        return websites

    # Detected System Operations
    async def create_detected_system(self, system: DetectedSystem, company_id: str) -> DetectedSystem:
        """Persist a detected system in SQLite (full model stored as a JSON blob)."""
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT OR REPLACE INTO detected_systems (id, company_id, system_type, name, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                system.id, company_id, system.system_type, system.name,
                system.model_dump_json(), datetime.utcnow().isoformat(),
            ),
        )
        await conn.commit()
        log.debug(f"Created detected system: {system.name} ({system.system_type})")
        return system

    async def list_detected_systems(
        self, company_id: str, system_type: str | None = None
    ) -> List[DetectedSystem]:
        """List detected systems for a company from SQLite."""
        conn = await self._get_connection()
        query = "SELECT data FROM detected_systems WHERE company_id = ?"
        params: list = [company_id]
        if system_type:
            query += " AND system_type = ?"
            params.append(system_type)
        cursor = await conn.execute(query, tuple(params))
        systems = []
        async for row in cursor:
            data = row["data"] if not isinstance(row, (tuple, list)) else row[0]
            systems.append(DetectedSystem.model_validate_json(data))
        return systems

    # Repo Operations
    async def create_repo(self, repo: Repo) -> Repo:
        """Create a new repository in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(repo)
        await conn.execute("""
            INSERT INTO repos (id, company_id, url, provider, name, full_name, 
                              is_private, description, last_scanned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc["id"], doc["company_id"], doc["url"], doc["provider"],
            doc["name"], doc["full_name"],
            1 if doc.get("is_private", False) else 0,
            doc.get("description"), doc.get("last_scanned"),
            doc["created_at"], doc["updated_at"]
        ))
        await conn.commit()
        log.debug(f"Created repo: {repo.id}")
        return repo

    async def get_repo(self, repo_id: str) -> Repo | None:
        """Get a repository by ID from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT * FROM repos WHERE id = ?", (repo_id,)
        )
        row = await cursor.fetchone()
        return self._prepare_result(row, Repo)

    async def update_repo(self, repo: Repo) -> Repo:
        """Update a repository in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(repo)
        await conn.execute("""
            UPDATE repos 
            SET company_id = ?, url = ?, provider = ?, name = ?, full_name = ?,
                is_private = ?, description = ?, last_scanned = ?, updated_at = ?
            WHERE id = ?
        """, (
            doc["company_id"], doc["url"], doc["provider"], doc["name"],
            doc["full_name"],
            1 if doc.get("is_private", False) else 0,
            doc.get("description"), doc.get("last_scanned"),
            doc["updated_at"], doc["id"]
        ))
        await conn.commit()
        log.debug(f"Updated repo: {repo.id}")
        return repo

    async def delete_repo(self, repo_id: str) -> bool:
        """Delete a repository from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def list_repos(
        self, company_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> List[Repo]:
        """List repositories from SQLite."""
        conn = await self._get_connection()
        query = "SELECT * FROM repos"
        params = []
        if company_id:
            query += " WHERE company_id = ?"
            params.append(company_id)
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await conn.execute(query, tuple(params))
        repos = []
        async for row in cursor:
            repos.append(self._prepare_result(row, Repo))
        return repos

    # Specialist Operations
    async def create_specialist(self, specialist: Specialist) -> Specialist:
        """Create a new specialist in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(specialist)
        await conn.execute("""
            INSERT INTO specialists (id, company_id, name, family, capabilities, tools,
                                     model_preference, runtime, system_types, bound_skills,
                                     is_provisioned, provisioned_at, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc["id"], doc.get("company_id"), doc["name"], doc["family"],
            doc.get("capabilities", "[]"), doc.get("tools", "[]"),
            doc.get("model_preference"), doc.get("runtime"),
            doc.get("system_types", "[]"), doc.get("bound_skills", "[]"),
            1 if doc.get("is_provisioned", False) else 0,
            doc.get("provisioned_at"), doc.get("status", "available"),
            doc["created_at"], doc["updated_at"]
        ))
        await conn.commit()
        log.debug(f"Created specialist: {specialist.id}")
        return specialist

    async def get_specialist(self, specialist_id: str) -> Specialist | None:
        """Get a specialist by ID from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT * FROM specialists WHERE id = ?", (specialist_id,)
        )
        row = await cursor.fetchone()
        return self._prepare_result(row, Specialist)

    async def update_specialist(self, specialist: Specialist) -> Specialist:
        """Update a specialist in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(specialist)
        await conn.execute("""
            UPDATE specialists 
            SET company_id = ?, name = ?, family = ?, capabilities = ?, tools = ?,
                model_preference = ?, runtime = ?, system_types = ?, bound_skills = ?,
                is_provisioned = ?, provisioned_at = ?, status = ?, updated_at = ?
            WHERE id = ?
        """, (
            doc.get("company_id"), doc["name"], doc["family"],
            doc.get("capabilities", "[]"), doc.get("tools", "[]"),
            doc.get("model_preference"), doc.get("runtime"),
            doc.get("system_types", "[]"), doc.get("bound_skills", "[]"),
            1 if doc.get("is_provisioned", False) else 0,
            doc.get("provisioned_at"), doc.get("status", "available"),
            doc["updated_at"], doc["id"]
        ))
        await conn.commit()
        log.debug(f"Updated specialist: {specialist.id}")
        return specialist

    async def delete_specialist(self, specialist_id: str) -> bool:
        """Delete a specialist from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute("DELETE FROM specialists WHERE id = ?", (specialist_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def list_specialists(
        self,
        company_id: str | None = None,
        family: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Specialist]:
        """List specialists from SQLite."""
        conn = await self._get_connection()
        query = "SELECT * FROM specialists"
        params = []
        conditions = []
        if company_id:
            conditions.append("company_id = ?")
            params.append(company_id)
        if family:
            conditions.append("family = ?")
            params.append(family)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await conn.execute(query, tuple(params))
        specialists = []
        async for row in cursor:
            specialists.append(self._prepare_result(row, Specialist))
        return specialists

    # Knowledge Operations
    async def create_knowledge_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Create a new knowledge item in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(item)
        await conn.execute("""
            INSERT INTO knowledge_items (id, company_id, title, knowledge_type, content, 
                                         tags, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc["id"], doc["company_id"], doc["title"], doc["knowledge_type"],
            doc["content"], doc.get("tags", "[]"),
            1 if doc.get("is_active", True) else 0,
            doc["created_at"], doc["updated_at"]
        ))
        await conn.commit()
        log.debug(f"Created knowledge item: {item.id}")
        return item

    async def get_knowledge_item(self, item_id: str) -> KnowledgeItem | None:
        """Get a knowledge item by ID from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT * FROM knowledge_items WHERE id = ?", (item_id,)
        )
        row = await cursor.fetchone()
        return self._prepare_result(row, KnowledgeItem)

    async def update_knowledge_item(self, item: KnowledgeItem) -> KnowledgeItem:
        """Update a knowledge item in SQLite."""
        conn = await self._get_connection()
        doc = self._prepare_doc(item)
        await conn.execute("""
            UPDATE knowledge_items 
            SET company_id = ?, title = ?, knowledge_type = ?, content = ?, 
                tags = ?, is_active = ?, updated_at = ?
            WHERE id = ?
        """, (
            doc["company_id"], doc["title"], doc["knowledge_type"], doc["content"],
            doc.get("tags", "[]"),
            1 if doc.get("is_active", True) else 0,
            doc["updated_at"], doc["id"]
        ))
        await conn.commit()
        log.debug(f"Updated knowledge item: {item.id}")
        return item

    async def delete_knowledge_item(self, item_id: str) -> bool:
        """Delete a knowledge item from SQLite."""
        conn = await self._get_connection()
        cursor = await conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def search_knowledge(
        self,
        query: str | None = None,
        company_id: str | None = None,
        tags: List[str] | None = None,
        knowledge_type: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[KnowledgeItem]:
        """Search knowledge items in SQLite."""
        conn = await self._get_connection()
        query_filter = "SELECT * FROM knowledge_items"
        params = []
        conditions = []
        if company_id:
            conditions.append("company_id = ?")
            params.append(company_id)
        if knowledge_type:
            conditions.append("knowledge_type = ?")
            params.append(knowledge_type)
        if query:
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if conditions:
            query_filter += " WHERE " + " AND ".join(conditions)
        query_filter += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await conn.execute(query_filter, tuple(params))
        items = []
        async for row in cursor:
            items.append(self._prepare_result(row, KnowledgeItem))
        return items

    # Company Graph Operations (Simplified for SQLite)
    async def get_company_graph(self, company_id: str) -> CompanyGraph | None:
        """Get the complete company graph for a company from SQLite."""
        company = await self.get_company(company_id)
        if not company:
            return None
        
        websites = await self.list_websites(company_id)
        repos = await self.list_repos(company_id)
        specialists = await self.list_specialists(company_id)
        knowledge = await self.search_knowledge(company_id=company_id)
        detected_systems = await self.list_detected_systems(company_id)

        return CompanyGraph(
            id=f"graph_{company_id}",
            company_id=company_id,
            company=company,
            websites=websites,
            repos=repos,
            systems=[],  # BusinessSystems — use detected_systems for now
            specialists=specialists,
            workflows=[],
            knowledge=knowledge,
            connectors=[],
            approval_policies=[],
            detected_systems=detected_systems,
            version="1.0",
            is_complete=len(detected_systems) > 0 and len(specialists) > 0,
            completeness_score=1.0 if (len(detected_systems) > 0 and len(specialists) > 0) else 0.5 if (len(detected_systems) > 0 or len(specialists) > 0) else 0.0
        )

    async def create_company_graph(self, graph: CompanyGraph) -> CompanyGraph:
        """Create a new company graph (No-op shim for SQLite, as it is aggregated dynamically)."""
        return graph

    async def update_company_graph(self, graph: CompanyGraph) -> CompanyGraph:
        """Update a company graph (No-op shim for SQLite)."""
        return graph

    async def delete_company_graph(self, graph_id: str) -> bool:
        """Delete a company graph (No-op shim for SQLite)."""
        return True

    async def create_graph_snapshot(self, snapshot: CompanyGraphSnapshot) -> CompanyGraphSnapshot:
        """Create a company graph snapshot (No-op shim for SQLite)."""
        return snapshot

    async def list_graph_snapshots(self, company_id: str, limit: int = 10, offset: int = 0) -> List[CompanyGraphSnapshot]:
        """List snapshots for a company graph (No-op shim for SQLite)."""
        return []


# =============================================================================
# SINGLETON AND FACTORY
# =============================================================================

_graph_store: CompanyGraphStore | None = None


def get_company_graph_store() -> CompanyGraphStore:
    """
    Get the singleton Company Graph store instance.
    
    Returns:
        The singleton CompanyGraphStore instance.
    """
    global _graph_store
    if _graph_store is None:
        _graph_store = CompanyGraphStore()
    return _graph_store


def set_company_graph_store(store: CompanyGraphStore) -> None:
    """
    Set the singleton Company Graph store instance (for testing).
    
    Args:
        store: The CompanyGraphStore instance to use.
    """
    global _graph_store
    _graph_store = store
