"""Tests for Company Graph models and services."""
import pytest
from datetime import datetime
from typing import Optional

# Test imports work
pytest.importorskip("pydantic")


class TestCompanyGraphModels:
    """Test Company Graph Pydantic models."""
    
    def test_models_can_be_imported(self):
        """Test that all Company Graph models can be imported."""
        try:
            from models.company_graph import (
                Company,
                CompanyGraph,
                Website,
                Repo,
                BusinessSystem,
                DetectedSystem,
                Specialist,
                Workflow,
                KnowledgeItem,
                Connector,
                ApprovalPolicy,
                StackInference,
                Evidence,
                CompanyCreateRequest,
                CompanyUpdateRequest,
                CompanyResponse,
                WebsiteScanRequest,
                WebsiteScanResult,
                RepoScanRequest,
                OnboardingProgress,
                SpecialistProvisionRequest,
                SpecialistProvisionResult,
            )
            assert True, "All models imported successfully"
        except ImportError as e:
            pytest.fail(f"Failed to import models: {e}")
    
    def test_company_model_creation(self):
        """Test Company model creation."""
        from models.company_graph import Company
        
        company = Company(
            name="Test Company",
            domain="test.com",
            business_category="saas",
            description="A test company",
        )
        
        assert company.name == "Test Company"
        assert company.domain == "test.com"
        assert company.business_category == "saas"
        assert company.is_active is True
        assert company.onboarding_status == "not_started"
        assert company.onboarding_progress == 0.0
        assert company.created_at is not None
    
    def test_company_model_validation(self):
        """Test Company model validation."""
        from models.company_graph import Company
        from pydantic import ValidationError
        
        # Missing required fields
        with pytest.raises(ValidationError):
            Company()
        
        with pytest.raises(ValidationError):
            Company(name="Test")  # Missing domain
    
    def test_specialist_model_creation(self):
        """Test Specialist model creation."""
        from models.company_graph import Specialist
        
        specialist = Specialist(
            name="Test Specialist",
            family="engineering",
            capabilities=["code", "development", "python"],
            is_provisioned=True,
            status="available",
        )
        
        assert specialist.name == "Test Specialist"
        assert specialist.family == "engineering"
        assert "code" in specialist.capabilities
        assert specialist.can_handle_task(["code"]) is True
        assert specialist.can_handle_task(["testing"]) is False
    
    def test_website_model_creation(self):
        """Test Website model creation."""
        from models.company_graph import Website
        
        website = Website(
            url="https://example.com",
            is_primary=True,
        )
        
        assert website.url == "https://example.com"
        assert website.is_primary is True
        assert website.scan_status is None  # Default is None, not "pending"


class TestCompanyGraphServices:
    """Test Company Graph services."""
    
    @pytest.mark.asyncio
    async def test_storage_service_initialization(self):
        """Test that storage service can be initialized."""
        try:
            from services.company_graph_store import get_company_graph_store
            
            # Should not raise
            store = get_company_graph_store()
            assert store is not None
            
        except ImportError as e:
            pytest.skip(f"Storage service not available: {e}")
    
    @pytest.mark.asyncio
    async def test_company_crud_with_sqlite(self):
        """Test company CRUD operations - skipped as requires specific config."""
        pytest.skip("SQLite CRUD test requires specific configuration")


class TestScannerService:
    """Test scanner service."""
    
    @pytest.mark.asyncio
    async def test_scanner_initialization(self):
        """Test that scanner service can be initialized."""
        try:
            from services.scanner import WebsiteScanner
            
            scanner = WebsiteScanner(company_id="test")
            assert scanner is not None
            assert scanner.company_id == "test"
        except ImportError:
            pytest.skip("Scanner service not available")


class TestSpecialistService:
    """Test specialist service."""
    
    @pytest.mark.asyncio
    async def test_specialist_service_initialization(self):
        """Test that specialist service can be initialized."""
        try:
            from services.specialist import get_specialist_service
            
            service = get_specialist_service()
            assert service is not None
        except ImportError:
            pytest.skip("Specialist service not available")


