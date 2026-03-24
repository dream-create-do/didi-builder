"""
dede_engine.py — DeDe Course Builder Engine v4.0
==================================================
Reads an original IMSCC + MeMe's GMO document + style selection.
Applies structural changes programmatically, content changes via LLM.

Supported action types from MeMe's Change Order:
  UPDATE_GRADING    — rebuild assignment groups XML (no LLM)
  ADD_RUBRIC        — add rubric criteria to rubrics.xml (no LLM)
  RENAME_ITEMS      — batch find/replace on page/assignment text (no LLM)
  PUBLISH_PAGE      — move unpublished page to published state (no LLM)
  REWRITE_CONTENT   — modify existing page/assignment content (LLM)
  CREATE_PAGE       — create a new wiki page (LLM)
  CREATE_ASSIGNMENT — create a new assignment with settings (LLM)
  CREATE_SECTION    — insert new section into existing page (LLM)
"""

import re
import os
import io
import uuid
import hashlib
import zipfile
from datetime import datetime

try:
    from style_templates import render_page, STYLES
except ImportError:
    STYLES = {'none': 'No Styling (Plain HTML)'}
    def render_page(style, page_type, data):
        return None


# ─────────────────────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────────────────────

def strip_html(html):
    html = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', html)
    for e, c in [('&nbsp;',' '),('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"')]:
        text = text.replace(e, c)
    return re.sub(r'\s+', ' ', text).strip()

def make_id(seed=None):
    h = hashlib.md5(str(seed).encode()).hexdigest() if seed else uuid.uuid4().hex
    return f"g{h}"

def xml_escape(text):
    if not text: return ''
    return str(text).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return re.sub(r'-+', '-', text)[:60]

CANVAS_NS = 'http://canvas.instructure.com/xsd/cccv1p0'


# ─────────────────────────────────────────────────────────────
#  IMSCC READER
# ─────────────────────────────────────────────────────────────

def read_imscc(file_bytes):
    """Read IMSCC into dict of {path: bytes} + parsed metadata."""
    course = {
        'files': {},
        'identity': {},
        'modules': [],
        'assignments': {},
        'grading_groups': [],
        'wiki_pages': {},
        'page_types': {},
    }

    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as z:
        for name in z.namelist():
            course['files'][name] = z.read(name)

    course['identity'] = _parse_identity(course)
    course['modules'] = _parse_modules(course)
    course['grading_groups'] = _parse_grading(course)
    course['wiki_pages'] = _parse_wiki_pages(course)
    course['assignments'] = _parse_assignments(course)
    course['page_types'] = _classify_pages(course)
    return course


def _parse_identity(course):
    xml = course['files'].get('course_settings/course_settings.xml', b'').decode('utf-8', errors='ignore')
    identity = {}
    for tag, key in [('title','title'),('course_code','code'),('start_at','start_date'),('conclude_at','end_date')]:
        m = re.search(rf'<{tag}>(.+?)</{tag}>', xml, re.DOTALL)
        if m: identity[key] = strip_html(m.group(1)).strip()
    return identity

def _parse_modules(course):
    xml = course['files'].get('course_settings/module_meta.xml', b'').decode('utf-8', errors='ignore')
    modules = []
    for block in re.split(r'<module\s+identifier=[^>]+>', xml)[1:]:
        t = re.search(r'<title>(.+?)</title>', block, re.DOTALL)
        p = re.search(r'<position>(.+?)</position>', block, re.DOTALL)
        s = re.search(r'<workflow_state>(.+?)</workflow_state>', block, re.DOTALL)
        items = []
        for ib in re.split(r'<item\s+identifier=[^>]+>', block)[1:]:
            it = re.search(r'<title>(.+?)</title>', ib, re.DOTALL)
            ct = re.search(r'<content_type>(.+?)</content_type>', ib, re.DOTALL)
            ref = re.search(r'<identifierref>(.+?)</identifierref>', ib, re.DOTALL)
            if it:
                items.append({'title': strip_html(it.group(1)).strip(),
                              'type': strip_html(ct.group(1)).strip() if ct else '',
                              'ref': ref.group(1).strip() if ref else ''})
        modules.append({
            'title': strip_html(t.group(1)).strip() if t else 'Untitled',
            'position': p.group(1).strip() if p else '0',
            'state': s.group(1).strip() if s else 'active',
            'items': items})
    return modules

