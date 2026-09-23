"""Read-only catalog validation/list/export. Never executes package contents."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('invalid catalog path')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('catalog path escapes root or is missing')
    if path.stat().st_size > 2_000_000:
        raise ValueError('catalog file too large')
    return path.read_bytes()


def load(root, path):
    return json.loads(read(root, path))


def validate(root=ROOT):
    metamodel = load(root, 'schemas/metamodel-reference.json')
    blueprints, components, blueprint_digests = {}, {}, {}
    for catalog, kind, collection in [('catalog/blueprints.json', 'architecture_blueprint', blueprints),
                                       ('catalog/components.json', 'reusable_component', components)]:
        index = load(root, catalog)
        if index.get('schema_version') != '1.0':
            raise ValueError('unsupported index version')
        for row in index['entries']:
            doc = load(root, row['path'])
            if doc.get('schema_version') != '1.0' or doc.get('kind') != kind or doc.get('id') != row['id'] or row['id'] in collection:
                raise ValueError('invalid or duplicate entry')
            if doc.get('deployable') is not False:
                raise ValueError('reference entries cannot claim cloud deployability')
            collection[row['id']] = doc
            if kind == 'architecture_blueprint':
                blueprint_digests[row['id']] = hashlib.sha256(read(root, row['path'])).hexdigest()
                nodes = {n['key']: n for n in doc['nodes']}
                if not nodes or len(nodes) != len(doc['nodes']):
                    raise ValueError('duplicate or empty nodes')
                for node in nodes.values():
                    if node['type'] not in metamodel['types']:
                        raise ValueError('unknown element type')
                if set(doc['scope']['included']) != set(nodes):
                    raise ValueError('blueprint scope mismatch')
                for edge in doc['relationships']:
                    relation = metamodel['relationships'].get(edge['type'])
                    if (not relation or edge['source'] not in nodes or edge['target'] not in nodes or
                        nodes[edge['source']]['type'] != relation['source'] or nodes[edge['target']]['type'] != relation['target']):
                        raise ValueError('invalid relationship endpoints')
                if not set(doc['viewpoints']) <= set(metamodel['viewpoints']):
                    raise ValueError('unknown viewpoint')
            else:
                if not doc['files']:
                    raise ValueError('empty component')
                for file in doc['files']:
                    digest = hashlib.sha256(read(root, file['path'])).hexdigest()
                    if digest != file['sha256']:
                        raise ValueError('component digest mismatch')
    demos = load(root, 'catalog/demos.json')['entries']
    ids = set()
    for demo in demos:
        if demo['id'] in ids or demo.get('cloud_verified') is not False:
            raise ValueError('duplicate or unverified demo claim')
        ids.add(demo['id'])
        if demo['blueprint'] not in blueprints or not set(demo['components']) <= set(components):
            raise ValueError('unresolved demo reference')
        if demo.get('blueprint_sha256') != blueprint_digests[demo['blueprint']]:
            raise ValueError('demo blueprint digest mismatch')
        for component, expected in demo['component_digests'].items():
            actual = hashlib.sha256(json.dumps(components[component], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            if component not in demo['components'] or actual != expected:
                raise ValueError('demo dependency digest mismatch')
        if set(demo['component_digests']) != set(demo['components']):
            raise ValueError('unpinned demo dependency')
    return {'blueprints': blueprints, 'components': components, 'demos': demos}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['validate', 'list', 'export'])
    parser.add_argument('--blueprint')
    args = parser.parse_args()
    catalog = validate()
    if args.command == 'export':
        if args.blueprint not in catalog['blueprints']:
            parser.error('choose an existing --blueprint')
        print(json.dumps(catalog['blueprints'][args.blueprint], indent=2))
    else:
        print(json.dumps({k: list(v) if isinstance(v, dict) else [x['id'] for x in v] for k,v in catalog.items()}, indent=2))
