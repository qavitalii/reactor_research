import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

spec = importlib.util.spec_from_file_location('recall_server', Path(__file__).parents[1] / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class OfflineRetrievalTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(server.semantic, 'similarities', side_effect=lambda q, h, c, t: [0.] * len(c))
        patcher.start()
        self.addCleanup(patcher.stop)


class LocalAnswerTests(OfflineRetrievalTests):
    def setUp(self):
        super().setUp()
        self.body = {'question': 'What is the code?', 'sources': [
            {'source_id': 's1', 'title': 'Note', 'turns': [{'content': 'The code is ORCHID-73.'}]}]}

    def reply(self, citations, abstain=False):
        return {'message': {'content': json.dumps({'answer': 'ORCHID-73', 'abstain': abstain, 'citations': citations})}}

    def test_exact_citation_is_mapped_to_original_source(self):
        with patch.object(server, 'ollama', return_value=self.reply([{'id': 1, 'quote': 'The code is ORCHID-73.'}])):
            self.assertEqual(server.answer(self.body)['citations'], [{'source_id': 's1', 'quote': 'The code is ORCHID-73.'}])

    def test_invented_quote_and_source_are_rejected(self):
        for citation in [{'id': 1, 'quote': 'Invented fact'}, {'id': 999, 'quote': 'The code is ORCHID-73.'}]:
            with patch.object(server, 'ollama', return_value=self.reply([citation])) as model:
                result = server.answer(self.body)
                self.assertEqual(model.call_count, 2)
                self.assertEqual(result['answer_status'], 'unverified')
                self.assertNotEqual(result['answer'], 'ORCHID-73')
                self.assertEqual(result['citations'][0]['quote'], 'The code is ORCHID-73.')

    def test_pdf_whitespace_is_restored_to_original_without_another_generation(self):
        original = 'The\tapproved\nbudget is\u00a07300\r\nPLN.'
        self.body['sources'][0]['turns'][0]['content'] = original
        with patch.object(server, 'ollama', return_value=self.reply([{'id': 1, 'quote': 'The approved budget is 7300 PLN.'}])) as model:
            result = server.answer(self.body)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(result['citations'][0]['quote'], original)

    def test_wrong_words_amounts_currencies_and_negations_are_not_normalized(self):
        original = 'The\tfee is 7300 PLN. Payment is not required today.'
        for quote in ['The fee is 8300 PLN.', 'The fee is 7300 USD.', 'Payment is required today.', 'Оплата не потрібна сьогодні.']:
            with self.subTest(quote=quote):
                self.assertIsNone(server.original_quote(original, quote))

    def test_partial_quote_maps_to_its_exact_original_span(self):
        original = 'Heading\nThe\tfee is\n7300 PLN.\nFooter'
        self.assertEqual(server.original_quote(original, 'fee is 7300 PLN.'), 'fee is\n7300 PLN.')

    def test_quote_across_overlapping_chunks_is_verified_without_duplicate_text(self):
        text = 'A long document. ' * 110 + 'The final code is ORCHID-73.'
        self.body['sources'][0]['turns'][0]['content'] = text
        selected, partial = server.excerpts(self.body)
        self.assertFalse(partial)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['text'], text)
        quote = text[1700:]
        with patch.object(server, 'ollama', return_value=self.reply([{'id': 1, 'quote': quote}])) as model:
            result = server.answer(self.body)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(result['citations'][0]['quote'], quote)

    def test_separate_turns_and_unselected_gaps_are_not_stitched_together(self):
        body = {'question': 'What?', 'sources': [{'source_id': 's1', 'turns': [
            {'content': 'First turn.'}, {'content': 'Second turn.'}]}]}
        self.assertEqual(len(server.excerpts(body)[0]), 2)
        body['sources'][0]['turns'] = [{'content': 'Unrelated filler. ' * 500}]
        chunks = server.source_chunks(body)
        self.assertGreater(len(chunks), 3)
        merged = server.merge_excerpts([chunks[0], chunks[-1]])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]['text'], chunks[0]['text'])

    def test_invalid_answer_is_regenerated_once_and_reverified(self):
        first = self.reply([{'id': 1, 'quote': 'A paraphrase'}])
        corrected = {'message': {'content': json.dumps({'answer': 'ORCHID-73', 'abstain': False, 'citations': [{'id': 1}]})}}
        with patch.object(server, 'ollama', side_effect=[first, corrected]) as model:
            result = server.answer(self.body)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(result['type'], 'model')
        self.assertEqual(result['citations'][0]['quote'], 'The code is ORCHID-73.')

    def test_repair_copies_existing_passages_without_translating_quotes(self):
        original = 'Wynagrodzenie\twynosi\n8300 złotych brutto.'
        self.body['sources'][0]['turns'][0]['content'] = original
        first = self.reply([{'id': 1, 'quote': 'Винагорода становить 8300 злотих брутто.'}])
        repaired = {'message': {'content': json.dumps({'answer': '8300 złotych brutto.', 'abstain': False, 'citations': [{'id': 1}]})}}
        with patch.object(server, 'ollama', side_effect=[first, repaired]):
            result = server.answer(self.body)
        self.assertEqual(result['citations'][0]['quote'], original)

    def test_repair_cannot_reference_unknown_passages(self):
        first = self.reply([{'id': 1, 'quote': 'Wrong quotation'}])
        for ids in [[999], [True], [[]], []]:
            repaired = {'message': {'content': json.dumps({'answer': 'Invented', 'abstain': False, 'citations': [{'id': i} for i in ids]})}}
            with self.subTest(ids=ids), patch.object(server, 'ollama', side_effect=[first, repaired]):
                result = server.answer(self.body)
            self.assertEqual(result['answer_status'], 'unverified')
            self.assertNotIn('Invented', json.dumps(result))

    def test_one_correct_quote_does_not_hide_an_invalid_quote(self):
        mixed = self.reply([{'id': 1, 'quote': 'The code is ORCHID-73.'}, {'id': 1, 'quote': 'A made up claim.'}])
        with patch.object(server, 'ollama', return_value=mixed):
            result = server.answer(self.body)
        self.assertEqual(result['answer_status'], 'unverified')
        self.assertNotIn('made up', json.dumps(result))

    def test_malformed_response_or_id_has_a_bounded_safe_fallback(self):
        for response in [{'message': {'content': 'not JSON'}}, self.reply([{'id': [], 'quote': 'The code is ORCHID-73.'}]),
                         {'message': {'content': '[]'}}, self.reply([{'id': True, 'quote': 'The code is ORCHID-73.'}])]:
            with self.subTest(response=response), patch.object(server, 'ollama', return_value=response) as model:
                result = server.answer(self.body)
                self.assertEqual(result['answer_status'], 'unverified')
                self.assertEqual(model.call_count, 2)

    def test_empty_sources_do_not_call_model(self):
        with patch.object(server, 'ollama') as model:
            with self.assertRaises(ValueError): server.answer({'question': 'Anything?', 'sources': []})
            model.assert_not_called()

    def test_retrieval_finds_late_passage_and_bounds_context(self):
        self.body['sources'][0]['turns'] = [{'content': ('Unrelated filler. ' * 4000) + 'The code is ORCHID-73.'}]
        selected, partial = server.excerpts(self.body)
        self.assertTrue(partial)
        self.assertIn('ORCHID-73', selected[0]['text'])
        self.assertLessEqual(sum(len(c['text']) for c in selected), 18000)

    def test_abstention_can_omit_citations(self):
        with patch.object(server, 'ollama', return_value=self.reply([], True)):
            self.assertTrue(server.answer(self.body)['abstain'])

