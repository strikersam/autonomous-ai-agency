import sys
import os
from pathlib import Path
import pytest
from unittest.mock import Mock
from pymongo import MongoClient

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Set environment variable during pytest configuration
def pytest_configure(config):
    os.environ['ADMIN_PASSWORD'] = 'test_password'

@pytest.fixture(autouse=True, scope="session")
def mock_mongo():
    mock_client = Mock(spec=MongoClient)
    mock_db = Mock()
    mock_client.database = Mock(return_value=mock_db)
    mock_client.__getitem__ = Mock(return_value=mock_db)
    mock_db.find_one = Mock(return_value={{'_id': 'testuser', 'name': 'Test User'}})
    from qwen.store import SchedulerStore
    SchedulerStore.client = mock_client
