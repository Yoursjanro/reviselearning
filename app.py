from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3, os, hashlib, secrets
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'elearning.db')
app=Flask(__name__)
app.secret_key=os.environ.get('ELEARNING_SECRET','change-this-local-secret-'+secrets.token_hex(8))

def db():
    con=sqlite3.connect(DB)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con

def init_db():
    con=db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,description TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY AUTOINCREMENT,course_id INTEGER NOT NULL,title TEXT NOT NULL,summary TEXT,content TEXT NOT NULL,lesson_order INTEGER DEFAULT 1,FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS quizzes(id INTEGER PRIMARY KEY AUTOINCREMENT,course_id INTEGER NOT NULL,title TEXT NOT NULL,FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT,quiz_id INTEGER NOT NULL,question TEXT NOT NULL,option_a TEXT NOT NULL,option_b TEXT NOT NULL,option_c TEXT NOT NULL,option_d TEXT NOT NULL,correct_answer TEXT NOT NULL,FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS enrollments(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,course_id INTEGER,enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,course_id),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS lesson_progress(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,lesson_id INTEGER,completed INTEGER DEFAULT 0,completed_at TEXT,UNIQUE(user_id,lesson_id),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS quiz_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,quiz_id INTEGER,score INTEGER,total INTEGER,points INTEGER DEFAULT 0,attempted_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS user_points(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,points INTEGER,reason TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS game_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,lesson_id INTEGER,game_name TEXT,score INTEGER,total INTEGER,points INTEGER DEFAULT 0,time_left INTEGER DEFAULT 0,played_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS learning_games(id INTEGER PRIMARY KEY AUTOINCREMENT,lesson_id INTEGER,game_type TEXT,title TEXT,description TEXT,time_limit INTEGER DEFAULT 60,question_count INTEGER DEFAULT 5,enabled INTEGER DEFAULT 1,UNIQUE(lesson_id,game_type),FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS learning_game_questions(id INTEGER PRIMARY KEY AUTOINCREMENT,game_id INTEGER,question TEXT,option_a TEXT,option_b TEXT,option_c TEXT,option_d TEXT,correct_answer TEXT DEFAULT 'A',points INTEGER DEFAULT 10,FOREIGN KEY(game_id) REFERENCES learning_games(id) ON DELETE CASCADE);
    """)
    if not con.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        con.execute('INSERT INTO users(full_name,username,password,role) VALUES(?,?,?,?)',('System Administrator','admin',generate_password_hash('admin123'),'admin'))
        con.execute('INSERT INTO users(full_name,username,password,role) VALUES(?,?,?,?)',('Demo Student','student',generate_password_hash('student123'),'student'))
    if not con.execute('SELECT 1 FROM courses LIMIT 1').fetchone():
        con.execute('INSERT INTO courses(title,description) VALUES(?,?)',('Computer Hardware Servicing','Introduction to computer hardware, components, safety, and basic troubleshooting.'))
        con.execute('INSERT INTO courses(title,description) VALUES(?,?)',('Basic Networking','Learn basic network concepts, cables, devices, and connectivity troubleshooting.'))
        c1=con.execute('SELECT id FROM courses WHERE title=?',('Computer Hardware Servicing',)).fetchone()['id']
        c2=con.execute('SELECT id FROM courses WHERE title=?',('Basic Networking',)).fetchone()['id']
        con.execute('INSERT INTO lessons(course_id,title,summary,content,lesson_order) VALUES(?,?,?,?,?)',(c1,'Computer System Unit','Know the major parts of a system unit.','The system unit contains the motherboard, processor, RAM, storage, power supply, and expansion devices. Always observe electrical safety when handling components.',1))
        con.execute('INSERT INTO lessons(course_id,title,summary,content,lesson_order) VALUES(?,?,?,?,?)',(c1,'Motherboard','Understand the main board and its slots.','The motherboard connects the major components of a computer. Common parts include the CPU socket, RAM slots, expansion slots, storage connectors, and power connectors.',2))
        con.execute('INSERT INTO lessons(course_id,title,summary,content,lesson_order) VALUES(?,?,?,?,?)',(c2,'Network Basics','Learn the purpose of a computer network.','A network allows computers and devices to communicate and share resources. Common devices include switches, routers, and wireless access points.',1))
        con.execute('INSERT INTO quizzes(course_id,title) VALUES(?,?)',(c1,'Hardware Basics Quiz'))
        con.execute('INSERT INTO quizzes(course_id,title) VALUES(?,?)',(c2,'Networking Basics Quiz'))
        q1=con.execute('SELECT id FROM quizzes WHERE title=?',('Hardware Basics Quiz',)).fetchone()['id']
        q2=con.execute('SELECT id FROM quizzes WHERE title=?',('Networking Basics Quiz',)).fetchone()['id']
        con.executemany('INSERT INTO questions(quiz_id,question,option_a,option_b,option_c,option_d,correct_answer) VALUES(?,?,?,?,?,?,?)',[
        (q1,'Which component is often called the main circuit board?','RAM','Motherboard','Power Supply','Hard Drive','B'),
        (q1,'Which component performs most processing tasks?','CPU','Monitor','Keyboard','Speaker','A'),
        (q2,'Which device commonly connects devices within a LAN?','Switch','Printer','Scanner','Projector','A')])
    # four game modes per lesson
    types={'blaster':('🎯 Hardware Blaster','Find the target and answer lesson questions.'),'racer':('🏎️ Hardware Racer','Answer correctly to accelerate toward the finish.'),'builder':('🧩 PC Builder','Choose the component or concept that fits the task.'),'repair':('🛠️ Repair Challenge','Diagnose the situation using what you learned.')}
    for l in con.execute('SELECT id FROM lessons').fetchall():
        for typ,(title,desc) in types.items():
            con.execute('INSERT OR IGNORE INTO learning_games(lesson_id,game_type,title,description) VALUES(?,?,?,?)',(l['id'],typ,title,desc))
    for g in con.execute('SELECT id FROM learning_games').fetchall():
        if not con.execute('SELECT 1 FROM learning_game_questions WHERE game_id=?',(g['id'],)).fetchone():
            qs=[
            ('Which component is the main circuit board?','Motherboard','Keyboard','Monitor','Speaker','A'),
            ('Which component performs most processing tasks?','CPU','Mouse','Monitor','Printer','A'),
            ('Which component stores data when power is off?','Storage drive','RAM','CPU cache','Monitor','A'),
            ('Which component supplies power to computer parts?','Power Supply Unit','Keyboard','Router','Webcam','A'),
            ('Which component stores temporary working data?','RAM','SSD','Power Supply','Monitor','A')]
            con.executemany('INSERT INTO learning_game_questions(game_id,question,option_a,option_b,option_c,option_d,correct_answer,points) VALUES(?,?,?,?,?,?,?,10)',[(g['id'],*q) for q in qs])
    con.commit(); con.close()
init_db()

def login_required(fn):
    @wraps(fn)
    def wrap(*a,**kw):
        if 'user' not in session: return redirect(url_for('login'))
        return fn(*a,**kw)
    return wrap
def admin_required(fn):
    @wraps(fn)
    def wrap(*a,**kw):
        if 'user' not in session: return redirect(url_for('login'))
        if session['user']['role']!='admin': flash('Admin access only.'); return redirect(url_for('dashboard'))
        return fn(*a,**kw)
    return wrap

@app.context_processor
def inject():
    return {'user':session.get('user')}
@app.route('/')
def index(): return redirect(url_for('dashboard') if 'user' in session else url_for('login'))
@app.route('/login',methods=['GET','POST'])
def login():
    error=''
    if request.method=='POST':
        con=db(); u=con.execute('SELECT * FROM users WHERE username=?',(request.form.get('username','').strip(),)).fetchone(); con.close()
        if u and check_password_hash(u['password'],request.form.get('password','')):
            session['user']={'id':u['id'],'username':u['username'],'full_name':u['full_name'],'role':u['role']}
            return redirect(url_for('dashboard'))
        error='Invalid username or password.'
    return render_template('login.html',error=error)
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/dashboard')
@login_required
def dashboard():
    con=db()
    stats={
      'Students': con.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
      'Courses': con.execute('SELECT COUNT(*) FROM courses').fetchone()[0],
      'Lessons': con.execute('SELECT COUNT(*) FROM lessons').fetchone()[0],
      'Quizzes': con.execute('SELECT COUNT(*) FROM quizzes').fetchone()[0],
      'Learning Games': con.execute('SELECT COUNT(*) FROM learning_games WHERE enabled=1').fetchone()[0],
      'Game Questions': con.execute('SELECT COUNT(*) FROM learning_game_questions').fetchone()[0]
    }
    courses=con.execute('SELECT * FROM courses ORDER BY id').fetchall()
    points=con.execute('SELECT COALESCE(SUM(points),0) FROM user_points WHERE user_id=?',(session['user']['id'],)).fetchone()[0]
    con.close()
    return render_template('dashboard.html',stats=stats,courses=courses,points=points)
@app.route('/courses')
@login_required
def courses():
    con=db(); rows=con.execute('SELECT c.*, (SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) lesson_count FROM courses c').fetchall(); con.close()
    return render_template('courses.html',courses=rows)
@app.route('/course/<int:cid>')
@login_required
def course(cid):
    con=db(); c=con.execute('SELECT * FROM courses WHERE id=?',(cid,)).fetchone(); lessons=con.execute('SELECT * FROM lessons WHERE course_id=? ORDER BY lesson_order,id',(cid,)).fetchall(); con.close()
    if not c: return 'Course not found',404
    return render_template('course.html',course=c,lessons=lessons)
@app.route('/lesson/<int:lid>')
@login_required
def lesson(lid):
    con=db(); l=con.execute('SELECT l.*,c.title course_title FROM lessons l JOIN courses c ON c.id=l.course_id WHERE l.id=?',(lid,)).fetchone(); con.close()
    if not l: return 'Lesson not found',404
    return render_template('lesson.html',lesson=l)
@app.route('/complete/<int:lid>',methods=['POST'])
@login_required
def complete(lid):
    con=db(); con.execute('INSERT OR IGNORE INTO lesson_progress(user_id,lesson_id,completed,completed_at) VALUES(?,?,1,CURRENT_TIMESTAMP)',(session['user']['id'],lid)); con.execute('UPDATE lesson_progress SET completed=1,completed_at=CURRENT_TIMESTAMP WHERE user_id=? AND lesson_id=?',(session['user']['id'],lid)); con.commit(); con.close(); flash('Lesson marked complete!'); return redirect(url_for('lesson',lid=lid))
@app.route('/quizzes')
@login_required
def quizzes():
    con=db(); rows=con.execute('SELECT q.*,c.title course_title FROM quizzes q JOIN courses c ON c.id=q.course_id').fetchall(); con.close()
    return render_template('quizzes.html',quizzes=rows)
@app.route('/quiz/<int:qid>',methods=['GET','POST'])
@login_required
def quiz(qid):
    con=db(); q=con.execute('SELECT * FROM quizzes WHERE id=?',(qid,)).fetchone(); questions=con.execute('SELECT * FROM questions WHERE quiz_id=?',(qid,)).fetchall()
    result=None
    if request.method=='POST':
        score=sum(1 for x in questions if request.form.get(str(x['id']))==x['correct_answer'])
        result={'score':score,'total':len(questions)}
        con.execute('INSERT INTO quiz_attempts(user_id,quiz_id,score,total,points) VALUES(?,?,?,?,?)',(session['user']['id'],qid,score,len(questions),score*10))
        con.execute('INSERT INTO user_points(user_id,points,reason) VALUES(?,?,?)',(session['user']['id'],score*10,'Quiz: '+q['title']))
        con.commit()
    con.close()
    if not q: return 'Quiz not found',404
    return render_template('quiz.html',quiz=q,questions=questions,result=result)
@app.route('/games')
@login_required
def games():
    con=db(); rows=con.execute('SELECT g.*,l.title lesson_title,l.id lesson_id FROM learning_games g JOIN lessons l ON l.id=g.lesson_id WHERE enabled=1 ORDER BY l.id,g.id').fetchall(); con.close()
    return render_template('games.html',games=rows)
@app.route('/game/<int:gid>',methods=['GET','POST'])
@login_required
def learning_game(gid):
    con=db()
    game=con.execute('SELECT g.*,l.title lesson_title FROM learning_games g JOIN lessons l ON l.id=g.lesson_id WHERE g.id=? AND g.enabled=1',(gid,)).fetchone()
    if not game:
        con.close(); return 'Game not found or disabled',404
    qs=con.execute('SELECT * FROM learning_game_questions WHERE game_id=? ORDER BY RANDOM() LIMIT ?',(gid,game['question_count'])).fetchall()
    result=None
    if request.method=='POST':
        score=0; pts=0
        for x in qs:
            if request.form.get(str(x['id']))==x['correct_answer']:
                score+=1; pts+=x['points']
        con.execute('INSERT INTO game_attempts(user_id,lesson_id,game_name,score,total,points,time_left) VALUES(?,?,?,?,?,?,?)',
                    (session['user']['id'],game['lesson_id'],game['title'],score,len(qs),pts,request.form.get('time_left',0)))
        con.execute('INSERT INTO user_points(user_id,points,reason) VALUES(?,?,?)',(session['user']['id'],pts,'Game: '+game['title']))
        con.commit(); result={'score':score,'total':len(qs),'points':pts}
    con.close()
    return render_template('learning_game.html',game=game,questions=qs,result=result)
@app.route('/shooter')
@login_required
def shooter(): return render_template('shooter.html')
@app.route('/leaderboard')
@login_required
def leaderboard():
    con=db(); rows=con.execute("SELECT u.full_name,COALESCE(SUM(p.points),0) points FROM users u LEFT JOIN user_points p ON p.user_id=u.id WHERE u.role='student' GROUP BY u.id ORDER BY points DESC").fetchall(); con.close()
    return render_template('leaderboard.html',rows=rows)
@app.route('/profile')
@login_required
def profile():
    con=db(); u=con.execute('SELECT * FROM users WHERE id=?',(session['user']['id'],)).fetchone(); con.close()
    return render_template('profile.html',account=u)
@app.route('/admin/users',methods=['GET','POST'])
@admin_required
def admin_users():
    con=db(); edit=None
    if request.method=='POST':
        uid=request.form.get('id'); name=request.form['full_name'].strip(); username=request.form['username'].strip(); password=request.form.get('password',''); role=request.form.get('role','student')
        try:
            if uid:
                if password: con.execute('UPDATE users SET full_name=?,username=?,role=?,password=? WHERE id=?',(name,username,role,generate_password_hash(password),uid))
                else: con.execute('UPDATE users SET full_name=?,username=?,role=? WHERE id=?',(name,username,role,uid))
            else: con.execute('INSERT INTO users(full_name,username,password,role) VALUES(?,?,?,?)',(name,username,generate_password_hash(password),role))
            con.commit(); flash('User saved successfully.')
        except sqlite3.IntegrityError: flash('That username already exists.')
        con.close(); return redirect(url_for('admin_users'))
    if request.args.get('edit'): edit=con.execute('SELECT * FROM users WHERE id=?',(request.args['edit'],)).fetchone()
    users=con.execute('SELECT id,full_name,username,role,created_at FROM users ORDER BY id DESC').fetchall(); con.close()
    return render_template('admin_users.html',users=users,edit=edit,show_users=request.args.get('view')=='1' or bool(edit),show_form=request.args.get('add')=='1' or bool(edit))
@app.route('/admin/users/delete/<int:uid>',methods=['POST'])
@admin_required
def delete_user(uid):
    if uid!=session['user']['id']:
        con=db(); con.execute('DELETE FROM users WHERE id=?',(uid,)); con.commit(); con.close()
    return redirect(url_for('admin_users'))
@app.route('/admin/courses',methods=['GET','POST'])
@admin_required
def admin_courses():
    con=db()
    if request.method=='POST':
        title=request.form['title'].strip(); desc=request.form['description'].strip(); cid=request.form.get('id')
        if cid: con.execute('UPDATE courses SET title=?,description=? WHERE id=?',(title,desc,cid))
        else: con.execute('INSERT INTO courses(title,description) VALUES(?,?)',(title,desc))
        con.commit(); con.close(); return redirect(url_for('admin_courses'))
    edit=con.execute('SELECT * FROM courses WHERE id=?',(request.args['edit'],)).fetchone() if request.args.get('edit') else None
    rows=con.execute('SELECT * FROM courses ORDER BY id DESC').fetchall(); con.close()
    return render_template('admin_courses.html',courses=rows,edit=edit,show_courses=request.args.get('view')=='1' or bool(edit),show_form=request.args.get('add')=='1' or bool(edit))
@app.route('/admin/lessons',methods=['GET','POST'])
@admin_required
def admin_lessons():
    con=db()
    if request.method=='POST':
        vals=(request.form['course_id'],request.form['title'],request.form.get('summary',''),request.form['content'],request.form.get('lesson_order',1))
        lid=request.form.get('id')
        if lid: con.execute('UPDATE lessons SET course_id=?,title=?,summary=?,content=?,lesson_order=? WHERE id=?',(*vals,lid))
        else: con.execute('INSERT INTO lessons(course_id,title,summary,content,lesson_order) VALUES(?,?,?,?,?)',vals)
        con.commit(); con.close(); return redirect(url_for('admin_lessons'))
    courses=con.execute('SELECT * FROM courses').fetchall(); rows=con.execute('SELECT l.*,c.title course_title FROM lessons l JOIN courses c ON c.id=l.course_id ORDER BY c.id,l.lesson_order').fetchall()
    edit=con.execute('SELECT * FROM lessons WHERE id=?',(request.args['edit'],)).fetchone() if request.args.get('edit') else None
    con.close(); return render_template('admin_lessons.html',courses=courses,lessons=rows,edit=edit,show_lessons=request.args.get('view')=='1' or bool(edit),show_form=request.args.get('add')=='1' or bool(edit))
@app.route('/admin/reports')
@admin_required
def admin_reports():
    con=db()
    rows=con.execute("""SELECT u.full_name,
      COALESCE((SELECT SUM(points) FROM user_points p WHERE p.user_id=u.id),0) xp,
      (SELECT COUNT(*) FROM lesson_progress lp WHERE lp.user_id=u.id AND lp.completed=1) lessons_completed,
      (SELECT COUNT(*) FROM quiz_attempts qa WHERE qa.user_id=u.id) quiz_attempts
      FROM users u WHERE u.role='student' ORDER BY xp DESC, u.full_name""").fetchall()
    con.close()
    return render_template('admin_reports.html',rows=rows)

@app.route('/admin/games')
@admin_required
def admin_games():
    con=db()
    rows=con.execute("""SELECT g.*,l.title lesson_title,c.title course_title,
      (SELECT COUNT(*) FROM learning_game_questions q WHERE q.game_id=g.id) question_total
      FROM learning_games g JOIN lessons l ON l.id=g.lesson_id
      JOIN courses c ON c.id=l.course_id ORDER BY c.title,l.lesson_order,l.title,g.id""").fetchall()
    con.close()
    return render_template('admin_games.html',rows=rows)

@app.route('/admin/game/<int:gid>',methods=['GET','POST'])
@admin_required
def admin_game_studio(gid):
    con=db()
    game=con.execute("""SELECT g.*,l.title lesson_title,c.title course_title
      FROM learning_games g JOIN lessons l ON l.id=g.lesson_id
      JOIN courses c ON c.id=l.course_id WHERE g.id=?""",(gid,)).fetchone()
    if not game:
        con.close(); return 'Game not found',404
    if request.method=='POST':
        action=request.form.get('action','settings')
        if action=='settings':
            title=request.form.get('title','').strip()
            description=request.form.get('description','').strip()
            try:
                time_limit=max(10,min(600,int(request.form.get('time_limit','60'))))
                question_count=max(1,min(100,int(request.form.get('question_count','5'))))
            except ValueError:
                con.close(); flash('Time and question count must be valid numbers.'); return redirect(url_for('admin_game_studio',gid=gid))
            enabled=1 if request.form.get('enabled')=='on' else 0
            if not title:
                con.close(); flash('Game title is required.'); return redirect(url_for('admin_game_studio',gid=gid))
            con.execute('UPDATE learning_games SET title=?,description=?,time_limit=?,question_count=?,enabled=? WHERE id=?',
                        (title,description,time_limit,question_count,enabled,gid))
            con.commit(); con.close(); flash('Game settings saved.'); return redirect(url_for('admin_game_studio',gid=gid))
        if action=='add_question':
            question=request.form.get('question','').strip()
            opts=[request.form.get('option_'+k,'').strip() for k in 'abcd']
            correct=request.form.get('correct_answer','A').upper()
            try: points=max(0,min(1000,int(request.form.get('points','10'))))
            except ValueError: points=10
            if not question or not all(opts) or correct not in 'ABCD':
                con.close(); flash('Enter the question, all four choices, and the correct answer.'); return redirect(url_for('admin_game_studio',gid=gid))
            con.execute('INSERT INTO learning_game_questions(game_id,question,option_a,option_b,option_c,option_d,correct_answer,points) VALUES(?,?,?,?,?,?,?,?)',
                        (gid,question,*opts,correct,points))
            con.commit(); con.close(); flash('Question added.'); return redirect(url_for('admin_game_studio',gid=gid))
        if action=='edit_question':
            qid=request.form.get('question_id')
            question=request.form.get('question','').strip()
            opts=[request.form.get('option_'+k,'').strip() for k in 'abcd']
            correct=request.form.get('correct_answer','A').upper()
            try: points=max(0,min(1000,int(request.form.get('points','10'))))
            except ValueError: points=10
            if not question or not all(opts) or correct not in 'ABCD':
                con.close(); flash('Enter the question, all four choices, and the correct answer.'); return redirect(url_for('admin_game_studio',gid=gid))
            con.execute('UPDATE learning_game_questions SET question=?,option_a=?,option_b=?,option_c=?,option_d=?,correct_answer=?,points=? WHERE id=? AND game_id=?',
                        (question,*opts,correct,points,qid,gid))
            con.commit(); con.close(); flash('Question updated.'); return redirect(url_for('admin_game_studio',gid=gid))
    questions=con.execute('SELECT * FROM learning_game_questions WHERE game_id=? ORDER BY id',(gid,)).fetchall()
    con.close()
    return render_template('admin_game_studio.html',game=game,questions=questions)

@app.route('/admin/game/<int:gid>/question/<int:qid>/delete',methods=['POST'])
@admin_required
def admin_game_question_delete(gid,qid):
    con=db(); con.execute('DELETE FROM learning_game_questions WHERE id=? AND game_id=?',(qid,gid)); con.commit(); con.close()
    flash('Question deleted.'); return redirect(url_for('admin_game_studio',gid=gid))

@app.route('/admin/game/<int:gid>/test',methods=['GET','POST'])
@admin_required
def admin_game_test(gid):
    con=db()
    game=con.execute("""SELECT g.*,l.title lesson_title FROM learning_games g
      JOIN lessons l ON l.id=g.lesson_id WHERE g.id=?""",(gid,)).fetchone()
    if not game:
        con.close(); return 'Game not found',404
    questions=con.execute('SELECT * FROM learning_game_questions WHERE game_id=? ORDER BY id LIMIT ?',
                          (gid,game['question_count'])).fetchall()
    result=None
    if request.method=='POST':
        score=0; points=0
        for q in questions:
            if request.form.get(str(q['id']))==q['correct_answer']:
                score+=1; points+=q['points']
        result={'score':score,'total':len(questions),'points':points}
    con.close()
    return render_template('admin_game_test.html',game=game,questions=questions,result=result)

@app.route('/admin/leaderboard')
@admin_required
def admin_leaderboard(): return redirect(url_for('leaderboard'))
if __name__=='__main__':
    init_db()
    app.run(host='0.0.0.0',port=5000,debug=False)