def _parse_grading(course):
    xml = course['files'].get('course_settings/assignment_groups.xml', b'').decode('utf-8', errors='ignore')
    groups = []
    for block in re.split(r'<assignmentGroup\s+identifier=[^>]+>', xml)[1:]:
        t = re.search(r'<title>(.+?)</title>', block, re.DOTALL)
        w = re.search(r'<group_weight>(.+?)</group_weight>', block, re.DOTALL)
        name = strip_html(t.group(1)).strip() if t else 'Unnamed'
        try: weight = float(w.group(1).strip()) if w else 0.0
        except ValueError: weight = 0.0
        groups.append({'name': name, 'weight': weight})
    return groups

def _parse_wiki_pages(course):
    pages = {}
    for path, content in course['files'].items():
        if path.startswith('wiki_content/') and path.endswith('.html'):
            page_name = path.replace('wiki_content/', '').replace('.html', '')
            pages[page_name] = content.decode('utf-8', errors='ignore')
    return pages

def _parse_assignments(course):
    assignments = {}
    for path, content in course['files'].items():
        if path.endswith('/assignment_settings.xml') and 'course_settings' not in path:
            folder_id = path.split('/')[0]
            xml = content.decode('utf-8', errors='ignore')
            title_m = re.search(r'<title>(.+?)</title>', xml, re.DOTALL)
            pts_m = re.search(r'<points_possible>(.+?)</points_possible>', xml, re.DOTALL)
            sub_m = re.search(r'<submission_types>(.+?)</submission_types>', xml, re.DOTALL)
            title = strip_html(title_m.group(1)).strip() if title_m else folder_id
            html_content = ''
            for fp in course['files']:
                if fp.startswith(f'{folder_id}/') and fp.endswith('.html'):
                    html_content = course['files'][fp].decode('utf-8', errors='ignore')
                    break
            assignments[title] = {
                'folder_id': folder_id,
                'points': pts_m.group(1).strip() if pts_m else '0',
                'sub_type': strip_html(sub_m.group(1)).strip() if sub_m else '',
                'instructions_html': html_content,
                'instructions_text': strip_html(html_content)}
    return assignments

def _classify_pages(course):
    types = {}
    for page_name in course['wiki_pages']:
        nl = page_name.lower()
        if any(k in nl for k in ['welcome','start-here','getting-started','homepage','read-me-first']):
            types[page_name] = 'homepage'
        elif any(k in nl for k in ['overview','introduction','module-overview']):
            types[page_name] = 'overview'
        else:
            types[page_name] = 'content'
    return types


# ─────────────────────────────────────────────────────────────
#  GMO PARSER — reads MeMe's full output document
# ─────────────────────────────────────────────────────────────

def parse_gmo(text):
    """Parse MeMe's GMO into change list + full document for LLM context."""
    changes = []
    if not text or not text.strip():
        return changes, text

    # Find the Change Order section (## CHANGE: blocks)
    blocks = re.split(r'^## CHANGE:\s*', text, flags=re.MULTILINE)

    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue

        title = lines[0].strip()
        change = {'title': title, 'action': '', 'target': '', 'guidance': '',
                  'raw_data': '', 'extra': {}}
        in_guidance = False
        in_data = False
        data_lines = []

        for line in lines[1:]:
            s = line.strip()
            if s.startswith('Action:'):
                change['action'] = s.replace('Action:', '').strip().upper().replace(' ', '_')
                in_guidance = in_data = False
            elif s.startswith('Target:'):
                change['target'] = s.replace('Target:', '').strip()
            elif s.startswith('Page Name:'):
                change['extra']['page_name'] = s.replace('Page Name:', '').strip()
            elif s.startswith('Assignment Name:'):
                change['extra']['assignment_name'] = s.replace('Assignment Name:', '').strip()
            elif s.startswith('Assignment Type:'):
                change['extra']['assignment_type'] = s.replace('Assignment Type:', '').strip()
            elif s.startswith('Points:'):
                change['extra']['points'] = s.replace('Points:', '').strip()
            elif s.startswith('Grading Group:'):
                change['extra']['grading_group'] = s.replace('Grading Group:', '').strip()
            elif s.startswith('Rubric:'):
                change['extra']['rubric'] = s.replace('Rubric:', '').strip()
            elif s.startswith('Position:'):
                change['extra']['position'] = s.replace('Position:', '').strip()
            elif s.startswith('Due:'):
                change['extra']['due'] = s.replace('Due:', '').strip()
            elif s.startswith('Notes:'):
                change['extra']['notes'] = s.replace('Notes:', '').strip()
            elif s.startswith('QM Standards:'):
                change['extra']['qm_standards'] = s.replace('QM Standards:', '').strip()
            elif s.startswith('Guidance:'):
                change['guidance'] = s.replace('Guidance:', '').strip().lstrip('|').strip()
                in_guidance = True
                in_data = False
            elif s.startswith('Data:') or s.startswith('Criteria:') or s.startswith('Order:'):
                in_data = True
                in_guidance = False
            elif s == '---':
                break
            elif in_guidance:
                change['guidance'] += '\n' + s
            elif in_data:
                data_lines.append(s)

        change['guidance'] = change['guidance'].strip()
        change['raw_data'] = '\n'.join(data_lines).strip()

        # Parse table data if present
        if change['raw_data'] and '|' in change['raw_data']:
            change['table'] = _parse_md_table(change['raw_data'])

        changes.append(change)

    return changes, text


