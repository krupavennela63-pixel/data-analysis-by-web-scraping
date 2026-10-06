import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import ScrapeSession, ScrapedData
from app import db

scraper_bp = Blueprint('scraper', __name__)


@scraper_bp.route('/scrape/new')
@login_required
def new_scrape():
    return render_template('scraper/new_scrape.html', title='New Scrape')


@scraper_bp.route('/scrape/select-elements', methods=['GET'])
@login_required
def select_elements():
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('scraper.new_scrape'))

    session = ScrapeSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    elements_data = request.args.get('elements')
    elements = {}
    if elements_data:
        try:
            elements = json.loads(elements_data)
        except Exception:
            pass

    return render_template('scraper/select_elements.html',
                           title='Select Elements',
                           session=session,
                           elements=elements)


@scraper_bp.route('/scrape/results/<int:session_id>')
@login_required
def results(session_id):
    session = ScrapeSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    return render_template('scraper/results.html', title='Scrape Results', session=session)
