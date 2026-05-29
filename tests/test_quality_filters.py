"""Tests for stop-slop quality filter."""
from __future__ import annotations

import pytest

from agent.quality_filters import StopSlopFilter, apply_stop_slop_filter


class TestStopSlopFilter:
    """Test suite for StopSlopFilter."""
    
    def test_banned_phrases_detection(self):
        """Test detection of common AI-generated phrases."""
        filter_obj = StopSlopFilter()
        
        text = "As an AI, I can help you with this. Let me explain what this means."
        issues = filter_obj.check_text(text)
        
        assert len(issues) > 0
        # Should detect "As an AI" and "Let me"
        phrases = [issue.text for issue in issues]
        assert any("ai" in phrase.lower() for phrase in phrases)
    
    def test_clean_text_removes_phrases(self):
        """Test that clean_text removes banned phrases."""
        filter_obj = StopSlopFilter()
        
        text = "As an AI, I would like to help. Basically, this is important."
        cleaned = filter_obj.clean_text(text, remove_phrases=True)
        
        # Phrases should be removed
        assert "as an ai" not in cleaned.lower()
        assert "basically" not in cleaned.lower()
        assert len(cleaned) < len(text)
    
    def test_score_text(self):
        """Test scoring of text authenticity."""
        filter_obj = StopSlopFilter()
        
        # AI-heavy text
        ai_text = "As an AI, let me explain. This is clearly important. I can help you with this."
        score = filter_obj.score_text(ai_text)
        
        assert score["total"] <= 50
        assert score["max"] == 50
        assert all(k in score for k in ["directness", "rhythm", "trust", "authenticity", "density"])
        
        # More authentic text
        authentic_text = "Here's how to solve the problem: First, identify the root cause. Then, implement the fix."
        score2 = filter_obj.score_text(authentic_text)
        
        assert score2["total"] > score["total"]  # Should score higher
    
    def test_passive_voice_detection_strict(self):
        """Test passive voice detection in strict mode."""
        filter_obj = StopSlopFilter(strict=True)
        
        text = "The problem was identified by the team."
        issues = filter_obj.check_text(text)
        
        passive_issues = [i for i in issues if i.type == "PASSIVE_VOICE"]
        assert len(passive_issues) > 0
    
    def test_structural_patterns(self):
        """Test detection of structural anti-patterns."""
        filter_obj = StopSlopFilter()
        
        # Test ALL_CAPS emphasis
        text = "This is REALLY important!"
        issues = filter_obj.check_text(text)
        assert any(i.type == "ALL_CAPS" for i in issues)
        
        # Test multiple exclamation marks
        text2 = "Amazing!!"
        issues2 = filter_obj.check_text(text2)
        assert any(i.type == "MULTIPLE_EXCLAMATION" for i in issues2)
    
    def test_apply_stop_slop_filter_score(self):
        """Test convenience function with score action."""
        result = apply_stop_slop_filter("As an AI, I am happy to help!", action="score")
        assert isinstance(result, dict)
        assert "total" in result
        assert "authenticity" in result
    
    def test_apply_stop_slop_filter_clean(self):
        """Test convenience function with clean action."""
        result = apply_stop_slop_filter("Basically, let me help you here.", action="clean")
        assert isinstance(result, str)
        assert "basically" not in result.lower()
        assert "let me" not in result.lower()
    
    def test_apply_stop_slop_filter_check(self):
        """Test convenience function with check action."""
        result = apply_stop_slop_filter("This is obviously important.", action="check")
        assert isinstance(result, list)
        assert len(result) > 0


class TestQualityScoring:
    """Test text quality scoring system."""
    
    def test_low_quality_text_scores_low(self):
        """Text with lots of AI tells should score low."""
        filter_obj = StopSlopFilter()
        
        text = (
            "As an AI, I would like to say that this is clearly very important. "
            "Let me be honest with you: obviously, this is something you really need to understand. "
            "Basically, in essence, we need to push the envelope here."
        )
        
        score = filter_obj.score_text(text)
        assert score["total"] < 35  # Below "needs revision" threshold
    
    def test_high_quality_text_scores_high(self):
        """Clean, direct text should score high."""
        filter_obj = StopSlopFilter()
        
        text = (
            "To solve this problem: "
            "1. Identify the root cause "
            "2. Develop a solution "
            "3. Test the fix thoroughly "
            "4. Deploy to production"
        )
        
        score = filter_obj.score_text(text)
        assert score["total"] > 35


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
