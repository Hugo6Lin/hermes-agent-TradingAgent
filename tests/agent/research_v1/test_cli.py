import pytest
from agent.research_v1.cli import parse_natural_language, parse_filter_criteria

def test_parse_analyze():
    result = parse_natural_language("分析一下 AAPL")
    assert result.command == "analyze"
    assert result.args["symbol"] == "AAPL"

def test_parse_report():
    result = parse_natural_language("看看 TSLA 报告")
    assert result.command == "report"
    assert result.args["symbol"] == "TSLA"

def test_parse_watchlist_add():
    result = parse_natural_language("帮我关注 NVDA")
    assert result.command == "watchlist"
    assert result.args["action"] == "add"
    assert result.args["symbol"] == "NVDA"

def test_parse_watchlist_list():
    result = parse_natural_language("显示我的自选股")
    assert result.command == "watchlist"
    assert result.args["action"] == "list"

def test_parse_grade():
    result = parse_natural_language("TSLA 现在什么评级")
    assert result.command == "grade"
    assert result.args["symbol"] == "TSLA"

def test_parse_status():
    result = parse_natural_language("系统状态怎么样")
    assert result.command == "status"

def test_parse_help():
    result = parse_natural_language("--help")
    assert result.command == "help"

def test_parse_default():
    result = parse_natural_language("UNKNOWN COMMAND")
    assert result.command == "analyze"

def test_parse_filter_criteria():
    result = parse_filter_criteria("sector=tech market_cap>50B grade>=B")
    assert result["sector"] == ("eq", "tech")
    assert result["market_cap"] == ("gt", "50B")
    assert result["grade"] == ("gte", "B")