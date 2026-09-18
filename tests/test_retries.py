import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from dissent.providers import BudgetExceeded, CallFailure, CallStore, Config, retry_after_seconds
from dissent.protocols import messages_for
from dissent.metrics import costs
from dissent.tasks import generate


def success():
    return contextlib.nullcontext(io.BytesIO(json.dumps({'model':'test/version','provider':'test','choices':[{'finish_reason':'stop','message':{'content':json.dumps({'answer':'A','reasoning':'checked','confidence':0.8})}}], 'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5,'cost':0.01}}).encode()))


def http_error(code, headers=None):
    return urllib.error.HTTPError('https://example.invalid',code,'withheld',headers or {},None)


def truncated():
    return contextlib.nullcontext(io.BytesIO(json.dumps({
        'choices': [{'finish_reason': 'length', 'message': {'content': '{'}}],
        'usage': {'prompt_tokens': 2, 'completion_tokens': 10, 'total_tokens': 12, 'cost': 0.02}
    }).encode()))


class RetryTests(unittest.TestCase):
    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'secret-test'})
    def test_truncation_increases_allowance_and_preserves_cost_and_cache(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', side_effect=[truncated(), truncated(), success()]) as http, patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            store = CallStore(folder, self.config())
            self.assertEqual(self.call(store)['answer'], 'A')
            payloads = [json.loads(c.args[0].data) for c in http.call_args_list]
            self.assertEqual([p['max_tokens'] for p in payloads], [8192, 16384, 32768])
            self.assertEqual(payloads[0]['messages'], payloads[2]['messages'])
            journal = json.loads(next(Path(folder).glob('*.json')).read_text())
            self.assertAlmostEqual(journal['usage']['cost'], 0.05)
            self.assertEqual([a['max_tokens'] for a in journal['attempts']], [8192, 16384, 32768])
            self.call(CallStore(folder, self.config()))
            self.assertEqual(http.call_count, 3)

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'secret-test'})
    def test_truncation_ceiling_is_terminal(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', side_effect=[truncated(), truncated()]) as http, patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            store = CallStore(folder, self.config(max_tokens=8192, max_tokens_ceiling=16384))
            with self.assertRaises(CallFailure): self.call(store)
            self.assertFalse(store.records['task/independent/0']['retryable'])
            with self.assertRaises(CallFailure): self.call(CallStore(folder, store.config, retry_failed=True))
            self.assertEqual(http.call_count, 2)

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'secret-test'})
    def test_truncation_budget_pause_resumes_with_larger_allowance(self):
        with tempfile.TemporaryDirectory() as folder, patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            with patch('urllib.request.urlopen', return_value=truncated()):
                with self.assertRaises(BudgetExceeded): self.call(CallStore(folder, self.config(), max_calls=1))
            with patch('urllib.request.urlopen', return_value=success()) as http:
                resumed = CallStore(folder, self.config(), max_calls=3)
                self.call(resumed)
                self.assertEqual(json.loads(http.call_args.args[0].data)['max_tokens'], 16384)
                self.assertAlmostEqual(resumed.known_cost, 0.03)

    def call(self, store):
        task = generate(1)[0][0]
        return store.call('task/independent/0','independent',task,{},messages_for('independent',task,{}))

    def config(self, **overrides):
        return Config(backend='openrouter', model='test/version', provider='test', **overrides)

    @patch.dict('os.environ', {'OPENROUTER_API_KEY':'secret-test'})
    def test_rate_limit_retries_identical_payload_and_keeps_unknown_charges(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', side_effect=[http_error(429,{'Retry-After':'2'}),success()]) as http, patch('time.sleep') as sleep, contextlib.redirect_stdout(io.StringIO()):
            store=CallStore(folder,self.config())
            self.assertEqual(self.call(store)['answer'],'A')
            self.assertGreaterEqual(sleep.call_args.args[0],2)
            self.assertEqual(http.call_args_list[0].args[0].data,http.call_args_list[1].args[0].data)
            self.assertEqual(store.attempt_count,2)
            totals=costs(list(store.records.values()))
            self.assertEqual(totals['request_attempts'],2)
            self.assertEqual(totals['retries'],1)
            self.assertIsNone(totals['cost'])
            self.assertEqual(totals['cost_known_subtotal'],0.01)
            self.call(store)
            self.assertEqual(http.call_count,2)
            self.assertNotIn('secret-test',next(Path(folder).glob('*.json')).read_text())

    @patch.dict('os.environ', {'OPENROUTER_API_KEY':'secret-test'})
    def test_authentication_error_never_retried(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', side_effect=http_error(401)) as http, patch('time.sleep') as sleep:
            with self.assertRaises(CallFailure):
                self.call(CallStore(folder,self.config()))
            self.assertEqual(http.call_count,1)
            sleep.assert_not_called()

    @patch.dict('os.environ', {'OPENROUTER_API_KEY':'secret-test'})
    def test_timeout_exhaustion_and_explicit_resume(self):
        with tempfile.TemporaryDirectory() as folder, patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            with patch('urllib.request.urlopen',side_effect=TimeoutError) as http:
                store=CallStore(folder,self.config(max_attempts=2))
                with self.assertRaises(CallFailure): self.call(store)
                self.assertEqual(http.call_count,2)
                with self.assertRaises(CallFailure): self.call(store)
                self.assertEqual(http.call_count,2)
            resumed=CallStore(folder,self.config(max_attempts=2),retry_failed=True)
            with patch('urllib.request.urlopen',return_value=success()): self.call(resumed)
            self.assertEqual(resumed.attempt_count,3)
            self.assertTrue(resumed.records['task/independent/0']['attempts'][0]['delivery_ambiguous'])

    @patch.dict('os.environ', {'OPENROUTER_API_KEY':'secret-test'})
    def test_request_cap_applies_to_retries(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen',side_effect=http_error(503)) as http, patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            store=CallStore(folder,self.config(),max_calls=1)
            with self.assertRaises(BudgetExceeded): self.call(store)
            self.assertEqual(http.call_count,1)
            self.assertEqual(store.records['task/independent/0']['status'],'paused')

    @patch.dict('os.environ', {'OPENROUTER_API_KEY':'secret-test'})
    def test_long_retry_after_defers_without_retrying_early(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen',side_effect=http_error(429,{'Retry-After':'120'})) as http, patch('time.sleep') as sleep:
            with self.assertRaises(CallFailure): self.call(CallStore(folder,self.config()))
            self.assertEqual(http.call_count,1)
            sleep.assert_not_called()

    @patch.dict('os.environ', {'OPENROUTER_API_KEY':'secret-test'})
    def test_http_200_error_envelope_retried(self):
        failure=contextlib.nullcontext(io.BytesIO(b'{"error":{"code":502,"message":"temporary"}}'))
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen',side_effect=[failure,success()]), patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            store=CallStore(folder,self.config())
            self.call(store)
            self.assertEqual(store.attempt_count,2)

    def test_retry_after_invalid_is_ignored(self):
        self.assertIsNone(retry_after_seconds('nan'))
        self.assertIsNone(retry_after_seconds('bad'))
        self.assertEqual(retry_after_seconds('-1'),0)
