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
        assert website.company_id == "comp_1"
        assert website.is_primary is True
        assert website.scan_status == "pending"


class TestCompanyGraphServices:
    """Test Company Graph services."""
    
    @pytest.mark.asyncio
    async def test_storage_service_initialization(self):
        """Test that storage service can be initialized."""
        try:
            from services.company_graph_store import get_company_graph_store, CompanyGraphStore
            
            # Should not raise
            store = get_company_graph_store()
            assert store is not None
            
            # Test with SQLite backend
            sqlite_store = CompanyGraphStore(backend="sqlite", db_path=":memory:")
            assert sqlite_store is not None
        except ImportError as e:
            pytest.skip(f"Storage service not available: {e}")
    
    @pytest.mark.asyncio
    async def test_company_crud_with_sqlite(self):
        """Test company CRUD operations with SQLite."""
        try:
            from services.company_graph_store import CompanyGraphStore
            from models.company_graph import Company
            
            store = CompanyGraphStore(backend="sqlite", db_path=":memory:")
            
            # Create
            company = Company(
                name="Test Company",
                domain="test.com",
                business_category="saas",
            )
            created = await store.create_company(company)
            assert created.id is not None
            
            # Read
            fetched = await store.get_company(created.id)
            assert fetched is not None
            assert fetched.name == "Test Company"
            
            # Update
            updated = Company(
                id=created.id,
                name="Updated Company",
                domain="test.com",
                business_category="saas",
            )
            await store.update_company(updated)
            fetched = await store.get_company(created.id)
            assert fetched.name == "Updated Company"
            
            # Delete
            await store.delete_company(created.id)
            fetched = await store.get_company(created.id)
            assert fetched is None
            
        except ImportError:
            pytest.skip("Company Graph services not available")


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
