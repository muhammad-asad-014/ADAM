from flask import Flask, request, render_template, jsonify, url_for, redirect, session, send_file, current_app, flash
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename  #secure file handling
import time
import string
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta, timezone
import random


load_dotenv()


# file logging
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)





SQLITE_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploaded_pdfs') 
ALLOWED_EXTENSIONS = {'pdf'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def check_expiry(date):
    app.logger.info("Validating Expiry")
    try:
        stored_date = datetime.strptime(date, SQLITE_DATETIME_FORMAT)

        # Attach UTC timezone (because DB stored the time in UTC)
        stored_date = stored_date.replace(tzinfo=timezone.utc)

        limit = datetime.now(timezone.utc) - timedelta(minutes=50)

        return stored_date < limit

    except ValueError:
        app.logger.error(f"Error: Date string '{date}' did not match the expected format.")
        return False


def del_expired():
    app.logger.info("Deleting expired users")
    try:
        with sqlite3.connect("database.db") as conn:
            app.logger.info("Connected with database")
            cursor = conn.cursor()
            cursor.execute("SELECT * from users")
            app.logger.info("Fetched users data")
            data = cursor.fetchall()
            for i in data:
                if check_expiry(i[-3]):
                    app.logger.info(f"User Expired: \nID: {i[0]}, Class: {i[4]}, Quiz ID: {i[6]}")
                    sql = "DELETE from users where id= ?"
                    app.logger.info("Deleting user")
                    cursor.execute(sql, (i[0],))
                    sql = "DELETE from quiz where id= ?"
                    app.logger.info("Deleting quiz")
                    cursor.execute(sql, (i[6],))
                    sql = f"DROP table {i[4]}"
                    app.logger.info("Deleting class")
                    cursor.execute(sql)
    except sqlite3.OperationalError as e:
        app.logger.error("Failed to open database:", e)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_id(prefix):
    import uuid
    app.logger.info("Generating random IDs")
    return f"{prefix}_{str(uuid.uuid4()).split('-')[0].upper()}"

app = Flask(__name__)   
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Application startup')

# 404 error
@app.errorhandler(404)
def page_not_found(e):
    app.logger.error(f'404 Error: {e}')
    
    return render_template('error.html', error_code=404, error_message="Page Not Found"), 404

# internal Server Error
@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f'500 Error: {e}')
    return render_template('error.html', error_code=500, error_message="Internal Server Error"), 500

# other common errors
@app.errorhandler(403)
def forbidden_error(e):
    app.logger.warning(f'403 Error: {e}')
    return render_template('error.html', error_code=403, error_message="Access Forbidden"), 403




@app.route('/')
def main():
    app.logger.info("Checking expired users")
    del_expired()
    app.logger.info('Deleted expired users')
    return render_template("index.html")

@app.route('/instructions/')
def instructions():
    app.logger.info("Displaying application guide.")
    return render_template("instructions.html")





def get_quiz_data(conn, quizID):
    app.logger.info("Getting quiz data from database")
    sql = 'SELECT * from quiz WHERE id = ?'
    cur = conn.cursor()
    cur.execute(sql, (quizID,))
    data = cur.fetchone()
    app.logger.info(f"got data : {data}")
    if data:
        column_names = [description[0] for description in cur.description]
        quiz_dict = dict(zip(column_names, data))
        quiz_dict['quizJSON'] = shuffler(quiz_dict["quizJSON"])
        app.logger.info("Extracted quiz data successfully")
        return quiz_dict
    else:
        app.logger.info("No quiz data found")
        return None





@app.route('/student/', methods =["GET", "POST"])
def student():
    if request.method == "POST":
        id = request.form.get("quizID")
        app.logger.info(f"POST request: got quiz id: {id}")
        try:
            with sqlite3.connect("database.db") as conn:
                app.logger.info("Getting quiz data")
                quiz_data = get_quiz_data(conn, id)

                if quiz_data==None:
                    app.logger.info("No quiz data found, returing back")
                    flash(f'Quiz ID "{id}" not found. Please check the ID and try again.', 'error')
                    return redirect(url_for('student'))
                else:
                    app.logger.info("Quiz data found, going to quiz")
                    session['quiz_data'] = quiz_data

                    return redirect(url_for("quiz"))
        except sqlite3.OperationalError as e:
                app.logger.error("Failed to open database:", e)
    return render_template("student_dashboard.html")



