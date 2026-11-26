import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date
from pathlib import Path


DB_PATH = Path(__file__).resolve().with_name("library.db")


DEMO_BOOKS = [
    ("Война и мир", "Лев Толстой", 1869, "Роман", 3),
    ("Преступление и наказание", "Фёдор Достоевский", 1866, "Роман", 2),
    ("Мастер и Маргарита", "Михаил Булгаков", 1967, "Роман", 4),
    ("Евгений Онегин", "Александр Пушкин", 1833, "Поэзия", 2),
    ("Гарри Поттер и философский камень", "Джоан Роулинг", 1997, "Фэнтези", 5),
    ("1984", "Джордж Оруэлл", 1949, "Антиутопия", 3),
    ("Маленький принц", "Антуан де Сент-Экзюпери", 1943, "Сказка", 4),
    ("Три товарища", "Эрих Мария Ремарк", 1936, "Роман", 2),
    ("Алхимик", "Паулу Коэльо", 1988, "Роман", 3),
    ("А зори здесь тихие", "Борис Васильев", 1969, "Повесть", 2),
    ("Шерлок Холмс", "Артур Конан Дойл", 1892, "Детектив", 4),
    ("Python для начинающих", "Эрик Мэтиз", 2016, "Программирование", 5),
]


class LibraryDatabase:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = str(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.seed_data()

    def create_tables(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'librarian'))
            );

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                year INTEGER NOT NULL,
                genre TEXT NOT NULL,
                total INTEGER NOT NULL CHECK(total >= 0),
                available INTEGER NOT NULL CHECK(available >= 0)
            );

            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                reader_name TEXT NOT NULL,
                loan_date TEXT NOT NULL,
                returned INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
            );
            """
        )
        self.connection.commit()

    def seed_data(self) -> None:
        users = [
            ("admin", "admin123", "admin"),
            ("librarian", "library123", "librarian"),
        ]
        self.connection.executemany(
            "INSERT OR IGNORE INTO users(login, password, role) VALUES (?, ?, ?)",
            users,
        )

        if self.connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
            self.connection.executemany(
                """
                INSERT INTO books(title, author, year, genre, total, available)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (title, author, year, genre, total, total)
                    for title, author, year, genre, total in DEMO_BOOKS
                ],
            )
        self.connection.commit()

    def authenticate(self, login: str, password: str):
        return self.connection.execute(
            "SELECT login, role FROM users WHERE login = ? AND password = ?",
            (login, password),
        ).fetchone()

    def get_books(self, search: str = ""):
        if not search.strip():
            return self.connection.execute(
                "SELECT * FROM books ORDER BY id"
            ).fetchall()
        query = search.strip().casefold()
        all_books = self.connection.execute(
            "SELECT * FROM books ORDER BY id"
        ).fetchall()
        return [
            book for book in all_books
            if query in str(book["title"]).casefold()
            or query in str(book["author"]).casefold()
            or query in str(book["genre"]).casefold()
        ]

    def add_book(self, title: str, author: str, year: int, genre: str, total: int) -> None:
        self.connection.execute(
            """
            INSERT INTO books(title, author, year, genre, total, available)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, author, year, genre, total, total),
        )
        self.connection.commit()

    def update_book(self, book_id: int, title: str, author: str, year: int,
                    genre: str, total: int) -> str:
        active_loans = self.connection.execute(
            "SELECT COUNT(*) FROM loans WHERE book_id = ? AND returned = 0",
            (book_id,),
        ).fetchone()[0]
        if active_loans > total:
            return "Новое количество меньше числа выданных экземпляров."

        self.connection.execute(
            """
            UPDATE books
            SET title = ?, author = ?, year = ?, genre = ?, total = ?, available = ?
            WHERE id = ?
            """,
            (title, author, year, genre, total, total - active_loans, book_id),
        )
        self.connection.commit()
        return ""

    def delete_book(self, book_id: int) -> None:
        self.connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
        self.connection.commit()

    def issue_book(self, book_id: int, reader_name: str, loan_date: str) -> str:
        book = self.connection.execute(
            "SELECT title, available FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        if book is None:
            return "Книга не найдена."
        if book["available"] <= 0:
            return "Свободных экземпляров этой книги нет."

        self.connection.execute(
            "UPDATE books SET available = available - 1 WHERE id = ?", (book_id,)
        )
        self.connection.execute(
            """
            INSERT INTO loans(book_id, reader_name, loan_date, returned)
            VALUES (?, ?, ?, 0)
            """,
            (book_id, reader_name, loan_date),
        )
        self.connection.commit()
        return ""

    def get_active_loans(self):
        return self.connection.execute(
            """
            SELECT loans.id, loans.book_id, books.title, loans.reader_name, loans.loan_date
            FROM loans
            JOIN books ON books.id = loans.book_id
            WHERE loans.returned = 0
            ORDER BY loans.id
            """,
        ).fetchall()

    def return_book(self, loan_id: int) -> str:
        loan = self.connection.execute(
            "SELECT book_id FROM loans WHERE id = ? AND returned = 0", (loan_id,)
        ).fetchone()
        if loan is None:
            return "Выдача не найдена или книга уже возвращена."

        book = self.connection.execute(
            "SELECT total, available FROM books WHERE id = ?", (loan["book_id"],)
        ).fetchone()
        if book["available"] >= book["total"]:
            return "Количество доступных экземпляров уже не меньше общего."

        self.connection.execute(
            "UPDATE loans SET returned = 1 WHERE id = ?", (loan_id,)
        )
        self.connection.execute(
            "UPDATE books SET available = available + 1 WHERE id = ?", (loan["book_id"],)
        )
        self.connection.commit()
        return ""

    def close(self) -> None:
        self.connection.close()


class LibraryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Библиотечная система")
        self.root.geometry("920x620")
        self.root.minsize(820, 540)
        self.db = LibraryDatabase()
        self.user = None
        self.current_frame = None
        self.show_login()

    def show_login(self) -> None:
        self.user = None
        self._clear_root()
        self.root.title("Библиотечная система — Авторизация")

        card = tk.Frame(self.root, padx=36, pady=30, relief="groove", borderwidth=2)
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="Вход в библиотечную систему",
                 font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        tk.Label(card, text="Логин:", font=("Segoe UI", 11)).grid(
            row=1, column=0, sticky="e", padx=(0, 10), pady=6
        )
        tk.Label(card, text="Пароль:", font=("Segoe UI", 11)).grid(
            row=2, column=0, sticky="e", padx=(0, 10), pady=6
        )

        self.login_entry = tk.Entry(card, font=("Segoe UI", 11), width=24)
        self.password_entry = tk.Entry(card, font=("Segoe UI", 11), width=24, show="*")
        self.login_entry.grid(row=1, column=1, pady=6)
        self.password_entry.grid(row=2, column=1, pady=6)

        buttons = tk.Frame(card)
        buttons.grid(row=3, column=0, columnspan=2, pady=(18, 0))
        tk.Button(buttons, text="Войти", command=self.login,
                  bg="#2563EB", fg="white", width=12, relief="flat", padx=8, pady=5).pack(side="left", padx=5)
        tk.Button(buttons, text="Выход", command=self.exit_app,
                  bg="#DC2626", fg="white", width=12, relief="flat", padx=8, pady=5).pack(side="left", padx=5)

        tk.Label(card, text="Администратор: admin / admin123\nБиблиотекарь: librarian / library123",
                 fg="#64748B", justify="left").grid(row=4, column=0, columnspan=2, pady=(16, 0))

        self.login_entry.bind("<Return>", lambda event: self.login())
        self.password_entry.bind("<Return>", lambda event: self.login())
        self.login_entry.focus_set()

    def login(self) -> None:
        login = self.login_entry.get().strip()
        password = self.password_entry.get()
        user = self.db.authenticate(login, password)
        if user is None:
            messagebox.showerror("Ошибка входа", "Неверный логин или пароль.", parent=self.root)
            self.password_entry.delete(0, "end")
            self.password_entry.focus_set()
            return

        self.user = dict(user)
        self.show_main()

    def show_main(self) -> None:
        self.root.title("Библиотечная система")
        self._clear_root()

        header = tk.Frame(self.root, bg="#1E3A5F", padx=16, pady=10)
        header.pack(fill="x")
        role_name = "Администратор" if self.user["role"] == "admin" else "Библиотекарь"
        tk.Label(header, text="Библиотечная система", font=("Segoe UI", 17, "bold"),
                 bg="#1E3A5F", fg="white").pack(side="left")
        tk.Label(header, text=f"{role_name}: {self.user['login']}",
                 bg="#1E3A5F", fg="#DCE6F1").pack(side="right")

        nav = tk.Frame(self.root, bg="#EDF2F7", padx=10, pady=8)
        nav.pack(fill="x")

        if self.user["role"] == "admin":
            self._nav_button(nav, "Добавить книгу", lambda: self.show_add_form())
        self._nav_button(nav, "Список книг", lambda: self.show_catalog())
        self._nav_button(nav, "Поиск", lambda: self.show_search())
        self._nav_button(nav, "Выдать книгу", lambda: self.show_issue())
        self._nav_button(nav, "Вернуть книгу", lambda: self.show_returns())
        self._nav_button(nav, "Выйти из аккаунта", self.show_login)

        self.content = tk.Frame(self.root, padx=12, pady=12)
        self.content.pack(fill="both", expand=True)
        self.show_catalog()

    def _nav_button(self, parent: tk.Frame, text: str, command) -> None:
        tk.Button(parent, text=text, command=command, font=("Segoe UI", 9),
                  bg="#FFFFFF", relief="solid", borderwidth=1, padx=8, pady=5).pack(
            side="left", padx=3
        )

    def _clear_content(self) -> None:
        for widget in self.content.winfo_children():
            widget.destroy()

    def _clear_root(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()

    def _create_tree(self, parent: tk.Widget, columns, headings, heights=18):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=heights)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=120, anchor="w")
        tree.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.place_forget()
        return tree

    def show_catalog(self) -> None:
        self._clear_content()
        tk.Label(self.content, text="Каталог книг", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))

        table_frame = tk.Frame(self.content)
        table_frame.pack(fill="both", expand=True)

        columns = ("id", "title", "author", "year", "genre", "total", "available")
        headings = ("№", "Название", "Автор", "Год", "Жанр", "Всего", "Доступно")
        self.catalog_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=16)
        widths = (45, 220, 170, 70, 120, 70, 90)
        for column, heading, width in zip(columns, headings, widths):
            self.catalog_tree.heading(column, text=heading)
            self.catalog_tree.column(column, width=width, anchor="w", minwidth=45)
        self.catalog_tree.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.catalog_tree.yview)
        y_scroll.pack(side="right", fill="y")
        self.catalog_tree.configure(yscrollcommand=y_scroll.set)
        self.refresh_catalog()

        if self.user["role"] == "admin":
            action_frame = tk.Frame(self.content)
            action_frame.pack(fill="x", pady=(8, 0))
            tk.Button(action_frame, text="Редактировать", command=self.edit_selected,
                      width=16).pack(side="left", padx=(0, 6))
            tk.Button(action_frame, text="Удалить", command=self.delete_selected,
                      width=16, bg="#DC2626", fg="white").pack(side="left")

    def refresh_catalog(self) -> None:
        if not hasattr(self, "catalog_tree"):
            return
        for item in self.catalog_tree.get_children():
            self.catalog_tree.delete(item)
        for book in self.db.get_books():
            self.catalog_tree.insert("", "end", iid=str(book["id"]), values=(
                book["id"], book["title"], book["author"], book["year"], book["genre"],
                book["total"], book["available"]
            ))

    def show_add_form(self, edit_book=None) -> None:
        self._clear_content()
        editing = edit_book is not None
        tk.Label(
            self.content,
            text="Редактирование книги" if editing else "Добавление книги",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        form = tk.Frame(self.content)
        form.pack(anchor="n", fill="x")

        fields = {}
        labels = [
            ("title", "Название книги"),
            ("author", "Автор"),
            ("year", "Год издания"),
            ("genre", "Жанр"),
            ("total", "Количество экземпляров"),
        ]
        for row, (key, label_text) in enumerate(labels):
            tk.Label(form, text=label_text + ":", width=24, anchor="e").grid(
                row=row, column=0, padx=(0, 10), pady=7
            )
            entry = tk.Entry(form, width=42)
            entry.grid(row=row, column=1, sticky="w")
            fields[key] = entry

        if editing:
            values = {
                "title": edit_book["title"],
                "author": edit_book["author"],
                "year": str(edit_book["year"]),
                "genre": edit_book["genre"],
                "total": str(edit_book["total"]),
            }
            for key, value in values.items():
                fields[key].insert(0, value)

        def save() -> None:
            title = fields["title"].get().strip()
            author = fields["author"].get().strip()
            year_text = fields["year"].get().strip()
            genre = fields["genre"].get().strip()
            total_text = fields["total"].get().strip()

            if not title or not author or not genre:
                messagebox.showerror("Ошибка", "Название, автор и жанр обязательны.", parent=self.root)
                return
            if not year_text.isdigit():
                messagebox.showerror("Ошибка", "Год издания должен быть целым числом.", parent=self.root)
                return
            if not total_text.isdigit():
                messagebox.showerror("Ошибка", "Количество экземпляров должно быть целым числом.", parent=self.root)
                return

            year = int(year_text)
            total = int(total_text)
            if year < 1 or year > 2100:
                messagebox.showerror("Ошибка", "Введите корректный год издания.", parent=self.root)
                return
            if total < 0:
                messagebox.showerror("Ошибка", "Количество экземпляров не может быть отрицательным.", parent=self.root)
                return

            if editing:
                error = self.db.update_book(
                    edit_book["id"], title, author, year, genre, total
                )
                if error:
                    messagebox.showerror("Ошибка", error, parent=self.root)
                    return
                messagebox.showinfo("Успех", "Данные книги изменены.", parent=self.root)
            else:
                self.db.add_book(title, author, year, genre, total)
                messagebox.showinfo("Успех", "Книга добавлена в каталог.", parent=self.root)
            self.show_catalog()

        actions = tk.Frame(self.content)
        actions.pack(anchor="w", pady=12, padx=(154, 0))
        tk.Button(actions, text="Сохранить", command=save, width=14,
                  bg="#2563EB", fg="white").pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Отмена", command=self.show_catalog, width=14).pack(side="left")

    def edit_selected(self) -> None:
        selected = self.catalog_tree.selection()
        if not selected:
            messagebox.showwarning("Не выбрана книга",
                                   "Выберите книгу в таблице для редактирования.",
                                   parent=self.root)
            return
        book_id = int(selected[0])
        book = self.db.connection.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        self.show_add_form(book)

    def delete_selected(self) -> None:
        selected = self.catalog_tree.selection()
        if not selected:
            messagebox.showwarning("Не выбрана книга",
                                   "Выберите книгу в таблице для удаления.",
                                   parent=self.root)
            return
        book_id = int(selected[0])
        book = self.db.connection.execute(
            "SELECT title FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        if messagebox.askyesno(
            "Удаление книги",
            f"Удалить книгу «{book['title']}»?",
            parent=self.root,
        ):
            self.db.delete_book(book_id)
            messagebox.showinfo("Успех", "Книга удалена.", parent=self.root)
            self.show_catalog()

    def show_search(self) -> None:
        self._clear_content()
        tk.Label(self.content, text="Поиск книг", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        search_frame = tk.Frame(self.content)
        search_frame.pack(fill="x", pady=(0, 8))
        tk.Label(search_frame, text="Поиск по названию, автору или жанру:").pack(side="left")
        search_entry = tk.Entry(search_frame, width=38)
        search_entry.pack(side="left", padx=8)

        table_frame = tk.Frame(self.content)
        table_frame.pack(fill="both", expand=True)
        columns = ("id", "title", "author", "year", "genre", "total", "available")
        headings = ("№", "Название", "Автор", "Год", "Жанр", "Всего", "Доступно")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=16)
        widths = (45, 220, 170, 70, 120, 70, 90)
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        def run_search() -> None:
            for item in tree.get_children():
                tree.delete(item)
            query = search_entry.get()
            books = self.db.get_books(query)
            for book in books:
                tree.insert("", "end", values=(
                    book["id"], book["title"], book["author"], book["year"],
                    book["genre"], book["total"], book["available"]
                ))
            if query.strip() and not books:
                messagebox.showinfo("Результаты поиска",
                                    "Совпадений не найдено.", parent=self.root)

        tk.Button(search_frame, text="Найти", command=run_search,
                  bg="#2563EB", fg="white", width=10).pack(side="left")
        search_entry.bind("<Return>", lambda event: run_search())

        search_entry.insert(0, "")
        run_search()

    def show_issue(self) -> None:
        self._clear_content()
        tk.Label(self.content, text="Выдача книги", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        form = tk.Frame(self.content)
        form.pack(fill="x", pady=(0, 8))
        tk.Label(form, text="Имя читателя:", width=16, anchor="e").grid(
            row=0, column=0, padx=(0, 8), pady=5
        )
        reader_entry = tk.Entry(form, width=32)
        reader_entry.grid(row=0, column=1, sticky="w")
        tk.Label(form, text="Дата выдачи:", width=16, anchor="e").grid(
            row=1, column=0, padx=(0, 8), pady=5
        )
        date_entry = tk.Entry(form, width=32)
        date_entry.grid(row=1, column=1, sticky="w")
        date_entry.insert(0, date.today().isoformat())

        table_frame = tk.Frame(self.content)
        table_frame.pack(fill="both", expand=True)
        columns = ("id", "title", "author", "year", "genre", "total", "available")
        headings = ("№", "Название", "Автор", "Год", "Жанр", "Всего", "Доступно")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=13)
        widths = (45, 220, 170, 70, 120, 70, 90)
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        for book in self.db.get_books():
            tree.insert("", "end", iid=str(book["id"]), values=(
                book["id"], book["title"], book["author"], book["year"],
                book["genre"], book["total"], book["available"]
            ))

        def issue() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Не выбрана книга",
                                       "Выберите книгу для выдачи.", parent=self.root)
                return
            reader = reader_entry.get().strip()
            loan_date = date_entry.get().strip()
            if not reader:
                messagebox.showerror("Ошибка", "Введите имя читателя.", parent=self.root)
                return
            if not loan_date:
                messagebox.showerror("Ошибка", "Введите дату выдачи.", parent=self.root)
                return

            error = self.db.issue_book(int(selected[0]), reader, loan_date)
            if error:
                messagebox.showerror("Ошибка выдачи", error, parent=self.root)
                return
            messagebox.showinfo("Успех", "Книга выдана читателю.", parent=self.root)
            self.show_issue()

        tk.Button(self.content, text="Выдать выбранную книгу", command=issue,
                  bg="#2563EB", fg="white", padx=10, pady=5).pack(anchor="w", pady=(8, 0))

    def show_returns(self) -> None:
        self._clear_content()
        tk.Label(self.content, text="Возврат книг и выданные экземпляры",
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))

        table_frame = tk.Frame(self.content)
        table_frame.pack(fill="both", expand=True)
        columns = ("loan_id", "title", "reader", "date")
        headings = ("№ выдачи", "Книга", "Читатель", "Дата выдачи")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=16)
        widths = (90, 330, 220, 150)
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        def refresh_loans() -> None:
            for item in tree.get_children():
                tree.delete(item)
            for loan in self.db.get_active_loans():
                tree.insert("", "end", iid=str(loan["id"]), values=(
                    loan["id"], loan["title"], loan["reader_name"], loan["loan_date"]
                ))

        refresh_loans()

        def return_selected() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Не выбрана выдача",
                                       "Выберите запись в списке выданных книг.",
                                       parent=self.root)
                return
            if messagebox.askyesno("Возврат книги",
                                   "Подтвердить возврат выбранной книги?",
                                   parent=self.root):
                error = self.db.return_book(int(selected[0]))
                if error:
                    messagebox.showerror("Ошибка", error, parent=self.root)
                    return
                messagebox.showinfo("Успех", "Книга возвращена.", parent=self.root)
                refresh_loans()

        tk.Button(self.content, text="Вернуть выбранную книгу", command=return_selected,
                  bg="#2563EB", fg="white", padx=10, pady=5).pack(anchor="w", pady=(8, 0))

    def exit_app(self) -> None:
        if messagebox.askyesno("Выход", "Выйти из приложения?",
                               parent=self.root):
            self.db.close()
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = LibraryApp(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()


if __name__ == "__main__":
    main()