def _parse_md_table(text):
    rows = []
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2: return rows
    header_line = None
    data_start = 0
    for i, line in enumerate(lines):
        if '|' in line and not re.match(r'^[\|\s\-:]+$', line):
            header_line = line
            data_start = i + 1
            break
    if not header_line: return rows
    headers = [h.strip() for h in header_line.split('|') if h.strip()]
    for line in lines[data_start:]:
        if re.match(r'^[\|\s\-:]+$', line): continue
        cells = [c.strip() for c in line.split('|') if c.strip()]
        if len(cells) >= len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


# ─────────────────────────────────────────────────────────────
#  STRUCTURAL CHANGES (no LLM)
# ─────────────────────────────────────────────────────────────

def apply_structural_changes(course, changes):
    """Apply changes that don't need AI."""
    log = []
    for change in changes:
        action = change['action']

        if action == 'UPDATE_GRADING':
            _apply_grading(course, change)
            log.append(f"✅ Updated grading structure")

        elif action == 'ADD_RUBRIC':
            _apply_rubric(course, change)
            log.append(f"✅ Added rubric: {change['target']}")

        elif action == 'RENAME_ITEMS':
            count = _apply_renames(course, change)
            log.append(f"✅ Renamed {count} items across course")

        elif action == 'PUBLISH_PAGE':
            _apply_publish(course, change)
            log.append(f"✅ Published page: {change.get('extra',{}).get('page_name', change['target'])}")

    return log


def _apply_grading(course, change):
    rows = change.get('table', [])
    if not rows: return
    lines = [f'<?xml version="1.0" encoding="UTF-8"?>\n',
             f'<assignmentGroups xmlns="{CANVAS_NS}">']
    for i, row in enumerate(rows, 1):
        name = row.get('Group Name', f'Group {i}')
        weight = row.get('Weight (%)', '0').replace('%', '').strip()
        drop = row.get('Drop Lowest', '0')
        gid = make_id(name)
        lines.append(f'  <assignmentGroup identifier="{gid}">')
        lines.append(f'    <title>{xml_escape(name)}</title>')
        lines.append(f'    <position>{i}</position>')
        lines.append(f'    <group_weight>{weight}</group_weight>')
        try:
            if int(drop) > 0:
                lines.append(f'    <rules><rule><drop_type>drop_lowest</drop_type><drop_count>{drop}</drop_count></rule></rules>')
        except (ValueError, TypeError): pass
        lines.append(f'  </assignmentGroup>')
    lines.append('</assignmentGroups>')
    course['files']['course_settings/assignment_groups.xml'] = '\n'.join(lines).encode('utf-8')


