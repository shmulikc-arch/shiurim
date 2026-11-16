"""Builds catalog.json from the Google Drive folders listed in sources.json.
Runs hourly in GitHub Actions (see .github/workflows/catalog.yml)."""
import json, os, sys, time, urllib.parse, urllib.request

KEY = os.environ.get('DRIVE_KEY', '')
REFERER = os.environ.get('REFERER', 'https://shmulikc-arch.github.io/')
AUDIO_EXT = ('.mp3', '.m4a', '.aac', '.ogg', '.wav')

def api(params):
    url = 'https://www.googleapis.com/drive/v3/files?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Referer': REFERER})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 3: raise
            time.sleep(2 ** attempt)

def children(folder_id):
    out, token = [], None
    while True:
        p = {'q': f"'{folder_id}' in parents and trashed=false", 'pageSize': 1000, 'key': KEY,
             'fields': 'nextPageToken,files(id,name,mimeType,size,createdTime)'}
        if token: p['pageToken'] = token
        j = api(p); out += j.get('files', []); token = j.get('nextPageToken')
        if not token: return out

def is_folder(f): return f['mimeType'] == 'application/vnd.google-apps.folder'
def is_audio(f): return f['mimeType'].startswith('audio/') or f['name'].lower().endswith(AUDIO_EXT)
def skip_folder(f): return 'בכתב' in f['name']

def audio_in(folder_id, depth=0):
    files = []
    for f in children(folder_id):
        if is_folder(f):
            if depth < 2 and not skip_folder(f): files += audio_in(f['id'], depth + 1)
        elif is_audio(f):
            files.append({'id': f['id'], 'name': f['name'], 'size': int(f.get('size', 0)), 'created': f['createdTime'][:10]})
    return files

def main():
    if not KEY: sys.exit('DRIVE_KEY missing')
    src = json.load(open('sources.json', encoding='utf-8'))
    cat = {'rabbis': []}
    total = 0
    for r in src['rabbis']:
        rr = {k: r[k] for k in ('id', 'name', 'photo')}; rr['collections'] = []
        for s in r['sources']:
            col = {'lang': s['lang'], 'label': s['label'], 'folders': []}
            top = children(s['root'])
            loose = [ {'id': f['id'], 'name': f['name'], 'size': int(f.get('size', 0)), 'created': f['createdTime'][:10]} for f in top if not is_folder(f) and is_audio(f)]
            if loose: col['folders'].append({'id': s['root'], 'name': '999 שיעורים נוספים', 'files': loose})
            for f in top:
                if is_folder(f) and not skip_folder(f):
                    files = audio_in(f['id'], 1)
                    if files: col['folders'].append({'id': f['id'], 'name': f['name'], 'files': files})
            total += sum(len(f['files']) for f in col['folders'])
            rr['collections'].append(col)
        cat['rabbis'].append(rr)
    # write only when content changed, so the hourly job doesn't create empty commits
    new = json.dumps(cat, ensure_ascii=False, sort_keys=True)
    try:
        old = json.load(open('library.json', encoding='utf-8')); old.pop('updated', None)
        if json.dumps(old, ensure_ascii=False, sort_keys=True) == new:
            print('no changes', total); return
    except Exception: pass
    cat['updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    json.dump(cat, open('library.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('catalog updated:', total, 'shiurim')

if __name__ == '__main__': main()
