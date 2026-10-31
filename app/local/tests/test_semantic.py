import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import semantic
import server


class EmbeddingCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'vectors.sqlite3'
        self.digest = 'original-model'
        self.inputs = []
        self.transport = Mock(side_effect=self.respond)

    def respond(self, path, data=None, timeout=None):
        if path == '/api/tags':
            return {'models': [{'name': semantic.MODEL, 'digest': self.digest}]}
        self.inputs.extend(data['input'])
        return {'embeddings': [[3., 4.] for _ in data['input']]}

    def test_deduplication_reuse_and_changed_content(self):
        first = semantic.embeddings(['private note', 'private note'], self.transport, self.path)
        self.assertEqual(self.inputs, ['private note'])
        self.assertEqual(first, [[.6, .8], [.6, .8]])
        semantic.embeddings(['private note', 'edited note'], self.transport, self.path)
        self.assertEqual(self.inputs, ['private note', 'edited note'])
        self.assertNotIn(b'private note', self.path.read_bytes())
        self.digest = 'updated-model'
        semantic.embeddings(['private note'], self.transport, self.path)
        self.assertEqual(self.inputs[-1], 'private note')
        self.assertEqual(len(self.inputs), 3)

    def test_missing_model_does_not_silently_return_lexical_results(self):
        with self.assertRaisesRegex(RuntimeError, 'search model is missing'):
            semantic.embeddings(['note'], Mock(return_value={'models': []}), self.path)

    def test_failed_batch_is_not_cached_as_a_success(self):
        def invalid(path, data=None, timeout=None):
            if path == '/api/tags': return self.respond(path)
            return {'embeddings': [[float('nan'), 1.]]}
        with self.assertRaises(RuntimeError):
            semantic.embeddings(['note'], invalid, self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM vectors').fetchone()[0], 0)
        semantic.embeddings(['note'], self.transport, self.path)
        self.assertEqual(self.inputs, ['note'])

    def test_incomplete_batch_and_zero_vectors_are_rejected(self):
        for response in [[], [[0., 0.]], [['bad', 1.]]]:
            def invalid(path, data=None, timeout=None):
                return self.respond(path) if path == '/api/tags' else {'embeddings': response}
            with self.subTest(response=response), self.assertRaises(RuntimeError):
                semantic.embeddings(['note'], invalid, self.path)


class HybridRetrievalTests(unittest.TestCase):
    def source(self, identifier, text):
        return {'source_id': identifier, 'title': 'Note', 'turns': [{'content': text}]}

    def test_original_query_survives_an_imperfect_translation(self):
        chunks = [{'title': '', 'text': 'First'}, {'title': '', 'text': 'Second'}]
        with patch.object(semantic, 'translated_queries', return_value=('A different meaning',)), \
                patch.object(semantic, 'embeddings', return_value=[[1., 0.], [0., 1.], [1., 0.], [0., 1.]]):
            scores = semantic.similarities('Запит', [], chunks, Mock())
        self.assertGreater(scores[0], scores[1])

    def test_semantic_hit_beyond_context_limit_with_no_shared_words(self):
        body = {'question': 'Хто займається постачанням?', 'sources': [
            self.source(f'noise-{i}', 'Office maintenance schedule. ' * 50) for i in range(30)] + [
            self.source('target', 'Maya coordinates supplier deliveries.')]}
        with patch.object(semantic, 'similarities', return_value=[.1] * 30 + [.8]):
            selected, partial = server.excerpts(body)
        self.assertTrue(partial)
        self.assertEqual(selected[0]['source_id'], 'target')
        self.assertLessEqual(sum(len(c['text']) for c in selected), 18000)
        self.assertLessEqual(len(selected), 24)
        self.assertFalse(set(server.tokens(body['question'])) & set(server.tokens(selected[0]['text'])))

    def test_exact_amount_keeps_its_priority_and_quote(self):
        body = {'question': '7300 зл', 'sources': [
            self.source('other', 'The budget is 8300 PLN.'),
            self.source('target', 'The budget is 7300 PLN.')]}
        with patch.object(semantic, 'similarities', return_value=[.8, .75]):
            result = server.search(body)
        self.assertEqual(result['results'][0]['source_id'], 'target')
        self.assertEqual(result['results'][0]['match'], 'exact')
        self.assertEqual(result['results'][0]['quote'], 'The budget is 7300 PLN.')
        self.assertEqual(len(result['results']), 1)

    def test_search_deduplicates_sources_and_excludes_weak_matches(self):
        body = {'question': 'How can I cancel?', 'sources': [
            self.source('refund', 'Cancellation refunds. ' * 150), self.source('unrelated', 'Coffee is downstairs.')]}
        chunks = server.source_chunks(body)
        with patch.object(semantic, 'similarities', return_value=[.7] * (len(chunks) - 1) + [.1]):
            self.assertEqual([r['source_id'] for r in server.search(body)['results']], ['refund'])

    def test_cached_excluded_source_cannot_enter_results_or_citations(self):
        body = {'question': 'Who coordinates deliveries?', 'sources': [self.source('allowed', 'Plants need water.')]}
        with patch.object(semantic, 'similarities', return_value=[.1]) as embed:
            self.assertEqual(server.search(body)['results'], [])
        self.assertEqual([c['source_id'] for c in embed.call_args.args[2]], ['allowed'])
        reply = {'message': {'content': json.dumps({'answer': 'Maya', 'abstain': False,
            'citations': [{'id': 1, 'quote': 'Maya coordinates supplier deliveries.'}]})}}
        with patch.object(semantic, 'similarities', return_value=[.1]), patch.object(server, 'ollama', return_value=reply):
            result = server.answer(body)
        self.assertEqual(result['answer_status'], 'unverified')
        self.assertEqual([c['source_id'] for c in result['citations']], ['allowed'])
        self.assertNotIn('Maya', json.dumps(result))


if __name__ == '__main__': unittest.main()