def _apply_rubric(course, change):
    rows = change.get('table', [])
    if not rows: return
    target = change.get('target', 'Unknown')
    rubric_lines = ['<rubric>', f'<title>{xml_escape(target)} Rubric</title>']
    total_pts = sum(float(r.get('Points', '0')) for r in rows if r.get('Points','').replace('.','').isdigit())
    rubric_lines.append(f'<points_possible>{total_pts}</points_possible>')
    rubric_lines.append('<criteria>')
    for row in rows:
        crit = row.get('Criterion', 'Unnamed')
        pts = row.get('Points', '0')
        ratings_raw = row.get('Ratings', '')
        rubric_lines.append('<criterion>')
        rubric_lines.append(f'<description>{xml_escape(crit)}</description>')
        rubric_lines.append(f'<long_description></long_description>')
        rubric_lines.append(f'<points>{pts}</points>')
        rubric_lines.append('<ratings>')
        if ratings_raw:
            for rs in ratings_raw.split(';'):
                rm = re.match(r'(.+?)\s*\((\d+\.?\d*)\)\s*:\s*(.*)', rs.strip())
                if rm:
                    rid = make_id(f"rat_{crit}_{rm.group(1)}")
                    rubric_lines.append(f'<rating><id>{rid}</id><description>{xml_escape(rm.group(1).strip())}</description><long_description>{xml_escape(rm.group(3).strip())}</long_description><points>{rm.group(2)}</points></rating>')
        else:
            rubric_lines.append(f'<rating><id>{make_id("full")}</id><description>Full Marks</description><long_description></long_description><points>{pts}</points></rating>')
            rubric_lines.append(f'<rating><id>{make_id("zero")}</id><description>No Marks</description><long_description></long_description><points>0.0</points></rating>')
        rubric_lines.append('</ratings></criterion>')
    rubric_lines.append('</criteria></rubric>')
    new_rubric = '\n'.join(rubric_lines)
    rubrics_xml = course['files'].get('course_settings/rubrics.xml', b'').decode('utf-8', errors='ignore')
    if '</rubrics>' in rubrics_xml:
        rubrics_xml = rubrics_xml.replace('</rubrics>', f'{new_rubric}\n</rubrics>')
    else:
        rubrics_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<rubrics xmlns="{CANVAS_NS}">\n{new_rubric}\n</rubrics>'
    course['files']['course_settings/rubrics.xml'] = rubrics_xml.encode('utf-8')


def _apply_renames(course, change):
    table = change.get('table', [])
    count = 0
    for row in table:
        find_text = row.get('Find (Header Text)', row.get('Find', ''))
        replace_text = row.get('Replace With', row.get('Replace', ''))
        if not find_text or not replace_text: continue
        # Apply to all HTML files and module_meta.xml
        for path in list(course['files'].keys()):
            if path.endswith('.html') or path.endswith('.xml'):
                content = course['files'][path]
                if isinstance(content, bytes):
                    text = content.decode('utf-8', errors='ignore')
                else:
                    text = content
                if find_text in text:
                    text = text.replace(find_text, replace_text)
                    course['files'][path] = text.encode('utf-8') if isinstance(content, bytes) else text
                    count += 1
    return count


def _apply_publish(course, change):
    page_name = change.get('extra', {}).get('page_name', '')
    if not page_name: return
    # Check if the page exists as unpublished in module_meta
    meta_path = 'course_settings/module_meta.xml'
    if meta_path in course['files']:
        xml = course['files'][meta_path].decode('utf-8', errors='ignore')
        # Find the item with this page reference and change state to active
        pattern = rf'(<item[^>]*>.*?{re.escape(page_name)}.*?<workflow_state>)unpublished(</workflow_state>)'
        new_xml = re.sub(pattern, r'\1active\2', xml, flags=re.DOTALL)
        course['files'][meta_path] = new_xml.encode('utf-8')


# ─────────────────────────────────────────────────────────────
#  STYLE ENGINE
# ─────────────────────────────────────────────────────────────

def apply_style(course, style):
    if style == 'none': return []
    log = []
    for page_name, html in list(course['wiki_pages'].items()):
        page_type = course['page_types'].get(page_name, 'content')
        if page_type in ('homepage', 'overview'):
            inner = strip_html(html)
            mod_num_m = re.search(r'(\d+)', page_name)
            data = {
                'course_code': course['identity'].get('code', ''),
                'course_title': course['identity'].get('title', ''),
                'description': inner[:500],
                'clos': [], 'instructor_name': '', 'instructor_info': '',
                'module_number': mod_num_m.group(1) if mod_num_m else '',
                'module_title': page_name.replace('-', ' ').title(),
                'overview': inner[:500], 'mlos': [], 'materials': [],
                'assignments': [], 'discussion': '',
            }
            new_html = render_page(style, page_type, data)
            if new_html:
                course['files'][f'wiki_content/{page_name}.html'] = new_html.encode('utf-8')
                log.append(f"🎨 Restyled {page_type}: {page_name}")
    for aname, adata in course['assignments'].items():
        folder = adata['folder_id']
        for fp in list(course['files'].keys()):
            if fp.startswith(f'{folder}/') and fp.endswith('.html'):
                data = {'title': aname, 'instructions': adata.get('instructions_text',''),
                        'points': adata.get('points',''), 'due': '', 'sub_type': adata.get('sub_type',''),
                        'purpose': '', 'rubric_html': ''}
                new_html = render_page(style, 'assignment', data)
                if new_html:
                    course['files'][fp] = new_html.encode('utf-8')
                    log.append(f"🎨 Restyled assignment: {aname}")
                break
    return log


