from tests.test_api import _client


def test_drafts_preserve_live_plan_and_history(tmp_path):
    with _client(tmp_path) as c:
        live = c.get('/api/plans/current').json()
        live = c.put(f'/api/plans/{live["id"]}/slots', json={'slots': [{'recipe_id': 1, 'servings': 3}]}).json()
        c.patch(f'/api/slots/{live["slots"][0]["id"]}', json={'cooked': True})
        draft = c.post('/api/plans', json={'title': 'Rotation', 'draft': True, 'source_plan_id': live['id']}).json()
        assert draft['status'] == 'draft'
        assert not draft['slots'][0]['cooked']
        assert c.get('/api/plans/current').json()['id'] == live['id']
        next_plan = c.post('/api/plans', json={'source_plan_id': draft['id']}).json()
        assert c.get('/api/plans/current').json()['id'] == next_plan['id']
        previous = c.get(f'/api/plans/{live["id"]}').json()
        assert previous['status'] == 'history'
        assert previous['slots'][0]['cooked']
        assert next_plan['slots'][0]['servings'] == 3
        assert c.post('/api/plans', json={'source_plan_id': 1}).status_code == 404  # other household


def test_schedule_arbitrary_future_date(tmp_path):
    with _client(tmp_path) as c:
        plan = c.get('/api/plans/current').json()
        plan = c.put(f'/api/plans/{plan["id"]}/slots', json={'slots': [{'recipe_id': 1}]}).json()
        slot = plan['slots'][0]
        result = c.patch(f'/api/slots/{slot["id"]}', json={'scheduled_date': '2035-12-25'})
        assert result.status_code == 200
        assert result.json()['day_index'] > 13
        assert c.get('/api/plans/current').json()['days'] == result.json()['day_index'] + 1
        assert c.patch(f'/api/slots/{slot["id"]}', json={'scheduled_date': '2000-01-01'}).status_code == 400
        assert c.patch(f'/api/slots/{slot["id"]}', json={'unschedule': True}).json()['day_index'] is None


def test_placements_persist_across_plans_and_are_private(tmp_path):
    with _client(tmp_path) as c:
        assert c.put('/api/grocery/places', json={'name': 'onion', 'store': 'local', 'aisle': 'produce'}).status_code == 200
        c.put('/api/grocery/places', json={'name': 'onion', 'aisle': 'other'})
        places = c.get('/api/grocery/places').json()['items']
        assert {'name': 'onion', 'store': 'local', 'aisle': 'other'} in places
        assert not any(p['name'] == 'hidden salt' for p in places)
        c.post('/api/plans', json={})
        assert {'name': 'onion', 'store': 'local', 'aisle': 'other'} in c.get('/api/grocery/places').json()['items']


def test_new_household_has_no_automatic_staples(tmp_path):
    with _client(tmp_path) as c:
        assert not any(i['never_shop'] or i['have'] for i in c.get('/api/pantry').json()['items'])


def test_database_configuration_is_mandatory(monkeypatch):
    import pytest
    from app.db.database import connect
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='DATABASE_URL is required'):
        connect()


def test_taste_sessions_use_postgresql(tmp_path):
    from app.taste_lab import taste
    module = taste()
    # Each test runs in its own PostgreSQL schema.
    module.init_db()
    sid = module.save_event({'anon_id': 'test-cook', 'kind': 'snapshot', 'body': {'likes': ['soup']}})
    rows = module.list_sessions()
    assert rows[0]['id'] == sid
    assert rows[0]['likes'] == ['soup']


def test_missing_email_configuration_fails(monkeypatch):
    import pytest
    from app.mailer import send_reset_email
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='RESEND_API_KEY is required'):
        send_reset_email('cook@example.com', 'https://example.com/reset/test')


def test_pantry_amounts_and_overrides_do_not_change_catalog(tmp_path):
    from tests.test_api import _link_soup_onion
    with _client(tmp_path) as c:
        _link_soup_onion(tmp_path)
        plan = c.get('/api/plans/current').json()
        c.put(f'/api/plans/{plan["id"]}/slots', json={'slots': [{'recipe_id': 1}]})
        item = c.post('/api/pantry/items', json={'name': 'onion', 'quantity': '1 kg', 'have': True}).json()
        line = next(l for l in c.get(f'/api/plans/{plan["id"]}/grocery').json()['lines'] if 'onion' in l['name'])
        assert line['from_pantry'] and not line['checked']
        assert c.patch(f'/api/pantry/items/{item["id"]}', json={'quantity': '500 g'}).json()['quantity'] == '500 g'
        original = c.get('/api/recipes/1').json()['ingredients']
        c.post('/api/overrides', json={'from_name': 'onion', 'to_name': 'garlic'})
        lines = c.get(f'/api/plans/{plan["id"]}/grocery').json()['lines']
        assert any('garlic' in l['name'] for l in lines)
        assert c.get('/api/recipes/1').json()['ingredients'] == original


