#!/usr/bin/env python3
import re
import sys
from typing import Dict, Tuple

def build_width_map(reference_xml_path: str) -> Dict[Tuple[str, str], str]:
    """
    Very light parser: extract (GroupId, LocalizedString Id) -> Width from the reference xml.
    Uses regex scanning but only reads attributes; robust enough for well-formed inputs.
    """
    with open(reference_xml_path, 'r', encoding='utf-8', newline='') as f:
        ref_text = f.read()

    group_open_re = re.compile(r'<Group\b[^>]*\bId="([^"]+)"[^>]*>', re.DOTALL)
    group_close_re = re.compile(r'</Group>', re.DOTALL)
    ls_tag_re = re.compile(r'<LocalizedString\b[^>]*?/?>', re.DOTALL)

    id_attr_re = re.compile(r'\bId="([^"]*)"')
    width_attr_re = re.compile(r'\bWidth="([^"]*)"')

    # Iterate through tags in order, tracking current group
    token_re = re.compile(r'(' + group_open_re.pattern + r'|' + group_close_re.pattern + r'|' + ls_tag_re.pattern + r')', re.DOTALL)

    current_group = None
    width_map: Dict[Tuple[str, str], str] = {}

    for m in token_re.finditer(ref_text):
        token = m.group(0)
        gopen = group_open_re.match(token)
        if gopen:
            current_group = gopen.group(1)
            continue
        if group_close_re.match(token):
            current_group = None
            continue
        ls = ls_tag_re.match(token)
        if ls and current_group is not None:
            tag = token
            id_m = id_attr_re.search(tag)
            if not id_m:
                continue
            loc_id = id_m.group(1)
            w_m = width_attr_re.search(tag)
            if not w_m:
                continue
            width = w_m.group(1)
            width_map[(current_group, loc_id)] = width

    return width_map

def apply_widths_surgically(source_xml_path: str, width_map: Dict[Tuple[str, str], str], output_path: str):
    """
    Edits only the Width attribute values (or inserts them if missing) for matching
    (GroupId, LocalizedString Id). Everything else is left byte-for-byte the same,
    apart from the replaced/inserted attribute text.
    """
    with open(source_xml_path, 'r', encoding='utf-8', newline='') as f:
        src_text = f.read()

    group_open_re = re.compile(r'<Group\b[^>]*\bId="([^"]+)"[^>]*>', re.DOTALL)
    group_close_re = re.compile(r'</Group>', re.DOTALL)
    ls_tag_re = re.compile(r'<LocalizedString\b[^>]*?/?>', re.DOTALL)

    id_attr_re = re.compile(r'\bId="([^"]*)"')
    width_attr_re = re.compile(r'\bWidth="([^"]*)"')

    token_re = re.compile(r'(' + group_open_re.pattern + r'|' + group_close_re.pattern + r'|' + ls_tag_re.pattern + r')', re.DOTALL)

    out_parts = []
    last_idx = 0
    current_group = None
    updated_count = 0

    for m in token_re.finditer(src_text):
        # Append unchanged content before this token
        out_parts.append(src_text[last_idx:m.start()])
        token = m.group(0)

        gopen = group_open_re.match(token)
        if gopen:
            current_group = gopen.group(1)
            out_parts.append(token)  # unchanged
            last_idx = m.end()
            continue

        if group_close_re.match(token):
            current_group = None
            out_parts.append(token)  # unchanged
            last_idx = m.end()
            continue

        ls = ls_tag_re.match(token)
        if ls and current_group is not None:
            tag = token
            id_m = id_attr_re.search(tag)
            if id_m:
                loc_id = id_m.group(1)
                key = (current_group, loc_id)
                if key in width_map:
                    new_width = width_map[key]

                    # Replace existing Width or insert a new one
                    if width_attr_re.search(tag):
                        # Replace only the value part
                        def _repl(wm):
                            return f'Width="{new_width}"'
                        new_tag = width_attr_re.sub(_repl, tag, count=1)
                    else:
                        # Insert Width="..." before Height= if present, else before the closing '/>' or '>'
                        insert_pos = None
                        height_pos = re.search(r'\bHeight="', tag)
                        if height_pos:
                            insert_pos = height_pos.start()
                            new_tag = tag[:insert_pos] + f'Width="{new_width}" ' + tag[insert_pos:]
                        else:
                            # Find position right before '/>' or '>'
                            close_m = re.search(r'\s*/?>\s*$', tag)
                            if not close_m:
                                new_tag = tag  # fallback, should not happen on well-formed tag
                            else:
                                insert_pos = close_m.start()
                                # preserve any spaces before the closer by adding a leading space
                                new_tag = tag[:insert_pos] + f' Width="{new_width}"' + tag[insert_pos:]
                    tag = new_tag
                    updated_count += 1

            out_parts.append(tag)
            last_idx = m.end()
            continue

        # Fallback: pass token through unchanged
        out_parts.append(token)
        last_idx = m.end()

    # Append the remainder
    out_parts.append(src_text[last_idx:])

    result = ''.join(out_parts)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        f.write(result)

    print(f"Updated {updated_count} width(s). Saved to: {output_path}")

def main():
    if len(sys.argv) != 4:
        print("Usage: python update_widths_preserve.py source.xml reference.xml output.xml")
        sys.exit(1)

    source, reference, output = sys.argv[1], sys.argv[2], sys.argv[3]
    width_map = build_width_map(reference)
    apply_widths_surgically(source, width_map, output)

if __name__ == "__main__":
    main()