# ─────────────────────────────────────────────────────────────
#  LLM CONTENT ENGINE
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
#  REPLACE/WITH EXTRACTION — direct string ops, no LLM
# ─────────────────────────────────────────────────────────────

def extract_replace_pairs(gmo_text):
    """
    Scan the full GMO (Parts 1 & 2) for REPLACE/WITH pairs.
    Returns a list of {old: str, new: str, section: str} dicts.
    
    Handles three MeMe patterns:
      1. Inline backtick:  **REPLACE:** `old` / **WITH:** `new`
      2. Code fence:       **REPLACE:** ``` old ``` / **WITH:** ``` new ```
      3. Inline text:      **REPLACE:** `old` / **WITH:** `new`
    """
    pairs = []
    
    # Pattern 1: Inline backtick pairs on same or adjacent lines
    #   **REPLACE:** `old text`
    #   **WITH:** `new text`
    for m in re.finditer(
        r'\*\*REPLACE:\*\*\s*`([^`]+)`\s*\n\s*\*\*WITH:\*\*\s*`([^`]+)`',
        gmo_text
    ):
        pairs.append({'old': m.group(1).strip(), 'new': m.group(2).strip(), 'type': 'inline'})
    
    # Pattern 2: Code fence blocks
    #   **REPLACE:**
    #   ```
    #   old text (multiline)
    #   ```
    #   **WITH:**
    #   ```
    #   new text (multiline)
    #   ```
    for m in re.finditer(
        r'\*\*REPLACE:\*\*\s*\n\s*```\n(.*?)```\s*\n\s*\*\*WITH:\*\*\s*\n\s*```\n(.*?)```',
        gmo_text,
        re.DOTALL
    ):
        old_text = m.group(1).strip()
        new_text = m.group(2).strip()
        if old_text and new_text:
            pairs.append({'old': old_text, 'new': new_text, 'type': 'block'})
    
    # Pattern 3: Also REPLACE: ``` old ``` / **WITH:** ``` new ```
    for m in re.finditer(
        r'\*\*REPLACE[:\*]+\s*\n\s*```\n(.*?)```\s*\n\s*\*\*WITH:\*\*\s*\n\s*```\n(.*?)```',
        gmo_text,
        re.DOTALL
    ):
        old_text = m.group(1).strip()
        new_text = m.group(2).strip()
        # Avoid duplicates from Pattern 2
        if not any(p['old'] == old_text and p['new'] == new_text for p in pairs):
            pairs.append({'old': old_text, 'new': new_text, 'type': 'block'})
    
    return pairs


def _normalize_for_match(text):
    """Normalize whitespace for fuzzy matching."""
    return re.sub(r'\s+', ' ', text).strip()


def apply_string_replacements(course, changes, replace_pairs):
    """
    Pre-pass: apply REPLACE/WITH pairs as direct string operations.
    Returns (log, handled_indices) where handled_indices are change indices
    that were fully resolved without LLM.
    """
    log = []
    handled = set()
    
    if not replace_pairs:
        return log, handled
    
    # For each REWRITE_CONTENT change, check if its target file contains
    # any of the REPLACE pairs' old text
    rewrite_changes = [(i, c) for i, c in enumerate(changes) 
                       if c['action'] == 'REWRITE_CONTENT']
    
    for idx, change in rewrite_changes:
        target_lower = change['target'].lower()
        applied_count = 0
        
        # Find matching files
        target_files = []
        for page_name, html in course['wiki_pages'].items():
            if target_lower in page_name.lower() or page_name.lower() in target_lower:
                target_files.append(('wiki', page_name, f'wiki_content/{page_name}.html'))
        for aname, adata in course['assignments'].items():
            if target_lower in aname.lower() or aname.lower() in target_lower:
                folder = adata['folder_id']
                for fp in course['files']:
                    if fp.startswith(f'{folder}/') and fp.endswith('.html'):
                        target_files.append(('assign', aname, fp))
        
        if not target_files:
            continue
        
        for file_type, name, file_path in target_files:
            content = course['files'].get(file_path, b'')
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')
            
            original_content = content
            
            for pair in replace_pairs:
                old_text = pair['old']
                new_text = pair['new']
                
                # Try exact match first
                if old_text in content:
                    content = content.replace(old_text, new_text, 1)
                    applied_count += 1
                    continue
                
                # Try normalized match (collapse whitespace)
                norm_old = _normalize_for_match(old_text)
                norm_content = _normalize_for_match(content)
                if norm_old in norm_content:
                    # Find the actual span in original content
                    # Build a regex from the normalized old text
                    escaped = re.escape(norm_old)
                    # Allow flexible whitespace between words
                    flex_pattern = re.sub(r'\\ ', r'\\s+', escaped)
                    m = re.search(flex_pattern, content, re.DOTALL)
                    if m:
                        content = content[:m.start()] + new_text + content[m.end():]
                        applied_count += 1
            
            if content != original_content:
                course['files'][file_path] = content.encode('utf-8')
                if file_type == 'wiki':
                    course['wiki_pages'][name] = content
                log.append(f"🔄 String replace ({applied_count} subs): {change['title']}")
                
                # Mark as handled if we applied at least one replacement
                handled.add(idx)
    
    return log, handled


