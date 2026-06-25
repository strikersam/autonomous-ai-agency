"""Tests for quality checker (stop-slop inspired)"""

import pytest

from agents.quality_checker import AITellType, StopSlopChecker


class TestStopSlopChecker:
    """Test AI tell detection and removal"""

    def test_detects_throat_clearing(self):
        """Should detect throat-clearing phrases"""
        checker = StopSlopChecker()
        
        text = "It's important to note that this is a feature."
        issues = checker.check_text(text)
        
        assert len(issues) > 0
        assert issues[0].tell_type == AITellType.THROAT_CLEARING

    def test_detects_multiple_throat_clearing(self):
        """Should detect multiple throat-clearing phrases"""
        checker = StopSlopChecker()
        
        text = """
        It's worth noting that this matters.
        As you may know, this is important.
        """
        issues = checker.check_text(text)
        
        throat_clearing_issues = [
            i for i in issues if i.tell_type == AITellType.THROAT_CLEARING
        ]
        assert len(throat_clearing_issues) >= 2

    def test_detects_emphasis_crutches(self):
        """Should detect weak emphasis adverbs"""
        checker = StopSlopChecker()
        
        text = "This is really important and truly significant."
        issues = checker.check_text(text)
        
        crutch_issues = [
            i for i in issues if i.tell_type == AITellType.EMPHASIS_CRUTCH
        ]
        assert len(crutch_issues) >= 2

    def test_detects_jargon(self):
        """Should detect business jargon"""
        checker = StopSlopChecker()
        
        text = "We need to leverage synergy and move forward with this paradigm shift."
        issues = checker.check_text(text)
        
        jargon_issues = [i for i in issues if i.tell_type == AITellType.JARGON]
        assert len(jargon_issues) >= 2

    def test_detects_meta_commentary(self):
        """Should detect meta-commentary"""
        checker = StopSlopChecker()
        
        text = "The following code demonstrates how to implement this."
        issues = checker.check_text(text)
        
        meta_issues = [i for i in issues if i.tell_type == AITellType.META_COMMENTARY]
        assert len(meta_issues) > 0

    def test_detects_wh_starters(self):
        """Should detect Wh-sentence starters"""
        checker = StopSlopChecker()
        
        text = """
        What does this function do?
        Why should we use it?
        How do we call it?
        """
        issues = checker.check_text(text)
        
        wh_issues = [i for i in issues if i.tell_type == AITellType.WH_STARTER]
        assert len(wh_issues) >= 2

    def test_cleans_throat_clearing(self):
        """Should remove throat-clearing phrases"""
        checker = StopSlopChecker()
        
        text = "It's important to note that this works well."
        cleaned = checker.clean_text(text)
        
        assert "It's important to note" not in cleaned
        assert "this works well" in cleaned

    def test_cleans_emphasis_crutches(self):
        """Should remove emphasis crutches"""
        checker = StopSlopChecker()
        
        text = "This is really important and very useful."
        cleaned = checker.clean_text(text)
        
        assert "really" not in cleaned
        assert "very" not in cleaned
        assert "important" in cleaned
        assert "useful" in cleaned

    def test_cleans_removes_double_spaces(self):
        """Should clean up extra spaces after removal"""
        checker = StopSlopChecker()
        
        text = "This is  really  important."  # Double spaces from removals
        cleaned = checker.clean_text(text)
        
        assert "  " not in cleaned

    def test_case_insensitive_detection(self):
        """Should detect phrases case-insensitively"""
        checker = StopSlopChecker()
        
        text = "IT'S IMPORTANT TO NOTE THAT this works."
        issues = checker.check_text(text)
        
        assert any(i.tell_type == AITellType.THROAT_CLEARING for i in issues)

    def test_no_issues_on_clean_text(self):
        """Should return no issues for clean text"""
        checker = StopSlopChecker()
        
        text = "This function validates user input and returns a boolean."
        issues = checker.check_text(text)
        
        assert len(issues) == 0

    def test_report_format(self):
        """Should format report correctly"""
        checker = StopSlopChecker()
        
        text = "It's important to note that this is really important."
        issues = checker.check_text(text)
        report = checker.report(issues)
        
        assert "⚠️" in report or "✓" in report
        assert str(len(issues)) in report

    def test_report_empty(self):
        """Should report success on clean text"""
        checker = StopSlopChecker()
        
        text = "Clean prose with no tells."
        issues = checker.check_text(text)
        report = checker.report(issues)
        
        assert "✓" in report

    def test_strict_mode_passive_voice(self):
        """Strict mode should detect passive voice"""
        checker_normal = StopSlopChecker(strict=False)
        checker_strict = StopSlopChecker(strict=True)
        
        text = "The function is called by the user."
        
        issues_normal = checker_normal.check_text(text)
        issues_strict = checker_strict.check_text(text)
        
        # Strict mode should find more issues
        assert len(issues_strict) >= len(issues_normal)

    def test_multiple_tell_types(self):
        """Should detect multiple types of tells in one text"""
        checker = StopSlopChecker()
        
        text = """
        It's important to note that this is really important.
        The following code demonstrates how to leverage synergy.
        """
        issues = checker.check_text(text)
        
        tell_types = {i.tell_type for i in issues}
        
        # Should detect at least throat clearing and emphasis
        assert AITellType.THROAT_CLEARING in tell_types
        assert AITellType.EMPHASIS_CRUTCH in tell_types

    def test_suggestions_provided(self):
        """Issues should have helpful suggestions"""
        checker = StopSlopChecker()
        
        text = "It's important to note that this matters."
        issues = checker.check_text(text)
        
        for issue in issues:
            assert issue.suggestion is not None
            assert len(issue.suggestion) > 0
