"""Verify downloaded sources against actual Git commit/tree/blob identities."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    downloads = json.loads((ROOT / 'provenance/source_downloads.json').read_text())
    records = []
    log = []
    for repository in sorted({r['repository'] for r in downloads}):
        rows = [r for r in downloads if r['repository'] == repository]
        commit = rows[0]['commit']
        cache = ROOT / 'sources/git_objects' / repository.split('/')[-1]
        cache.parent.mkdir(exist_ok=True)
        commands = [
            ['git', 'init', '--bare', str(cache)],
            ['git', '-C', str(cache), 'fetch', '--depth=1', '--filter=blob:none',
             'https://github.com/' + repository + '.git', commit],
        ]
        for command in commands:
            r = subprocess.run(command, capture_output=True, text=True)
            log.append({'command': command, 'exit_code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr})
            if r.returncode:
                (ROOT / 'provenance/source_git_verification.json').write_text(json.dumps(log, indent=2) + '\n')
                raise RuntimeError('Git verification failed; see logs/source_git_verification.json')
        actual_commit = subprocess.check_output(['git', '-C', str(cache), 'rev-parse', 'FETCH_HEAD^{commit}'], text=True).strip()
        for row in rows:
            tree = subprocess.check_output(['git', '-C', str(cache), 'ls-tree', actual_commit, '--', row['path']], text=True).strip()
            blob = tree.split()[2]
            raw = (ROOT / 'sources' / row['file']).read_bytes()
            local = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            records.append({'file': row['file'], 'repository': repository, 'expected_commit': commit,
                            'actual_commit': actual_commit, 'tree_record': tree,
                            'downloaded_blob_sha1': local, 'tree_blob_sha1': blob,
                            'sha256': hashlib.sha256(raw).hexdigest(),
                            'result': 'PASS' if blob == local and actual_commit == commit else 'FAIL'})
        print(repository, actual_commit, 'verified source blobs:', len(rows))
    (ROOT / 'provenance/source_git_verification.json').write_text(json.dumps(log, indent=2) + '\n')
    (ROOT / 'provenance/source_git_verification.json').write_text(json.dumps({
        'run_utc': datetime.now(timezone.utc).isoformat(), 'checks': records,
        'overall_pass': all(r['result'] == 'PASS' for r in records)}, indent=2) + '\n')
    if not all(r['result'] == 'PASS' for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
