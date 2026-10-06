import io
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
import pandas as pd

from app import db
from app.models import ScrapeSession, ScrapedData
from app.scraper import (
    validate_url, check_robots_txt, fetch_page,
    detect_html_elements, multi_page_scrape
)
from app.analyzer import clean_dataframe, analyze_dataframe, generate_chart_data, dataframe_to_records

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/fetch-page', methods=['POST'])
@login_required
def fetch_page_api():
    """Fetch a URL, validate it, and return detected HTML elements."""
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'success': False, 'error': 'URL is required.'}), 400

    valid, result = validate_url(url)
    if not valid:
        return jsonify({'success': False, 'error': result}), 400

    url = result  # normalized URL

    # Check robots.txt
    allowed = check_robots_txt(url)
    if not allowed:
        return jsonify({
            'success': False,
            'error': 'This website\'s robots.txt disallows scraping. Please respect website policies.'
        }), 403

    soup, error = fetch_page(url)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    elements = detect_html_elements(soup)

    # Create a scrape session
    session = ScrapeSession(
        user_id=current_user.id,
        url=url,
        title=elements.get('page_title', 'Unknown'),
        status='element_selection',
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({
        'success': True,
        'session_id': session.id,
        'url': url,
        'title': elements.get('page_title'),
        'elements': elements,
    })


@api_bp.route('/scrape', methods=['POST'])
@login_required
def scrape_api():
    """Execute scraping with selected selectors."""
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    selectors = data.get('selectors', [])
    multi_page = data.get('multi_page', False)
    max_pages = min(int(data.get('max_pages', 3)), 10)

    if not session_id:
        return jsonify({'success': False, 'error': 'Session ID is required.'}), 400

    session = ScrapeSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not session:
        return jsonify({'success': False, 'error': 'Session not found.'}), 404

    if not selectors:
        return jsonify({'success': False, 'error': 'Please select at least one element to scrape.'}), 400

    session.selected_selectors = json.dumps(selectors)
    session.status = 'scraping'
    db.session.commit()

    try:
        if multi_page:
            rows, errors = multi_page_scrape(session.url, selectors, max_pages=max_pages)
        else:
            from app.scraper import fetch_page as fp, scrape_with_selectors as sws
            soup, error = fp(session.url)
            if error:
                session.status = 'failed'
                session.error_message = error
                db.session.commit()
                return jsonify({'success': False, 'error': error}), 400
            rows = sws(soup, selectors)
            errors = []

        if not rows:
            session.status = 'failed'
            session.error_message = 'No data could be extracted with the selected elements. Try different selectors.'
            db.session.commit()
            return jsonify({
                'success': False,
                'error': 'No data extracted. The selected elements might not contain meaningful content.',
                'warnings': errors,
            }), 400

        # Clean data
        df = pd.DataFrame(rows)
        df_clean = clean_dataframe(df)

        if df_clean.empty:
            session.status = 'failed'
            session.error_message = 'Data was empty after cleaning.'
            db.session.commit()
            return jsonify({'success': False, 'error': 'All scraped data was empty after cleaning.'}), 400

        # Save to DB (clear previous data)
        ScrapedData.query.filter_by(session_id=session.id).delete()
        for i, row in enumerate(dataframe_to_records(df_clean)):
            sd = ScrapedData(
                session_id=session.id,
                data_json=json.dumps(row),
                row_index=i,
            )
            db.session.add(sd)

        # Analyze
        stats = analyze_dataframe(df_clean)
        chart_data = generate_chart_data(df_clean, stats)

        session.status = 'completed'
        session.record_count = len(df_clean)
        session.completed_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'session_id': session.id,
            'record_count': len(df_clean),
            'columns': list(df_clean.columns),
            'preview': dataframe_to_records(df_clean.head(10)),
            'stats': stats,
            'charts': chart_data,
            'warnings': errors,
        })

    except Exception as e:
        session.status = 'failed'
        session.error_message = str(e)[:500]
        db.session.commit()
        return jsonify({'success': False, 'error': f'Scraping failed: {str(e)[:300]}'}), 500


@api_bp.route('/results/<int:session_id>', methods=['GET'])
@login_required
def get_results(session_id):
    """Get full results for a session."""
    session = ScrapeSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not session:
        return jsonify({'success': False, 'error': 'Session not found.'}), 404

    scraped_rows = ScrapedData.query.filter_by(session_id=session_id)\
        .order_by(ScrapedData.row_index).all()

    rows = [json.loads(r.data_json) for r in scraped_rows]

    if not rows:
        return jsonify({'success': False, 'error': 'No data found for this session.'}), 404

    df = pd.DataFrame(rows)
    stats = analyze_dataframe(df)
    chart_data = generate_chart_data(df, stats)

    return jsonify({
        'success': True,
        'session_id': session.id,
        'url': session.url,
        'title': session.title,
        'record_count': session.record_count,
        'columns': list(df.columns),
        'data': dataframe_to_records(df),
        'preview': dataframe_to_records(df.head(50)),
        'stats': stats,
        'charts': chart_data,
        'created_at': session.created_at.isoformat() if session.created_at else None,
    })


@api_bp.route('/download/<int:session_id>/<format>', methods=['GET'])
@login_required
def download(session_id, format):
    """Download scraped data as CSV or Excel."""
    if format not in ('csv', 'excel'):
        return jsonify({'error': 'Invalid format. Use csv or excel.'}), 400

    session = ScrapeSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not session:
        return jsonify({'error': 'Session not found.'}), 404

    scraped_rows = ScrapedData.query.filter_by(session_id=session_id)\
        .order_by(ScrapedData.row_index).all()
    rows = [json.loads(r.data_json) for r in scraped_rows]

    if not rows:
        return jsonify({'error': 'No data to download.'}), 404

    df = pd.DataFrame(rows)
    safe_title = ''.join(c for c in (session.title or 'data') if c.isalnum() or c in '_- ')[:50]

    if format == 'csv':
        output = io.BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{safe_title}_data.csv'
        )
    else:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Scraped Data')
            # Add stats sheet
            stats = analyze_dataframe(df)
            stats_rows = []
            for col, col_stat in stats.get('column_stats', {}).items():
                row = {'Column': col, 'Type': col_stat['type'],
                       'Non-Null': col_stat['non_null'], 'Null %': col_stat['null_pct'],
                       'Unique': col_stat['unique_count']}
                if col_stat['type'] == 'numeric':
                    row.update({'Mean': col_stat.get('mean'), 'Min': col_stat.get('min'),
                                'Max': col_stat.get('max'), 'Sum': col_stat.get('sum')})
                stats_rows.append(row)
            pd.DataFrame(stats_rows).to_excel(writer, index=False, sheet_name='Statistics')

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{safe_title}_data.xlsx'
        )


@api_bp.route('/session/<int:session_id>/delete', methods=['DELETE'])
@login_required
def delete_session(session_id):
    session = ScrapeSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not session:
        return jsonify({'error': 'Session not found.'}), 404
    db.session.delete(session)
    db.session.commit()
    return jsonify({'success': True})
