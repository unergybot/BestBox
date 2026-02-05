"""Tests for hybrid router with secondary domains."""

from agents.router import RouteDecision


def test_route_decision_has_secondary_domains():
    decision = RouteDecision(
        destination="erp_agent",
        secondary_domains=["it_ops"],
        reasoning="Needs policy docs",
    )
    assert decision.secondary_domains == ["it_ops"]


def test_route_decision_empty_secondary():
    decision = RouteDecision(
        destination="crm_agent",
        reasoning="CRM only",
    )
    assert decision.secondary_domains == []
