from flask import Flask, render_template, request, redirect, url_for, session, current_app
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sqlite3
from os import path

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'секретно-секретный секрет')
app.config['DB_TYPE'] = os.getenv('DB_TYPE', 'postgres')


def db_connect():
    if current_app.config['DB_TYPE'] == 'postgres':
        conn = psycopg2.connect(
            host='127.0.0.1',
            database='cadr',
            user='ira_rgz',
            password='12345'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        dir_path = path.dirname(path.realpath(__file__))
        db_path = path.join(dir_path, "database.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    return conn, cur

def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()


# Главная страница
@app.route('/')
def main():
    return render_template('main.html')

# Страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'password': 
            session['logged_in'] = True
            return redirect(url_for('main'))
        else:
            return render_template('login.html', error='Неверный логин или пароль')
    return render_template('login.html')

# Выход из аккаунта кадровика
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('main'))

# Список сотрудников
@app.route('/employees')
def employees():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'name')  # По умолчанию сортировка по имени
    order = request.args.get('order', 'asc')  # По умолчанию сортировка по возрастанию
    gender = request.args.get('gender', '')
    probation = request.args.get('probation', '')

    conn, cur = db_connect()

    # Поиск и сортировка
    if current_app.config['DB_TYPE'] == 'postgres':
        query = """
            SELECT * FROM employees
            WHERE (name LIKE %s OR position LIKE %s OR phone LIKE %s OR email LIKE %s)
        """
    else:
        query = """
            SELECT * FROM employees
            WHERE (name LIKE ? OR position LIKE ? OR phone LIKE ? OR email LIKE ?)
        """
    params = [f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%']

    # Условие для поиска по полу
    if gender:
        if current_app.config['DB_TYPE'] == 'postgres':
            query += " AND gender = %s"
        else:
            query += " AND gender = ?"
        params.append(gender)

    # Условие для поиска по испытательному сроку
    if probation == 'true':
        query += " AND probation = TRUE"
    elif probation == 'false':
        query += " AND probation = FALSE"

    # Сортировка и пагинация
    if current_app.config['DB_TYPE'] == 'postgres':
        query += """
            ORDER BY {} {}
            LIMIT 20 OFFSET %s
        """.format(sort_by, order)
    else:
        query += """
            ORDER BY {} {}
            LIMIT 20 OFFSET ?
        """.format(sort_by, order)
    params.append((page - 1) * 20)

    cur.execute(query, params)
    employees = cur.fetchall() 

    # Получение общего количества сотрудников для пагинации
    if current_app.config['DB_TYPE'] == 'postgres':
        count_query = """
            SELECT COUNT(*) FROM employees
            WHERE (name LIKE %s OR position LIKE %s OR phone LIKE %s OR email LIKE %s)
        """
    else:
        count_query = """
            SELECT COUNT(*) FROM employees
            WHERE (name LIKE ? OR position LIKE ? OR phone LIKE ? OR email LIKE ?)
        """
    count_params = [f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%']
 
    if gender:
        if current_app.config['DB_TYPE'] == 'postgres':
            count_query += " AND gender = %s"
        else:
            count_query += " AND gender = ?"
        count_params.append(gender)

    if probation == 'true':
        count_query += " AND probation = TRUE"
    elif probation == 'false':
        count_query += " AND probation = FALSE"

    cur.execute(count_query, count_params)
    total_count = cur.fetchone()['count']

    db_close(conn, cur)

    return render_template('employees.html', employees=employees, search=search, sort_by=sort_by, order=order,
                           logged_in=session.get('logged_in', False), page=page, total_pages=(total_count // 20) + 1,
                           gender=gender, probation=probation)

# Добавление сотрудника
@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        gender = request.form['gender']
        phone = request.form['phone']
        email = request.form['email']
        probation = request.form.get('probation') == 'on'
        hire_date = request.form['hire_date']

        conn, cur = db_connect()
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("""
                INSERT INTO employees (name, position, gender, phone, email, probation, hire_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, position, gender, phone, email, probation, hire_date))
        else:
            cur.execute("""
                INSERT INTO employees (name, position, gender, phone, email, probation, hire_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, position, gender, phone, email, probation, hire_date))
        db_close(conn, cur)

        return redirect(url_for('employees'))

    return render_template('edit_employee.html', action='add', logged_in=session.get('logged_in', False))

# Редактирование сотрудника
@app.route('/edit_employee/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT * FROM employees WHERE id = %s", (id,))
    else:
        cur.execute("SELECT * FROM employees WHERE id = ?", (id,))
    employee = cur.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        gender = request.form['gender']
        phone = request.form['phone']
        email = request.form['email']
        probation = request.form.get('probation') == 'on'
        hire_date = request.form['hire_date']

        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute("""
                UPDATE employees
                SET name = %s, position = %s, gender = %s, phone = %s, email = %s, probation = %s, hire_date = %s
                WHERE id = %s
            """, (name, position, gender, phone, email, probation, hire_date, id))
        else:
            cur.execute("""
                UPDATE employees
                SET name = ?, position = ?, gender = ?, phone = ?, email = ?, probation = ?, hire_date = ?
                WHERE id = ?
            """, (name, position, gender, phone, email, probation, hire_date, id))
        db_close(conn, cur)

        return redirect(url_for('employees'))

    return render_template('edit_employee.html', action='edit', employee=employee, logged_in=session.get('logged_in', False))

# Удаление сотрудника
@app.route('/delete_employee/<int:id>')
def delete_employee(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute("DELETE FROM employees WHERE id = %s", (id,))
    else:
        cur.execute("DELETE FROM employees WHERE id =?", (id,))
    db_close(conn, cur)

    return redirect(url_for('employees'))