def test_prep_uses_overlay_tags_and_drops_removed_meals(tmp_path):
    with _client(tmp_path) as c:
        plan = c.get('/api/plans/current').json()
        plan = c.put(f'/api/plans/{plan["id"]}/slots', json={'slots': [{'recipe_id': 1}]}).json()
        recipe = c.patch('/api/recipes/1', json={'in_place': True, 'instructions': [{'text': 'Mise en Place:\nDice onion.', 'prep': True}, {'text': 'Wash hands and simmer soup.'}]}).json()
        assert recipe['catalog']
        c.post(f'/api/plans/{plan["id"]}/grocery')
        tasks = c.get(f'/api/plans/{plan["id"]}/prep').json()['tasks']
        assert len(tasks) == 1 and tasks[0]['title'] == 'Mise en Place'
        assert 'Dice onion.' in tasks[0]['notes']
        c.patch(f'/api/prep/{tasks[0]["id"]}', json={'done': True})
        c.post(f'/api/plans/{plan["id"]}/grocery')
        assert c.get(f'/api/plans/{plan["id"]}/prep').json()['tasks'][0]['done']
        c.delete(f'/api/slots/{plan["slots"][0]["id"]}')
        assert c.get(f'/api/plans/{plan["id"]}/prep').json()['tasks'] == []


def test_grocery_editor_survives_flags_and_keeps_manual_edits(tmp_path):
    from tests.test_api import _link_soup_onion
    with _client(tmp_path) as c:
        _link_soup_onion(tmp_path)
        plan = c.get('/api/plans/current').json()
        c.put(f'/api/plans/{plan["id"]}/slots', json={'slots': [{'recipe_id': 1}]})
        line = next(l for l in c.post(f'/api/plans/{plan["id"]}/grocery').json()['lines'] if 'onion' in l['name'])
        c.patch(f'/api/grocery/lines/{line["id"]}', json={'custom_text': 'yellow onion', 'quantity': '2 medium', 'store': 'local', 'aisle': 'other'})
        assert c.get("/api/overrides").json()["items"] == []
        item = c.post('/api/pantry/items', json={'name': 'yellow onion', 'have': True, 'never_shop': True, 'quantity': '1 kg'}).json()
        lines = c.get(f'/api/plans/{plan["id"]}/grocery').json()['lines']
        updated = next(l for l in lines if l['id'] == line['id'])
        assert updated['name'] == 'yellow onion' and updated['quantity'] == '2 medium'
        assert updated['never_shop'] and updated['from_pantry']
        preserved = c.post('/api/pantry/items', json={'name': 'yellow onion', 'have': True, 'never_shop': True}).json()
        assert preserved['quantity'] == '1 kg'
        assert updated['store'] == 'local' and updated['aisle'] == 'other'
        assert c.delete(f'/api/pantry/items/{item["id"]}').status_code == 200
        after = next(l for l in c.get(f'/api/plans/{plan["id"]}/grocery').json()['lines'] if l['id'] == line['id'])
        assert not after['never_shop'] and not after['from_pantry']
        assert after['quantity'] == '2 medium'


def test_removing_last_store_clears_saved_placements(tmp_path):
    with _client(tmp_path) as c:
        c.put('/api/household', json={'prefs': {'grocery': {'stores': [{'id': 'costco', 'name': 'Costco'}]}}})
        c.put('/api/grocery/places', json={'name': 'onion', 'store': 'costco', 'aisle': 'produce'})
        assert c.put('/api/household', json={'prefs': {'grocery': {'stores': []}}}).status_code == 200
        row = next(p for p in c.get('/api/grocery/places').json()['items'] if p['name'] == 'onion')
        assert row['store'] == '' and row['aisle'] == 'produce'