def submit_quiz(conn, data, className):

    sql = f''' INSERT INTO {className}(st_id, st_name, t_marks, o_marks)
            VALUES(?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, data)
    conn.commit()
    return cur.lastrowid

@app.route('/quiz/', methods =["GET", "POST"])
def quiz():
    if request.method == 'POST':
        submission_type = request.form.get('submission_type')
        if submission_type == 'abandoned':
            stID = request.form.get("student_id")
            stName = request.form.get("student_name")
            tMarks = request.form.get("total_marks")
            oMarks = request.form.get("obtained_marks")
            classDB = request.form.get("classdb")
            app.logger.info(f"POST request: data received for incomplete submission: {stID},{stName},{tMarks},{oMarks},{classDB}")
            try:
                with sqlite3.connect("database.db") as conn:
                    app.logger.info("Submitting quiz data")
                    data = (stID, stName, tMarks, oMarks)
                    submitted_st = submit_quiz(conn, data, classDB)
                    app.logger.info(f"Submitted successfully {submitted_st}")
            except sqlite3.OperationalError as e:
                app.logger.error("Failed to Submit Quiz:", e)
            return redirect(url_for("student"))
        else:
            stID = request.form.get("student_id")
            stName = request.form.get("student_name")
            tMarks = request.form.get("total_marks")
            oMarks = request.form.get("obtained_marks")
            classDB = request.form.get("classdb")
            app.logger.info(f"POST request: data received: {stID},{stName},{tMarks},{oMarks},{classDB}")
            try:
                with sqlite3.connect("database.db") as conn:
                    app.logger.info("Submitting quiz data")
                    data = (stID, stName, tMarks, oMarks)
                    submitted_st = submit_quiz(conn, data, classDB)
                    app.logger.info(f"Submitted successfully {submitted_st}")
            except sqlite3.OperationalError as e:
                app.logger.error("Failed to Submit Quiz:", e)
            return redirect(url_for("student"))


    data = session.get("quiz_data")

    return render_template("quiz.html", data = data)


@app.route('/teacher/')
def teacher():
    return render_template('teacher.html')


@app.route("/create-quiz/", methods=["GET", "POST"])
def create_quiz():
    if request.method == "POST":
        app.logger.info("POST request received")
        teacher_fname = request.form.get('teacher_fname')
        teacher_email = request.form.get('teacher_email')
        subject_name = request.form.get('subject_name') 
        quiz_topics = request.form.get('quiz_topics')
        quiz_questions = request.form.get('quiz_questions')
        quiz_document = request.files.get('quiz_document')
        teacher_timezone = request.form.get("timezone")
        save_path = None
        app.logger.info("Data collected from post request")
        if not teacher_email or not subject_name: 
            return jsonify({'success': False, 'message': 'Missing required fields.'}), 400

        # FILE UPLOAD
        if quiz_document and quiz_document.filename != '':
            if allowed_file(quiz_document.filename):
                app.logger.info("Uploading document")
                filename = secure_filename(quiz_document.filename)
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                
                try:
                    quiz_document.save(save_path)
                    # You would now use 'save_path' to process the PDF content
                    app.logger.info(f"PDF document saved successfully to: {save_path}")
                except Exception as e:
                    app.logger.error(f"File Save Error: {e}")
                    return jsonify({'success': False, 'message': f'Server failed to save file: {e}'}), 500
            else:
                app.logger.error("Invalid file type. Only PDF is allowed.")
                return jsonify({'success': False, 'message': 'Invalid file type. Only PDF is allowed.'}), 400

        elif not quiz_topics:
             return jsonify({'success': False, 'message': 'Quiz must have either a document or topics.'}), 400

        # time for quiz generation
        app.logger.info("Trying to generate quiz")
        fetched_quiz = quiz_generator(quiz_topics,save_path)
        app.logger.info("Quiz generated successfully")
        if fetched_quiz['redflag']:
            return jsonify({'success': False, 'message': 'Server failed to generate quiz.'}), 500
        else:
            time.sleep(2) 
            teacher_id = generate_unique_id("TCH")
            quiz_id = generate_unique_id("QZ")
            classDB = generate_unique_id('CLS')
            creation_date = datetime.now(timezone.utc).strftime(SQLITE_DATETIME_FORMAT)
            try:
                with sqlite3.connect("database.db") as conn:
                    user = (teacher_id, teacher_fname, teacher_email, subject_name, classDB, creation_date, quiz_id, False)
                    user_id = add_user(conn, user)
                    app.logger.info(f"Created user with id: {user_id}")
                    quiz_data = (quiz_id, fetched_quiz['quiz_JSON'], subject_name, teacher_fname, classDB)
                    created_quiz = add_quiz(conn, quiz_data)
                    app.logger.info(f"created quiz with id: {create_quiz}")
                    if create_temp_table(conn, classDB):
                        # 5. Return JSON Response to the JavaScript's fetch() call
                        return jsonify({
                            'success': True,
                            'teacher_id': teacher_id,
                            'quiz_id': quiz_id,
                            'message': 'Quiz successfully generated.'
                        })
                    else:
                        app.logger.error("Failed to create table:", e)
                        return jsonify({'success': False, 'message': 'Server failed to generate quiz.'}), 500 
            except sqlite3.OperationalError as e:
                app.logger.error("Failed to open database:", e)
                return jsonify({'success': False, 'message': 'Server failed to generate quiz.'}), 500            
    return render_template('create_quiz.html')

def create_temp_table(conn, table_name):
    cur = conn.cursor()
    sql = f"""CREATE TABLE {table_name}(
        st_id text PRIMARY KEY,
        st_name text NOT NULL,
        t_marks integer NOT NULL,
        o_marks integer NOT NULL
        
        );"""
    cur.execute(sql)
    return True

def add_user(conn, usr):
    sql = ''' INSERT INTO users(id, name, email, subject, classDB, created_on, quizID, quiz_ended)
              VALUES(?,?,?,?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, usr)
    conn.commit()
    return cur.lastrowid

