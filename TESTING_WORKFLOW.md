# Help Desk System - Complete Testing Workflow

## 1. Pre-Testing Setup

### 1.1 Environment Setup
```bash
# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL database
# Ensure database 'help_db' exists and is running

# Run the application
python app.py
```

### 1.2 Test Data Setup
Ensure the following test users exist in the database:

| Role | Email | Password | Role ID |
|------|-------|----------|---------|
| Super Admin | manasvi@gmail.com | test123 | 1 |
| Support Manager | testmanager@test.com | test123 | 2 |
| Support Agent | testagent@test.com | AgentPass123! | 3 |
| Support Agent | jishakikani@gmail.com | test123 | 3 |
| Support Agent | jinal@gmail.com | test123 | 3 |
| Employee | khushi@gmail.com | test123 | 6 |
| Employee | khushi12@gmail.com | test123 | 6 |
| Admin | admin@test.com | test123 | 5 |
| Customer | bhavtik@gmail.com | test123 | 6 |

### 1.3 Test Browsers
- Chrome/Edge (recommended)
- Firefox
- Mobile browser (for responsive testing)

---

## 2. Authentication & Login Testing

### 2.1 Login Page Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AUTH-01 | Valid Super Admin login | 1. Go to `/login`<br>2. Enter `manasvi@gmail.com` / `test123`<br>3. Click Login | Redirected to `/super-admin-dashboard` |
| AUTH-02 | Valid Support Manager login | 1. Go to `/login`<br>2. Enter `testmanager@test.com` / `test123`<br>3. Click Login | Redirected to `/support_manager/dashboard` |
| AUTH-03 | Valid Support Agent login | 1. Go to `/login`<br>2. Enter `testagent@test.com` / `AgentPass123!`<br>3. Click Login | Redirected to `/support_agent/dashboard` |
| AUTH-04 | Valid Admin login | 1. Go to `/login`<br>2. Enter `admin@test.com` / `test123`<br>3. Click Login | Redirected to `/admin/dashboard` |
| AUTH-05 | Valid Employee login | 1. Go to `/login`<br>2. Enter `khushi@gmail.com` / `test123`<br>3. Click Login | Redirected to `/customer-dashboard` |
| AUTH-06 | Valid Customer login | 1. Go to `/login`<br>2. Enter `bhavtik@gmail.com` / `test123`<br>3. Click Login | Redirected to `/customer-dashboard` |
| AUTH-07 | Invalid email | 1. Go to `/login`<br>2. Enter invalid email / any password<br>3. Click Login | Alert: "Invalid Email" |
| AUTH-08 | Invalid password | 1. Go to `/login`<br>2. Enter valid email / wrong password<br>3. Click Login | Alert: "Invalid Password" |
| AUTH-09 | Empty fields | 1. Go to `/login`<br>2. Leave fields empty<br>3. Click Login | Alert: "Please enter both email and password" |
| AUTH-10 | Session persistence | 1. Login successfully<br>2. Refresh page<br>3. Close browser and reopen | Remains logged in (session persists) |
| AUTH-11 | Admin login redirect | 1. Login as Admin<br>2. Check redirect | Redirected to `/admin/dashboard` |

### 2.2 Registration Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AUTH-12 | Valid registration | 1. Go to `/register`<br>2. Fill all fields with valid data<br>3. Click Create Account | Redirected to `/login` with success message |
| AUTH-13 | Duplicate email | 1. Register with existing email<br>2. Submit form | Alert: "Email already exists" |
| AUTH-14 | Missing required fields | 1. Leave required fields empty<br>2. Submit form | Browser validation prevents submission |

### 2.3 Password Management Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AUTH-15 | Forgot password request | 1. Go to `/forgot-password`<br>2. Enter registered email<br>3. Submit | Success message shown (email sent in production) |
| AUTH-16 | Password reset with valid token | 1. Use valid reset token<br>2. Enter new password<br>3. Submit | Redirected to `/login` with success message |
| AUTH-17 | Password reset with invalid token | 1. Use invalid/expired token<br>2. View page | Error message displayed |
| AUTH-18 | Change password (logged-in user) | 1. Login as any user<br>2. Go to `/auth/change-password`<br>3. Enter current, new, and confirm password<br>4. Submit | Success message, redirected to login |
| AUTH-19 | Change password - wrong current | 1. Login<br>2. Go to change password<br>3. Enter wrong current password<br>4. Submit | Error: "Current password is incorrect" |
| AUTH-20 | Change password - password mismatch | 1. Login<br>2. Go to change password<br>3. Enter different new/confirm passwords<br>4. Submit | Error: "New passwords do not match" |
| AUTH-21 | Admin reset password for any user | 1. Login as Super Admin<br>2. Reset password for any user | User password updated successfully |

---

## 3. Super Admin Module Testing

### 3.1 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-01 | Dashboard loads | 1. Login as Super Admin<br>2. View dashboard | All stats cards visible (Users, Departments, Customers, Tickets, Open, Closed) |
| SA-02 | Charts render | 1. View dashboard<br>2. Check charts section | Ticket Analytics bar chart and Tickets By Category doughnut chart render |
| SA-03 | Recent tickets table | 1. View dashboard<br>2. Scroll to Recent Tickets | Table displays recent tickets with status badges |
| SA-04 | Top agents section | 1. View dashboard<br>2. Scroll to Top Agents | Table displays agents with solved ticket counts |

### 3.2 Users Management Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-05 | View users list | 1. Go to `/users`<br>2. View table | All users displayed with ID, Name, Email, Mobile, Status, Department, Role |
| SA-06 | Search users | 1. Enter name/email in search box<br>2. Click Search | Filtered results displayed |
| SA-07 | Add user - valid | 1. Click "Add User"<br>2. Fill all fields<br>3. Submit | Success flash, user added, modal closes |
| SA-08 | Add user - duplicate email | 1. Add user with existing email<br>2. Submit | Danger flash: "Email already exists" |
| SA-09 | Edit user | 1. Click edit icon on user row<br>2. Modify fields<br>3. Submit | Success flash, user updated |
| SA-10 | Delete user | 1. Click delete icon<br>2. Confirm deletion | Success flash, user removed from list |
| SA-11 | Toggle user status | 1. Click toggle status button<br>2. User status changes | Status badge toggles between Active/Inactive |
| SA-12 | Role dropdown in Add User | 1. Open Add User modal<br>2. Check Role dropdown | All 6 roles visible: Super Admin, Support Manager, Support Agent, Employee, Admin, Users |

