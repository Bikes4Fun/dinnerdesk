from app.domain.prep import prep_from_slots


def test_prep_title_uses_heading_line():
    tasks = prep_from_slots(
        [
            {
                "recipe_id": 1,
                "recipe_name": "Kebabs",
                "instructions": [
                    {
                        "text": "Mise en Place:\n- Wash produce\n- Mince garlic",
                        "prep": True,
                    }
                ],
            }
        ]
    )
    assert tasks[0]["title"] == "Mise en Place"


def test_prep_title_strips_inline_heading():
    tasks = prep_from_slots(
        [
            {
                "recipe_id": 1,
                "recipe_name": "Kebabs",
                "instructions": [
                    {
                        "text": "Salad dressing and chicken marinade: whisk together\n- oil",
                        "prep": True,
                    }
                ],
            }
        ]
    )
    assert tasks[0]["title"] == "Salad dressing and chicken marinade"


def test_cooking_steps_are_never_prep():
    assert prep_from_slots([{'recipe_id': 1, 'instructions': [{'text': 'Wash hands, then cook chicken.'}]}]) == []


def test_untagged_recipe_gets_make_ahead_steps():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Boats', 'instructions': [
        {'text': 'Heat the oven to 400°F.'},
        {'text': 'Rinse the mushrooms and cut them into small dice. Peel and mince the garlic.'},
        {'text': 'Cook the onion 3-4 minutes in the pan.'},
        {'text': 'Grate about 1 cup of mozzarella.'},
        {'text': 'For the dressing, whisk the oil, vinegar and Dijon in a small bowl.'},
        {'text': 'Plate the boats and sprinkle with parsley.'},
    ]}])
    titles = {t['title'] for t in tasks}
    assert titles == {'Prep mushrooms', 'Prep garlic', 'Grate mozzarella', 'Make dressing'}
    assert all(t['auto'] for t in tasks)
    assert tasks[0]['meals'][0]['steps'][0]['key']


def test_tagged_steps_win_over_suggestions():
    tasks = prep_from_slots([{'recipe_id': 1, 'instructions': [
        {'text': 'Dice the onion.'},
        {'text': 'Make the marinade: whisk soy and garlic.', 'prep': True},
    ]}])
    assert [t['title'] for t in tasks] == ['Make the marinade']
    assert tasks[0]['auto'] is False


def test_suggested_steps_batch_the_same_item_across_meals():
    tasks = prep_from_slots([
        {'recipe_id': 1, 'recipe_name': 'Tacos', 'instructions': [{'text': 'Dice the onion. Mince the garlic.'}]},
        {'recipe_id': 2, 'recipe_name': 'Chili', 'instructions': [{'text': 'Chop the onion.'}]},
    ])
    by_title = {t['title']: t for t in tasks}
    assert set(by_title) == {'Prep onion', 'Prep garlic'}
    assert by_title['Prep onion']['recipe_ids'] == [1, 2]
    assert tasks[0]['title'] == 'Prep onion'  # shared work first


def test_step_key_ignores_spacing_and_case():
    from app.domain.prep import step_key
    assert step_key('Dice  the onion.') == step_key('dice the onion.')


def test_browning_fruit_and_drained_beans_are_not_prep():
    from app.domain.prep import likely_prep
    assert likely_prep('Halve the avocado and slice it thin.') is None
    assert likely_prep('Pour the beans into a colander and rinse.') is None


def test_shared_heading_keeps_every_meals_steps_once():
    slots = [
        {'recipe_id': 1, 'recipe_name': 'Kebabs', 'instructions': [{'text': 'Make tzatziki:\nDice cucumber.', 'prep': True}]},
        {'recipe_id': 2, 'recipe_name': 'Bowls', 'instructions': [{'text': 'Make tzatziki:\nMince garlic.', 'prep': True}]},
    ]
    tasks = prep_from_slots(slots + [slots[0]])
    assert len(tasks) == 1
    assert tasks[0]['recipe_ids'] == [1, 2]
    assert tasks[0]['notes'].count('Kebabs') == 1
    assert 'Bowls' in tasks[0]['notes'] and 'Mince garlic.' in tasks[0]['notes']


