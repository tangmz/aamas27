import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dissent.environment import check_environment, load_env, model_settings


class EnvironmentTests(unittest.TestCase):
    def test_quotes_comments_precedence_and_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('export OPENROUTER_API_KEY="fixture#literal" # note\nOPENROUTER_MODEL=model/version # comment\nOPENROUTER_PROVIDER=provider\nPATH=ignored\n')
            env = {'OPENROUTER_MODEL': 'existing/version'}
            load_env(path, env)
            self.assertEqual(env, {'OPENROUTER_API_KEY': 'fixture#literal', 'OPENROUTER_MODEL': 'existing/version', 'OPENROUTER_PROVIDER': 'provider'})

    def test_malformed_file_does_not_expose_or_partially_load_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('OPENROUTER_MODEL=valid\nOPENROUTER_API_KEY="secret-fixture\n')
            env = {}
            with self.assertRaises(ValueError) as error:
                load_env(path, env)
            self.assertNotIn('secret-fixture', str(error.exception))
            self.assertEqual(env, {})

    def test_mock_does_not_use_live_settings_and_cli_overrides_environment(self):
        with patch.dict(os.environ, {'OPENROUTER_MODEL': 'live/model', 'OPENROUTER_PROVIDER': 'live-provider'}, clear=True):
            self.assertEqual(model_settings('mock'), ('mock-fixture-v1', 'offline'))
            self.assertEqual(model_settings('openrouter'), ('live/model', 'live-provider'))
            self.assertEqual(model_settings('openrouter', 'override', 'other'), ('override', 'other'))

    def test_local_check_reports_names_not_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'Missing settings: OPENROUTER_API_KEY'):
                check_environment()
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fixture-secret', 'OPENROUTER_MODEL': 'model/version', 'OPENROUTER_PROVIDER': 'provider'}, clear=True):
            self.assertNotIn('fixture-secret', check_environment())