### 3.3 Departments Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-13 | View departments | 1. Go to `/departments` | Table displays all departments |
| SA-14 | Add department | 1. Click "Add Department"<br>2. Enter name<br>3. Submit | Department added successfully |
| SA-15 | Edit department | 1. Click edit icon<br>2. Modify name<br>3. Submit | Department updated |
| SA-16 | Delete department | 1. Click delete icon<br>2. Confirm | Department deleted |

### 3.4 Roles Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-17 | View roles | 1. Go to `/roles` | Table displays all 6 roles |
| SA-18 | Add role | 1. Click "Add Role"<br>2. Enter role name<br>3. Submit | Role added successfully |
| SA-19 | Edit role | 1. Click edit icon<br>2. Modify name<br>3. Submit | Role updated |
| SA-20 | Delete role | 1. Click delete icon<br>2. Confirm | Role deleted |

### 3.5 Tickets Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-21 | View all tickets | 1. Go to `/tickets` | All tickets displayed in table |
| SA-22 | Add ticket | 1. Click "Add Ticket"<br>2. Fill form<br>3. Submit | Ticket created with auto-generated ticket number |
| SA-23 | Edit ticket | 1. Click edit on ticket<br>2. Modify fields<br>3. Submit | Ticket updated |
| SA-24 | Delete ticket | 1. Click delete icon<br>2. Confirm | Ticket deleted |
| SA-25 | Ticket assignment | 1. Go to `/ticket-assignment`<br>2. Select ticket and agent<br>3. Assign | Ticket assigned, notification created |

### 3.6 Ticket Status Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-26 | View statuses | 1. Go to `/ticket-status` | All statuses listed |
| SA-27 | Add status | 1. Click "Add Status"<br>2. Enter name<br>3. Submit | Status added |
| SA-28 | Edit status | 1. Click edit icon<br>2. Modify name<br>3. Submit | Status updated |
| SA-29 | Delete status | 1. Click delete icon<br>2. Confirm | Status deleted |

### 3.7 Categories Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-30 | View categories | 1. Go to `/categories` | All categories listed |
| SA-31 | Add category | 1. Enter category name<br>2. Submit | Category added |
| SA-32 | Edit category | 1. Click edit icon<br>2. Modify name<br>3. Submit | Category updated |
| SA-33 | Delete category | 1. Click delete icon<br>2. Confirm | Category deleted |

### 3.8 Priorities Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-34 | View priorities | 1. Go to `/priorities` | All priorities listed |
| SA-35 | Add priority | 1. Enter priority name<br>2. Submit | Priority added |
| SA-36 | Edit priority | 1. Click edit icon<br>2. Modify name<br>3. Submit | Priority updated |
| SA-37 | Delete priority | 1. Click delete icon<br>2. Confirm | Priority deleted |

### 3.9 SLA Rules Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-38 | View SLA rules | 1. Go to `/sla-rules` | All SLA rules listed |
| SA-39 | Add SLA rule | 1. Click "Add SLA Rule"<br>2. Fill priority, response time, resolution time<br>3. Submit | SLA rule added |
| SA-40 | Edit SLA rule | 1. Click edit icon<br>2. Modify values<br>3. Submit | SLA rule updated |
| SA-41 | Delete SLA rule | 1. Click delete icon<br>2. Confirm | SLA rule deleted |

### 3.10 Escalations Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-42 | View escalations | 1. Go to `/escalations` | All escalations listed |
| SA-43 | Add escalation | 1. Click "Add Escalation"<br>2. Fill form<br>3. Submit | Escalation added |
| SA-44 | Edit escalation | 1. Click edit icon<br>2. Modify fields<br>3. Submit | Escalation updated |
| SA-45 | Delete escalation | 1. Click delete icon<br>2. Confirm | Escalation deleted |

### 3.11 Notifications Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-46 | View notifications | 1. Go to `/notifications` | All notifications listed |
| SA-47 | Add notification | 1. Click "Add Notification"<br>2. Fill title and message<br>3. Submit | Notification added |
| SA-48 | Edit notification | 1. Click edit icon<br>2. Modify fields<br>3. Submit | Notification updated |
| SA-49 | Delete notification | 1. Click delete icon<br>2. Confirm | Notification deleted |

### 3.12 Reports Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-50 | View reports page | 1. Go to `/reports` | Reports dashboard loads |
| SA-51 | Ticket report | 1. Click "Ticket Report"<br>2. View data | Ticket statistics displayed |
| SA-52 | User report | 1. Click "User Report"<br>2. View data | User statistics displayed |
| SA-53 | Notification report | 1. Click "Notification Report"<br>2. View data | Notification statistics displayed |

### 3.13 Settings Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-54 | View settings | 1. Go to `/settings` | Current settings displayed |
| SA-55 | Update settings | 1. Modify settings fields<br>2. Click "Save Settings" | Settings updated, success flash |

### 3.14 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SA-56 | Super Admin logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

## 4. Support Manager Module Testing

### 4.1 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SM-01 | Dashboard loads | 1. Login as Support Manager<br>2. Go to `/support_manager/dashboard` | Dashboard loads with dynamic stats: Total Tickets, Open Tickets, Assigned, Closed |
| SM-02 | Dashboard charts render | 1. View dashboard<br>2. Check Ticket Analytics bar chart | Bar chart shows tickets grouped by status with real data |
| SM-03 | Priority chart renders | 1. View dashboard<br>2. Check Priority doughnut chart | Doughnut chart shows tickets grouped by priority |
| SM-04 | Recent tickets table | 1. View dashboard<br>2. Scroll to Recent Tickets | Table shows 10 most recent tickets with status badges |
| SM-05 | Access denied for non-managers | 1. Login as Support Agent<br>2. Try to access `/support_manager/dashboard` | Redirected to agent dashboard with "Access Denied" |
| SM-06 | Unauthenticated access | 1. Logout<br>2. Try to access `/support_manager/dashboard` | Redirected to `/login` |

### 4.2 Ticket Management Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SM-07 | View all tickets | 1. Login as Support Manager<br>2. Go to `/support_manager/tickets` | All tickets displayed in table |
| SM-08 | Search tickets | 1. Go to `/support_manager/tickets`<br>2. Enter search term<br>3. Click Search | Filtered results displayed |
| SM-09 | View ticket detail | 1. Click on a ticket<br>2. View details | Full ticket info, comments, attachments, status dropdown, agent assignment shown |
| SM-10 | Update ticket status | 1. Open ticket detail<br>2. Select new status from dropdown<br>3. Click Update | Status updated, success flash, status history recorded |
| SM-11 | Assign ticket to agent | 1. Open ticket detail<br>2. Select agent from dropdown<br>3. Click Assign | Ticket assigned, success flash |
| SM-12 | Unassign ticket | 1. Open ticket detail<br>2. Select "Unassign" from agent dropdown<br>3. Click Assign | Ticket unassigned successfully |

