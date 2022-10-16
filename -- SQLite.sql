-- SQLite
CREATE TABLE transactions (
    'id' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    'symbol' VARCHAR,
    'name' VARCHAR,
    'shares' INT,
    'price' FLOAT,
    'total' FLOAT
)