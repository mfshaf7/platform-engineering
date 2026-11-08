#!/usr/bin/env python3
"""Exact OCI recovery, upstream denial and interrupted replacement proof."""
import hashlib
import gzip
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import runtime_artifact_integrity as integrity


def fixture(*, architecture='amd64', omit_layer=False, corrupt_layer=False, extra=None):
    blobs = {}

    def descriptor(value, media):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        digest = 'sha256:' + hashlib.sha256(body).hexdigest()
        blobs['blobs/sha256/' + digest.split(':')[1]] = body
        return {'digest': digest, 'size': len(body), 'mediaType': media}

    unpacked = io.BytesIO()
    with tarfile.open(fileobj=unpacked, mode='w') as value:
        member = tarfile.TarInfo('bin/tool'); member.mode=0o755; member.size=len(b'approved binary')
        value.addfile(member,io.BytesIO(b'approved binary'))
    layer = descriptor(gzip.compress(unpacked.getvalue(),mtime=0), 'application/vnd.oci.image.layer.v1.tar+gzip')
    config = descriptor({'os': 'linux', 'architecture': architecture,
        'rootfs':{'diff_ids':['sha256:'+hashlib.sha256(unpacked.getvalue()).hexdigest()]}}, 'application/vnd.oci.image.config.v1+json')
    manifest = descriptor({'schemaVersion': 2, 'config': config, 'layers': [layer]}, 'application/vnd.oci.image.manifest.v1+json')
    reference = 'docker.io/example/tool@' + manifest['digest']
    manifest['annotations'] = {'io.containerd.image.name': reference, 'org.opencontainers.image.ref.name': '@' + manifest['digest']}
    files = {'oci-layout': b'{"imageLayoutVersion":"1.0.0"}',
             'index.json': json.dumps({'schemaVersion': 2, 'manifests': [manifest]}).encode(), **blobs}
    name = 'blobs/sha256/' + layer['digest'].split(':')[1]
    if omit_layer:
        del files[name]
    if corrupt_layer:
        files[name] = b'altered compressed content'
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode='w') as archive:
        for name, body in files.items():
            member = tarfile.TarInfo(name); member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
        if extra:
            member = tarfile.TarInfo(extra)
            archive.addfile(member, io.BytesIO())
    return reference, result.getvalue()


