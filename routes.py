import datetime
from flask import redirect, render_template, request, url_for, session, flash
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
from app import app, db
from validations import validate_password, validate_topic, validate_username
from flask import redirect, session, url_for
from sqlalchemy import text

@app.route("/like_area/<int:area_id>", methods=["POST"])
def like_area(area_id):
    user_id = session.get("user_id")
    try:        
        sql = text("INSERT INTO areas_likes (area_id, user_id, likes, liked_at) VALUES (:area_id, :user_id, 1, NOW())")
        db.session.execute(sql, {"area_id": area_id, "user_id": user_id})
        db.session.commit()
    
    except:
        db.session.rollback()
    return redirect("/")

@app.route("/unlike_area/<int:area_id>", methods=["POST"])
def unlike_area(area_id):
    user_id = session.get("user_id")
    try:
        sql = text("DELETE FROM areas_likes WHERE area_id = :area_id AND user_id = :user_id")
        db.session.execute(sql, {"area_id": area_id, "user_id": user_id})
        db.session.commit()
    except:
        db.session.rollback()
    return redirect("/")

@app.route("/")
def index():
    try:
        sql = text("""
            SELECT a.id, a.topic, a.created_at, a.creator, 
                   COALESCE(SUM(al.likes), 0) AS likes,
                   ARRAY_AGG(al.user_id) AS liked_users,
                   COALESCE(av.visits, 0) AS visit_count
            FROM areas a
            LEFT JOIN areas_likes al ON a.id = al.area_id 
            LEFT JOIN areas_visits av ON a.id = av.area_id
            GROUP BY a.id, a.topic, a.created_at, a.creator, av.visits
            ORDER BY a.created_at DESC
        """)
        result = db.session.execute(sql)
        areas = result.fetchall()
        count = len(areas)
        return render_template("index.html", areas=areas, user_id=session.get("user_id"), count=count)

    except:
        return redirect("/")

@app.route("/delete_area/<int:area_id>", methods=["POST"])
def delete_area(area_id):
    try:
        sql_delete_messages = text("DELETE FROM messages WHERE area_id = :area_id")
        db.session.execute(sql_delete_messages, {"area_id": area_id})
        
        sql_delete_area = text("DELETE FROM areas WHERE id = :id")
        db.session.execute(sql_delete_area, {"id": area_id})
        db.session.commit()
        return redirect("/")
    except:
        db.session.rollback()
    return redirect("/")

@app.route("/delete_message/<int:message_id>", methods=["POST"])
def delete_message(message_id):
    try:
        sql = text("SELECT area_id FROM messages WHERE id = :message_id")
        result = db.session.execute(sql, {"message_id": message_id})
        area_id = result.fetchone()[0]

        sql_delete_message = text("DELETE FROM messages WHERE id = :message_id")
        db.session.execute(sql_delete_message, {"message_id": message_id})
        db.session.commit()
        return redirect(f"/chatroom/{area_id}")
    except:
        db.session.rollback()
        return redirect("/")

@app.route("/new_area")
def new():
    return render_template("new_area.html")

@app.route("/add_discussion_area", methods=["POST"])
def add_discussion_area():
    topic = request.form["topic"].strip()

    errors = validate_topic(topic)
    if errors:
        for error in errors:
            flash(error)
        return redirect(url_for('new'))
    
    creator_username = session['username']
    sql = text("INSERT INTO areas (topic, created_at, creator) VALUES (:topic, :created_at, :creator)")
    db.session.execute(
        sql,
        {"topic": topic, "created_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "creator": creator_username}
    )
    db.session.commit()
    return redirect("/")

@app.route("/chatroom/<int:id>")
def chatroom(id):
    sql_topic = text("SELECT topic FROM areas WHERE id = :id")
    result_topic = db.session.execute(sql_topic, {"id": id})
    topic = result_topic.scalar()

    sql_messages = text("SELECT id, message, created_at, sender FROM messages WHERE area_id = :id")
    result_messages = db.session.execute(sql_messages, {"id": id})
    messages = result_messages.fetchall()

    sql_check = text("SELECT visits FROM areas_visits WHERE area_id = :area_id")
    result_check = db.session.execute(sql_check, {"area_id": id})

    if result_check.fetchone() is None:
        sql_insert = text("INSERT INTO areas_visits (area_id, visits) VALUES (:area_id, 1)")
        db.session.execute(sql_insert, {"area_id": id})
    else:
        sql_update_visits = text("UPDATE areas_visits SET visits = visits + 1 WHERE area_id = :area_id")
        db.session.execute(sql_update_visits, {"area_id": id})
    
    db.session.commit()
    return render_template("chatroom.html", messages=messages, area_id=id, topic=topic)

@app.route("/send_message", methods=["POST"])
def send_message():
    message = request.form["message"]
    area_id = request.form["area_id"]
    sender_username = session['username']
    sql = text("INSERT INTO messages (area_id, message, created_at, sender) VALUES (:area_id, :message, :created_at, :sender)")
    db.session.execute(
        sql,
        {"area_id": area_id, "message": message, "created_at": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "sender": sender_username}
    )
    db.session.commit()
    return redirect(url_for('chatroom', id=area_id))

@app.route("/new_message/<int:area_id>")
def new_message(area_id):
    return render_template("new_message.html", area_id=area_id)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        errors = []

        if password != confirm_password:
            errors.append("Salasanat eivät täsmää")
        
        if validate_password(password):
            errors.extend(validate_password(password))

        if validate_username(username):
            errors.extend(validate_username(username))
        
        if errors:
            for error in errors:
                flash(error)
            return render_template("register.html")
        
        hash_value = generate_password_hash(password)
        sql = text("INSERT INTO users (username, password) VALUES (:username, :password)")
        db.session.execute(sql, {"username": username, "password": hash_value})
        db.session.commit()
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        sql = text("SELECT id, password FROM users WHERE username=:username")
        result = db.session.execute(sql, {"username": username})
        user = result.fetchone()

        if not user:
            flash("Väärä käyttäjätunnus tai salasana")
            return redirect("/login")

        hash_value = user.password
        if check_password_hash(hash_value, password):
            session["user_id"] = user.id
            session["username"] = username
            return redirect("/")
        else:
            flash("Väärä käyttäjätunnus tai salasana")
            return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    del session["username"]
    return redirect("/")
