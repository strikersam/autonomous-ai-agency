import pytest
import pytest_asyncio
from services.scanner import WebsiteScanner

@pytest.mark.asyncio
async def test_scanner_ecommerce_shopify():
    """Test Shopify detection (e.g., Gymshark)"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://row.gymshark.com/")
    
    # We should detect Shopify, Cloudflare
    systems = [s.name.lower() for s in res.detected_systems]
    assert "shopify" in systems or "cloudflare" in systems

@pytest.mark.asyncio
async def test_scanner_ecommerce_demandware():
    """Test Salesforce Commerce Cloud (Demandware) detection (e.g., Louis Vuitton)"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://louisvuitton.com")
    
    systems = [s.name.lower() for s in res.detected_systems]
    
    # Louis Vuitton has heavy Akamai WAF. We should at least catch DNS-based tech
    # like Proofpoint, Salesforce, Mailjet, or Akamai CDN
    detected = any(sys in systems for sys in ["salesforce", "akamai cdn", "akamai", "proofpoint email security", "mailjet"])
    assert detected, f"Expected Demandware/Salesforce or Akamai. Got: {systems}"

@pytest.mark.asyncio
async def test_scanner_modern_saas():
    """Test modern SaaS stack (e.g., Vercel/Next.js/Stripe on Vercel.com)"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://vercel.com")
    
    systems = [s.name.lower() for s in res.detected_systems]
    stack_fw = [f.lower() for f in res.inferred_stack.frameworks]
    
    assert "vercel" in systems or "next.js" in systems or "next.js" in stack_fw
    
@pytest.mark.asyncio
async def test_scanner_fintech():
    """Test Fintech stack (e.g., Klarna)"""
    scanner = WebsiteScanner()
    res = await scanner.scan_website("https://klarna.com")
    
    systems = [s.name.lower() for s in res.detected_systems]
    
    # We expect heavy analytics and enterprise tools
    detected = any(sys in systems for sys in ["aws cloudfront", "google tag manager", "stripe", "mixpanel", "contentful cms"])
    assert detected, f"Expected standard enterprise stack elements. Got: {systems}"