class ArchiveTests(unittest.TestCase):
    def test_complete_exact_archive_and_reference_binding(self):
        reference, body = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.tar'; path.write_bytes(body)
            integrity.verify_archive(path, reference)
            with self.assertRaises(integrity.IntegrityError):
                integrity.verify_archive(path, reference.replace('example/tool', 'another/tool'))

    def test_altered_missing_foreign_platform_duplicate_and_traversal_denied(self):
        for options in ({'corrupt_layer': True}, {'omit_layer': True}, {'architecture': 'arm64'},
                        {'extra': 'index.json'}, {'extra': '../escape'}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                reference, body = fixture(**options)
                path = Path(directory) / 'image.tar'; path.write_bytes(body)
                with self.assertRaises(integrity.IntegrityError):
                    integrity.verify_archive(path, reference)

    def test_archive_and_directory_symlinks_denied(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(integrity, 'STATE', Path(directory)):
            reference, body = fixture(); original = Path(directory) / 'original'; original.write_bytes(body)
            link = Path(directory) / 'alias'; link.symlink_to(original)
            with self.assertRaises(integrity.IntegrityError): integrity.verify_archive(link, reference)
            (Path(directory) / 'verified-archives').symlink_to(Path(directory))
            with self.assertRaises(integrity.IntegrityError): integrity.archive_path(reference)

    def test_repair_with_upstream_unavailable_keeps_original_before_removal(self):
        reference, body = fixture()
        with tempfile.TemporaryDirectory() as directory, patch.object(integrity, 'STATE', Path(directory)):
            calls = []
            def command(args, **kwargs):
                calls.append(args)
                if args[:2] == ['crictl', 'pull']:
                    raise integrity.IntegrityError('upstream denies this image')
                if args[3:5] == ['images', 'export']:
                    Path(args[-2]).write_bytes(body)
                if args[3:5] == ['images', 'rm']:
                    integrity.verify_archive(integrity.archive_path(reference), reference)
                return b''
            incident = Path(directory) / 'incident.json'
            with patch.object(integrity, 'command', side_effect=command), patch.object(integrity, 'baseline'), \
                 patch.object(integrity, 'image_users', return_value=[]), \
                 patch.object(integrity, 'compare', return_value=({}, [])), \
                 patch.object(integrity.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
                integrity.repair(reference, [reference], {'config': 'id', 'chain': 'chain'}, incident)
            self.assertLess(next(i for i,c in enumerate(calls) if c[3:5] == ['images','export']),
                            next(i for i,c in enumerate(calls) if c[3:5] == ['images','rm']))
            self.assertEqual(sum(c[3:5] == ['images','import'] for c in calls), 1)
            self.assertFalse(any(c[:2] == ['crictl','pull'] for c in calls))
            self.assertEqual(json.loads(incident.read_text())['phase'], 'restored-awaiting-readiness')

    def test_failed_export_never_removes_the_original(self):
        reference, _ = fixture()
        with tempfile.TemporaryDirectory() as directory, patch.object(integrity, 'STATE', Path(directory)):
            calls = []
            def command(args, **kwargs):
                calls.append(args)
                raise integrity.IntegrityError('compressed original is unavailable')
            with patch.object(integrity, 'command', side_effect=command), patch.object(integrity, 'baseline'), \
                 patch.object(integrity, 'image_users', return_value=[]), self.assertRaises(integrity.IntegrityError):
                integrity.repair(reference, [reference], {'config':'id'}, Path(directory)/'incident.json')
            self.assertFalse(any(c[3:5] == ['images','rm'] for c in calls))
            self.assertFalse((Path(directory)/'incident.json').exists())

    def test_fresh_baseline_uses_retained_original_when_native_content_and_upstream_are_unavailable(self):
        reference, body=fixture()
        class MissingNative:
            def wait(self, **kwargs):return 1
        with tempfile.TemporaryDirectory() as directory,patch.object(integrity,'STATE',Path(directory)):
            archive=integrity.archive_path(reference);archive.write_bytes(body)
            with patch.object(integrity.subprocess,'Popen',return_value=MissingNative()), \
                 patch.object(integrity,'registry_blob',side_effect=AssertionError('upstream is unavailable')) as upstream:
                baseline=integrity.baseline(reference,fresh=True)
            self.assertEqual(baseline['entries']['bin/tool']['sha256'],hashlib.sha256(b'approved binary').hexdigest())
            upstream.assert_not_called()

    def test_failed_import_is_latched_and_never_replays_removal(self):
        reference, body = fixture()
        with tempfile.TemporaryDirectory() as directory, patch.object(integrity, 'STATE', Path(directory)):
            archive = integrity.archive_path(reference); archive.write_bytes(body)
            incident = Path(directory) / 'incident.json'
            def command(args, **kwargs):
                if args[3:5] == ['images','import']: raise integrity.IntegrityError('import interrupted')
                return b''
            with patch.object(integrity, 'command', side_effect=command), patch.object(integrity, 'baseline'), \
                 patch.object(integrity, 'image_users', return_value=[]), \
                 patch.object(integrity.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), \
                 self.assertRaises(integrity.IntegrityError):
                integrity.repair(reference, [reference], {'config':'id','chain':'chain'}, incident)
            self.assertEqual(json.loads(incident.read_text())['phase'], 'importing-archive')
            with patch.object(integrity, 'command') as command, self.assertRaises(integrity.IntegrityError):
                integrity.repair(reference, [reference], {'config':'id'}, incident)
            command.assert_not_called()

    def test_missing_metadata_resumes_only_before_the_single_archive_import(self):
        reference, body = fixture()
        for phase in ('attempted', 'importing-archive'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory, patch.object(integrity, 'STATE', Path(directory)):
                root=Path(directory); archive=integrity.archive_path(reference); archive.write_bytes(body)
                incident=root/(hashlib.sha256(reference.encode()).hexdigest()+'.incident.json')
                integrity.write(incident, {'phase':phase,'reference':reference,'aliases':[reference]})
                integrity.write(root/'inventory.json', [reference])
                def native(args):
                    if args[0]=='crictl': return {'images':[]}
                    return {'items':[]}
                with patch.object(integrity, 'native_json', side_effect=native), \
                     patch.object(integrity, 'command', return_value=b'REF TYPE DIGEST\n'):
                    if phase=='attempted':
                        assets,_=integrity.admitted_inventory({'namespaces':[],'repositories':['docker.io/example/tool'],'automatic_repair':True})
                        self.assertEqual(assets,[(reference,[])])
                    else:
                        with self.assertRaises(integrity.IntegrityError):
                            integrity.admitted_inventory({'namespaces':[],'repositories':['docker.io/example/tool'],'automatic_repair':True})
                if phase=='attempted':
                    with patch.object(integrity,'admitted_inventory',return_value=([(reference,[])],[])), \
                         patch.object(integrity,'baseline',return_value={'config':'exact'}), \
                         patch.object(integrity,'image_users',return_value=[]), \
                         patch.object(integrity,'compare',return_value=({},[])), \
                         patch.object(integrity,'command',return_value=b'') as command:
                        pending=integrity.operate('check',{})
                        self.assertTrue(pending['corrupt'][0]['resume_from_archive'])
                        integrity.operate('repair',{'automatic_repair':True})
                    self.assertFalse(any(c.args[0][3:5]==['images','rm'] for c in command.call_args_list))


if __name__ == '__main__':
    unittest.main()