def add_quiz(conn, quiz):
    sql = '''INSERT INTO quiz(id, quizJSON, subject, host, classDB)
             VALUES(?,?,?,?,?) '''
    
    cur = conn.cursor()
    cur.execute(sql, quiz)
    conn.commit()
    return cur.lastrowid



def shuffler(json_txt):
    app.logger.info("Shuffling Quiz")
    import json
    import random
    txt_list = json.loads(json_txt)
    random.shuffle(txt_list)
    return txt_list

def shuffler_verify(json_txt):
    import json
    import random
    app.logger.info("Loading API json response")
    txt_list = json.loads(json_txt)
    app.logger.info("Shuffling API response")
    random.shuffle(txt_list)
    app.logger.info("Shuffled successfully")
    if json.dumps(txt_list):
        return True
    else:
        app.logger.error("Error in shuffle and verify")
        return False

def text_extractor(file_path):
    from langchain_community.document_loaders import PyMuPDFLoader
    app.logger.info("Loading document for text extraction")
    loader = PyMuPDFLoader(file_path)
    docs = loader.load()
    app.logger.info("Doc loaded in PyMuPDF")
    txt = ""
    for doc in docs:
        txt += doc.page_content
    app.logger.info("Doc text retreived")
    app.logger.info("Deleting uploaded doc")
    os.remove(file_path)
    app.logger.info("Doc removed successfullt")
    return txt

def quiz_generator(quiz_topics = None, quiz_doc = None):
    from openai import OpenAI
    userTxt = quiz_topics
    if quiz_doc:
        app.logger.info("Found document")
        userTxt = text_extractor(quiz_doc)
    client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv('OPENROUTER_API_KEY'),
    )