LLM_ACTIONS = {'CREATE_PAGE', 'REWRITE_CONTENT', 'CREATE_ASSIGNMENT', 'CREATE_SECTION'}

def apply_content_changes(course, changes, full_gmo_text, api_key, progress_callback=None, handled_indices=None):
    """Apply LLM-powered changes. Skips indices already handled by string replacement."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    log = []
    handled_indices = handled_indices or set()
    content_changes = [(i, c) for i, c in enumerate(changes) if c['action'] in LLM_ACTIONS and i not in handled_indices]

    # Truncate GMO to fit context (keep first 80K chars — covers Parts 1 & 2)
    gmo_context = full_gmo_text[:80000]

    for j, (idx, change) in enumerate(content_changes):
        if progress_callback:
            progress_callback(f"AI processing ({j+1}/{len(content_changes)}): {change['title'][:60]}")

        try:
            if change['action'] == 'CREATE_PAGE':
                html = _llm_create_page(client, course, change, gmo_context)
                if html:
                    pname = change.get('extra',{}).get('page_name', '') or slugify(change['target'])
                    course['files'][f'wiki_content/{pname}.html'] = html.encode('utf-8')
                    course['wiki_pages'][pname] = html
                    log.append(f"📝 Created page: {change['title']}")

            elif change['action'] == 'CREATE_ASSIGNMENT':
                result = _llm_create_assignment(client, course, change, gmo_context)
                if result:
                    log.append(f"📝 Created assignment: {change['extra'].get('assignment_name', change['title'])}")

            elif change['action'] == 'CREATE_SECTION':
                html = _llm_create_section(client, course, change, gmo_context)
                if html:
                    log.append(f"📝 Added section to: {change['target']}")

            elif change['action'] == 'REWRITE_CONTENT':
                result = _llm_rewrite(client, course, change, gmo_context)
                if result:
                    log.append(f"📝 Rewrote: {change['title']}")
                else:
                    log.append(f"⚠️ Could not find target for: {change['title']}")

        except Exception as e:
            log.append(f"❌ Error on {change['title']}: {str(e)[:100]}")

    return log


def _build_llm_prompt(course, change, gmo_context, task_description, current_content=''):
    """Build a standardized prompt for DeDe's LLM calls."""
    return f"""You are DeDe, a Canvas course builder. You are implementing changes from MeMe's consultation.

COURSE: {course['identity'].get('title', 'Unknown')} ({course['identity'].get('code', '')})

TASK: {task_description}

CHANGE ORDER ENTRY:
Title: {change['title']}
Action: {change['action']}
Target: {change['target']}
Guidance: {change['guidance']}

{f'CURRENT CONTENT OF TARGET:{chr(10)}{current_content[:3000]}' if current_content else ''}

MEME'S FULL CONSULTATION (reference for cross-references like "Part 2 Fix 2.2"):
{gmo_context}

RULES:
- Output ONLY the HTML content (no <html>, <head>, <body> tags)
- Follow MeMe's guidance precisely — use the exact replacement text from Parts 1 & 2 when referenced
- If MeMe wrote specific text with REPLACE/WITH blocks, use that EXACT text
- Use semantic HTML: <h2>, <h3>, <p>, <ul>, <li>
- Do not add DesignPlus classes (styling is handled separately)
- Do not invent content MeMe didn't specify"""


def _llm_create_page(client, course, change, gmo_context):
    prompt = _build_llm_prompt(course, change, gmo_context,
        "Create a new Canvas wiki page with the content specified by MeMe.")
    response = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=4000,
        messages=[{"role": "user", "content": prompt}])
    return response.content[0].text if response.content else ''


