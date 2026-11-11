import copy
import json
from pathlib import Path

from app.domain.prep import SemanticPrepEngine, prep_from_slots
from app.domain.prep_presentation import PrepTaskPresentation


def test_prep_presentation_matches_shared_platform_contract_without_mutating_source():
    fixture = json.loads((Path(__file__).parent / 'fixtures/prep_presentation.json').read_text())
    original = copy.deepcopy(fixture['task'])
    assert PrepTaskPresentation(fixture['task']).instruction_groups() == fixture['expected']
    assert fixture['task'] == original


def test_prep_engine_preserves_entry_point_and_does_not_leak_household_state():
    engine = SemanticPrepEngine()
    first = [{'recipe_id': 1, 'instructions': [{'text': 'Dice the onion.'}]}]
    second = [{'recipe_id': 2, 'instructions': [{'text': 'Mince the garlic.'}]}]
    assert engine.build(first) == prep_from_slots(first)
    assert engine.build(second) == prep_from_slots(second)
    assert engine.build([]) == []
    assert engine.build(first) == prep_from_slots(first)
