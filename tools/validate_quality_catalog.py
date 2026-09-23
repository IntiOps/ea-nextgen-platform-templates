"""Validate authored quality bindings and content pins without running scanners."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'components/validation/core'))
from evidence import validate_profile


def validate(root=ROOT):
    manifest=json.loads((root/'catalog/validation.json').read_text())
    if manifest['schema_version']!='1.0' or manifest['deployment_authorized'] is not False:
        raise ValueError('invalid quality catalog contract')
    def read(path):
        p=(root/path).resolve()
        if '..' in Path(path).parts or Path(path).is_absolute() or not p.is_relative_to(root.resolve()):
            raise ValueError('path outside catalog')
        return p.read_bytes()
    for file in manifest['files']:
        if hashlib.sha256(read(file['path'])).hexdigest()!=file['sha256']:
            raise ValueError('quality component digest mismatch')
    pinned={f['path'] for f in manifest['files']}
    if len(pinned)!=len(manifest['files']):raise ValueError('duplicate file pin')
    for binding in manifest['bindings']:
        read(binding['target'])
        if binding['profile'] not in pinned:raise ValueError('profile must be pinned')
        validate_profile(json.loads(read(binding['profile'])))
        if binding['mode']!='source_validation' or binding['cloud_verified'] is not False:
            raise ValueError('source checks cannot claim cloud coverage')
    return manifest


if __name__=='__main__':
    result=validate()
    print(f"Quality catalog: {len(result['files'])} pinned files, {len(result['bindings'])} source bindings")