class TestOnboardingService:
    """Test onboarding service."""
    
    @pytest.mark.asyncio
    async def test_onboarding_service_initialization(self):
        """Test that onboarding service can be initialized."""
        try:
            from services.onboarding import get_onboarding_service

            service = get_onboarding_service()
            assert service is not None
        except ImportError:
            pytest.skip("Onboarding service not available")


class TestMongoStoreExtraFieldTolerance:
    """Regression for the create-company 500.

    ``MongoDBStore.create_company_graph`` writes a ``graph_id`` reference onto
    the *company* document. Because ``Company`` is declared ``extra="forbid"``,
    reading that document back (``get_company`` → ``model_validate``) raised
    ``ValidationError`` — surfaced to users as
    ``Could not create company: Request failed with status code 500`` right after
    BUG-1 unblocked the endpoint. The store must drop persisted bookkeeping
    fields it doesn't model.
    """

    def test_prepare_result_tolerates_persisted_graph_id(self):
        bson = pytest.importorskip("bson")
        try:
            from services.company_graph_store import MongoDBStore
            from models.company_graph import Company
        except (ImportError, ModuleNotFoundError):
            pytest.skip("company graph store not importable")

        store = MongoDBStore()  # no connection; __init__ only nulls handles
        oid = bson.ObjectId()
        doc = {
            "_id": oid,
            "name": "Acme",
            "domain": "acme.com",
            "business_category": "other",
            # bookkeeping field written onto the company doc — not a Company field
            "graph_id": "graph_abc123",
            "updated_at": "2026-05-30T00:00:00",
        }
        company = store._prepare_result(doc, Company)
        assert company is not None
        assert company.id == str(oid)
        assert company.name == "Acme"
        # the extra persisted field must have been dropped, not crash validation
        assert not hasattr(company, "graph_id")

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_mongo_create_company_then_graph_roundtrip(self):
        """End-to-end against the real Mongo (CI service): the exact handler
        sequence create_company → get_or_create_company_graph must not 500."""
        try:
            from services.company_graph import CompanyGraphService
            from services.company_graph_store import CompanyGraphStore
        except (ImportError, ModuleNotFoundError):
            pytest.skip("company graph service not importable")

        # Auto-skip if MongoDB is not reachable (e.g. CI without mongo service)
        import pymongo.errors
        try:
            import pymongo
            _client = pymongo.MongoClient(
                "mongodb://localhost:27017",
                serverSelectionTimeoutMS=2000,
            )
            _client.admin.command("ping")
            _client.close()
        except (pymongo.errors.ServerSelectionTimeoutError, pymongo.errors.ConnectionFailure, Exception):
            pytest.skip("MongoDB not available — skipping roundtrip test")

        svc = None
        company_id = None
        try:
            svc = CompanyGraphService(store=CompanyGraphStore(backend="mongodb"))
            company = await svc.create_company(
                name="RegressionCo", domain="regression.test",
                business_category="other", owner_id="u_regression",
            )
            company_id = company.id
            # This is where the 500 occurred before the fix.
            graph = await svc.get_or_create_company_graph(company.id)
            assert graph is not None
            assert graph.company_id == company.id
            # reading the company back must also validate cleanly
            back = await svc.get_company(company.id)
            assert back is not None and back.id == company.id
        finally:
            if svc and company_id:
                try:
                    await svc.delete_company(company_id)
                except Exception:
                    pass


