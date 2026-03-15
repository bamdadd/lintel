"""Convert GitHub-flavored Markdown to Telegram HTML."""

from __future__ import annotations

import html
import re


def md_to_telegram_html(text: str) -> str:
    """Convert common Markdown to Telegram-supported HTML.

    Telegram's HTML mode supports: <b>, <i>, <u>, <s>, <code>, <pre>,
    <a href="...">, <blockquote>.

    This handles the most common patterns from LLM output:
    - **bold** → <b>bold</b>
    - *italic* → <i>italic</i>
    - `code` → <code>code</code>
    - ```code blocks``` → <pre>code</pre>
    - [text](url) → <a href="url">text</a>
    - # headings → <b>heading</b>
    - - list items → • list items
    - > blockquotes → <blockquote>text</blockquote>
    """
    # Escape HTML entities first (before we add our own tags)
    # But we need to do this carefully — process code blocks first
    # to avoid double-escaping.

    result = _convert(text)
    return result.strip()


def _is_table_separator(line: str) -> bool:
    """Check if a line is a markdown table separator (|---|---|)."""
    stripped = line.strip()
    return bool(re.match(r"^\|[\s\-:|]+\|$", stripped))


def _parse_table_row(line: str) -> list[str]:
    """Split a markdown table row into cells."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _format_table(table_lines: list[str]) -> list[str]:
    """Convert markdown table lines to a readable Telegram format.

    Renders each data row as a labeled block using the header as keys.
    """
    if not table_lines:
        return []

    headers = _parse_table_row(table_lines[0])

    data_rows: list[list[str]] = []
    for line in table_lines[1:]:
        if _is_table_separator(line):
            continue
        data_rows.append(_parse_table_row(line))

    if not data_rows:
        return [_convert_inline(html.escape(" | ".join(headers)))]

    result: list[str] = []
    for row in data_rows:
        parts: list[str] = []
        for i, cell in enumerate(row):
            if not cell:
                continue
            header = headers[i] if i < len(headers) else ""
            escaped_cell = _convert_inline(html.escape(cell))
            if header:
                escaped_header = html.escape(header)
                parts.append(f"<b>{escaped_header}:</b> {escaped_cell}")
            else:
                parts.append(escaped_cell)
        result.append("\n".join(parts))

    return ["\n\n".join(result)]


def _convert(text: str) -> str:
    lines = text.split("\n")
    output: list[str] = []
    in_code_block = False
    code_block_lines: list[str] = []
    in_blockquote = False
    blockquote_lines: list[str] = []
    in_table = False
    table_lines: list[str] = []

    for line in lines:
        # Code block toggle
        if line.strip().startswith("```"):
            if in_code_block:
                # End code block
                code_content = html.escape("\n".join(code_block_lines))
                output.append(f"<pre>{code_content}</pre>")
                code_block_lines = []
                in_code_block = False
            else:
                # Flush blockquote if open
                if in_blockquote:
                    output.append(f"<blockquote>{chr(10).join(blockquote_lines)}</blockquote>")
                    blockquote_lines = []
                    in_blockquote = False
                in_code_block = True
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Table rows: lines starting and ending with |
        is_table_line = line.strip().startswith("|") and line.strip().endswith("|")
        if is_table_line:
            if in_blockquote:
                output.append(f"<blockquote>{chr(10).join(blockquote_lines)}</blockquote>")
                blockquote_lines = []
                in_blockquote = False
            table_lines.append(line)
            in_table = True
            continue

        if in_table:
            output.extend(_format_table(table_lines))
            table_lines = []
            in_table = False

        # Blockquote
        if line.startswith("> "):
            content = _convert_inline(html.escape(line[2:]))
            blockquote_lines.append(content)
            in_blockquote = True
            continue

        if in_blockquote:
            output.append(f"<blockquote>{chr(10).join(blockquote_lines)}</blockquote>")
            blockquote_lines = []
            in_blockquote = False

        # Headings → bold
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            heading_text = _convert_inline(html.escape(heading_match.group(2)))
            output.append(f"\n<b>{heading_text}</b>")
            continue

        # List items: - or * at start → bullet
        list_match = re.match(r"^(\s*)[-*]\s+(.+)$", line)
        if list_match:
            indent = "  " * (len(list_match.group(1)) // 2)
            item_text = _convert_inline(html.escape(list_match.group(2)))
            output.append(f"{indent}• {item_text}")
            continue

        # Numbered list items
        num_match = re.match(r"^(\s*)\d+\.\s+(.+)$", line)
        if num_match:
            indent = "  " * (len(num_match.group(1)) // 2)
            item_text = _convert_inline(html.escape(num_match.group(2)))
            output.append(f"{indent}{item_text}")
            continue

        # Regular line — escape HTML then convert inline formatting
        escaped = html.escape(line)
        output.append(_convert_inline(escaped))

    # Flush remaining
    if in_code_block:
        code_content = html.escape("\n".join(code_block_lines))
        output.append(f"<pre>{code_content}</pre>")
    if in_blockquote:
        output.append(f"<blockquote>{chr(10).join(blockquote_lines)}</blockquote>")
    if in_table:
        output.extend(_format_table(table_lines))

    return "\n".join(output)


def _convert_inline(text: str) -> str:
    """Convert inline markdown formatting (on already HTML-escaped text)."""
    # Inline code: `code` → <code>code</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Bold: **text** → <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Italic: *text* → <i>text</i> (but not inside bold tags)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Strikethrough: ~~text~~ → <s>text</s>
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # Links: [text](url) — url was HTML-escaped, unescape for href
    def _link_replace(m: re.Match[str]) -> str:
        link_text = m.group(1)
        url = html.unescape(m.group(2))
        return f'<a href="{url}">{link_text}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_replace, text)

    return text
