import re
from dataclasses import dataclass

COMMAND_PATTERNS = [
    (r"分析一下\s+(\w+)", "analyze", {"symbol": lambda m: m.group(1)}),
    (r"看看\s+(\w+)\s*(?:最新报告|报告)", "report", {"symbol": lambda m: m.group(1), "latest": True}),
    (r"筛选\s+(.+?)\s*(?:的|以上的)?(.+)", "filter", {}),
    (r"帮我关注\s+(\w+)", "watchlist", {"action": "add", "symbol": lambda m: m.group(1)}),
    (r"显示我的自选股", "watchlist", {"action": "list"}),
    (r"(\w+)\s*(?:现在什么评级|评级)", "grade", {"symbol": lambda m: m.group(1)}),
    (r"系统状态", "status", {}),
    (r"(/config|配置|查看配置|系统配置)", "config", {}),
    (r"/config\s+set\s+(\w+)\s*=\s*(.+)", "config_set", {}),
    (r"/config\s+get\s+(\w+)", "config_get", {}),
    (r"--help", "help", {}),
]

@dataclass
class ParsedCommand:
    command: str
    args: dict

def parse_natural_language(text: str) -> ParsedCommand:
    """Parse natural language to (command, args).

    Returns ParsedCommand with command name and args dict.
    """
    text = text.strip()

    for pattern, cmd, static_args in COMMAND_PATTERNS:
        match = re.match(pattern, text)
        if match:
            args = dict(static_args)

            # Handle /config set key=value
            if cmd == "config_set":
                args["key"] = match.group(1)
                args["value"] = match.group(2)
            # Handle /config get key
            elif cmd == "config_get":
                args["key"] = match.group(1)
            # Handle lambda extractors for other patterns
            else:
                for key, extractor in static_args.items():
                    if callable(extractor) and extractor.__name__ == '<lambda>':
                        try:
                            args[key] = extractor(match)
                        except:
                            pass
            return ParsedCommand(command=cmd, args=args)

    # Default: treat as analysis request
    return ParsedCommand(command="analyze", args={"symbol": text})

def parse_filter_criteria(criteria_text: str) -> dict:
    """Parse filter criteria like 'sector=tech market_cap>50B grade>=B'"""
    result = {}
    tokens = criteria_text.split()
    for token in tokens:
        if '>=' in token:
            key, val = token.split('>=', 1)
            result[key] = ('gte', val)
        elif '<=' in token:
            key, val = token.split('<=', 1)
            result[key] = ('lte', val)
        elif '>' in token:
            key, val = token.split('>', 1)
            result[key] = ('gt', val)
        elif '<' in token:
            key, val = token.split('<', 1)
            result[key] = ('lt', val)
        elif '=' in token:
            key, val = token.split('=', 1)
            result[key] = ('eq', val)
        else:
            result['_raw'] = result.get('_raw', []) + [token]
    return result