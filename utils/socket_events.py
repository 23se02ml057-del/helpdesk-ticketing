from flask_socketio import SocketIO, emit, join_room
from sqlalchemy import text
from help_db import db
from datetime import datetime

_socketio = None

def init_socketio(app):
    global _socketio
    _socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    @_socketio.on('connect')
    def handle_connect():
        print('Client connected')
    
    @_socketio.on('disconnect')
    def handle_disconnect():
        print('Client disconnected')
    
    @_socketio.on('join_user_room')
    def handle_join_user_room(data):
        user_id = data.get('user_id')
        if user_id:
            join_room(f'user_{user_id}')
            print(f'User {user_id} joined room user_{user_id}')
    
    @_socketio.on('ticket_status_updated')
    def handle_ticket_status_updated(data):
        ticket_id = data.get('ticket_id')
        new_status = data.get('new_status')
        requester_id = data.get('requester_id')
        
        if ticket_id and new_status and requester_id:
            _socketio.emit('ticket_status_changed', {
                'ticket_id': ticket_id,
                'new_status': new_status,
                'requester_id': requester_id
            }, room=f'user_{requester_id}')
            print(f'Emitted status change for ticket {ticket_id} to user {requester_id}: {new_status}')
    
    return _socketio


def emit_ticket_status_change(ticket_id, new_status, requester_id):
    """Emit ticket status change event to the requester's room"""
    if _socketio is None:
        print('Warning: Socket.IO not initialized')
        return
    
    try:
        _socketio.emit('ticket_status_changed', {
            'ticket_id': ticket_id,
            'new_status': new_status,
            'requester_id': requester_id
        }, room=f'user_{requester_id}')
        print(f'Emitted status change for ticket {ticket_id} to user {requester_id}: {new_status}')
    except Exception as e:
        print(f'Error emitting socket event: {e}')


def emit_new_customer(user_id, first_name, last_name, email, mobile, department_name):
    """Emit new customer event to all connected clients"""
    if _socketio is None:
        print('Warning: Socket.IO not initialized')
        return
    
    try:
        _socketio.emit('new_customer', {
            'user_id': user_id,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'mobile': mobile,
            'department_name': department_name,
            'total_tickets': 0,
            'last_login': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })
        print(f'Emitted new customer event: {email}')
    except Exception as e:
        print(f'Error emitting new customer event: {e}')