def _llm_create_assignment(client, course, change, gmo_context):
    """Create a new assignment: HTML instructions + assignment_settings.xml."""
    extra = change.get('extra', {})
    assign_name = extra.get('assignment_name', change['title'])
    points = extra.get('points', '0')
    sub_type = 'online_text_entry'
    if 'discussion' in extra.get('assignment_type', '').lower():
        sub_type = 'discussion_topic'

    # Generate instructions HTML via LLM
    prompt = _build_llm_prompt(course, change, gmo_context,
        f"Create the assignment instructions for '{assign_name}'. "
        f"Follow MeMe's guidance exactly — the full instruction text is in the referenced Part 2 section.")
    response = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=4000,
        messages=[{"role": "user", "content": prompt}])
    html = response.content[0].text if response.content else ''
    if not html: return False

    # Create assignment files
    assign_id = make_id(f"assign_{assign_name}")
    slug = slugify(assign_name)
    html_href = f'{assign_id}/{slug}.html'
    xml_href = f'{assign_id}/assignment_settings.xml'

    # Find grading group ID
    group_name = extra.get('grading_group', '')
    group_id = make_id(group_name) if group_name else make_id('default')

    settings_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<assignment identifier="{assign_id}"
  xmlns="{CANVAS_NS}">
  <title>{xml_escape(assign_name)}</title>
  <workflow_state>published</workflow_state>
  <points_possible>{points}</points_possible>
  <grading_type>points</grading_type>
  <submission_types>{sub_type}</submission_types>
  <assignment_group_identifierref>{group_id}</assignment_group_identifierref>
  <peer_reviews>false</peer_reviews>
