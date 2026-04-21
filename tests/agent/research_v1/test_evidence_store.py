"""Tests for EvidenceStore."""
import pytest

from agent.research_v1.evidence_store import EvidenceStore, normalize_subagent_output
from agent.research_v1.contracts import (
    EvidenceItem,
    AgentRole,
    Direction,
    ClaimType,
    EvidenceImportance,
)


class TestNormalizeStructured:
    """Tests for normalizing structured dict payloads."""

    def setup_method(self):
        self.store = EvidenceStore()

    def test_normalize_dict_with_summary_json(self):
        """Structured payload with summary_json extracts metrics as evidence."""
        payload = {
            "report": "Revenue grew 8% year over year.",
            "summary_json": {
                "revenue_growth": 0.08,
                "pe_ratio": 25.4,
                "direction": "bullish",
                "confidence": 0.82,
            },
        }
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=payload,
        )
        assert len(items) >= 2
        # Check revenue_growth metric extracted
        revenue_items = [i for i in items if "revenue_growth" in i.claim]
        assert len(revenue_items) >= 1

    def test_normalize_dict_with_explicit_claims(self):
        """Payload with explicit claims list extracts each claim."""
        payload = {
            "claims": [
                {
                    "claim": "P/E ratio is below industry average",
                    "value": 18.5,
                    "direction": "bullish",
                    "confidence": 0.8,
                },
                {
                    "claim": "Revenue growth slowing",
                    "value": -0.02,
                    "direction": "bearish",
                    "confidence": 0.6,
                },
            ]
        }
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=payload,
        )
        assert len(items) == 2
        claims = [i.claim for i in items]
        assert any("P/E ratio" in c for c in claims)
        assert any("Revenue growth" in c for c in claims)

    def test_normalize_dict_raw_payload_preserved(self):
        """Raw payload is always preserved in evidence items."""
        payload = {
            "summary_json": {"pe_ratio": 20.0},
            "original_field": "kept",
        }
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.TECHNICAL,
            raw_output=payload,
        )
        for item in items:
            assert "original_field" in item.raw_payload

    def test_normalize_dict_no_invented_fields(self):
        """Normalization does not add fields not present in the payload."""
        payload = {"summary_json": {}}
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=payload,
        )
        # Should still produce at least one item (fallback)
        assert len(items) >= 1
        # The item should not have fabricated metric values
        for item in items:
            if item.value is not None:
                assert isinstance(item.value, (dict, str, int, float, type(None)))

    def test_normalize_string_confidence_in_summary(self):
        """String confidence 'high' in summary_json does not crash."""
        payload = {
            "summary_json": {
                "revenue_growth": 0.1,
                "confidence": "high",
            },
        }
        # Should not raise, should return items
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=payload,
        )
        assert len(items) >= 1
        # confidence should be parsed to a float
        for item in items:
            assert isinstance(item.confidence, float)
            assert 0.0 <= item.confidence <= 1.0

    def test_normalize_string_confidence_low_in_summary(self):
        """String confidence 'low' in summary_json is parsed correctly."""
        payload = {
            "summary_json": {
                "pe_ratio": 30.0,
                "confidence": "low",
            },
        }
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=payload,
        )
        assert len(items) >= 1
        # 'low' should map to ~0.35
        for item in items:
            assert item.confidence < 0.5

    def test_normalize_string_confidence_in_claims(self):
        """String confidence 'medium' in a claim dict does not crash."""
        payload = {
            "claims": [
                {
                    "claim": "P/E ratio is attractive",
                    "value": 18.5,
                    "direction": "bullish",
                    "confidence": "medium",
                },
            ]
        }
        # Should not raise
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=payload,
        )
        assert len(items) == 1
        assert isinstance(items[0].confidence, float)
        # 'medium' should map to ~0.65
        assert 0.5 < items[0].confidence < 0.8

    def test_normalize_mixed_numeric_and_string_confidence(self):
        """Mixed numeric and string confidence values are all parsed safely."""
        payload = {
            "claims": [
                {
                    "claim": "Revenue strong",
                    "value": 0.08,
                    "confidence": "high",  # string
                },
                {
                    "claim": "Debt manageable",
                    "value": 1.5,
                    "confidence": 0.6,  # numeric
                },
            ]
        }
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=payload,
        )
        assert len(items) == 2
        # All should be valid floats in [0,1]
        for item in items:
            assert isinstance(item.confidence, float)
            assert 0.0 <= item.confidence <= 1.0


class TestNormalizeFreeform:
    """Tests for normalizing freeform text payloads."""

    def setup_method(self):
        self.store = EvidenceStore()

    def test_normalize_text_extracts_bullets(self):
        """Bulleted list text is split into individual claim items."""
        text = """
        - Revenue grew 8% year over year
        - P/E ratio is below industry average
        - RSI showing oversold conditions
        """
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=text,
        )
        assert len(items) >= 3
        assert all(isinstance(i, EvidenceItem) for i in items)

    def test_normalize_text_infers_direction(self):
        """Bullish keywords result in BULLISH direction."""
        text = "Strong buy signal. Revenue growing. Positive momentum."
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.TECHNICAL,
            raw_output=text,
        )
        # At least one item should be bullish
        directions = [i.direction for i in items]
        assert Direction.BULLISH in directions

    def test_normalize_text_infers_direction_bearish(self):
        """Bearish keywords result in BEARISH direction."""
        text = "Revenue declining. Debt levels rising. Negative outlook."
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            raw_output=text,
        )
        directions = [i.direction for i in items]
        assert Direction.BEARISH in directions

    def test_normalize_text_preserves_raw_payload(self):
        """Original text is preserved in raw_payload."""
        text = "This is the full analysis report text."
        items = self.store.normalize(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.NEWS,
            raw_output=text,
        )
        for item in items:
            assert "original_text" in item.raw_payload


