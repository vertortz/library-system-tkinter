import tempfile
import unittest
from pathlib import Path

from library_app import LibraryDatabase


class LibraryDatabaseTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = LibraryDatabase(Path(folder.name) / "test.db")

    def tearDown(self):
        self.db.close()

    def test_demo_books_and_users_exist(self):
        self.assertGreaterEqual(len(self.db.get_books()), 10)
        self.assertIsNotNone(self.db.authenticate("admin", "admin123"))
        self.assertIsNotNone(self.db.authenticate("librarian", "library123"))

    def test_search_is_partial_and_case_insensitive(self):
        books = self.db.get_books("ВОЙНА")
        self.assertEqual(len(books), 1)

    def test_issue_and_return_change_available_count(self):
        book = self.db.get_books()[0]
        error = self.db.issue_book(book["id"], "Иван Иванов", "2026-11-26")
        self.assertEqual(error, "")
        updated = self.db.connection.execute(
            "SELECT available FROM books WHERE id = ?", (book["id"],)
        ).fetchone()
        self.assertEqual(updated["available"], book["available"] - 1)

        loan = self.db.get_active_loans()[0]
        error = self.db.return_book(loan["id"])
        self.assertEqual(error, "")
        restored = self.db.connection.execute(
            "SELECT available FROM books WHERE id = ?", (book["id"],)
        ).fetchone()
        self.assertEqual(restored["available"], book["available"])

    def test_update_book_rejects_total_below_active_loans(self):
        book = self.db.get_books()[0]
        self.db.issue_book(book["id"], "Тест Читатель", "2026-11-26")
        error = self.db.update_book(
            book["id"], book["title"], book["author"], book["year"],
            book["genre"], 0
        )
        self.assertNotEqual(error, "")

    def test_cannot_issue_when_no_available_copies(self):
        book = self.db.get_books()[0]
        self.db.update_book(
            book["id"], book["title"], book["author"], book["year"],
            book["genre"], 0
        )
        error = self.db.issue_book(book["id"], "Тест Читатель", "2026-11-26")
        self.assertNotEqual(error, "")


if __name__ == "__main__":
    unittest.main()
