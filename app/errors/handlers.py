from flask import render_template, request, jsonify
from app.extensions import db
from app.errors import bp

@bp.app_errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Page not found'}), 404
    return render_template('errors/404.html'), 404

@bp.app_errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'An internal error occurred'}), 500
    return render_template('errors/500.html'), 500

@bp.app_errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'You do not have permission to access this resource'}), 403
    return render_template('errors/403.html'), 403 