class TestDetectedSystemPersistence:
    """Regression for the website-scan 500.

    ``POST /api/company/{id}/scan/website`` called ``store.list_detected_systems``
    / ``store.create_detected_system``, but neither method existed on any store —
    so a successful scan that detected systems raised ``AttributeError`` → HTTP
    500 (``Website scan failed: Request failed with status code 500``). These
    methods are now implemented on the dispatcher and both backends.
    """

    def test_store_exposes_detected_system_methods(self):
        try:
            from services.company_graph_store import (
                CompanyGraphStore, MongoDBStore, SQLiteStore,
            )
        except (ImportError, ModuleNotFoundError):
            pytest.skip("company graph store not importable")
        for cls in (CompanyGraphStore, MongoDBStore, SQLiteStore):
            assert hasattr(cls, "create_detected_system"), \
                f"{cls.__name__} is missing create_detected_system"
            assert hasattr(cls, "list_detected_systems"), \
                f"{cls.__name__} is missing list_detected_systems"

    @pytest.mark.asyncio
    async def test_sqlite_detected_system_roundtrip(self, tmp_path):
        try:
            from services.company_graph_store import SQLiteStore
            from models.company_graph import DetectedSystem
        except (ImportError, ModuleNotFoundError):
            pytest.skip("company graph store not importable")

        store = SQLiteStore()
        store._db_path = str(tmp_path / "cg.db")  # isolated temp DB

        ds = DetectedSystem(name="Shopify", system_type="CMS", confidence=0.9)
        await store.create_detected_system(ds, "co_1")

        got = await store.list_detected_systems("co_1")
        assert len(got) == 1
        assert got[0].name == "Shopify"
        assert got[0].confidence == 0.9          # full model preserved via JSON blob
        assert not hasattr(got[0], "company_id")  # company_id is stored on the row, not the model
        # system_type filtering
        assert len(await store.list_detected_systems("co_1", system_type="CMS")) == 1
        assert await store.list_detected_systems("co_1", system_type="CRM") == []
        # scoped to the company
        assert await store.list_detected_systems("other_co") == []

    @pytest.mark.asyncio
    async def test_sqlite_graph_includes_and_cleans_detected_systems(self, tmp_path):
        """get_company_graph must surface persisted detections, and
        delete_company must remove them (no orphan rows)."""
        try:
            from services.company_graph_store import SQLiteStore
            from models.company_graph import Company, DetectedSystem
        except (ImportError, ModuleNotFoundError):
            pytest.skip("company graph store not importable")

        store = SQLiteStore()
        store._db_path = str(tmp_path / "cg.db")

        company = await store.create_company(Company(name="Acme", domain="acme.com"))
        await store.create_detected_system(
            DetectedSystem(name="Shopify", system_type="CMS"), company.id
        )

        graph = await store.get_company_graph(company.id)
        assert graph is not None
        assert [d.name for d in graph.detected_systems] == ["Shopify"]

        # delete_company also removes the company's detected systems
        await store.delete_company(company.id)
        assert await store.list_detected_systems(company.id) == []


class TestGraphEndpointServiceContract:
    """Regression for the `GET /api/company/{id}/graph` 500 (found by the new
    e2e company-lifecycle coverage).

    The endpoint calls
    ``service.get_company_graph(company_id, include_detected_systems=...,
    include_specialists=..., include_workflows=...)`` and
    ``service.calculate_graph_completeness(company_id)``, but the service's
    `get_company_graph` accepted only `company_id` (→ TypeError) and
    `calculate_graph_completeness` didn't exist at all (→ AttributeError) — both
    surfaced as HTTP 500. This guards the exact call signatures the endpoint uses.
    """

    @pytest.mark.asyncio
    async def test_service_graph_signatures_match_endpoint(self, tmp_path):
        try:
            from services.company_graph import CompanyGraphService
            from services.company_graph_store import SQLiteStore
        except (ImportError, ModuleNotFoundError):
            pytest.skip("company graph service not importable")

        store = SQLiteStore()
        store._db_path = str(tmp_path / "cg.db")
        svc = CompanyGraphService(store=store)

        company = await svc.create_company(name="Acme", domain="acme.com", owner_id="u1")

        # Exactly the call the endpoint makes (keyword include_* flags).
        graph = await svc.get_company_graph(
            company_id=company.id,
            include_detected_systems=True,
            include_specialists=True,
            include_workflows=True,
        )
        assert graph is not None

        score = await svc.calculate_graph_completeness(company.id)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestMalformedCompanyId:
    """Regression: GET /api/company/<non-objectid> returned 500 in production
    because MongoDBStore.get_company raised ValueError on invalid ObjectId."""

    def test_mongodb_get_company_returns_none_for_invalid_objectid(self):
        import asyncio
        from services.company_graph_store import MongoDBStore

        store = MongoDBStore()
        result = asyncio.get_event_loop().run_until_complete(
            store.get_company("companies")  # not a valid ObjectId
        )
        assert result is None