### 4.3 Team Management Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SM-13 | View team page | 1. Login as Support Manager<br>2. Go to `/support_manager/team` | All support agents listed with performance stats |
| SM-14 | Search team members | 1. Go to `/support_manager/team`<br>2. Enter search term<br>3. Submit | Filtered agent results displayed |
| SM-15 | Agent performance stats | 1. View team page | Each agent shows total tickets, resolved, pending counts |

### 4.4 Reports Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SM-16 | View reports page | 1. Login as Support Manager<br>2. Go to `/support_manager/reports` | Reports dashboard loads with stats cards |
| SM-17 | Status distribution chart | 1. View reports page<br>2. Check status chart | Doughnut chart shows tickets by status |
| SM-18 | Priority distribution chart | 1. View reports page<br>2. Check priority chart | Bar chart shows tickets by priority |
| SM-19 | Agent performance table | 1. View reports page<br>2. Scroll to Agent Performance | Table shows agents with total, resolved, pending ticket counts |

### 4.5 Profile Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SM-20 | View profile | 1. Login as Support Manager<br>2. Go to `/support_manager/profile` | Profile info displayed (name, email, role, department) |

### 4.6 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SM-21 | Manager logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

## 5. Support Agent Module Testing

### 5.1 Authentication Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-01 | Agent login | 1. Go to `/login`<br>2. Enter agent credentials<br>3. Click Login | Redirected to `/support_agent/dashboard` |
| AG-02 | Agent access denied | 1. Try to access `/super-admin-dashboard`<br>2. Check access | "Access Denied" flash message |

### 5.2 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-03 | Dashboard loads | 1. Login as Support Agent<br>2. View dashboard | Stats cards: My Tickets, Open, In Progress, Resolved, Closed |
| AG-04 | Recent tickets | 1. View dashboard<br>2. Scroll to Recent Assigned Tickets | Table shows tickets assigned to agent |

### 5.3 My Tickets Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-05 | View my tickets | 1. Go to `/support_agent/tickets` | Only tickets assigned to agent displayed |
| AG-06 | Search tickets | 1. Enter search term<br>2. Submit | Filtered results displayed |
| AG-07 | View ticket detail | 1. Click on ticket<br>2. View details | Full ticket info, comments, attachments displayed |

### 5.4 Ticket Actions Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-08 | Update ticket status | 1. Open ticket detail<br>2. Select new status<br>3. Submit | Status updated, history recorded |
| AG-09 | Add comment | 1. Open ticket detail<br>2. Enter comment<br>3. Submit | Comment added to ticket |
| AG-10 | Upload attachment | 1. Open ticket detail<br>2. Select file<br>3. Upload | File uploaded, attachment listed |
| AG-11 | Resolve ticket | 1. Click "Resolve" button<br>2. Confirm | Ticket status changed to Resolved |
| AG-12 | Close ticket | 1. Click "Close" button<br>2. Confirm | Ticket status changed to Closed |
| AG-13 | Reassign ticket | 1. Select new agent from dropdown<br>2. Submit | Ticket reassigned, notification sent |

### 5.5 Notifications Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-14 | View notifications | 1. Go to `/support_agent/notifications` | All notifications listed |
| AG-15 | Mark notification as read | 1. Click on notification<br>2. View detail | Notification marked as read |
| AG-16 | Delete notification | 1. Click delete icon<br>2. Confirm | Notification deleted |

### 5.6 Profile Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-17 | View profile | 1. Go to `/support_agent/profile` | Profile info displayed |

### 5.7 Reports Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-18 | View agent reports | 1. Go to `/support_agent/reports` | Agent-specific statistics displayed |
| AG-19 | View ticket stats | 1. Check stats section | Total, Open, In Progress, Resolved, Closed counts displayed |

### 5.8 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AG-20 | Agent logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

## 6. Admin Module Testing

### 6.1 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-01 | Dashboard loads | 1. Login as Admin<br>2. Go to `/admin/dashboard` | Dashboard with dynamic stats loads |
| AD-02 | Stats cards render | 1. View dashboard | Cards show: Total Tickets, Open, In Progress, Resolved, Customers, Agents, Employees, Closed |
| AD-03 | Ticket analytics chart | 1. View dashboard<br>2. Check Ticket Analytics chart | Bar chart shows tickets by status with real data |
| AD-04 | Priority chart renders | 1. View dashboard<br>2. Check Priority chart | Doughnut chart shows tickets by priority |
| AD-05 | Recent tickets table | 1. View dashboard | Table shows 10 most recent tickets with status/priority badges |

### 6.2 Tickets Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-06 | View all tickets | 1. Go to `/admin/tickets` | All tickets displayed in table |
| AD-07 | Search tickets | 1. Enter search term<br>2. Submit | Filtered results displayed |
| AD-08 | View ticket detail | 1. Click "View" on a ticket | Full ticket details, comments, attachments displayed |
| AD-09 | Update ticket status | 1. Open ticket detail<br>2. Select new status<br>3. Click Update | Status updated, success flash, status history recorded |
| AD-10 | Assign ticket to agent | 1. Open ticket detail<br>2. Select agent<br>3. Click Assign | Ticket assigned, success flash |

### 6.3 Customers Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-11 | View customers | 1. Go to `/admin/customers` | All customers listed with ticket counts |
| AD-12 | Search customers | 1. Enter search term<br>2. Submit | Filtered results displayed |

### 6.4 Agents Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-13 | View agents | 1. Go to `/admin/agents` | All support agents listed with performance stats |
| AD-14 | Search agents | 1. Enter search term<br>2. Submit | Filtered results displayed |

### 6.5 Reports Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-15 | View reports | 1. Go to `/admin/reports` | Reports dashboard loads with stats cards |
| AD-16 | Status distribution chart | 1. View reports | Doughnut chart shows tickets by status |
| AD-17 | Priority distribution chart | 1. View reports | Bar chart shows tickets by priority |
| AD-18 | Agent performance table | 1. View reports | Table shows agents with ticket stats |

