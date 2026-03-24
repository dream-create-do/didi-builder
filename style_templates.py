"""
style_templates.py — Azure Modern, Blue & Gold, No Styling
"""
STYLES = {'none': 'No Styling (Plain HTML)', 'azure_modern': 'Azure Modern', 'blue_and_gold': 'Blue & Gold'}

def render_page(style, page_type, data):
    r = {'none': {'homepage': _p_home, 'overview': _p_over, 'assignment': _p_assign},
         'azure_modern': {'homepage': _az_home, 'overview': _az_over, 'assignment': _az_assign},
         'blue_and_gold': {'homepage': _bg_home, 'overview': _bg_over, 'assignment': _bg_assign}}
    return r.get(style, r['none']).get(page_type, r['none']['overview'])(data)

def _e(t):
    if not t: return ''
    return str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def _az_ft():
    return '<div class="dp-content-block" style="background-color:#173955;color:#fff;"><h4 style="text-align:center;font-size:18pt;">Need Help?</h4><p style="text-align:center;color:#fff;">Select the button for the type of support you need.</p><div class="dp-column-container container-fluid" style="padding:0 150px;"><div class="row"><div class="col" style="background:#fff;color:#000;margin:5px;text-align:center;padding:10px;">Phone</div><div class="col" style="background:#fff;color:#000;margin:5px;text-align:center;padding:10px;">Chat</div><div class="col" style="background:#fff;color:#000;margin:5px;text-align:center;padding:10px;">Walk-in</div></div></div></div>'

def _bg_ft():
    return '<div style="background-color:#f0c50c;padding:40px 0;"></div><div style="background-color:#112d54;color:#fff;padding:20px 60px;"><div style="background:#fff;color:#000;padding:15px;border-radius:5px;margin-top:-60px;"><h2 style="font-size:18pt;"><strong>Need Help?</strong></h2><p style="font-size:12pt;">Select the link for support.</p><div style="display:flex;gap:10px;"><div style="flex:1;background:#112d54;color:#fff;border-radius:10px;padding:15px;text-align:center;">Phone</div><div style="flex:1;background:#112d54;color:#fff;border-radius:10px;padding:15px;text-align:center;">Chat</div></div></div></div><div style="background:#112d54;padding:10px;"></div>'

# ── PLAIN ──
def _p_home(d):
    clos = ''.join(f'<li><strong>{_e(c.get("id",""))}</strong> — {_e(c.get("text",""))}</li>' for c in d.get('clos',[]))
    return f'<h1>Welcome to {_e(d.get("course_code",""))}: {_e(d.get("course_title",""))}</h1><h2>Course Description</h2><p>{d.get("description","")}</p>{"<h2>Course Learning Objectives</h2><ul>"+clos+"</ul>" if clos else ""}'

def _p_over(d):
    mlos = ''.join(f'<li><strong>{_e(m.get("id",""))}</strong> — {_e(m.get("text",""))}</li>' for m in d.get('mlos',[]))
    return f'<h1>Module {d.get("module_number","")}: {_e(d.get("module_title",""))}</h1><p>{d.get("overview","")}</p>{"<h2>Module Learning Objectives</h2><ul>"+mlos+"</ul>" if mlos else ""}'

def _p_assign(d):
    return f'<h1>{_e(d.get("title",""))}</h1><p><strong>Points:</strong> {_e(d.get("points",""))} | <strong>Due:</strong> {_e(d.get("due",""))}</p><h2>Instructions</h2><p>{d.get("instructions","")}</p>{d.get("rubric_html","")}'

# ── AZURE MODERN ──
def _az_home(d):
    cards = ''.join(f'<div class="col" style="background:#fff;color:#000;border-radius:10px;padding:10px;margin:5px;text-align:center;"><h4><strong>{_e(c.get("blooms",""))}</strong></h4><p style="font-size:10pt;">{_e(c.get("text",""))} ({_e(c.get("id",""))})</p></div>' for c in d.get('clos',[]))
    return f'''<div id="dp-wrapper" class="dp-wrapper"><div class="dp-content-block"><div class="dp-column-container container-fluid"><div class="row"><div class="col-lg-6" style="padding:50px;"><h2 style="font-size:18pt;">Welcome to</h2><h3 style="font-size:24pt;"><strong>{_e(d.get("course_code",""))}: {_e(d.get("course_title",""))}</strong></h3></div><div class="col-lg-6" style="padding:50px;text-align:center;"><img src="https://files.ciditools.com/cidilabs/dp_icon_placeholder.jpg" alt="Course image" width="360" height="270" style="height:auto;"/></div></div></div></div><div class="dp-content-block" style="background-color:#173955;color:#fff;padding:20px 20px 40px;border-radius:10px;"><h3 style="padding-left:30px;">Course Objectives</h3><div class="dp-column-container container-fluid" style="padding:0 30px;"><div class="row">{cards}</div></div></div><div class="dp-content-block" style="padding-top:20px;"><h3 style="padding-left:30px;">Course Description</h3><p style="padding:0 30px;">{d.get("description","")}</p></div>{_az_ft()}</div>'''