</assignment>'''

    course['files'][html_href] = html.encode('utf-8')
    course['files'][xml_href] = settings_xml.encode('utf-8')
    course['assignments'][assign_name] = {
        'folder_id': assign_id, 'points': points,
        'sub_type': sub_type, 'instructions_html': html,
        'instructions_text': strip_html(html)}

    # Add to manifest
    _add_to_manifest(course, assign_id, html_href,
        'associatedcontent/imscc_xmlv1p1/learning-application-resource')
    return True


def _llm_create_section(client, course, change, gmo_context):
    """Insert a new section into an existing page."""
    target_lower = change['target'].lower()
    for page_name, html in course['wiki_pages'].items():
        if target_lower in page_name.lower() or page_name.lower() in target_lower:
            prompt = _build_llm_prompt(course, change, gmo_context,
                f"Insert a new section into the page '{page_name}'. "
                f"Return the COMPLETE updated page content, not just the new section. "
                f"Place the new section as described in MeMe's guidance.",
                current_content=html)
            response = client.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=8000,
                messages=[{"role": "user", "content": prompt}])
            new_html = response.content[0].text if response.content else ''
            if new_html:
                course['files'][f'wiki_content/{page_name}.html'] = new_html.encode('utf-8')
                course['wiki_pages'][page_name] = new_html
                return True
    return False


def _llm_rewrite(client, course, change, gmo_context):
    """Rewrite content in an existing page or assignment."""
    target_lower = change['target'].lower()

    # Search wiki pages
    for page_name, html in list(course['wiki_pages'].items()):
        if target_lower in page_name.lower() or page_name.lower() in target_lower:
            prompt = _build_llm_prompt(course, change, gmo_context,
                f"Rewrite the content of page '{page_name}' following MeMe's guidance. "
                f"If MeMe specified exact REPLACE/WITH text, use it verbatim. "
                f"Return the COMPLETE updated page content.",
                current_content=html)
            response = client.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=8000,
                messages=[{"role": "user", "content": prompt}])
            new_html = response.content[0].text if response.content else ''
            if new_html:
                course['files'][f'wiki_content/{page_name}.html'] = new_html.encode('utf-8')
                course['wiki_pages'][page_name] = new_html
                return True

    # Search assignments
    for aname, adata in list(course['assignments'].items()):
        if target_lower in aname.lower() or aname.lower() in target_lower:
            folder = adata['folder_id']
            for fp in list(course['files'].keys()):
                if fp.startswith(f'{folder}/') and fp.endswith('.html'):
                    prompt = _build_llm_prompt(course, change, gmo_context,
                        f"Rewrite the assignment instructions for '{aname}' following MeMe's guidance. "
                        f"If MeMe specified exact REPLACE/WITH text, use it verbatim. "
                        f"Return the COMPLETE updated assignment content.",
                        current_content=adata['instructions_html'])
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514", max_tokens=8000,
                        messages=[{"role": "user", "content": prompt}])
                    new_html = response.content[0].text if response.content else ''
                    if new_html:
                        course['files'][fp] = new_html.encode('utf-8')
                        return True
    return False


def _add_to_manifest(course, res_id, href, res_type):
    """Add a resource entry to imsmanifest.xml."""
    manifest_path = 'imsmanifest.xml'
    if manifest_path in course['files']:
        xml = course['files'][manifest_path].decode('utf-8', errors='ignore')
        new_entry = (f'    <resource identifier="{res_id}" type="{res_type}" href="{href}">'
                     f'\n      <file href="{href}"/>\n    </resource>')
        xml = xml.replace('</resources>', f'{new_entry}\n  </resources>')
        course['files'][manifest_path] = xml.encode('utf-8')


# ─────────────────────────────────────────────────────────────
#  IMSCC WRITER
# ─────────────────────────────────────────────────────────────

def write_imscc(course, output):
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path, content in course['files'].items():
            if isinstance(content, str): content = content.encode('utf-8')
            zf.writestr(path, content)


# ─────────────────────────────────────────────────────────────
#  MAIN PIPELINE
# ─────────────────────────────────────────────────────────────

def run_dede(imscc_bytes, gmo_text='', style='none', api_key=None, progress_callback=None):
    """
    Main pipeline.
    Args:
        imscc_bytes: original .imscc file bytes
        gmo_text: MeMe's full GMO document (optional)
        style: design style to apply
        api_key: Anthropic API key (needed for content changes)
        progress_callback: function(msg) for UI updates
    Returns: (output_bytes, log_lines)
    """
    log = []

    # Step 1: Read IMSCC
    if progress_callback: progress_callback("Reading original course...")
    course = read_imscc(imscc_bytes)
    log.append(f"📂 Read IMSCC: {len(course['files'])} files, "
               f"{len(course['modules'])} modules, "
               f"{len(course['assignments'])} assignments, "
               f"{len(course['wiki_pages'])} wiki pages")

    # Step 2: Parse GMO
    changes = []
    if gmo_text:
        if progress_callback: progress_callback("Parsing MeMe's GMO...")
        changes, full_gmo = parse_gmo(gmo_text)
        structural = [c for c in changes if c['action'] not in LLM_ACTIONS]
        content = [c for c in changes if c['action'] in LLM_ACTIONS]
        log.append(f"📋 Parsed GMO: {len(changes)} changes "
                   f"({len(structural)} structural, {len(content)} content)")
    else:
        full_gmo = ''

    # Step 3: Structural changes
    if changes:
        if progress_callback: progress_callback("Applying structural changes...")
        struct_log = apply_structural_changes(course, changes)
        log.extend(struct_log)

    # Step 4: Style
    if style != 'none':
        if progress_callback: progress_callback(f"Applying {style} design...")
        style_log = apply_style(course, style)
        log.extend(style_log)

    # Step 4.5: String replacement pre-pass (no LLM, no cost)
    handled_indices = set()
    if gmo_text:
        if progress_callback: progress_callback("Extracting REPLACE/WITH pairs...")
        replace_pairs = extract_replace_pairs(full_gmo)
        if replace_pairs:
            log.append(f"🔍 Found {len(replace_pairs)} REPLACE/WITH pair(s) in GMO")
            str_log, handled_indices = apply_string_replacements(course, changes, replace_pairs)
            log.extend(str_log)
            if handled_indices:
                log.append(f"💰 Saved {len(handled_indices)} LLM call(s) via direct string replacement")

    # Step 5: Content changes (LLM — only for changes not handled by string ops)
    all_content = [c for c in changes if c['action'] in LLM_ACTIONS]
    remaining_content = [c for i, c in enumerate(changes) if c['action'] in LLM_ACTIONS and i not in handled_indices]
    if remaining_content and api_key:
        content_log = apply_content_changes(course, changes, full_gmo, api_key, progress_callback, handled_indices)
        log.extend(content_log)
    elif remaining_content and not api_key:
        log.append(f"⚠️ {len(remaining_content)} content changes require an API key — skipped")
    elif all_content and not remaining_content:
        log.append(f"✅ All content changes handled by string replacement — no API calls needed")

    # Step 6: Write
    if progress_callback: progress_callback("Writing IMSCC...")
    output = io.BytesIO()
    write_imscc(course, output)
    output.seek(0)
    log.append(f"📦 Output: {output.getbuffer().nbytes / 1024:.1f} KB")
    return output.getvalue(), log