### 6.6 Profile Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-19 | View profile | 1. Go to `/admin/profile` | Profile info displayed |
| AD-20 | Old dashboard redirect | 1. Access `/admin-dashboard` | 302 redirect to `/admin/dashboard` |

### 6.7 RBAC Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-21 | Agent blocked from admin | 1. Login as Support Agent<br>2. Access `/admin/dashboard` | Redirected to login with "Access Denied" |
| AD-22 | Super Admin blocked from admin | 1. Login as Super Admin<br>2. Access `/admin/dashboard` | Redirected to login with "Access Denied" |
| AD-23 | Unauthenticated access | 1. Logout<br>2. Access `/admin/dashboard` | Redirected to `/login` |

### 6.8 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-24 | Admin logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

### 6.1 Authentication Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-01 | Employee login | 1. Go to `/login`<br>2. Enter employee credentials<br>3. Click Login | Redirected to `/customer-dashboard` |
| EMP-02 | Employee access to customer portal | 1. Login as employee<br>2. Access `/customer-dashboard` | Dashboard loads successfully |

### 6.2 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-03 | Dashboard loads | 1. Login as employee<br>2. View dashboard | Stats cards: My Tickets, Open, Resolved, Closed |
| EMP-04 | Recent tickets | 1. View dashboard<br>2. Check Recent Tickets table | Employee's tickets displayed |

### 6.3 My Tickets Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-05 | View my tickets | 1. Go to `/customer-tickets` | All employee's tickets displayed |
| EMP-06 | Search tickets | 1. Enter search term<br>2. Submit | Filtered results displayed |
| EMP-07 | View ticket detail | 1. Click on ticket<br>2. View details | Full ticket info and comments displayed |

### 6.4 Submit Ticket Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-08 | Submit new ticket | 1. Go to `/submit-ticket`<br>2. Fill title, description, category<br>3. Submit | Ticket created with auto-generated ticket number |
| EMP-09 | Submit ticket - missing fields | 1. Leave required fields empty<br>2. Submit | Danger flash: "Title, Description, and Category are required" |
| EMP-10 | Submit ticket - valid data | 1. Fill all fields correctly<br>2. Submit | Success flash, redirected to My Tickets |

### 6.5 Ticket Actions Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-11 | Add comment | 1. Open ticket detail<br>2. Enter comment<br>3. Submit | Comment added |
| EMP-12 | Reopen ticket | 1. Click "Reopen" on closed/resolved ticket<br>2. Confirm | Ticket status changed to Reopened |

### 6.6 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-13 | Employee logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

## 7. Customer Module Testing

### 7.1 Authentication Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-01 | Customer login | 1. Go to `/login`<br>2. Enter customer credentials<br>3. Click Login | Redirected to `/customer-dashboard` |
| CU-02 | Wrong role access | 1. Login as Super Admin<br>2. Try to access `/customer-dashboard` | "Access Denied" flash message |

### 7.2 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-03 | Dashboard loads | 1. Login as customer<br>2. View dashboard | Stats cards and recent tickets displayed |
| CU-04 | Quick actions | 1. View dashboard<br>2. Click "Submit New Ticket" | Redirected to submit ticket page |

### 7.3 My Tickets Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-05 | View my tickets | 1. Go to `/customer-tickets` | All customer's tickets displayed |
| CU-06 | Search tickets | 1. Enter search term<br>2. Submit | Filtered results displayed |
| CU-07 | View ticket detail | 1. Click on ticket<br>2. View details | Full ticket info and public comments displayed |

### 7.4 Submit Ticket Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-08 | Submit new ticket | 1. Go to `/submit-ticket`<br>2. Fill form<br>3. Submit | Ticket created successfully |
| CU-09 | Missing fields | 1. Leave required fields empty<br>2. Submit | Validation error displayed |

### 7.5 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-10 | Customer logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

## 8. Role-Based Access Control Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| RBAC-01 | Super Admin access | 1. Login as Super Admin<br>2. Access all pages | All pages accessible |
| RBAC-02 | Support Manager access | 1. Login as Support Manager<br>2. Access `/support_manager/*` pages | All manager pages accessible |
| RBAC-03 | Support Agent restriction | 1. Login as Support Agent<br>2. Try to access `/users` | Redirected or access denied |
| RBAC-04 | Customer restriction | 1. Login as Customer<br>2. Try to access `/users` | "Access Denied" message |
| RBAC-05 | Employee access | 1. Login as Employee<br>2. Access customer pages | Customer pages accessible |
| RBAC-06 | Unauthenticated access | 1. Logout<br>2. Try to access `/super-admin-dashboard` | Redirected to `/login` |
| RBAC-07 | Manager access to own routes | 1. Login as Support Manager<br>2. Access `/support_manager/*` routes | All manager routes accessible |
| RBAC-08 | Non-manager blocked from manager routes | 1. Login as Support Agent<br>2. Try to access `/support_manager/dashboard` | Redirected to `/login` with "Access Denied" |
| RBAC-09 | Customer blocked from manager routes | 1. Login as Customer<br>2. Try to access `/support_manager/tickets` | Redirected to `/login` with "Access Denied" |
| RBAC-10 | Admin access to own routes | 1. Login as Admin<br>2. Access `/admin/*` routes | All admin routes accessible |
| RBAC-11 | Non-admin blocked from admin routes | 1. Login as Support Manager<br>2. Try to access `/admin/dashboard` | Redirected to `/login` with "Access Denied" |
| RBAC-12 | Super Admin blocked from admin routes | 1. Login as Super Admin<br>2. Try to access `/admin/dashboard` | Redirected to `/login` with "Access Denied" |

---

## 9. Database Integrity Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| DB-01 | Roles table | 1. Query roles table | 6 roles present: Super Admin, Support Manager, Support Agent, Employee, Admin, Users |
| DB-02 | Departments table | 1. Query departments table | 4 departments present |
| DB-03 | Users table | 1. Query users table | All test users present with correct roles |
| DB-04 | Tickets table | 1. Query tickets table | Tickets have valid foreign keys |
| DB-05 | Password hashing | 1. Check user password_hash | Passwords are hashed (not plain text) |

---

## 10. Security Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SEC-01 | SQL Injection - login | 1. Enter `' OR '1'='1` in email field<br>2. Submit | Login fails (no SQL injection) |
| SEC-02 | XSS - search | 1. Enter `<script>alert('xss')</script>` in search<br>2. Submit | Script tag escaped, no alert |
| SEC-03 | CSRF protection | 1. Inspect forms<br>2. Check for CSRF tokens | CSRF tokens present in forms |
| SEC-04 | Session fixation | 1. Login<br>2. Check session ID | Session ID changes after login |
| SEC-05 | Password visibility | 1. Check database<br>2. Check network requests | Passwords never sent in plain text over network |

