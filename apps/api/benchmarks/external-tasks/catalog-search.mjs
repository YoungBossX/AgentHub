export function searchBooks(books, query) {
  return books.filter((book) => book.title.includes(query));
}
