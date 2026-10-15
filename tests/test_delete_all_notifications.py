from app import app

def test_delete_all_routes_exist():
    rules = [rule.rule for rule in app.url_map.iter_rules()]
    assert '/notifications/delete-all' in rules, "Missing Super Admin delete-all route"
    assert '/admin/notifications/delete-all' in rules, "Missing Admin delete-all route"
    assert '/support_manager/notifications/delete-all' in rules, "Missing Support Manager delete-all route"
    assert '/support_agent/notifications/delete-all' in rules, "Missing Support Agent delete-all route"
    assert '/customer-notifications/delete-all' in rules, "Missing Customer delete-all route"
    print('OK: All delete-all routes registered')


def test_delete_all_view_functions_exist():
    assert app.view_functions.get('notifications.delete_all_notifications') is not None, "notifications.delete_all_notifications missing"
    assert app.view_functions.get('admin.delete_all_notifications') is not None, "admin.delete_all_notifications missing"
    assert app.view_functions.get('support_manager.delete_all_notifications') is not None, "support_manager.delete_all_notifications missing"
    assert app.view_functions.get('support_agent.delete_all_notifications') is not None, "support_agent.delete_all_notifications missing"
    assert app.view_functions.get('customer.delete_all_notifications') is not None, "customer.delete_all_notifications missing"
    print('OK: All delete-all view functions exist')


def test_admin_template_has_delete_all():
    html = open('templates/admin_notifications.html').read()
    assert 'deleteAllNotificationsModal' in html, "Missing delete-all modal in admin template"
    assert 'Delete All Notifications' in html, "Missing delete-all button text in admin template"
    assert 'confirmDeleteAllBtn' in html, "Missing confirm button in admin template"
    assert 'url_for(\'admin.delete_all_notifications\')' in html, "Missing delete-all URL in admin template"
    print('OK: Admin template has delete-all UI')


def test_agent_template_has_delete_all():
    html = open('templates/agent_notifications.html').read()
    assert 'deleteAllNotificationsModal' in html, "Missing delete-all modal in agent template"
    assert 'Delete All Notifications' in html, "Missing delete-all button text in agent template"
    assert 'confirmDeleteAllBtn' in html, "Missing confirm button in agent template"
    assert 'url_for(\'support_agent.delete_all_notifications\')' in html, "Missing delete-all URL in agent template"
    print('OK: Agent template has delete-all UI')


def test_manager_template_has_delete_all():
    html = open('templates/manager_notifications.html').read()
    assert 'deleteAllNotificationsModal' in html, "Missing delete-all modal in manager template"
    assert 'Delete All Notifications' in html, "Missing delete-all button text in manager template"
    assert 'confirmDeleteAllBtn' in html, "Missing confirm button in manager template"
    assert 'url_for(\'support_manager.delete_all_notifications\')' in html, "Missing delete-all URL in manager template"
    print('OK: Manager template has delete-all UI')


def test_super_admin_template_has_delete_all():
    html = open('templates/notifications.html').read()
    assert 'deleteAllNotificationsModal' in html, "Missing delete-all modal in super admin template"
    assert 'Delete All Notifications' in html, "Missing delete-all button text in super admin template"
    assert 'confirmDeleteAllBtn' in html, "Missing confirm button in super admin template"
    assert 'url_for(\'notifications.delete_all_notifications\')' in html, "Missing delete-all URL in super admin template"
    assert 'data-user-id' in html, "Missing user-id data attribute for selective deletion"
    print('OK: Super Admin template has delete-all UI with user isolation')


def test_customer_template_has_delete_all():
    html = open('templates/customer_notifications.html').read()
    assert 'deleteAllNotificationsModal' in html, "Missing delete-all modal in customer template"
    assert 'Delete All' in html, "Missing delete-all button text in customer template"
    assert 'confirmDeleteAllBtn' in html, "Missing confirm button in customer template"
    assert 'url_for(\'customer.delete_all_notifications\')' in html, "Missing delete-all URL in customer template"
    print('OK: Customer template has delete-all UI')


def test_backend_only_deletes_current_user():
    from routes.admin import admin_bp
    from routes.support_agent import support_agent_bp
    from routes.support_manager import support_manager_bp
    from routes.notifications import notifications_bp
    from routes.customer import customer_bp

    admin_source = open('routes/admin.py').read()
    agent_source = open('routes/support_agent.py').read()
    manager_source = open('routes/support_manager.py').read()
    notifications_source = open('routes/notifications.py').read()
    customer_source = open('routes/customer.py').read()

    assert "WHERE user_id = :user_id" in admin_source, "Admin delete-all missing user filter"
    assert "WHERE user_id = :user_id" in agent_source, "Agent delete-all missing user filter"
    assert "WHERE user_id = :user_id" in manager_source, "Manager delete-all missing user filter"
    assert "WHERE user_id = :user_id" in notifications_source, "Super Admin delete-all missing user filter"
    assert "WHERE user_id = :user_id" in customer_source, "Customer delete-all missing user filter"
    print('OK: All delete-all routes filter by current user')


if __name__ == '__main__':
    test_delete_all_routes_exist()
    test_delete_all_view_functions_exist()
    test_admin_template_has_delete_all()
    test_agent_template_has_delete_all()
    test_manager_template_has_delete_all()
    test_super_admin_template_has_delete_all()
    test_customer_template_has_delete_all()
    test_backend_only_deletes_current_user()
    print('\nAll delete-all notification tests passed!')
