"""
==============================================================
 EVM Voting Management System
 Flask + SQLite/MySQL + Matplotlib
 Fully Functional, Clean, Bug-Free
==============================================================
"""

import os
import uuid
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_from_directory
)
from werkzeug.utils import secure_filename

from database import get_db
from chart_generator import make_charts

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'evm_voting_system_secure_secret_key_2026')

# Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
CHART_FOLDER = os.path.join(BASE_DIR, 'static', 'charts')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CHART_FOLDER'] = CHART_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_FOLDER, exist_ok=True)

# Admin Credentials (configurable via environment variables)
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASS = os.getenv('ADMIN_PASS', 'evm2025@admin')


def allowed_file(filename):
    """Check if the uploaded file has a valid image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    """Decorator to protect admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Admin authentication required to access this page.', 'warning')
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# --------------------------------------------------------------
# ROUTES
# --------------------------------------------------------------

@app.route('/')
def home():
    """Home page displaying active polls and current top leader."""
    db = get_db()
    if not db:
        flash('Could not establish database connection.', 'error')
        return render_template('index.html', polls=[], top_leader=None)

    cur = db.cursor()
    # Fetch all polls ordered by latest first
    cur.execute('SELECT id, question FROM polls ORDER BY id DESC')
    polls = cur.fetchall()

    top_leader = None
    if polls:
        latest_poll_id = polls[0][0]
        latest_poll_question = polls[0][1]
        cur.execute('''
            SELECT o.option_text, o.image_path, COUNT(v.id) as vote_cnt
            FROM options o
            LEFT JOIN votes v ON o.id = v.option_id
            WHERE o.poll_id = %s
            GROUP BY o.id, o.option_text, o.image_path
            ORDER BY vote_cnt DESC
            LIMIT 1
        ''', (latest_poll_id,))
        top_row = cur.fetchone()
        if top_row and top_row[2] > 0:
            top_leader = {
                'name': top_row[0],
                'image': top_row[1],
                'votes': top_row[2],
                'poll_id': latest_poll_id,
                'poll_question': latest_poll_question
            }

    cur.close()
    db.close()
    return render_template('index.html', polls=polls, top_leader=top_leader)


