from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_babel import gettext as _
from sqlalchemy import text
from help_db import db
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, timezone
from utils.ai_service import AIService, ai_service
import json
import io
from fpdf import FPDF

customer_bp = Blueprint('customer', __name__)





def require_customer():
    user_id = session.get("user_id")
    if not user_id:
        flash(_("please_login_first"), "danger")
        return redirect(url_for("login_page"))
    
    role = db.session.execute(
        text("""
            SELECT r.role_name, u.role_id
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()
    
    if not role or (role[0] not in ["Customer", "Employee"] and role[1] not in [4, 6]):
        flash(_("access_denied"), "danger")
        return redirect(url_for("login_page"))
    return None


@customer_bp.route('/customer-logout')
def logout():
    session.clear()
    flash(_("logged_out_successfully"), "success")
    return redirect(url_for("login_page"))


@customer_bp.route('/customer-dashboard')
def dashboard():
    auth_check = require_customer()
    if auth_check:
        return auth_check
    
    user_id = session.get("user_id")
    
    total_tickets = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE requester_id = :user_id
        """),
        {"user_id": user_id}
    ).scalar()
    
    open_tickets = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE requester_id = :user_id AND status_name = 'Open'
        """),
        {"user_id": user_id}
    ).scalar()
    
    resolved_tickets = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE requester_id = :user_id AND status_name = 'Resolved'
        """),
        {"user_id": user_id}
    ).scalar()
    
    closed_tickets = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE requester_id = :user_id AND status_name = 'Closed'
        """),
        {"user_id": user_id}
    ).scalar()
    
    pending_tickets = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE requester_id = :user_id AND status_name IN ('Pending', 'In Progress', 'On Hold')
        """),
        {"user_id": user_id}
    ).scalar()
    
    recent_tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.status_name,
                t.priority_name,
                t.created_at,
                t.updated_at
            FROM tickets t
            WHERE t.requester_id = :user_id
            ORDER BY t.ticket_id DESC
            LIMIT 10
        """),
        {"user_id": user_id}
    ).fetchall()
    
    # Chart data: Tickets by Status
    status_data = db.session.execute(
        text("""
            SELECT 
                COALESCE(t.status_name, 'Unknown') as status_name,
                COUNT(*) as count
            FROM tickets t
            WHERE t.requester_id = :user_id
            GROUP BY t.status_name
            ORDER BY count DESC
        """),
        {"user_id": user_id}
    ).fetchall()
    
    status_labels = [row.status_name for row in status_data] if status_data else []
    status_counts = [row.count for row in status_data] if status_data else []
    
    # Chart data: Ticket activity over time (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    activity_data = db.session.execute(
        text("""
            SELECT 
                DATE(created_at) as ticket_date,
                COUNT(*) as count
            FROM tickets
            WHERE requester_id = :user_id
              AND created_at >= :start_date
            GROUP BY DATE(created_at)
            ORDER BY ticket_date
        """),
        {"user_id": user_id, "start_date": thirty_days_ago}
    ).fetchall()
    
    # Create a complete date range for the last 30 days
    date_labels = []
    date_counts = []
    activity_dict = {row.ticket_date.strftime('%Y-%m-%d'): row.count for row in activity_data} if activity_data else {}
    
    for i in range(30):
        date = (datetime.now(timezone.utc) - timedelta(days=29-i)).date()
        date_str = date.strftime('%Y-%m-%d')
        display_str = date.strftime('%d %b')
        date_labels.append(display_str)
        date_counts.append(activity_dict.get(date_str, 0))
    
    return render_template(
        "customer_dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        resolved_tickets=resolved_tickets,
        closed_tickets=closed_tickets,
        pending_tickets=pending_tickets,
        recent_tickets=recent_tickets,
        status_labels=status_labels,
        status_counts=status_counts,
        activity_labels=date_labels,
        activity_counts=date_counts
    )


@customer_bp.route('/customer-tickets')
def my_tickets():
    auth_check = require_customer()
    if auth_check:
        return auth_check
    
    user_id = session.get("user_id")
    search = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    page = int(request.args.get("page", 1))
    per_page = 10
    
    # Build query with filters
    query = """
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.description,
            c.category_name,
            t.created_at,
            t.ai_suggested_priority,
            t.issue_type_id,
            it.issue_name,
            t.status_name,
            t.priority_name
        FROM tickets t
        LEFT JOIN categories c ON t.category_name = c.category_name
        LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
        WHERE t.requester_id = :user_id
    """
    params = {"user_id": user_id}
    
    if search:
        query += " AND (t.ticket_number ILIKE :search OR t.title ILIKE :search)"
        params["search"] = f"%{search}%"
    
    if status_filter:
        query += " AND t.status_name = :status_filter"
        params["status_filter"] = status_filter
    
    if priority_filter:
        query += " AND t.priority_name = :priority_filter"
        params["priority_filter"] = priority_filter
    
    # Count total for pagination
    count_query = "SELECT COUNT(*) " + query[query.find("FROM"):]
    total = db.session.execute(text(count_query), params).scalar()
    
    # Pagination
    query += " ORDER BY t.ticket_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page
    
    tickets = db.session.execute(text(query), params).fetchall()
    
    total_pages = ((total or 0) + per_page - 1) // per_page
    
    # Get available statuses and priorities for filter dropdowns
    statuses = db.session.execute(text("SELECT DISTINCT status_name FROM tickets ORDER BY status_name")).fetchall()
    status_list = [s[0] for s in statuses] if statuses else []
    
    priorities = db.session.execute(text("SELECT DISTINCT priority_name FROM tickets ORDER BY priority_name")).fetchall()
    priority_list = [p[0] for p in priorities] if priorities else []
    
    return render_template(
        "customer_tickets.html",
        tickets=tickets,
        search=search,
        status_filter=status_filter,
        priority_filter=priority_filter,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_num": page - 1,
            "next_num": page + 1,
        },
        status_list=status_list,
        priority_list=priority_list
    )


@customer_bp.route('/api/customer-tickets/search')
def api_customer_tickets_search():
    auth_check = require_customer()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    page = int(request.args.get("page", 1))
    per_page = 10
    
    params = {"user_id": user_id}
    
    query = """
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            c.category_name,
            t.issue_type_id,
            it.issue_name,
            t.created_at,
            t.status_name,
            t.priority_name
        FROM tickets t
        LEFT JOIN categories c ON t.category_name = c.category_name
        LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
        WHERE t.requester_id = :user_id
    """
    
    if q:
        query += " AND (t.ticket_number ILIKE :search OR t.title ILIKE :search)"
        params["search"] = f"%{q}%"
    
    if status_filter:
        query += " AND t.status_name = :status_filter"
        params["status_filter"] = status_filter
    
    if priority_filter:
        query += " AND t.priority_name = :priority_filter"
        params["priority_filter"] = priority_filter
    
    # Count total
    count_query = "SELECT COUNT(*) " + query[query.find("FROM"):]
    total = db.session.execute(text(count_query), params).scalar()
    
    # Pagination
    query += " ORDER BY t.ticket_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page
    
    tickets = db.session.execute(text(query), params).fetchall()

    rows = []
    for tk in tickets:
        rows.append({
            "ticket_id": tk.ticket_id,
            "ticket_number": tk.ticket_number,
            "title": tk.title,
            "category_name": tk.category_name or 'N/A',
            "issue_name": tk.issue_name or '-',
            "created_at": tk.created_at.strftime('%Y-%m-%d') if tk.created_at else 'N/A',
            "status_name": tk.status_name,
            "priority_name": tk.priority_name
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": ((total or 0) + per_page - 1) // per_page,
    })


@customer_bp.route('/customer-tickets/<int:ticket_id>')
def ticket_detail(ticket_id):
    auth_check = require_customer()
    if auth_check:
        return auth_check
    
    user_id = session.get("user_id")
    
    ticket = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.description,
                t.status_name,
                t.priority_name,
                c.category_name,
                t.created_at,
                t.updated_at,
                t.assigned_to,
                d.department_name,
                it.issue_name
            FROM tickets t
            LEFT JOIN categories c ON t.category_name = c.category_name
            LEFT JOIN departments d ON t.department_id = d.department_id
            LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
            WHERE t.ticket_id = :ticket_id
              AND t.requester_id = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()
    
    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(url_for("customer.my_tickets"))
    
    comments = db.session.execute(
        text("""
            SELECT
                tc.comment_id,
                tc.comment_text,
                tc.created_at,
                u.first_name,
                u.last_name,
                r.role_name
            FROM ticket_comments tc
            JOIN users u ON tc.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE tc.ticket_id = :ticket_id
              AND tc.is_internal = FALSE
            ORDER BY tc.comment_id ASC
        """),
        {"ticket_id": ticket_id}
    ).fetchall()
    
    return render_template(
        "customer_ticket_detail.html",
        ticket=ticket,
        comments=comments
    )


@customer_bp.route('/customer-tickets/<int:ticket_id>/comment', methods=['POST'])
def add_comment(ticket_id):
    auth_check = require_customer()
    if auth_check:
        return auth_check
    
    user_id = session.get("user_id")
    
    ticket = db.session.execute(
        text("""
            SELECT ticket_id FROM tickets
            WHERE ticket_id = :ticket_id
              AND requester_id = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()
    
    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(url_for("customer.my_tickets"))
    
    comment_text = request.form.get("comment_text")
    if not comment_text:
        flash(_("comment_text_is_required"), "danger")
        return redirect(url_for("customer.ticket_detail", ticket_id=ticket_id))
    
    existing = db.session.execute(
        text("""
            SELECT comment_id FROM ticket_comments
            WHERE ticket_id = :ticket_id
              AND user_id = :user_id
              AND comment_text = :comment_text
              AND created_at > NOW() - INTERVAL '5 minutes'
        """),
        {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "comment_text": comment_text
        }
    ).fetchone()
    
    if existing:
        flash(_("duplicate_comment_detected"), "warning")
        return redirect(url_for("customer.ticket_detail", ticket_id=ticket_id))
    
    db.session.execute(
        text("""
            INSERT INTO ticket_comments (ticket_id, user_id, comment_text)
            VALUES (:ticket_id, :user_id, :comment_text)
        """),
        {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "comment_text": comment_text
        }
    )
    db.session.commit()

    ticket_info = db.session.execute(
        text("SELECT ticket_number, title, assigned_to FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    if ticket_info and ticket_info[2]:
        from utils.notifications import create_notification
        create_notification(
            ticket_info[2],
            "New Comment",
            f"New comment on ticket #{ticket_info[0]} - {ticket_info[1]}"
        )

    flash(_("comment_added_successfully"), "success")
    return redirect(url_for("customer.ticket_detail", ticket_id=ticket_id))


@customer_bp.route('/customer-tickets/<int:ticket_id>/reopen', methods=['POST'])
def reopen_ticket(ticket_id):
    auth_check = require_customer()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    ticket = db.session.execute(
        text("""
            SELECT ticket_id, reopen_count FROM tickets
            WHERE ticket_id = :ticket_id
              AND requester_id = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(url_for("customer.my_tickets"))

    db.session.execute(
        text("""
            UPDATE tickets
            SET status_name = 'Open',
                reopen_count = :reopen_count
            WHERE ticket_id = :ticket_id
        """),
        {
            "ticket_id": ticket_id,
            "reopen_count": (ticket[1] or 0) + 1
        }
    )
    db.session.commit()

    ticket_info = db.session.execute(
        text("""
            SELECT t.ticket_number, t.title, u.first_name, u.last_name
            FROM tickets t
            LEFT JOIN users u ON t.requester_id = u.user_id
            WHERE t.ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()

    if ticket_info:
        from utils.notifications import create_notification
        customer_name = f"{ticket_info[2] or ''} {ticket_info[3] or ''}".strip() or "A customer"
        message = f"Ticket #{ticket_info[0]} - {ticket_info[1]} has been reopened by {customer_name}."

        admins = db.session.execute(
            text("SELECT user_id FROM users WHERE role_id = 1 AND status = 'Active'")
        ).fetchall()
        for admin in admins:
            create_notification(admin[0], "Ticket Reopened", message)

        managers = db.session.execute(
            text("SELECT user_id FROM users WHERE role_id = 2 AND status = 'Active'")
        ).fetchall()
        for manager in managers:
            create_notification(manager[0], "Ticket Reopened", message)

    flash(_("ticket_reopened_successfully"), "success")
    return redirect(url_for("customer.ticket_detail", ticket_id=ticket_id))


@customer_bp.route('/customer-tickets/<int:ticket_id>/close', methods=['POST'])
def close_ticket(ticket_id):
    auth_check = require_customer()
    if auth_check:
        return auth_check
    
    user_id = session.get("user_id")
    
    ticket = db.session.execute(
        text("""
            SELECT ticket_id, status_name FROM tickets
            WHERE ticket_id = :ticket_id
              AND requester_id = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(url_for("customer.my_tickets"))

    old_status = ticket[1]

    db.session.execute(
        text("""
            UPDATE tickets
            SET status_name = 'Closed'
            WHERE ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    )
    db.session.commit()

    from utils.email_service import send_closed_ticket_email
    send_closed_ticket_email(ticket_id, old_status, 'Closed', support_agent_name='Support Team')

    flash(_("ticket_closed_successfully"), "success")
    return redirect(url_for("customer.ticket_detail", ticket_id=ticket_id))


@customer_bp.route('/submit-ticket', methods=['GET', 'POST'])
def submit_ticket():
    auth_check = require_customer()
    if auth_check:
        return auth_check
    
    user_id = session.get("user_id")
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        if not title:
            flash(_("title_is_required"), "danger")
            return redirect(url_for("customer.submit_ticket"))
        
        print(f"\n[AI DEBUG] ========== TICKET ANALYSIS ==========")
        print(f"[AI DEBUG] Title: {title}")
        print(f"[AI DEBUG] Description: {description}")
        
        # Fetch valid categories and settings
        valid_categories = {c[0] for c in db.session.execute(text("SELECT category_name FROM categories")).fetchall()}
        settings_row = db.session.execute(
            text("SELECT auto_assign_tickets, default_priority FROM settings ORDER BY setting_id DESC LIMIT 1")
        ).fetchone()
        auto_assign = settings_row[0] if settings_row else True
        default_priority = settings_row[1] if settings_row and settings_row[1] else "Medium"
        
        # AI CATEGORY DETECTION using deterministic DB-based classifier
        category_result = ai_service.classify_category_from_db(title, description or '')
        ai_category = category_result.get("category")
        category_confidence = category_result.get("confidence", "low") if category_result.get("success") else "low"
        category_source = "deterministic"
        
        print(f"[AI DEBUG] Category classification: {ai_category} (confidence: {category_confidence}, source: {category_source})")
        
        if not ai_category or ai_category not in valid_categories:
            print(f"[AI DEBUG] WARNING: Category '{ai_category}' not in DB categories {valid_categories}")
            for fallback_cat in ["Technical", "System Access", "Software Issue", "Network Issue", "Hardware Issue", "General Query"]:
                if fallback_cat in valid_categories:
                    ai_category = fallback_cat
                    print(f"[AI DEBUG] Using fallback category: {ai_category}")
                    break
        
        if not ai_category:
            ai_category = "General Query" if "General Query" in valid_categories else (list(valid_categories)[0] if valid_categories else "Technical")
            print(f"[AI DEBUG] Using final fallback category: {ai_category}")
        
        # Determine required skill for the selected category
        skill_result = ai_service.find_best_skill_for_category(ai_category, title)
        required_skill_id = skill_result.get("skill_id") if skill_result.get("success") else None
        print(f"[AI DEBUG] Required skill: {skill_result.get('skill_name')} (ID: {required_skill_id})")
        
        # Try to match title against predefined issue types for AI context
        validated_issue_type_id = None
        issue_type_context = ""
        matched_issue = db.session.execute(
            text("""
                SELECT issue_type_id, issue_name
                FROM issue_types
                WHERE status = 'Active'
                  AND LOWER(issue_name) = LOWER(:title)
                LIMIT 1
            """),
            {"title": title.strip()}
        ).fetchone()
        
        if matched_issue:
            validated_issue_type_id = matched_issue[0]
            issue_type_context = matched_issue[1]
            print(f"[AI DEBUG] Matched predefined issue type: {issue_type_context} (ID: {validated_issue_type_id})")
        else:
            print(f"[AI DEBUG] No predefined issue type match for title - using custom issue")
        
        print(f"[AI DEBUG] Final Category: {ai_category} (source: {category_source})")
        print(f"[AI DEBUG] Issue Type ID: {validated_issue_type_id}")
        
        # LLM PRIORITY DETECTION (with category and issue type context)
        print(f"[AI DEBUG] Analyzing priority...")
        priority_result = ai_service.analyze_priority(title, description or '', category=ai_category, issue_type=issue_type_context)
        
        if priority_result.get("success"):
            ai_priority = priority_result.get("priority", default_priority)
            priority_source = "llm"
            print(f"[AI DEBUG] LLM priority: {ai_priority} (reason: {priority_result.get('reasoning')})")
        else:
            print(f"[AI DEBUG] LLM priority failed: {priority_result.get('error')}, using deterministic fallback")
            fallback_priority = ai_service.classify_priority(title, description or '', category=ai_category)
            ai_priority = fallback_priority.get("priority", default_priority)
            priority_source = "deterministic"
            print(f"[AI DEBUG] Deterministic priority: {ai_priority} (reason: {fallback_priority.get('reasoning')})")
        
        # DEPARTMENT DETERMINATION from DB category relationship
        dept_info = ai_service.get_department_for_category_from_db(ai_category)
        if dept_info.get("success"):
            department_id = dept_info.get("department_id")
            ai_suggested_department = dept_info.get("department_name")
        else:
            print(f"[AI DEBUG] WARNING: Could not determine department for category '{ai_category}': {dept_info.get('error')}")
            department_id = None
            ai_suggested_department = None
        
        print(f"[AI DEBUG] Department: {ai_suggested_department} (ID: {department_id})")
        
        # AGENT ASSIGNMENT
        assigned_to = None
        match_score = 0
        assignment_method = None
        assignment_reason = None
        matched_skill_id = None
        
        if auto_assign and ai_suggested_department:
            print(f"[AI DEBUG] Auto-assignment is enabled")
            agent_result = ai_service.find_best_agent(
                ai_suggested_department,
                category=ai_category,
                issue_title=title,
                issue_description=description,
                allow_fallback=False,
                required_skill_id=required_skill_id
            )
            if agent_result.get("success"):
                assigned_to = agent_result.get("agent_id")
                department_id = agent_result.get("department_id")
                match_score = agent_result.get("match_score", 0)
                assignment_method = agent_result.get("assignment_method", "AI Match")
                matched_skill_id = agent_result.get("matched_skill_id")
                assignment_reason = agent_result.get("reasoning")
                print(f"[AI DEBUG] Assigned Agent: {agent_result.get('agent_name')} (ID: {assigned_to}, dept_id: {department_id}, score: {match_score}, method: {assignment_method})")
            else:
                print(f"[AI DEBUG] Assignment failed: {agent_result.get('reasoning')}")
                assignment_reason = agent_result.get("reasoning", "No suitable agent found")
        else:
            print(f"[AI DEBUG] Auto-assignment is disabled or no department determined")
        
        ai_confidence = "high" if category_confidence == "high" and priority_result.get("success") else "medium" if category_confidence in ["medium", "high"] else "low"
        ai_correction_type = None
        if category_source == "llm":
            ai_correction_type = "priority_ai_assigned"
        
        last_ticket = db.session.execute(
            text("SELECT ticket_number FROM tickets ORDER BY ticket_id DESC LIMIT 1")
        ).fetchone()
        
        if last_ticket:
            try:
                last_number = int(last_ticket[0][-4:])
            except Exception:
                last_number = 0
            new_number = last_number + 1
        else:
            new_number = 1
        
        ticket_number = f"TKT{datetime.now().strftime('%Y%m%d')}{new_number:04d}"
        
        from utils.notifications import calculate_due_date
        due_date = calculate_due_date(ai_priority, datetime.now(timezone.utc))
        
        db.session.execute(
            text("""
                INSERT INTO tickets
                (ticket_number, title, description, category_name, priority_name, status_name, requester_id, source,
                 assigned_to, department_id, issue_type_id, due_date,
                 ai_suggested_category, ai_suggested_priority,
                 ai_suggested_department, ai_suggested_agent, ai_confidence, ai_correction_type)
                VALUES (:ticket_number, :title, :description, :category_name, :priority_name, 'New', :requester_id, 'Web',
                        :assigned_to, :department_id, :issue_type_id, :due_date,
                        :ai_suggested_category, :ai_suggested_priority,
                        :ai_suggested_department, :ai_suggested_agent, :ai_confidence, :ai_correction_type)
            """),
            {
                "ticket_number": ticket_number,
                "title": title,
                "description": description,
                "category_name": ai_category,
                "priority_name": ai_priority,
                "requester_id": user_id,
                "assigned_to": assigned_to,
                "department_id": department_id,
                "issue_type_id": validated_issue_type_id,
                "due_date": due_date,
                "ai_suggested_category": ai_category,
                "ai_suggested_priority": ai_priority,
                "ai_suggested_department": ai_suggested_department,
                "ai_suggested_agent": assigned_to,
                "ai_confidence": ai_confidence,
                "ai_correction_type": ai_correction_type,
            }
        )
        db.session.commit()
        
        ticket_id_row = db.session.execute(
            text("SELECT ticket_id FROM tickets WHERE ticket_number = :ticket_number"),
            {"ticket_number": ticket_number}
        ).fetchone()
        ticket_id = ticket_id_row[0] if ticket_id_row else None
        
        if ticket_id and assigned_to and match_score > 0:
            final_matched_skill_id = matched_skill_id if matched_skill_id else required_skill_id
            
            db.session.execute(
                text("""
                    INSERT INTO ticket_assignment_history
                    (ticket_id, agent_id, department_id, matched_skill_id, match_score, assignment_reason)
                    VALUES (:ticket_id, :agent_id, :dept_id, :skill_id, :score, :reason)
                """),
                {
                    "ticket_id": ticket_id,
                    "agent_id": assigned_to,
                    "dept_id": department_id,
                    "skill_id": final_matched_skill_id,
                    "score": match_score,
                    "reason": assignment_method or "AI Match"
                }
            )
            db.session.commit()
            
            if assignment_method == "Fallback Department Match":
                print(f"[AI DEBUG] Warning: Assigned via fallback, no exact skill match")
        
        # ML Resolution Time Prediction (non-blocking - ticket is already saved)
        try:
            from utils.ml_service import predict_and_store_for_ticket
            ml_result = predict_and_store_for_ticket(
                ticket_id=ticket_id or 0,
                title=title,
                description=description or '',
                category=ai_category,
                priority=ai_priority,
                department=ai_suggested_department or '',
                issue_type=issue_type_context,
                priority_name=ai_priority
            )
            if ml_result and ml_result.get("success"):
                print(f"[ML DEBUG] Prediction: {ml_result.get('predicted_display')} | Risk: {ml_result.get('sla_breach_risk')}")
            else:
                print(f"[ML DEBUG] Prediction unavailable: {ml_result.get('error', 'model not trained') if ml_result else 'no predictor'}")
        except Exception as ml_error:
            print(f"[ML DEBUG] ML prediction failed (non-blocking): {str(ml_error)}")

        print(f"[AI DEBUG] Ticket saved: {ticket_number}")
        print(f"[AI DEBUG] ==========================================\n")
        
        if ticket_id and assigned_to:
            from utils.notifications import notify_ticket_created
            notify_ticket_created(ticket_id, title, session.get("user_id"))

        flash(_("ticket_submitted_successfully"), "success")
        return redirect(url_for("customer.my_tickets"))
    
    return render_template(
        "customer_submit_ticket.html"
    )


@customer_bp.route('/customer-profile')
def customer_profile():
    auth_check = require_customer()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    user = db.session.execute(
        text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.profile_image,
                   r.role_name, d.department_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN departments d ON u.department_id = d.department_id
            WHERE u.user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()

    return render_template("customer_profile.html", user=user)


import os
from werkzeug.utils import secure_filename

@customer_bp.route('/customer-profile/upload-photo', methods=["POST"])
def upload_customer_photo():
    auth_check = require_customer()
    if auth_check:
        return auth_check

    file = request.files.get("profile_image")
    if file and file.filename:
        filename = secure_filename(file.filename)
        UPLOAD_FOLDER = "static/uploads/profile"
        try:
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            
            db.session.execute(text("""
                UPDATE users
                SET profile_image = :img
                WHERE user_id = :id
            """), {
                "img": filename,
                "id": session["user_id"]
            })
            db.session.commit()
            flash(_("Profile updated successfully"), "success")
        except Exception as e:
            print("Error uploading photo:", e)
            flash(_("Failed to upload profile picture."), "danger")
            
    return redirect(url_for('customer.customer_profile'))


@customer_bp.route('/customer-notifications')
def customer_notifications():
    auth_check = require_customer()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    notifications = db.session.execute(
        text("""
            SELECT notification_id, title, message, is_read, created_at
            FROM notifications
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": user_id}
    ).fetchall()

    unread_count = db.session.execute(
        text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = FALSE"),
        {"user_id": user_id}
    ).scalar()

    return render_template(
        "customer_notifications.html",
        notifications=notifications,
        unread_count=unread_count
    )


@customer_bp.route('/customer-notifications/<int:notification_id>/read', methods=['GET', 'POST'])
def mark_notification_read(notification_id):
    auth_check = require_customer()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    db.session.execute(
        text("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE notification_id = :notification_id
              AND user_id = :user_id
        """),
        {"notification_id": notification_id, "user_id": user_id}
    )
    db.session.commit()
    flash(_("notification_marked_as_read"), "success")
    return redirect(url_for("customer.customer_notifications"))


@customer_bp.route('/customer-notifications/<int:notification_id>/delete', methods=['POST'])
def delete_notification(notification_id):
    auth_check = require_customer()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    db.session.execute(
        text("""
            DELETE FROM notifications
            WHERE notification_id = :notification_id
              AND user_id = :user_id
        """),
        {"notification_id": notification_id, "user_id": user_id}
    )
    db.session.commit()
    flash(_("notification_deleted"), "success")
    return redirect(url_for("customer.customer_notifications"))


@customer_bp.route('/customer-notifications/delete-all', methods=['POST'])
def delete_all_notifications():
    auth_check = require_customer()
    if auth_check:
        return jsonify({"success": False, "message": "Access Denied"}), 403

    user_id = session.get("user_id")
    try:
        result = db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )
        deleted_count = result.rowcount if hasattr(result, 'rowcount') else 0
        db.session.commit()
        if deleted_count == 0:
            return jsonify({"success": True, "message": "No notifications to delete", "deleted_count": 0})
        return jsonify({"success": True, "message": "All notifications deleted successfully", "deleted_count": deleted_count})
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Failed to delete notifications"}), 500


class TicketPDF(FPDF):
    """Professional PDF generator for customer tickets"""
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, 'Help Desk & Ticket Management System', 0, 0, 'L')
            self.cell(0, 5, f'Page {self.page_no()}', 0, 1, 'R')
            self.line(10, 12, 200, 12)
            self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')


@customer_bp.route('/customer-tickets/<int:ticket_id>/download-pdf')
def download_ticket_pdf(ticket_id):
    auth_check = require_customer()
    if auth_check:
        return auth_check
    
    user_id = session.get("user_id")
    
    # Fetch ticket with all details - validate ownership
    ticket = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.description,
                t.status_name,
                t.priority_name,
                t.category_name,
                t.created_at,
                t.updated_at,
                t.assigned_to,
                u.first_name as requester_first,
                u.last_name as requester_last,
                u.email as requester_email,
                d.department_name,
                it.issue_name
            FROM tickets t
            LEFT JOIN users u ON t.requester_id = u.user_id
            LEFT JOIN departments d ON t.department_id = d.department_id
            LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
            WHERE t.ticket_id = :ticket_id
              AND t.requester_id = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()
    
    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(url_for("customer.my_tickets"))
    
    # Fetch comments/conversation
    comments = db.session.execute(
        text("""
            SELECT
                tc.comment_text,
                tc.created_at,
                u.first_name,
                u.last_name,
                r.role_name
            FROM ticket_comments tc
            JOIN users u ON tc.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE tc.ticket_id = :ticket_id
              AND tc.is_internal = FALSE
            ORDER BY tc.comment_id ASC
        """),
        {"ticket_id": ticket_id}
    ).fetchall()
    
    # Generate PDF
    pdf = TicketPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Title bar
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(13, 110, 253)  # Primary blue
    pdf.cell(0, 12, 'TICKET DETAIL REPORT', 0, 1, 'L')
    
    # Decorative line
    pdf.set_draw_color(13, 110, 253)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)
    
    # Ticket info grid
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(0, 0, 0)
    
    # Helper for label-value pairs
    def add_field(label, value, label_width=45):
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(label_width, 7, label, 0, 0)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 7, str(value) if value else 'N/A', 0, 1)
    
    # Row 1: Ticket Number & Status
    add_field('Ticket #:', ticket.ticket_number)
    add_field('Status:', ticket.status_name)
    # Row 2: Title & Priority
    add_field('Title:', ticket.title)
    add_field('Priority:', ticket.priority_name)
    # Row 3: Category & Department
    add_field('Category:', ticket.category_name)
    add_field('Department:', ticket.department_name)
    # Row 4: Issue Type & Created
    add_field('Issue Type:', ticket.issue_name)
    add_field('Created:', ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else 'N/A')
    # Row 5: Updated & Requester
    add_field('Updated:', ticket.updated_at.strftime('%Y-%m-%d %H:%M') if ticket.updated_at else 'N/A')
    requester_name = f"{ticket.requester_first or ''} {ticket.requester_last or ''}".strip()
    add_field('Requester:', requester_name)
    # Row 6: Email & Assigned Agent
    add_field('Email:', ticket.requester_email)
    if ticket.assigned_to:
        agent = db.session.execute(
            text("SELECT first_name, last_name FROM users WHERE user_id = :uid"),
            {"uid": ticket.assigned_to}
        ).fetchone()
        agent_name = f"{agent[0] or ''} {agent[1] or ''}".strip() if agent else 'N/A'
        add_field('Assigned Agent:', agent_name)
    
    pdf.ln(5)
    
    # Description section
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(13, 110, 253)
    pdf.cell(0, 8, 'DESCRIPTION', 0, 1)
    pdf.set_draw_color(13, 110, 253)
    pdf.set_line_width(0.4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    
    pdf.set_font('Helvetica', '', 9.5)
    pdf.set_text_color(0, 0, 0)
    # Handle multi-line description
    description_text = ticket.description if ticket.description else 'No description provided.'
    pdf.multi_cell(0, 5, description_text)
    
    pdf.ln(6)
    
    # Comments/Conversation section
    if comments:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(13, 110, 253)
        pdf.cell(0, 8, 'CONVERSATION HISTORY', 0, 1)
        pdf.set_draw_color(13, 110, 253)
        pdf.set_line_width(0.4)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)
        
        for idx, comment in enumerate(comments, 1):
            # Check if we need a new page
            if pdf.get_y() > 240:
                pdf.add_page()
            
            # Comment header
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(55, 65, 81)
            commenter = f"{comment.first_name or ''} {comment.last_name or ''}".strip()
            role = comment.role_name or 'User'
            header = f"#{idx}  {commenter}  ({role})"
            pdf.cell(0, 6, header, 0, 1)
            
            # Timestamp
            pdf.set_font('Helvetica', 'I', 8)
            pdf.set_text_color(100, 100, 100)
            timestamp = comment.created_at.strftime('%Y-%m-%d %H:%M') if comment.created_at else 'N/A'
            pdf.cell(0, 5, timestamp, 0, 1)
            pdf.ln(1)
            
            # Comment text
            pdf.set_font('Helvetica', '', 9.5)
            pdf.set_text_color(0, 0, 0)
            comment_text = comment.comment_text if comment.comment_text else ''
            pdf.multi_cell(0, 5, comment_text)
            
            # Separator between comments
            if idx < len(comments):
                pdf.ln(3)
                pdf.set_draw_color(200, 200, 200)
                pdf.set_line_width(0.3)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(5)
    else:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, 'No conversation history available.', 0, 1)
    
    pdf.ln(10)
    
    # Footer note
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f'Generated on {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} by Help Desk System', 0, 1, 'C')
    pdf.cell(0, 5, f'Ticket #{ticket.ticket_number} - Confidential', 0, 1, 'C')
    
    # Output PDF to bytes
    pdf_bytes = pdf.output()
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    pdf_buffer = io.BytesIO(pdf_bytes)
    
    filename = f"ticket-{ticket.ticket_number}.pdf"
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