---

## 11. Responsive Design Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| RESP-01 | Desktop view (1920x1080) | 1. Open application<br>2. Check layout | Full sidebar visible, content centered |
| RESP-02 | Tablet view (768px) | 1. Resize to tablet<br>2. Check layout | Sidebar toggle works, content adapts |
| RESP-03 | Mobile view (375px) | 1. Resize to mobile<br>2. Check layout | Sidebar hidden, hamburger menu works |
| RESP-04 | Login page mobile | 1. View login on mobile<br>2. Check form | Form fields stack vertically, buttons full width |

---

## 12. Cross-Browser Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| BROWSER-01 | Chrome | 1. Open in Chrome<br>2. Test login flow | All features work |
| BROWSER-02 | Firefox | 1. Open in Firefox<br>2. Test login flow | All features work |
| BROWSER-03 | Edge | 1. Open in Edge<br>2. Test login flow | All features work |

---

## 13. Performance Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| PERF-01 | Page load time | 1. Open DevTools Network tab<br>2. Load dashboard | Page loads in < 2 seconds |
| PERF-02 | Database query speed | 1. Load users page with 100+ users<br>2. Check load time | Page loads in < 3 seconds |
| PERF-03 | Concurrent logins | 1. Open 5 browser tabs<br>2. Login in each | All logins succeed, no crashes |

---

## 14. Known Issues & Fixes Applied

| Issue | Root Cause | Fix Applied |
|-------|-----------|-------------|
| Employee login shows "Access Denied" | `require_customer()` only allowed role_id 6 | Updated to allow role_id 4 (Employee) and 6 (Customer) |
| Login redirect missing Admin role | `login.js` didn't handle role_id 5 | Added redirect for role_id 5 to `/admin/dashboard` |
| Duplicate `/users` route | Both `app.py` and `routes/users.py` defined `/users` | Removed duplicate from `app.py` |
| Duplicate `data-status` attribute | HTML had two `data-status` attributes | Changed second to `data-department` |
| Missing `/admin-dashboard` route | Route not defined in `app.py` | Added redirect to `/admin/dashboard` |
| No authentication on admin routes | Routes were publicly accessible | Added `before_request` handler to protect all non-public routes |
| Old `login.js` not referenced | Template loaded wrong JS file | Updated `login.html` to load `js/login.js` |
| Support Manager dashboard hardcoded | Dashboard showed static dummy data | Implemented dynamic dashboard with real database queries |
| No Support Manager blueprint | Manager routes mixed with app.py | Created `routes/support_manager.py` blueprint with access control |
| No Admin blueprint | Admin routes mixed with app.py | Created `routes/admin.py` blueprint with access control |
| Customers shown in Users page | Users page showed all roles including customers | Added `WHERE role_id != 6` filter to `get_users()` and `user_report()` |
| Customers not shown in real-time | No real-time updates on Customers page | Added Socket.IO event emission on customer login/register, with client-side listener |
| Logout doesn't clear session | Logout route didn't clear session | Added `session.clear()` to logout route |
| Dashboard user count includes customers | `total_users` counted all users | Updated to `WHERE role_id != 6` |
| Admin role missing from login redirect | `login.js` didn't handle role_id 5 | Added redirect for role_id 5 to `/admin/dashboard` |

---

## 14. Customer & User Role Separation Testing

### 14.1 Users Page - Customer Exclusion

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ROLE-01 | Customers excluded from Users page | 1. Login as Super Admin<br>2. Go to `/users/`<br>3. Check user table | Only internal users (Super Admin, Support Manager, Support Agent, Employee, Admin) shown. No customers. |
| ROLE-02 | Internal users visible in Users page | 1. Login as Super Admin<br>2. Go to `/users/`<br>3. Check user table | All internal user roles visible with correct role names |
| ROLE-03 | Customer search in Users page | 1. Login as Super Admin<br>2. Go to `/users/`<br>3. Search for customer email | Customer not found in results |
| ROLE-04 | Customer excluded from User Report | 1. Login as Super Admin<br>2. Go to `/user-report`<br>3. Check user table | Only internal users shown. No customers. |
| ROLE-05 | Dashboard user count excludes customers | 1. Login as Super Admin<br>2. View `/super-admin-dashboard`<br>3. Check Total Users count | Count shows only internal users (roles 1-5). Customers counted separately. |

### 14.2 Customers Page - Real-time Display

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ROLE-06 | Customers page loads | 1. Login as Super Admin<br>2. Go to `/customers` | All customers displayed in table with name, email, mobile, department, status, tickets, last login |
| ROLE-06 | New customer appears in real-time | 1. Open `/customers` page in browser<br>2. Login as a customer from another tab<br>3. Return to customers page | New customer row appears automatically without page refresh |
| ROLE-07 | Customer registration appears in real-time | 1. Open `/customers` page in browser<br>2. Register a new customer from another tab<br>3. Return to customers page | New customer row appears automatically |
| ROLE-08 | Customer search | 1. Go to `/customers`<br>2. Enter search term<br>3. Click Search | Filtered customer results displayed |
| ROLE-09 | Customer status display | 1. View customers table | Active customers show green badge, Inactive show red badge |
| ROLE-09 | Employee login | 1. Login with employee credentials (role_id 4) | Redirected to `/customer-dashboard` |
| ROLE-10 | Employee dashboard access | 1. Login as employee<br>2. Access `/customer-dashboard` | Dashboard loads successfully |
| ROLE-11 | Employee tickets access | 1. Login as employee<br>2. Access `/customer-tickets` | Tickets page loads successfully |
| ROLE-12 | Employee submit ticket | 1. Login as employee<br>2. Access `/submit-ticket` | Submit ticket page loads successfully |
| ROLE-13 | Employee logout | 1. Login as employee<br>2. Click Logout | Session cleared, redirected to `/login` |

---

## 15. Test Execution Checklist

### Pre-requisites
- [ ] Database is running and migrated
- [ ] Test users created with known passwords
- [ ] Application starts without errors
- [ ] All static files are accessible

### Smoke Test (5 minutes)
- [ ] Login as Super Admin works
- [ ] Dashboard loads
- [ ] Users page loads (no customers shown)
- [ ] Customers page loads
- [ ] Logout works (session cleared)

