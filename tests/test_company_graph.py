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

        try:
            svc = CompanyGraphService(store=CompanyGraphStore(backend="mongodb"))
            company = await svc.create_company(
                name="RegressionCo", domain="regression.test",
                business_category="other", owner_id="u_regression",
            )
            # This is where the 500 occurred before the fix.
            graph = await svc.get_or_create_company_graph(company.id)
            assert graph is not None
            assert graph.company_id == company.id
            # reading the company back must also validate cleanly
            back = await svc.get_company(company.id)
            assert back is not None and back.id == company.id
        finally:
            try:
                await svc.delete_company(company.id)
            except Exception:
                pass
