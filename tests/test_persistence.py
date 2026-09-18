import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dissent.common import write_json


class AtomicWriteTests(unittest.TestCase):
    def test_transient_lock_retries_without_losing_previous_record(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'audit.json'
            write_json(target,{'status':'pending'})
            original=Path.replace
            attempts=[]
            def locked(path,destination):
                attempts.append(1)
                if len(attempts)<3:
                    self.assertEqual(json.loads(target.read_text()),{'status':'pending'})
                    raise PermissionError('temporary lock')
                return original(path,destination)
            with patch.object(Path,'replace',locked), patch('dissent.common.time.sleep') as sleep:
                write_json(target,{'status':'ok'})
                self.assertEqual(sleep.call_count,2)
            self.assertEqual(json.loads(target.read_text()),{'status':'ok'})

    def test_permanent_permission_failure_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'audit.json'
            write_json(target,{'status':'pending'})
            with patch.object(Path,'replace',side_effect=PermissionError), patch('dissent.common.time.sleep'):
                with self.assertRaises(PermissionError): write_json(target,{'status':'ok'})
            self.assertEqual(json.loads(target.read_text()),{'status':'pending'})
            self.assertTrue(target.with_suffix('.json.tmp').exists())
