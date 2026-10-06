from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import ScrapeSession

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    recent_sessions = ScrapeSession.query.filter_by(user_id=current_user.id)\
        .order_by(ScrapeSession.created_at.desc()).limit(5).all()
    total_sessions = ScrapeSession.query.filter_by(user_id=current_user.id).count()
    successful_sessions = ScrapeSession.query.filter_by(user_id=current_user.id, status='completed').count()

    stats = {
        'total_sessions': total_sessions,
        'successful_sessions': successful_sessions,
        'total_records': sum(s.record_count or 0 for s in
                             ScrapeSession.query.filter_by(user_id=current_user.id).all()),
    }
    return render_template('main/dashboard.html', title='Dashboard',
                           recent_sessions=recent_sessions, stats=stats)


@main_bp.route('/history')
@login_required
def history():
    sessions = ScrapeSession.query.filter_by(user_id=current_user.id)\
        .order_by(ScrapeSession.created_at.desc()).all()
    return render_template('main/history.html', title='Scrape History', sessions=sessions)