# API call with reasoning
    try:
        app.logger.info("Trying API call")
        response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[
            {
                "role": "assistant",
                "content": """
                You are a quiz generator. Based on the following text, create exactly 10 multiple-choice questions.

        Output ONLY valid JSON in this exact format:
        [
            {
                "question": "Calculus: Evaluate the limit: \\(\\lim_{x \\to 0} \\frac{\\sin(x)}{x}\\)",
                "options": [
                    { "text": "\\(0\\)", "rationale": "Incorrect. Common misconception.", "correct": false },
                    { "text": "\\(1\\)", "rationale": "Correct! Fundamental limit.", "correct": true },
                    { "text": "\\(\\infty\\)", "rationale": "Incorrect.", "correct": false },
                    { "text": "Undefined", "rationale": "Incorrect.", "correct": false }
                ]
            },
            {
                "question": "Linear Algebra: Dimensions of \\(AB\\) if \\(A\\) is \\(3 \\times 2\\) and \\(B\\) is \\(2 \\times 3\\)?",
                "options": [
                    { "text": "\\(2 \\times 2\\)", "rationale": "Incorrect.", "correct": false },
                    { "text": "\\(3 \\times 3\\)", "rationale": "Correct! (3x2)*(2x3) = 3x3.", "correct": true },
                    { "text": "\\(3 \\times 2\\)", "rationale": "Incorrect.", "correct": false },
                    { "text": "Undefined", "rationale": "Incorrect.", "correct": false }
                ]
            }
        ]

        Rules:
        - Generate exactly 10 questions.
        - Each question must have 4 options.
        - Each answer must be at different order.
        - Do not include explanations, comments, or text outside JSON.

            """
            },
            {
                "role": "user",
                "content": f"quiz topics: {userTxt}"
            }
            ],
        extra_body={"reasoning": {"enabled": True}}
        )
        app.logger.info("Got response from API")
        quiz_JSON = response.choices[0].message.content
        app.logger.info("verifying API response")
        if shuffler_verify(quiz_JSON):
            app.logger.info("No problem in response all okay...")
            return {"quiz_JSON": quiz_JSON, 'redflag': False}
        else:
            app.logger.error("Some error in API response")
            return {"quiz_JSON": quiz_JSON, 'redflag': True}

    except Exception as e:
        app.logger.error("Got no response from API reporting ERROR")
        quiz_JSON = f"ERROR: {e}"
        return {"quiz_JSON": quiz_JSON, 'redflag': True}



@app.route("/teacher-login/", methods = ['GET','POST'])
def teacher_login():
    if request.method == "POST":
        id = request.form.get("teacherID")
        app.logger.info(f"POST request: got teacher id: {id}")
        try:
            with sqlite3.connect("database.db") as conn:
                app.logger.info("Getting teacher data")
                teacher_data = get_teacher_data(conn, id)

                if teacher_data==None:
                    app.logger.warning("No teacher data retreived")
                    flash(f'Teacher ID "{id}" not found. Please check the ID and try again.', 'error')
                    return redirect(url_for('teacher_login'))
                else:
                    app.logger.info("Data retreived, redirecting to dashboard")
                    

                    return redirect(url_for("teacher_dashboard"))
                    
        except sqlite3.OperationalError as e:
                app.logger.error("Failed to open database:", e)
    return render_template('teacher_login.html')


def get_teacher_data(conn, teacher_id):
    sql = 'SELECT * from users WHERE id = ?'
    cur = conn.cursor()
    cur.execute(sql, (teacher_id,))
    data = cur.fetchone()
    app.logger.info(f"Got teacher data from database: {data}")
    if data:
        column_names = [description[0] for description in cur.description]
        user_dict = dict(zip(column_names, data))
        app.logger.info(f"Data after filtering: {user_dict}")
        session['teacher_data'] = user_dict
        return True
    else:
        return None




def get_class_data(conn, classDB):
    app.logger.info("Getting class data from database")
    sql = f'SELECT * from {classDB}'
    cur = conn.cursor()
    cur.execute(sql)
    data = cur.fetchall()
    app.logger.info("Retreived class data ")
    app.logger.info(f"Class data {data}, Lenght: {len(data)}, Type: {type(data)}")
    if len(data)>0:
        app.logger.info("Returining class data")
        return data
    else:
        app.logger.info("Returning none")
        return None


def delete_quiz(conn, quizid, teacherID):
    sql = 'DELETE from quiz WHERE id = ?'
    sql2 = "UPDATE users SET quiz_ended=? WHERE id = ?"
    cur = conn.cursor()
    try:
        cur.execute(sql, (quizid,))
        conn.commit()
        app.logger.info("Quiz deleted successfully")
        cur.execute(sql2, (True, teacherID))
        conn.commit()
        return True
    except sqlite3.OperationalError as e:
        app.logger.error(e)
        return False


@app.route('/teacher-dashboard/', methods = ["GET", 'POST'])
def teacher_dashboard():
    data = session.get("teacher_data")
    if request.method == "POST":
        try:
            with sqlite3.connect("database.db") as conn:
                app.logger.info("Deleting Quiz ")
                delete_quiz(conn, data['quizID'], data['id'])
                get_teacher_data(conn, data['id'])
                return redirect(url_for("teacher_dashboard")) 
        except sqlite3.OperationalError as e:
            app.logger.error("Failed to open database:", e)    
    try:
        with sqlite3.connect("database.db") as conn:
            app.logger.info("Detting data")
            class_data = get_class_data(conn, data['classDB']) 
            data['classData'] = class_data           
            app.logger.info(f"Sending class data: {data}")
    except sqlite3.OperationalError as e:
        app.logger.error("Failed to open database:", e)
    
    return render_template("teacher_dashboard.html", data= data)





