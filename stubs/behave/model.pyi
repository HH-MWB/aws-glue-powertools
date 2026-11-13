from collections.abc import Iterator

class Row:
    def __getitem__(self, item: str) -> str: ...
    def __iter__(self) -> Iterator[str]: ...

class Table:
    headings: list[str]
    rows: list[Row]
    def __iter__(self) -> Iterator[Row]: ...