def _az_over(d):
    mlos = ''.join(f'<div class="col" style="background:#173955;color:#fff;border-radius:10px;margin:5px;padding:10px;text-align:center;"><strong>{_e(m.get("blooms",""))}</strong><br/>{_e(m.get("text",""))}</div>' for m in d.get('mlos',[]))
    mats = ''.join(f'<li>{_e(m)}</li>' for m in d.get('materials',[]))
    assigns = ''.join(f'<li>{_e(a)}</li>' for a in d.get('assignments',[]))
    return f'''<div id="dp-wrapper" class="dp-wrapper"><div class="dp-content-block"><div style="padding:100px 0;background:#173955;color:#fff;text-align:center;"><h2 style="font-size:52pt;"><strong>Module {d.get("module_number","")}:</strong></h2><p style="font-size:36pt;">{_e(d.get("module_title",""))}</p></div></div><div style="padding:20px;text-align:center;"><h3 style="font-size:36pt;">Introduction</h3><p>{d.get("overview","")}</p></div><div style="padding:20px 0 60px;"><h3 style="text-align:center;font-size:24pt;">Module Learning Objectives</h3><div class="dp-column-container container-fluid" style="padding:0 25px;"><div class="row">{mlos}</div></div></div><div style="background:#173955;color:#fff;padding:25px;"><h3 style="text-align:center;font-size:24pt;">Instructional Materials</h3><ul>{mats}</ul></div><div style="padding-top:20px;"><h3 style="text-align:center;font-size:24pt;">Assessments &amp; Activities</h3><ul>{assigns}</ul></div>{_az_ft()}</div>'''

def _az_assign(d):
    rub = f'<div style="padding:20px;"><h3 style="font-size:24pt;">Grading Rubric</h3>{d.get("rubric_html","")}</div>' if d.get("rubric_html") else ''
    return f'''<div id="dp-wrapper" class="dp-wrapper"><div class="dp-content-block"><div style="padding:100px 0;background:#173955;color:#fff;text-align:center;"><h2 style="font-size:52pt;">{_e(d.get("title",""))}</h2></div></div><div style="padding:20px;"><h3 style="font-size:36pt;">Instructions</h3><p>{d.get("instructions","")}</p></div>{rub}{_az_ft()}</div>'''

# ── BLUE & GOLD ──
def _bg_home(d):
    clos = ''.join(f'<li><strong>{_e(c.get("id",""))}</strong> — {_e(c.get("text",""))}</li>' for c in d.get('clos',[]))
    return f'''<div id="dp-wrapper" class="dp-wrapper"><div class="dp-content-block"><div style="background:#112d54;color:#fff;padding:200px 50px 75px;text-align:center;"><h2 style="font-size:36pt;"><strong>Welcome to {_e(d.get("course_code",""))}</strong></h2><h3><strong>{_e(d.get("course_title",""))}</strong></h3><div style="display:flex;gap:12px;justify-content:center;margin-top:60px;"><div style="background:#ffcc00;color:#000;padding:8px 30px;border-radius:25px;">Start Here</div><div style="background:#ffcc00;color:#000;padding:8px 30px;border-radius:25px;">Syllabus</div></div></div></div><div style="padding:30px;"><div style="background:#ffcc00;color:#000;padding:20px;border-radius:10px;"><h4 style="font-size:24pt;">Course Overview</h4><p>{d.get("description","")}</p>{"<h3>Course Learning Objectives</h3><ul>"+clos+"</ul>" if clos else ""}</div></div>{_bg_ft()}</div>'''

def _bg_over(d):
    mlos = ''.join(f'<div class="col-md" style="margin:5px;background:#f6f5ff;border-radius:10px;padding:10px;"><h3 style="text-align:center;"><strong>{_e(m.get("id",""))}</strong></h3><p>{_e(m.get("text",""))}</p></div>' for m in d.get('mlos',[]))
    mats = ''.join(f'<li>{_e(m)}</li>' for m in d.get('materials',[]))
    assigns = ''.join(f'<li>{_e(a)}</li>' for a in d.get('assignments',[]))
    return f'''<div id="dp-wrapper" class="dp-wrapper"><div class="dp-content-block"><div style="background:#112d54;color:#fff;padding:80px 50px;text-align:center;"><h2 style="font-size:36pt;"><strong>Module {d.get("module_number","")}: {_e(d.get("module_title",""))}</strong></h2></div></div><div style="padding:25px;"><h2 style="font-size:24pt;"><strong>Introduction</strong></h2><p>{d.get("overview","")}</p><div class="container-fluid"><div class="row" style="margin:0 25px;">{mlos}</div></div></div><div style="background:#f0c50c;padding:40px 0;"></div><div style="padding:20px;"><h2 style="text-align:center;font-size:24pt;"><strong>Instructional Materials</strong></h2><ul>{mats}</ul></div><hr/><div style="padding:20px;"><h2 style="text-align:center;font-size:24pt;"><strong>Assignments &amp; Activities</strong></h2><ul>{assigns}</ul></div>{_bg_ft()}</div>'''

def _bg_assign(d):
    rub = f'<h3><strong>Grading Criteria</strong></h3>{d.get("rubric_html","")}' if d.get("rubric_html") else ''
    return f'''<div id="dp-wrapper" class="dp-wrapper"><div style="padding-left:20px;padding-bottom:16px;"><div style="background:#112d54;padding-top:30px;"><div class="dp-column-container container-fluid"><div class="row"><div class="col-lg-9" style="background:#ffcc00;color:#000;margin-bottom:-60px;padding:20px;border-radius:20px;margin-left:-20px;"><h2><strong>{_e(d.get("title",""))}</strong></h2></div></div></div><p>&nbsp;</p></div></div><div style="padding-top:30px;"><h3><strong>Instructions</strong></h3><p>{d.get("instructions","")}</p>{rub}<h3><strong>How to Submit</strong></h3><p>Submit through the Canvas assignment link above.</p></div><p>Questions about accessibility? Contact your instructor.</p>{_bg_ft()}</div>'''