### Full Regression Test (2 hours)
- [ ] All AUTH tests pass (AUTH-01 to AUTH-21)
- [ ] All SA tests pass (SA-01 to SA-56)
- [ ] All SM tests pass (SM-01 to SM-21)
- [ ] All AD tests pass (AD-01 to AD-24)
- [ ] All AG tests pass (AG-01 to AG-20)
- [ ] All EMP tests pass (EMP-01 to EMP-13)
- [ ] All CU tests pass (CU-01 to CU-10)
- [ ] All RBAC tests pass (RBAC-01 to RBAC-12)
- [ ] All ROLE tests pass (ROLE-01 to ROLE-13)
- [ ] All SEC tests pass (SEC-01 to SEC-05)

### 6.9 Admin Agent Management Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-25 | View agents list | 1. Login as Admin<br>2. Go to `/admin/agents` | All support agents listed with performance stats |
| AD-26 | Search agents | 1. Enter name/email in search box<br>2. Click Search | Filtered agent results displayed |
| AD-27 | Edit agent | 1. Click Edit on agent row<br>2. Modify fields<br>3. Submit | Agent updated, success flash |
| AD-28 | Delete agent | 1. Click delete icon<br>2. Confirm | Agent deleted, tickets unassigned |

### 6.10 Admin Customer Management Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-29 | View customers list | 1. Login as Admin<br>2. Go to `/admin/customers` | All customers listed with ticket counts |
| AD-30 | Search customers | 1. Enter name/email in search box<br>2. Click Search | Filtered customer results displayed |
| AD-31 | Edit customer | 1. Click Edit on customer row<br>2. Modify fields<br>3. Submit | Customer updated, success flash |
| AD-32 | Delete customer | 1. Click delete icon<br>2. Confirm | Customer deleted, tickets preserved |

### 6.11 Admin Settings Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-33 | View settings | 1. Go to `/admin/settings` | Current settings displayed in form |
| AD-34 | Update settings | 1. Modify settings fields<br>2. Click Save Settings | Settings updated, success flash |

### 6.12 Admin Notifications Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| AD-35 | View notifications | 1. Go to `/admin/notifications` | All admin notifications listed |
| AD-36 | Mark notification as read | 1. Click mark-read link<br>2. Check notification | Notification marked as read |
| AD-37 | Delete notification | 1. Click delete link<br>2. Confirm | Notification deleted |

---

## 7. Employee Module Testing

### 7.1 Authentication Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-01 | Employee login | 1. Go to `/login`<br>2. Enter employee credentials<br>3. Click Login | Redirected to `/customer-dashboard` |
| EMP-02 | Employee access to customer portal | 1. Login as employee<br>2. Access `/customer-dashboard` | Dashboard loads successfully |

### 7.2 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-03 | Dashboard loads | 1. Login as employee<br>2. View dashboard | Stats cards: My Tickets, Open, Resolved, Closed |
| EMP-04 | Recent tickets | 1. View dashboard<br>2. Check Recent Tickets table | Employee's tickets displayed |

### 7.3 My Tickets Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-05 | View my tickets | 1. Go to `/customer-tickets` | All employee's tickets displayed |
| EMP-06 | Search tickets | 1. Enter search term<br>2. Submit | Filtered results displayed |
| EMP-07 | View ticket detail | 1. Click on ticket<br>2. View details | Full ticket info and comments displayed |

### 7.4 Submit Ticket Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-08 | Submit new ticket | 1. Go to `/submit-ticket`<br>2. Fill title, description, category<br>3. Submit | Ticket created with auto-generated ticket number |
| EMP-09 | Submit ticket - missing fields | 1. Leave required fields empty<br>2. Submit | Danger flash: "Title, Description, and Category are required" |
| EMP-10 | Submit ticket - valid data | 1. Fill all fields correctly<br>2. Submit | Success flash, redirected to My Tickets |

### 7.5 Ticket Actions Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-11 | Add comment | 1. Open ticket detail<br>2. Enter comment<br>3. Submit | Comment added |
| EMP-12 | Reopen ticket | 1. Click "Reopen" on closed/resolved ticket<br>2. Confirm | Ticket status changed to Reopened |

### 7.6 Profile Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-13 | View profile | 1. Go to `/customer-profile` | Profile info displayed |
| EMP-14 | Profile fields | 1. View profile page<br>2. Check fields | Name, Email, Mobile, Role, Department shown |

### 7.7 Notifications Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-15 | View notifications | 1. Go to `/customer-notifications` | All notifications listed |
| EMP-16 | Mark notification as read | 1. Click mark-read button<br>2. Check notification | Notification marked as read |
| EMP-17 | Delete notification | 1. Click delete button<br>2. Confirm | Notification deleted |

### 7.8 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| EMP-18 | Employee logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

## 8. Customer Module Testing

### 8.1 Authentication Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-01 | Customer login | 1. Go to `/login`<br>2. Enter customer credentials<br>3. Click Login | Redirected to `/customer-dashboard` |
| CU-02 | Wrong role access | 1. Login as Super Admin<br>2. Try to access `/customer-dashboard` | "Access Denied" flash message |

### 8.2 Dashboard Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-03 | Dashboard loads | 1. Login as customer<br>2. View dashboard | Stats cards and recent tickets displayed |
| CU-04 | Quick actions | 1. View dashboard<br>2. Click "Submit New Ticket" | Redirected to submit ticket page |

### 8.3 My Tickets Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-05 | View my tickets | 1. Go to `/customer-tickets` | All customer's tickets displayed |
| CU-06 | Search tickets | 1. Enter search term<br>2. Submit | Filtered results displayed |
| CU-07 | View ticket detail | 1. Click on ticket<br>2. View details | Full ticket info and public comments displayed |

### 8.4 Submit Ticket Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-08 | Submit new ticket | 1. Go to `/submit-ticket`<br>2. Fill form<br>3. Submit | Ticket created successfully |
| CU-09 | Missing fields | 1. Leave required fields empty<br>2. Submit | Validation error displayed |

### 8.5 Profile Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-10 | View profile | 1. Go to `/customer-profile` | Profile info displayed |

### 8.6 Notifications Tests

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-11 | View notifications | 1. Go to `/customer-notifications` | All notifications listed |
| CU-12 | Mark notification as read | 1. Click mark-read button | Notification marked as read |
| CU-13 | Delete notification | 1. Click delete button | Notification deleted |