class SearchNormalizationTests(OfflineRetrievalTests):
    def test_currency_aliases_share_retrieval_tokens(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/search-equivalences.json').read_text())
        for query, canonical in cases:
            with self.subTest(query=query):
                self.assertEqual(server.tokens(query), server.tokens(canonical))

    def test_short_keywords_and_amounts_find_exact_quotes_without_model(self):
        original = 'The approved budget is 7300 PLN.'
        body = {'sources': [{'source_id': 'budget', 'turns': [{'content': original}]}]}
        for query in ['approved', '7300 зл', '7 300 zł', '7300', '7300 PLN']:
            with self.subTest(query=query), patch.object(server, 'ollama') as model:
                result = server.answer({**body, 'question': query})
                model.assert_not_called()
                self.assertEqual(result['type'], 'search')
                self.assertEqual(result['citations'], [{'source_id': 'budget', 'quote': original}])

    def test_amounts_are_not_partial_matches_or_currency_conversions(self):
        for original in ['The budget is 17300 PLN.', 'The budget is 7300 USD.', 'The budget is 8300 PLN.']:
            body = {'question': '7300 зл', 'sources': [{'source_id': 'other', 'turns': [{'content': original}]}]}
            self.assertIsNone(server.keyword_lookup(body))

    def test_question_still_uses_model_with_original_language_and_search_aid(self):
        original = 'The approved budget is 7300 PLN.'
        body = {'question': 'Чи погоджено 7300 зл?', 'sources': [
            {'source_id': 'budget', 'turns': [{'content': original}]}]}
        response = {'message': {'content': json.dumps({'answer': 'Так, бюджет затверджено.',
            'abstain': False, 'citations': [{'id': 1, 'quote': original}]})}}
        with patch.object(server, 'ollama', return_value=response) as model:
            result = server.answer(body)
        sent = json.loads(model.call_args.args[1]['messages'][1]['content'])
        self.assertEqual(sent['question'], body['question'])
        self.assertIn('7300 pln', sent['normalized_question'])
        self.assertEqual(result['citations'][0]['quote'], original)

    def test_late_passage_and_sentence_quote_are_preserved(self):
        original = 'The approved budget is 7300 PLN.'
        text = ('Unrelated sentence. ' * 4000) + original
        body = {'question': '7300 зл', 'sources': [{'source_id': 'late', 'turns': [{'content': text}]}]}
        selected, partial = server.excerpts(body)
        self.assertTrue(partial)
        self.assertIn(original, selected[0]['text'])
        self.assertEqual(server.answer(body)['citations'][0]['quote'], original)

class FollowupTests(OfflineRetrievalTests):
    def test_followup_context_recovers_a_late_source_in_large_collection(self):
        sources = [{'source_id': f'other-{i}', 'title': 'Other',
                    'turns': [{'content': 'Unrelated filler. ' * 80}]} for i in range(30)]
        sources.append({'source_id': 'target', 'title': 'Orchid',
                        'turns': [{'content': 'Orchid registration costs 460 EUR.'}]})
        body = {'question': 'How much was it?', 'previous_questions': ['What about Orchid registration?'],
                'sources': sources}
        selected, partial = server.excerpts(body)
        self.assertTrue(partial)
        self.assertEqual(selected[0]['source_id'], 'target')
        self.assertLessEqual(sum(len(c['text']) for c in selected), 18000)

    def test_invalid_or_unbounded_history_is_rejected_before_inference(self):
        body = {'question': 'How much?', 'sources': [
            {'source_id': 's1', 'turns': [{'content': 'The fee is 460 EUR.'}]}]}
        for context in ['not a list', ['x'] * 4, [None], [''], ['x' * 1001]]:
            with self.subTest(context=context), patch.object(server, 'ollama') as model:
                with self.assertRaises(ValueError):
                    server.answer({**body, 'previous_questions': context})
                model.assert_not_called()

    def test_context_is_sent_separately_and_cannot_validate_a_quote(self):
        body = {'question': 'How much?', 'previous_questions': ['Was the budget 9999 EUR?'],
                'sources': [{'source_id': 's1', 'turns': [{'content': 'The fee is 460 EUR.'}]}]}
        response = {'message': {'content': json.dumps({'answer': '9999 EUR', 'abstain': False,
            'citations': [{'id': 1, 'quote': 'Was the budget 9999 EUR?'}]})}}
        with patch.object(server, 'ollama', return_value=response) as model:
            result = server.answer(body)
        self.assertEqual(result['answer_status'], 'unverified')
        self.assertNotIn('9999', json.dumps(result))
        for call in model.call_args_list:
            sent = json.loads(call.args[1]['messages'][1]['content'])
            self.assertEqual(sent['previous_questions'], body['previous_questions'])
        sent = json.loads(model.call_args_list[0].args[1]['messages'][1]['content'])
        self.assertEqual(sent['excerpts'][0]['text'], 'The fee is 460 EUR.')

if __name__ == '__main__': unittest.main()