def test_prep_has_meal_sections_and_collapsed_quantities():
    from app.domain.prep import prep_from_slots
    tasks = prep_from_slots([
        {'recipe_id': 1, 'recipe_name': 'Salad', 'ingredients': [{'name': 'romaine lettuce', 'quantity': '2 heads'}], 'instructions': [{'text': 'Wash and dry lettuce. Chop leaves.', 'prep': True}]},
        {'recipe_id': 2, 'recipe_name': 'Tacos', 'ingredients': [{'name': 'romaine lettuce', 'quantity': '1 head'}], 'instructions': [{'text': 'Wash and dry lettuce. Shred.', 'prep': True}]},
    ])
    assert len(tasks) == 1
    assert tasks[0]['quantities'] == ['3 head romaine lettuce']
    assert [m['name'] for m in tasks[0]['meals']] == ['Salad', 'Tacos']
    assert tasks[0]['meals'][1]['instructions'] == ['Wash and dry lettuce. Shred.']


def test_named_components_batch_across_recipes_without_duplicate_quantities():
    slots = [
        {"recipe_id": 1, "recipe_name": "Roast beef with mashed potatoes", "ingredients": [{"name": "potatoes", "quantity": "2 lb"}], "instructions": [{"text": "Peel the potatoes."}, {"text": "Dice the potatoes."}]},
        {"recipe_id": 2, "recipe_name": "Chicken with mashed potatoes", "ingredients": [{"name": "potatoes", "quantity": "1 lb"}], "instructions": [{"text": "Peel and dice potatoes."}]},
    ]
    task = prep_from_slots(slots)[0]
    assert task["title"] == "Prep mashed potatoes"
    assert task["recipe_ids"] == [1, 2]
    assert task["quantities"] == ["3 lb potatoes"]
    assert len(task["meals"][0]["steps"]) == 2


def test_tzatziki_component_keeps_knifework_together_but_excludes_cooking():
    tasks = prep_from_slots([{"recipe_id": 1, "recipe_name": "Kebabs with tzatziki", "instructions": [
        {"text": "Finely dice the cucumber."}, {"text": "Mix yogurt and garlic."}, {"text": "Grill chicken until cooked."}]}])
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Make tzatziki"
    assert len(tasks[0]["meals"][0]["steps"]) == 2


def test_same_ingredient_in_two_recipes_is_one_task_with_both_amounts():
    tasks = prep_from_slots([
        {'recipe_id': 1, 'recipe_name': 'Roast beef',
         'ingredients': [{'name': 'potatoes', 'quantity': '2 lb'}],
         'instructions': [{'text': 'Wash, peel and large dice the potatoes. Rinse the potatoes again.'}]},
        {'recipe_id': 2, 'recipe_name': 'Salisbury steak',
         'ingredients': [{'name': 'potatoes', 'quantity': '1 lb'}],
         'instructions': [{'text': 'Peel and cube the potatoes.'}]},
    ])
    assert len(tasks) == 1
    task = tasks[0]
    assert task['title'] == 'Prep potatoes'
    assert [m['name'] for m in task['meals']] == ['Roast beef', 'Salisbury steak']
    assert task['quantities'] == ['3 lb potatoes']  # each meal's amount counted once


def test_heading_names_the_component():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Kebabs',
        'ingredients': [{'name': 'cucumber', 'quantity': '1'}, {'name': 'plain greek yogurt', 'quantity': '1 cup'}],
        'instructions': [{'text': 'Make the tzatziki: Finely dice 1/4 of the cucumber. Stir together with the yogurt.'}]}])
    assert [t['title'] for t in tasks] == ['Make tzatziki']
    assert len(tasks[0]['meals'][0]['steps']) == 2


def test_filler_words_do_not_pull_in_ingredients():
    from app.domain.prep import mentioned
    ings = [{'name': 'chicken or vegetable broth'}, {'name': 'chicken breasts, boneless skinless'},
            {'name': 'frozen peas'}]
    assert mentioned('Chop the vegetables or the herbs.', ings) == []
    assert [i['name'] for i in mentioned('Cut the chicken into strips.', ings)] == ['chicken breasts, boneless skinless']