def get_quiz_details_and_results(teacher_id):
    try:
        with sqlite3.connect("database.db") as conn:
            sql = 'SELECT * from users WHERE id = ?'
            cur = conn.cursor()
            cur.execute(sql, (teacher_id,))
            data = cur.fetchone()
            app.logger.info(f"Retreived data : {data}")
            if data:
                column_names = [description[0] for description in cur.description]
                user_dict = dict(zip(column_names, data))
                data = {
                'quizID': user_dict['quizID'],
                'subject': user_dict['subject'],
                'created_on': user_dict['created_on'],
                'classDB': user_dict['classDB'],
                'name': "Prof. "+user_dict['name'],
                'total_questions': 10,
                # The crucial list structure: (stID, stName, total_marks, obtained_marks)
                'classData': get_class_data(conn, user_dict['classDB'])
                }
            else:
                user_dict =  None
                data = None

            return data
            
    except sqlite3.Error as e:
        app.logger.error(f"Database error in report generator: {e}")
        return None


# --- The Flask Route ---
@app.route('/download-report/<teacher_id>', methods=['GET'])
def download_report(teacher_id):
    # 1. Fetch Data
    data = get_quiz_details_and_results(teacher_id)

    if not data:
        return "Error: Could not retrieve quiz data for report.", 500

    # 2. Setup PDF Document
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        title=f"ADAM Quiz Report {teacher_id}",
        leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40
    )
    
    # 3. Define Styles
    styles = getSampleStyleSheet()
    
    # Custom Colors
    col_primary = colors.HexColor("#2C3E50") # Dark Blue
    col_accent  = colors.HexColor("#3498DB") # Bright Blue
    col_success = colors.HexColor("#27AE60") # Green
    col_error   = colors.HexColor("#C0392B") # Red
    col_light   = colors.HexColor("#ECF0F1") # Light Gray

    # Custom Paragraph Styles
    style_title = ParagraphStyle(
        'AdamTitle', parent=styles['Heading1'], 
        textColor=col_primary, alignment=TA_CENTER, fontSize=24, spaceAfter=20
    )
    style_subtitle = ParagraphStyle(
        'AdamSub', parent=styles['Heading2'], 
        textColor=col_accent, alignment=TA_CENTER, fontSize=12, spaceAfter=20
    )
    style_card_label = ParagraphStyle(
        'CardLabel', parent=styles['Normal'], 
        textColor=colors.white, alignment=TA_CENTER, fontSize=10, fontName='Helvetica-Bold'
    )
    style_card_score = ParagraphStyle(
        'CardScore', parent=styles['Normal'], 
        textColor=colors.white, alignment=TA_CENTER, fontSize=18, fontName='Helvetica-Bold', leading=22
    )
    style_card_name = ParagraphStyle(
        'CardName', parent=styles['Normal'], 
        textColor=colors.white, alignment=TA_CENTER, fontSize=9, fontName='Helvetica-Oblique'
    )

    story = []

    # --- 4. DATA PROCESSING (Statistics) ---
    class_data = data.get('classData', [])
    top_student_name = "N/A"
    top_score = 0
    low_student_name = "N/A"
    low_score = 0
    avg_score = 0
    total_students = len(class_data)

    if total_students > 0:
        # Sort by obtained marks (Index 3 assumed based on your previous code)
        # Structure: [s_id, s_name, total_marks, obtained_marks]
        sorted_by_score = sorted(class_data, key=lambda x: x[3], reverse=True)
        
        # Top Student
        top_student = sorted_by_score[0]
        top_student_name = top_student[1]
        top_score = top_student[3]

        # Lowest Student
        low_student = sorted_by_score[-1]
        low_student_name = low_student[1]
        low_score = low_student[3]

        # Average
        total_obtained = sum(student[3] for student in class_data)
        avg_score = total_obtained / total_students
    
    quiz_total_marks = int(data.get('total_questions', 0)) # Assuming 1 mark per question

    # --- 5. REPORT CONTENT BUILDER ---

    # Header
    story.append(Paragraph("ADAM ASSESSMENT REPORT", style_title))
    story.append(Paragraph(f"{data.get('subject', 'General')}", style_subtitle))
    
    # --- STATISTICS DASHBOARD (New Feature) ---
    # We create a table with 3 colorful cells for High, Avg, Low
    
    # Content for the Dashboard Cards
    # Card 1: Top Performer
    c1_content = [
        Paragraph("TOP PERFORMER", style_card_label),
        Spacer(1, 6),
        Paragraph(f"{top_score} / {quiz_total_marks}", style_card_score),
        Spacer(1, 4),
        Paragraph(top_student_name, style_card_name)
    ]
    
    # Card 2: Class Average
    c2_content = [
        Paragraph("CLASS AVERAGE", style_card_label),
        Spacer(1, 6),
        Paragraph(f"{avg_score:.2f}", style_card_score),
        Spacer(1, 4),
        Paragraph(f"Across {total_students} students", style_card_name)
    ]

    # Card 3: Needs Attention
    c3_content = [
        Paragraph("LOWEST SCORE", style_card_label),
        Spacer(1, 6),
        Paragraph(f"{low_score} / {quiz_total_marks}", style_card_score),
        Spacer(1, 4),
        Paragraph(low_student_name, style_card_name)
    ]

    # Create the Dashboard Table
    dash_data = [[c1_content, c2_content, c3_content]]
    dash_table = Table(dash_data, colWidths=[170, 170, 170])
    
    dash_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        
        # Card 1 Style (Green/Success)
        ('BACKGROUND', (0,0), (0,0), col_success),
        ('bottomPadding', (0,0), (0,0), 15),
        ('topPadding', (0,0), (0,0), 15),

        # Card 2 Style (Blue/Primary)
        ('BACKGROUND', (1,0), (1,0), col_accent),
        
        # Card 3 Style (Red/Error)
        ('BACKGROUND', (2,0), (2,0), col_error),
    ]))
    
    story.append(dash_table)
    story.append(Spacer(1, 25))

    # --- TEACHER DETAILS (Simplified) ---
    story.append(Paragraph("Assessment Details", styles['Heading2']))
    
    details_data = [
        ["Teacher:", data.get('name', 'N/A'), "Created On (UTC):", data.get('created_on', 'N/A')],
        ["Quiz ID:", data['quizID'], "Total Questions:", str(quiz_total_marks)]
    ]
    
    meta_table = Table(details_data, colWidths=[80, 185, 80, 185])
    meta_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), col_light), # Labels Column 1
        ('BACKGROUND', (2,0), (2,-1), col_light), # Labels Column 2
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 25))

    # --- DETAILED RESULTS TABLE ---
    story.append(Paragraph("Detailed Student Rankings", styles['Heading2']))

    # Headers
    table_data = []
    table_data.append(["Rank", "Student ID", "Student Name", "Obtained", "Total", "Status"])

    if class_data:
        # Re-sort for the list (Highest marks first)
        sorted_results = sorted(class_data, key=lambda x: x[3], reverse=True)
        
        for index, (s_id, s_name, total_marks, obtained_marks) in enumerate(sorted_results, 1):
            
            # Percentage & Status Logic
            try:
                percentage = (obtained_marks / total_marks) * 100 if total_marks else 0
            except:
                percentage = 0
            
            status = "PASS" if percentage >= 50 else "FAIL"
            
            # Formatting the row
            table_data.append([
                str(index), 
                s_id, 
                s_name, 
                str(obtained_marks), 
                str(total_marks),
                f"{percentage:.1f}%"
            ])
    else:
        table_data.append(["-", "-", "No Data Available", "-", "-", "-"])

    # Results Table Layout
    results_table = Table(table_data, colWidths=[40, 80, 200, 70, 70, 70])
    
    results_table.setStyle(TableStyle([
        # Header Styling
        ('BACKGROUND', (0, 0), (-1, 0), col_primary),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'), # Align names left
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        
        # Grid & Row Styling
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, col_light]), # Zebra striping
    ]))

    story.append(results_table)
    story.append(Spacer(1, 30))

    # --- Footer ---
    story.append(Paragraph(
        f"\u00A9 ADAM: A Dynamic Assessment Module", 
        ParagraphStyle('Footer', alignment=TA_CENTER, textColor=colors.grey)
    ))

    # 6. Build
    doc.build(story)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ADAM_Report_{teacher_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    )



app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', ''.join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*()", k=32)))


if __name__=='__main__':
   app.run(host='0.0.0.0',debug=False)