### 8.7 Logout Test

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| CU-14 | Customer logout | 1. Click "Logout" in sidebar<br>2. Check session | Redirected to `/login`, session cleared |

---

## 9. Role-Based Access Control Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| RBAC-01 | Super Admin access | 1. Login as Super Admin<br>2. Access all pages | All pages accessible |
| RBAC-02 | Support Manager access | 1. Login as Support Manager<br>2. Access `/support_manager/*` pages | All manager pages accessible |
| RBAC-03 | Support Agent restriction | 1. Login as Support Agent<br>2. Try to access `/users` | Redirected or access denied |
| RBAC-04 | Customer restriction | 1. Login as Customer<br>2. Try to access `/users` | "Access Denied" message |
| RBAC-05 | Employee access | 1. Login as Employee<br>2. Access customer pages | Customer pages accessible |
| RBAC-06 | Unauthenticated access | 1. Logout<br>2. Try to access `/super-admin-dashboard` | Redirected to `/login` |
| RBAC-07 | Manager access to own routes | 1. Login as Support Manager<br>2. Access `/support_manager/*` routes | All manager routes accessible |
| RBAC-08 | Non-manager blocked from manager routes | 1. Login as Support Agent<br>2. Try to access `/support_manager/dashboard` | Redirected to `/login` with "Access Denied" |
| RBAC-09 | Customer blocked from manager routes | 1. Login as Customer<br>2. Try to access `/support_manager/tickets` | Redirected to `/login` with "Access Denied" |
| RBAC-10 | Admin access to own routes | 1. Login as Admin<br>2. Access `/admin/*` routes | All admin routes accessible |
| RBAC-11 | Non-admin blocked from admin routes | 1. Login as Support Manager<br>2. Try to access `/admin/dashboard` | Redirected to `/login` with "Access Denied" |
| RBAC-12 | Super Admin blocked from admin routes | 1. Login as Super Admin<br>2. Try to access `/admin/dashboard` | Redirected to `/login` with "Access Denied" |

---

## 10. Database Integrity Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| DB-01 | Roles table | 1. Query roles table | 6 roles present: Super Admin, Support Manager, Support Agent, Employee, Admin, Users |
| DB-02 | Departments table | 1. Query departments table | 4 departments present |
| DB-03 | Users table | 1. Query users table | All test users present with correct roles |
| DB-04 | Tickets table | 1. Query tickets table | Tickets have valid foreign keys |
| DB-05 | Password hashing | 1. Check user password_hash | Passwords are hashed (not plain text) |

---

## 11. Security Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| SEC-01 | SQL Injection - login | 1. Enter `' OR '1'='1` in email field<br>2. Submit | Login fails (no SQL injection) |
| SEC-02 | XSS - search | 1. Enter `<script>alert('xss')</script>` in search<br>2. Submit | Script tag escaped, no alert |
| SEC-03 | CSRF protection | 1. Inspect forms<br>2. Check for CSRF tokens | CSRF tokens present in forms |
| SEC-04 | Session fixation | 1. Login<br>2. Check session ID | Session ID changes after login |
| SEC-05 | Password visibility | 1. Check database<br>2. Check network requests | Passwords never sent in plain text over network |

---

## 12. Responsive Design Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| RESP-01 | Desktop view (1920x1080) | 1. Open application<br>2. Check layout | Full sidebar visible, content centered |
| RESP-02 | Tablet view (768px) | 1. Resize to tablet<br>2. Check layout | Sidebar toggle works, content adapts |
| RESP-03 | Mobile view (375px) | 1. Resize to mobile<br>2. Check layout | Sidebar hidden, hamburger menu works |
| RESP-04 | Login page mobile | 1. View login on mobile<br>2. Check form | Form fields stack vertically, buttons full width |

---

## 13. Cross-Browser Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| BROWSER-01 | Chrome | 1. Open in Chrome<br>2. Test login flow | All features work |
| BROWSER-02 | Firefox | 1. Open in Firefox<br>2. Test login flow | All features work |
| BROWSER-03 | Edge | 1. Open in Edge<br>2. Test login flow | All features work |

---

## 14. Performance Testing

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| PERF-01 | Page load time | 1. Open DevTools Network tab<br>2. Load dashboard | Page loads in < 2 seconds |
| PERF-02 | Database query speed | 1. Load users page with 100+ users<br>2. Check load time | Page loads in < 3 seconds |
| PERF-03 | Concurrent logins | 1. Open 5 browser tabs<br>2. Login in each | All logins succeed, no crashes |

---

## 15. Known Issues & Fixes Applied

| Issue | Root Cause | Fix Applied |
|-------|-----------|-------------|
| Employee login shows "Access Denied" | `require_customer()` only allowed role_id 6 | Updated to allow role_id 4 (Employee) and 6 (Customer) |
| Login redirect missing Admin role | `login.js` didn't handle role_id 5 | Added redirect for role_id 5 to `/admin/dashboard` |
| Duplicate `/users` route | Both `app.py` and `routes/users.py` defined `/users` | Removed duplicate from `app.py` |
| Duplicate `data-status` attribute | HTML had two `data-status` attributes | Changed second to `data-department` |
| Missing `/admin-dashboard` route | Route not defined in `app.py` | Added redirect to `/admin/dashboard` |
| No authentication on admin routes | Routes were publicly accessible | Added `before_request` handler to protect all non-public routes |
| Old `login.js` not referenced | Template loaded wrong JS file | Updated `login.html` to load `js/login.js` |
| Support Manager dashboard hardcoded | Dashboard showed static dummy data | Implemented dynamic dashboard with real database queries |
| No Support Manager blueprint | Manager routes mixed with app.py | Created `routes/support_manager.py` blueprint with access control |
| No Admin blueprint | Admin routes mixed with app.py | Created `routes/admin.py` blueprint with access control |
| Customers shown in Users page | Users page showed all roles including customers | Added `WHERE role_id != 6` filter to `get_users()` and `user_report()` |
| Customers not shown in real-time | No real-time updates on Customers page | Added Socket.IO event emission on customer login/register, with client-side listener |
| Logout doesn't clear session | Logout route didn't clear session | Added `session.clear()` to logout route |
| Dashboard user count includes customers | `total_users` counted all users | Updated to `WHERE role_id != 6` |
| Admin role missing from login redirect | `login.js` didn't handle role_id 5 | Added redirect for role_id 5 to `/admin/dashboard` |
| Undefined `data` variable in tickets.py `create_sla()` | Function referenced `data` before assignment | Added `data = request.get_json(silent=True) or request.form` |
| Missing IntegrityError import in routes/users.py | `except IntegrityError` without import | Added `from sqlalchemy.exc import IntegrityError` |
| Model file contained route handlers | `models/user.py` had blueprint code | Removed blueprint, kept only User model |
| Duplicate commit in customer submit ticket | Two `db.session.commit()` calls | Removed duplicate commit |
| Inconsistent ticket number format | `save_ticket` used different format than `add_ticket` | Standardized to `TKT{YYYYMMDD}{NNNN}` format |
| Duplicate GROUP BY in SQL queries | `GROUP BY col, col` syntax | Removed duplicate column in GROUP BY |
| Wrong route parameter in edit_priority | Route used `<int:id>` for string lookup | Changed to `<priority_name>` parameter |