class TestMixedRoleBatches:
    """Tests for mixed-role evidence batches."""

    def setup_method(self):
        self.store = EvidenceStore()

    def test_mixed_role_evidence_batches(self):
        """Evidence from different roles can coexist in the same batch."""
        fundamentals_payload = {
            "summary_json": {"revenue_growth": 0.08, "direction": "bullish"},
        }
        technical_payload = {
            "summary_json": {"rsi": 35.0, "direction": "bullish"},
        }
        news_payload = {
            "summary_json": {"sentiment": "positive", "direction": "bullish"},
        }

        items = []
        items.extend(
            self.store.normalize(
                "task-1", "sub-1", "AAPL", AgentRole.FUNDAMENTALS, fundamentals_payload
            )
        )
        items.extend(
            self.store.normalize(
                "task-1", "sub-2", "AAPL", AgentRole.TECHNICAL, technical_payload
            )
        )
        items.extend(
            self.store.normalize(
                "task-1", "sub-3", "AAPL", AgentRole.NEWS, news_payload
            )
        )

        roles = {item.agent_role for item in items}
        assert AgentRole.FUNDAMENTALS in roles
        assert AgentRole.TECHNICAL in roles
        assert AgentRole.NEWS in roles

    def test_each_item_has_correct_role(self):
        """Each evidence item carries the role of its source agent."""
        payload = {"summary_json": {"pe_ratio": 20.0}}
        items = self.store.normalize(
            "task-1", "sub-1", "AAPL", AgentRole.FUNDAMENTALS, payload
        )
        for item in items:
            assert item.agent_role == AgentRole.FUNDAMENTALS


class TestConflictDetection:
    """Tests for conflict detection in evidence batches."""

    def setup_method(self):
        self.store = EvidenceStore()

    def test_detect_conflicts_between_opposing_directions(self):
        """Conflicting bullish and bearish items are detected."""
        item1 = EvidenceItem(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue growing",
            direction=Direction.BULLISH,
        )
        item2 = EvidenceItem(
            task_id="task-1",
            subtask_id="sub-2",
            ticker="AAPL",
            agent_role=AgentRole.TECHNICAL,
            claim="RSI showing breakdown",
            direction=Direction.BEARISH,
        )
        conflicts = self.store.detect_conflicts([item1, item2])
        assert len(conflicts) >= 1

    def test_no_conflict_when_directions_agree(self):
        """No conflict reported when directions agree."""
        item1 = EvidenceItem(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue growing",
            direction=Direction.BULLISH,
        )
        item2 = EvidenceItem(
            task_id="task-1",
            subtask_id="sub-2",
            ticker="AAPL",
            agent_role=AgentRole.TECHNICAL,
            claim="Golden cross",
            direction=Direction.BULLISH,
        )
        conflicts = self.store.detect_conflicts([item1, item2])
        assert len(conflicts) == 0

    def test_neutral_does_not_conflict(self):
        """Items with NEUTRAL direction don't trigger conflicts."""
        item1 = EvidenceItem(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue flat",
            direction=Direction.NEUTRAL,
        )
        item2 = EvidenceItem(
            task_id="task-1",
            subtask_id="sub-2",
            ticker="AAPL",
            agent_role=AgentRole.TECHNICAL,
            claim="RSI neutral",
            direction=Direction.NEUTRAL,
        )
        conflicts = self.store.detect_conflicts([item1, item2])
        assert len(conflicts) == 0


class TestMissingFieldDetection:
    """Tests for missing field/signaling in evidence batches."""

    def setup_method(self):
        self.store = EvidenceStore()

    def test_detect_missing_required_roles(self):
        """Missing required roles are reported."""
        items = [
            EvidenceItem(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
            ),
            EvidenceItem(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
            ),
            # NEWS intentionally missing
        ]
        missing = self.store.detect_missing_fields(
            items, ["fundamentals", "technical", "news"]
        )
        assert "news" in missing or AgentRole.NEWS.value in missing

    def test_all_roles_present_no_missing(self):
        """When all required roles present, no missing reported."""
        items = [
            EvidenceItem(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
            ),
            EvidenceItem(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
            ),
            EvidenceItem(
                task_id="task-1",
                subtask_id="sub-3",
                ticker="AAPL",
                agent_role=AgentRole.NEWS,
                claim="News positive",
            ),
        ]
        missing = self.store.detect_missing_fields(
            items, ["fundamentals", "technical", "news"]
        )
        assert len(missing) == 0


class TestConvenienceFunction:
    """Tests for the normalize_subagent_output convenience function."""

    def test_convenience_function_returns_items(self):
        """Convenience function returns a list of EvidenceItems."""
        payload = {"summary_json": {"rsi": 45.0}}
        items = normalize_subagent_output(
            task_id="task-1",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.TECHNICAL,
            raw_output=payload,
        )
        assert isinstance(items, list)
        assert all(isinstance(i, EvidenceItem) for i in items)


class TestErrorHandling:
    """Tests for error handling in the evidence store."""

    def test_unsupported_output_type_raises(self):
        store = EvidenceStore()
        with pytest.raises(ValueError, match="Unsupported output type"):
            store.normalize(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                raw_output=123,  # invalid type
            )