# ------------------- ADMIN AUTHENTICATION -------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if session.get('admin_logged_in'):
        return redirect(url_for('create_poll'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == ADMIN_USER and password == ADMIN_PASS:
            session['admin_logged_in'] = True
            flash('Successfully logged in as administrator.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('create_poll'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """Log out admin session."""
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


# ------------------- POLL CREATION FLOW -------------------

@app.route('/create_poll', methods=['GET', 'POST'])
@admin_required
def create_poll():
    """Create a new poll with candidate names and symbol images."""
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        candidate_names = request.form.getlist('candidate_name[]')
        candidate_files = request.files.getlist('candidate_image[]')

        if not question:
            flash('Please enter a poll question.', 'error')
            return render_template('create_poll.html')

        valid_candidates = []
        temp_id = str(uuid.uuid4())

        for idx, (name, file) in enumerate(zip(candidate_names, candidate_files)):
            clean_name = name.strip()
            if not clean_name:
                continue

            saved_image = None
            if file and file.filename and allowed_file(file.filename):
                ext = secure_filename(file.filename).rsplit('.', 1)[-1].lower()
                unique_filename = f"temp_{temp_id}_{idx}_{uuid.uuid4().hex[:8]}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                try:
                    file.save(filepath)
                    saved_image = unique_filename
                except Exception as e:
                    print(f"Error saving uploaded image: {e}")

            valid_candidates.append({
                'name': clean_name,
                'image': saved_image
            })

        if len(valid_candidates) < 2:
            flash('Please provide at least 2 valid candidates.', 'error')
            return render_template('create_poll.html', saved_question=question)

        # Store in session for preview
        session['temp_poll'] = {
            'temp_id': temp_id,
            'question': question,
            'candidates': valid_candidates
        }
        return redirect(url_for('preview_poll', temp_id=temp_id))

    return render_template('create_poll.html')


@app.route('/preview/<temp_id>')
@admin_required
def preview_poll(temp_id):
    """Preview the EVM layout before finalizing."""
    temp_data = session.get('temp_poll')
    if not temp_data or temp_data.get('temp_id') != temp_id:
        flash('Poll creation session expired or invalid. Please start again.', 'warning')
        return redirect(url_for('create_poll'))

    return render_template('preview_poll.html', temp_data=temp_data, temp_id=temp_id)


@app.route('/confirm_poll/<temp_id>', methods=['POST'])
@admin_required
def confirm_poll(temp_id):
    """Save finalized poll to the database."""
    temp_data = session.get('temp_poll')
    if not temp_data or temp_data.get('temp_id') != temp_id:
        flash('Poll session expired. Please create again.', 'error')
        return redirect(url_for('create_poll'))

    db = get_db()
    if not db:
        flash('Database error while saving poll.', 'error')
        return redirect(url_for('create_poll'))

    cur = db.cursor()
    try:
        cur.execute('INSERT INTO polls (question) VALUES (%s)', (temp_data['question'],))
        poll_id = cur.lastrowid

        for cand in temp_data['candidates']:
            permanent_image = None
            if cand['image']:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], cand['image'])
                if os.path.exists(old_path):
                    _, ext = os.path.splitext(cand['image'])
                    permanent_image = f"{poll_id}_{uuid.uuid4().hex[:12]}{ext.lower()}"
                    new_path = os.path.join(app.config['UPLOAD_FOLDER'], permanent_image)
                    try:
                        os.replace(old_path, new_path)
                    except Exception:
                        permanent_image = cand['image']

            cur.execute(
                'INSERT INTO options (poll_id, option_text, image_path) VALUES (%s, %s, %s)',
                (poll_id, cand['name'], permanent_image)
            )

        db.commit()
        session.pop('temp_poll', None)
        flash('Election poll has been successfully created and published!', 'success')
        return redirect(url_for('home'))

    except Exception as e:
        db.rollback()
        print(f"Error creating poll: {e}")
        flash('An error occurred while publishing the poll.', 'error')
        return redirect(url_for('create_poll'))
    finally:
        cur.close()
        db.close()


# ------------------- VOTER VERIFICATION & VOTING -------------------

@app.route('/voter_details/<int:poll_id>', methods=['GET', 'POST'])
def voter_details(poll_id):
    """Voter registration and verification screen."""
    db = get_db()
    if not db:
        flash('Database connection unavailable.', 'error')
        return redirect(url_for('home'))

    cur = db.cursor()
    cur.execute('SELECT question FROM polls WHERE id = %s', (poll_id,))
    poll_row = cur.fetchone()
    if not poll_row:
        cur.close()
        db.close()
        flash('Poll not found.', 'error')
        return redirect(url_for('home'))

    question = poll_row[0]

    if request.method == 'POST':
        voter_id = request.form.get('voter_id', '').strip().upper()
        name = request.form.get('name', '').strip()
        age_str = request.form.get('age', '').strip()
        address = request.form.get('address', '').strip()

        if not voter_id or not name or not age_str:
            flash('Please fill in all required fields.', 'error')
            cur.close()
            db.close()
            return render_template('voter_form.html', poll_id=poll_id, question=question)

        try:
            age = int(age_str)
            if age < 18:
                flash('You must be at least 18 years old to vote.', 'error')
                cur.close()
                db.close()
                return render_template('voter_form.html', poll_id=poll_id, question=question)
        except ValueError:
            flash('Invalid age entered.', 'error')
            cur.close()
            db.close()
            return render_template('voter_form.html', poll_id=poll_id, question=question)

        # Check if voter already exists; if not, insert
        cur.execute('SELECT id FROM voters WHERE voter_id = %s', (voter_id,))
        if not cur.fetchone():
            cur.execute(
                'INSERT INTO voters (voter_id, name, age, address) VALUES (%s, %s, %s, %s)',
                (voter_id, name, age, address)
            )
            db.commit()

        session['voter_id'] = voter_id
        cur.close()
        db.close()
        return redirect(url_for('poll', poll_id=poll_id))

    cur.close()
    db.close()
    return render_template('voter_form.html', poll_id=poll_id, question=question)


@app.route('/poll/<int:poll_id>', methods=['GET', 'POST'])
def poll(poll_id):
    """EVM ballot voting interface."""
    voter_id = session.get('voter_id')
    if not voter_id:
        flash('Please verify your voter credentials first.', 'info')
        return redirect(url_for('voter_details', poll_id=poll_id))

    db = get_db()
    if not db:
        flash('Database error.', 'error')
        return redirect(url_for('home'))

    cur = db.cursor()
    cur.execute('SELECT question FROM polls WHERE id = %s', (poll_id,))
    poll_row = cur.fetchone()
    if not poll_row:
        cur.close()
        db.close()
        flash('Poll not found.', 'error')
        return redirect(url_for('home'))

    question = poll_row[0]

    # Check if voter already voted in this poll
    cur.execute('SELECT option_id FROM votes WHERE poll_id = %s AND voter_id = %s', (poll_id, voter_id))
    existing_vote = cur.fetchone()
    user_voted_id = existing_vote[0] if existing_vote else None

    if request.method == 'POST':
        if user_voted_id:
            cur.close()
            db.close()
            flash('You have already cast your vote in this poll.', 'warning')
            return redirect(url_for('results', poll_id=poll_id))

        option_id = request.form.get('option_id')
        if not option_id:
            flash('Please select a candidate to cast your vote.', 'warning')
            cur.close()
            db.close()
            return redirect(url_for('poll', poll_id=poll_id))

        try:
            cur.execute(
                'INSERT INTO votes (poll_id, option_id, voter_id) VALUES (%s, %s, %s)',
                (poll_id, int(option_id), voter_id)
            )
            db.commit()
            flash('Your vote has been officially recorded in the EVM system!', 'success')
            cur.close()
            db.close()
            return redirect(url_for('results', poll_id=poll_id))
        except Exception as e:
            db.rollback()
            print(f"Error casting vote: {e}")
            flash('Failed to record vote. You may have already voted.', 'error')
            cur.close()
            db.close()
            return redirect(url_for('results', poll_id=poll_id))

    # Fetch all options for this poll
    cur.execute('SELECT id, option_text, image_path FROM options WHERE poll_id = %s ORDER BY id ASC', (poll_id,))
    options = cur.fetchall()

    cur.close()
    db.close()
    return render_template(
        'poll.html',
        poll_id=poll_id,
        question=question,
        options=options,
        voter_id=voter_id,
        voted=user_voted_id
    )


# ------------------- RESULTS & CHARTS -------------------

@app.route('/results/<int:poll_id>')
def results(poll_id):
    """View ranked election results and charts."""
    db = get_db()
    if not db:
        flash('Database error.', 'error')
        return redirect(url_for('home'))

    cur = db.cursor()
    cur.execute('SELECT question FROM polls WHERE id = %s', (poll_id,))
    poll_row = cur.fetchone()
    if not poll_row:
        cur.close()
        db.close()
        flash('Poll not found.', 'error')
        return redirect(url_for('home'))

    question = poll_row[0]

    # Fetch ranked results with vote count
    cur.execute('''
        SELECT o.id, o.option_text, o.image_path, COUNT(v.id) as vote_count
        FROM options o
        LEFT JOIN votes v ON o.id = v.option_id
        WHERE o.poll_id = %s
        GROUP BY o.id, o.option_text, o.image_path
        ORDER BY vote_count DESC, o.id ASC
    ''', (poll_id,))
    ranked = cur.fetchall()

    total_votes = sum(r[3] for r in ranked) if ranked else 0

    # User's vote if session exists
    voter_id = session.get('voter_id')
    user_voted = None
    if voter_id:
        cur.execute('SELECT option_id FROM votes WHERE poll_id = %s AND voter_id = %s', (poll_id, voter_id))
        v_row = cur.fetchone()
        if v_row:
            user_voted = v_row[0]

    cur.close()
    db.close()

    # Generate charts
    labels = [r[1] for r in ranked]
    votes = [r[3] for r in ranked]
    bar_chart, pie_chart, chart_ts = make_charts(app.config['CHART_FOLDER'], poll_id, labels, votes)

    return render_template(
        'results.html',
        poll_id=poll_id,
        question=question,
        ranked=ranked,
        total_votes=total_votes,
        user_voted=user_voted,
        voter_id=voter_id,
        bar_chart=bar_chart,
        pie_chart=pie_chart,
        chart_ts=chart_ts or 1
    )


@app.route('/charts/<path:filename>')
def serve_chart(filename):
    """Serve chart images."""
    return send_from_directory(app.config['CHART_FOLDER'], filename)


# ------------------- ERROR HANDLERS -------------------

@app.errorhandler(404)
def not_found_error(error):
    return render_template('base.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html'), 500


# --------------------------------------------------------------
# APPLICATION ENTRYPOINT
# --------------------------------------------------------------
if __name__ == '__main__':
    print("==================================================")
    print(" EVM Voting Management System Starting...")
    print(f" Admin Credentials: {ADMIN_USER} / {ADMIN_PASS}")
    print(" Open in browser: http://127.0.0.1:5000")
    print("==================================================")
    app.run(debug=True, host='127.0.0.1', port=5000)
