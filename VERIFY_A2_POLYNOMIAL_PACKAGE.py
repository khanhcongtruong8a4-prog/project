from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST_A2_POLYNOMIAL_REPRODUCTION.json').read_text())
for n,r in manifest['files'].items():
 p=root/n
 if not p.is_file() or p.stat().st_size!=r['size']:raise SystemExit('Missing/size mismatch: '+n)
 with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
 if actual!=r['sha256']:raise SystemExit('SHA256 mismatch: '+n)
print('Verified',len(manifest['files']),'exact files; source',manifest.get('source_commit',manifest.get('source_version')))