def test_tagging_current_plan_recipe_updates_prep(tmp_path):
    from tests.test_api import _client
    with _client(tmp_path) as c:
        plan = c.get('/api/plans/current').json()
        result = c.put(f'/api/plans/{plan["id"]}/slots', json={'slots': [{'recipe_id': 1}]})
        assert result.status_code == 200
        result = c.patch('/api/recipes/1', json={'instructions': [{'text': 'Wash and chop onion.', 'prep': True}]})
        assert result.status_code == 200
        tasks = c.get(f'/api/plans/{plan["id"]}/prep').json()['tasks']
        assert len(tasks) == 1
        assert tasks[0]['meals'][0]['id'] == 1
        assert tasks[0]['meals'][0]['instructions'] == ['Wash and chop onion.']


def test_prep_refreshes_stale_tasks_without_losing_completion(tmp_path):
    from app.db.database import connect
    with _client(tmp_path) as c:
        plan = c.get('/api/plans/current').json()
        c.put(f'/api/plans/{plan["id"]}/slots', json={'slots': [{'recipe_id': 1}]})
        c.patch('/api/recipes/1', json={'instructions': [{'text': 'Chop onion.', 'prep': True}]})
        task = c.get(f'/api/plans/{plan["id"]}/prep').json()['tasks'][0]
        c.patch(f'/api/prep/{task["id"]}', json={'done': True})
        db = connect()
        db.execute("UPDATE prep_tasks SET details_json = '{}' WHERE id = ?", (task['id'],))
        db.commit()
        db.close()
        refreshed = c.get(f'/api/plans/{plan["id"]}/prep').json()['tasks'][0]
        assert refreshed['id'] == task['id']
        assert refreshed['done']
        assert refreshed['meals'][0]['instructions'] == ['Chop onion.']
        db = connect()
        db.execute('DELETE FROM prep_tasks WHERE plan_id = ?', (plan['id'],))
        db.commit()
        db.close()
        assert len(c.get(f'/api/plans/{plan["id"]}/prep').json()['tasks']) == 1


def test_repeated_manual_grocery_items_combine_quantities_and_ids(tmp_path):
    with _client(tmp_path) as c:
        plan = c.get('/api/plans/current').json()
        url = f'/api/plans/{plan["id"]}/grocery/lines'
        first = c.post(url, json={'name': 'jalapeño peppers', 'quantity': '2', 'store': 'costco'}).json()
        second = c.post(url, json={'name': 'jalapeño peppers', 'quantity': '3', 'store': 'costco'}).json()
        assert second['id'] == first['id']
        assert second['quantity'] == '5'
        lines = c.get(f'/api/plans/{plan["id"]}/grocery').json()['lines']
        assert len(lines) == 1
        assert lines[0]['quantity'] == '5'


def test_manual_repeat_of_recipe_ingredient_retains_meal_and_scaling(tmp_path):
    with _client(tmp_path) as c:
        c.patch('/api/recipes/1', json={'ingredients': [{'name': 'onion', 'quantity': '2'}]})
        plan = c.get('/api/plans/current').json()
        plan = c.put(f'/api/plans/{plan["id"]}/slots', json={'slots': [{'recipe_id': 1, 'servings': 4}]}).json()
        line = c.get(f'/api/plans/{plan["id"]}/grocery').json()['lines'][0]
        added = c.post(f'/api/plans/{plan["id"]}/grocery/lines', json={'name': 'onion'}).json()
        assert added['id'] == line['id']
        assert added['quantity'] == '2'
        assert added['used_in'][0]['id'] == 1
        c.patch(f'/api/slots/{plan["slots"][0]["id"]}', json={'servings': 8})
        lines = c.get(f'/api/plans/{plan["id"]}/grocery').json()['lines']
        assert len(lines) == 1
        assert lines[0]['quantity'] == '4'


def test_new_week_keeps_prep_tags_for_saved_recipe_edits(tmp_path):
    with _client(tmp_path) as c:
        first = c.get('/api/plans/current').json()
        c.put(f'/api/plans/{first["id"]}/slots', json={'slots': [{'recipe_id': 1}]})
        c.patch('/api/recipes/1', json={'instructions': [{'text': 'Chop onion.', 'prep': True}]})
        next_plan = c.post('/api/plans', json={'source_plan_id': first['id']}).json()
        assert next_plan['id'] != first['id']
        tasks = c.get(f'/api/plans/{next_plan["id"]}/prep').json()['tasks']
        assert len(tasks) == 1
        assert tasks[0]['meals'][0]['instructions'] == ['Chop onion.']
