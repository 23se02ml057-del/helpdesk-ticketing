from app import app

def test_admin_notification_routes_exist():
    rules = [rule.rule for rule in app.url_map.iter_rules()]
    assert '/admin/notifications' in rules, "Missing GET /admin/notifications"
    assert '/admin/notifications/mark-read/<int:notification_id>' in rules, "Missing mark-read route"
    assert '/admin/notifications/<int:notification_id>/delete' in rules, "Missing delete route"
    assert '/admin/notifications/mark-all-read' in rules, "Missing mark-all-read route"
    assert '/admin/notifications/delete-all-read' in rules, "Missing delete-all-read route"
    print('OK: All admin notification routes registered')


def test_admin_notification_methods():
    admin_notif = app.view_functions.get('admin.notifications')
    assert admin_notif is not None, "admin.notifications view function missing"

    mark_read = app.view_functions.get('admin.mark_notification_read')
    assert mark_read is not None, "mark_notification_read view function missing"

    delete = app.view_functions.get('admin.delete_notification')
    assert delete is not None, "delete_notification view function missing"

    mark_all = app.view_functions.get('admin.mark_all_notifications_read')
    assert mark_all is not None, "mark_all_notifications_read view function missing"

    delete_all = app.view_functions.get('admin.delete_all_read_notifications')
    assert delete_all is not None, "delete_all_read_notifications view function missing"
    print('OK: All admin notification view functions exist')


def test_template_has_table_and_actions():
    from flask import render_template_string
    html = open('templates/admin_notifications.html').read()
    assert 'table-hover' in html, "Missing table class"
    assert 'fa-trash' in html, "Missing delete icon"
    assert 'fa-check' in html, "Missing mark-read icon"
    assert 'filter=all' in html or 'filter' in html, "Missing filter dropdown"
    assert 'mark_all_read' in html or 'mark-all-read' in html or 'Mark All Read' in html, "Missing mark all read button"
    assert 'url_for(\'admin.delete_notification\'' in html, "Missing delete action URL"
    assert 'url_for(\'admin.mark_notification_read\'' in html, "Missing mark-read action URL"
    print('OK: Template has table, actions, filters, and bulk actions')


if __name__ == '__main__':
    test_admin_notification_routes_exist()
    test_admin_notification_methods()
    test_template_has_table_and_actions()
    print('\nAll admin notification tests passed!')
