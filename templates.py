"""Normalized primitive templates: kind, center xyz, dimensions xyz."""
TEMPLATES = {
    'person': [('box',[0,0,-.1],[.75,1,.75]),('sphere',[0,0,.35],[.6,.6,.3])],
    'car': [('box',[0,0,-.05],[1,1,.45]),('box',[0,0,.25],[.55,.8,.35])],
    'horse': [('box',[-.05,0,.05],[.7,.7,.4]),('box',[.3,0,.27],[.18,.45,.4]),('box',[.4,0,.38],[.2,.5,.18])],
    'animal': [('box',[0,0,.05],[.7,.65,.4]),('sphere',[.35,0,.2],[.3,.5,.3])],
    'table': [('box',[0,0,.4],[1,1,.2])],
    'box': [('box',[0,0,0],[1,1,1])],
    'sphere': [('sphere',[0,0,0],[1,1,1])],
    'cylinder': [('cylinder',[0,0,0],[1,1,1])],
}
for kind in ('horse','animal','table'):
    for x in (-.25,.25):
        for y in (-.23,.23):
            TEMPLATES[kind].append(('box',[x,y,-.28],[.1,.1,.44 if kind!='table' else .76]))
for x in (-.3,.3):
    for y in (-.45,.45):
        # Rotation about X puts the cylinder axis across the vehicle.
        TEMPLATES['car'].append(('wheel',[x,y,-.32],[.22,.22,.28]))

def kind_for_category(category):
    if category=='person': return 'person'
    if category=='horse': return 'horse'
    if category in ('car','truck','bus'): return 'car'
    if category in ('dog','cat','cow','sheep','elephant','bear','zebra','giraffe'): return 'animal'
    if category=='dining table': return 'table'
    if category in ('sports ball','orange','apple'): return 'sphere'
    if category in ('bottle','cup','vase'): return 'cylinder'
    return 'box'
