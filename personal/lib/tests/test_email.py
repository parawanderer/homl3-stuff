import pytest
from pathlib import Path


from ..email import EmailReader

def test_multipart_multiple_text():
    emails = [
        Path('datasets/spam/easy_ham/00066.7dda463deb5e41ba1af3a0da55ab504b'),
        Path('datasets/spam/easy_ham/00067.23813c5ac6ce66fd892ee5501fd5dbd2')
    ]

    results = EmailReader.read(emails)

    assert results is not None
    assert len(results) == 2