---

## 16. Customer & User Role Separation Testing

### 16.1 Users Page - Customer Exclusion

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ROLE-01 | Customers excluded from Users page | 1. Login as Super Admin<br>2. Go to `/users/`<br>3. Check user table | Only internal users (Super Admin, Support Manager, Support Agent, Employee, Admin) shown. No customers. |
| ROLE-02 | Internal users visible in Users page | 1. Login as Super Admin<br>2. Go to `/users/`<br>3. Check user table | All internal user roles visible with correct role names |
| ROLE-03 | Customer search in Users page | 1. Login as Super Admin<br>2. Go to `/users/`<br>3. Search for customer email | Customer not found in results |
| ROLE-04 | Customer excluded from User Report | 1. Login as Super Admin<br>2. Go to `/user-report`<br>3. Check user table | Only internal users shown. No customers. |
| ROLE-05 | Dashboard user count excludes customers | 1. Login as Super Admin<br>2. View `/super-admin-dashboard`<br>3. Check Total Users count | Count shows only internal users (roles 1-5). Customers counted separately. |

### 16.2 Customers Page - Real-time Display

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ROLE-06 | Customers page loads | 1. Login as Super Admin<br>2. Go to `/customers` | All customers displayed in table with name, email, mobile, department, status, tickets, last login |
| ROLE-07 | New customer appears in real-time | 1. Open `/customers` page in browser<br>2. Login as a customer from another tab<br>3. Return to customers page | New customer row appears automatically without page refresh |
| ROLE-08 | Customer registration appears in real-time | 1. Open `/customers` page in browser<br>2. Register a new customer from another tab<br>3. Return to customers page | New customer row appears automatically |
| ROLE-09 | Customer search | 1. Go to `/customers`<br>2. Enter search term<br>3. Click Search | Filtered customer results displayed |
| ROLE-10 | Customer status display | 1. View customers table | Active customers show green badge, Inactive show red badge |
| ROLE-11 | Employee login | 1. Login with employee credentials (role_id 4) | Redirected to `/customer-dashboard` |
| ROLE-12 | Employee dashboard access | 1. Login as employee<br>2. Access `/customer-dashboard` | Dashboard loads successfully |
| ROLE-13 | Employee tickets access | 1. Login as employee<br>2. Access `/customer-tickets` | Tickets page loads successfully |
| ROLE-14 | Employee submit ticket | 1. Login as employee<br>2. Access `/submit-ticket` | Submit ticket page loads successfully |
| ROLE-15 | Employee logout | 1. Login as employee<br>2. Click Logout | Session cleared, redirected to `/login` |

---

## 17. Admin Module Extended Testing

### 17.1 Admin Agent Management

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ADM-01 | View agents list | 1. Login as Admin<br>2. Go to `/admin/agents` | All agents listed with performance stats |
| ADM-02 | Search agents | 1. Enter search term<br>2. Submit | Filtered results displayed |
| ADM-03 | Edit agent | 1. Click Edit button<br>2. Modify fields<br>3. Submit | Agent updated, success flash |
| ADM-04 | Delete agent | 1. Click delete button<br>2. Confirm | Agent deleted, tickets unassigned |

### 17.2 Admin Customer Management

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ADM-05 | View customers list | 1. Login as Admin<br>2. Go to `/admin/customers` | All customers listed with ticket counts |
| ADM-06 | Search customers | 1. Enter search term<br>2. Submit | Filtered results displayed |
| ADM-07 | Edit customer | 1. Click Edit button<br>2. Modify fields<br>3. Submit | Customer updated, success flash |
| ADM-08 | Delete customer | 1. Click delete button<br>2. Confirm | Customer deleted, tickets preserved |

### 17.3 Admin Settings

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ADM-09 | View settings | 1. Go to `/admin/settings` | Settings form displayed |
| ADM-10 | Update settings | 1. Modify fields<br>2. Submit | Settings saved, success flash |

### 17.4 Admin Notifications

| Test ID | Test Case | Steps | Expected Result |
|---------|-----------|-------|-----------------|
| ADM-11 | View notifications | 1. Go to `/admin/notifications` | All admin notifications listed |
| ADM-12 | Mark as read | 1. Click mark-read link | Notification marked as read |
| ADM-13 | Delete notification | 1. Click delete link | Notification deleted |

---

## 18. Test Execution Checklist

### Pre-requisites
- [ ] Database is running and migrated
- [ ] Test users created with known passwords
- [ ] Application starts without errors
- [ ] All static files are accessible

### Smoke Test (5 minutes)
- [ ] Login as Super Admin works
- [ ] Dashboard loads
- [ ] Users page loads (no customers shown)
- [ ] Customers page loads
- [ ] Logout works (session cleared)

### Full Regression Test (2 hours)
- [ ] All AUTH tests pass (AUTH-01 to AUTH-21)
- [ ] All SA tests pass (SA-01 to SA-56)
- [ ] All SM tests pass (SM-01 to SM-21)
- [ ] All AD tests pass (AD-01 to AD-37)
- [ ] All AG tests pass (AG-01 to AG-20)
- [ ] All EMP tests pass (EMP-01 to EMP-18)
- [ ] All CU tests pass (CU-01 to CU-14)
- [ ] All RBAC tests pass (RBAC-01 to RBAC-12)
- [ ] All ROLE tests pass (ROLE-01 to ROLE-15)
- [ ] All SEC tests pass (SEC-01 to SEC-05)
- [ ] All ADM tests pass (ADM-01 to ADM-13)

### Sign-off
- [ ] All critical tests passed
- [ ] No blocking bugs found
- [ ] Performance acceptable
- [ ] Security scan passed
- [ ] Documentation updated
