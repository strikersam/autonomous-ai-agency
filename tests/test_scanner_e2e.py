import pytest
import pytest_asyncio
from services.scanner import WebsiteScanner

@pytest.mark.asyncio
async def test_scanner_tech_platform():
    """Test technology platform detection (e.g., Docker)"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://docker.com")
    
    systems = [s.name.lower() for s in res.detected_systems]
    assert "nginx" in systems or "wordpress" in systems or "google tag manager" in systems

@pytest.mark.asyncio
async def test_scanner_open_source_docs():
    """Test open source documentation detection (e.g., React)"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://react.dev")
    
    systems = [s.name.lower() for s in res.detected_systems]
    
    detected = any(sys in systems for sys in ["vercel", "next.js", "react"])
    assert detected, f"Expected Vercel or Next.js. Got: {systems}"

@pytest.mark.asyncio
async def test_scanner_modern_saas():
    """Test modern SaaS stack"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://vercel.com")
    
    systems = [s.name.lower() for s in res.detected_systems]
    stack_fw = [f.lower() for f in res.inferred_stack.frameworks]
    
    assert "vercel" in systems or "next.js" in systems or "next.js" in stack_fw
    
@pytest.mark.asyncio
async def test_scanner_developer_tools():
    """Test Developer tools stack"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://github.com")
    
    systems = [s.name.lower() for s in res.detected_systems]
    
    # We expect some tracking or standard elements
    detected = any(sys in systems for sys in ["fastly", "aws route 53", "microsoft 365", "salesforce", "google search console"])
    assert detected, f"Expected standard enterprise stack elements. Got: {systems}"