def test_cooking_sentence_does_not_drop_the_prep_sentence():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Stir fry', 'instructions': [
        {'text': 'Slice the zucchini into half moons. Heat oil in a large pan.'}]}])
    assert [t['title'] for t in tasks] == ['Prep zucchini']
    assert tasks[0]['meals'][0]['steps'][0]['text'] == 'Slice the zucchini into half moons.'


def test_unnamed_dressings_stay_with_their_own_meal():
    tasks = prep_from_slots([
        {'recipe_id': 1, 'recipe_name': 'Salad A', 'instructions': [{'text': 'For the dressing, whisk oil and vinegar.'}]},
        {'recipe_id': 2, 'recipe_name': 'Salad B', 'instructions': [{'text': 'For the dressing, whisk tahini and lemon.'}]},
    ])
    assert [t['recipe_ids'] for t in tasks] == [[1], [2]]


# #29: prep task names from real recipes.

def test_whisking_several_things_is_a_mix_not_whisk_garlic():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Bowls',
        'ingredients': [{'name': 'olive oil'}, {'name': 'red wine vinegar'}, {'name': 'garlic', 'quantity': '1 clove'}],
        'instructions': [{'text': 'Whisk together the olive oil, vinegar and garlic.'}]}])
    assert [t['title'] for t in tasks] == ['Mix olive oil, red wine vinegar & garlic']
    only_garlic = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Bowls',
        'ingredients': [{'name': 'garlic'}], 'instructions': [{'text': 'Whisk in the garlic.'}]}])
    assert [t['title'] for t in only_garlic] == ['Make sauce']  # garlic going into a sauce


def test_whisking_eggs_keeps_its_name():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Frittata',
        'ingredients': [{'name': 'eggs', 'quantity': '6'}], 'instructions': [{'text': 'Whisk the eggs.'}]}])
    assert [t['title'] for t in tasks] == ['Whisk eggs']


def test_trimming_roots_names_the_vegetable_not_off_roots():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Stir fry',
        'instructions': [{'text': 'Trim off the roots of the green onions.'}]}])
    assert [t['title'] for t in tasks] == ['Prep green onions']


def test_grating_on_a_grater_names_the_cheese():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Pasta',
        'instructions': [{'text': 'Grate the parmesan on the small holes of a box grater.'}]}])
    assert [t['title'] for t in tasks] == ['Grate parmesan']


def test_a_sauce_that_needs_the_stove_is_not_prep():
    from app.domain.prep import likely_prep
    assert likely_prep('Whisk the sauce in a saucepan until it thickens.') is None
    assert likely_prep('Combine the glaze ingredients and bring to a boil.') is None
    assert likely_prep('Whisk the sauce over medium heat.') is None


def test_black_pepper_and_bell_pepper_are_different_groceries():
    from app.domain.prep import mentioned
    ings = [{'name': 'ground black pepper'}, {'name': 'red bell peppers'}]
    assert [i['name'] for i in mentioned('Dice the bell pepper.', ings)] == ['red bell peppers']
    assert [i['name'] for i in mentioned('Dice the pepper.', ings)] == ['red bell peppers']
    assert [i['name'] for i in mentioned('Season with black pepper.', ings)] == ['ground black pepper']


def test_one_sentence_naming_several_ingredients_does_not_bleed():
    tasks = prep_from_slots([{'recipe_id': 1, 'recipe_name': 'Chili',
        'ingredients': [{'name': 'onion', 'quantity': '1'}, {'name': 'bell pepper', 'quantity': '2'},
                        {'name': 'celery', 'quantity': '3 stalks'}],
        'instructions': [{'text': 'Dice the onion, bell pepper and celery.'}]}])
    by_title = {t['title']: t for t in tasks}
    assert set(by_title) == {'Prep onion', 'Prep bell pepper', 'Prep celery'}
    assert by_title['Prep onion']['quantities'] == ['1 onion']
    assert by_title['Prep bell pepper']['quantities'] == ['2 bell pepper']
