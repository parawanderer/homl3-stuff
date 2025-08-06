from collections import defaultdict
import email
from email import policy
from email.message import EmailMessage
import json
from pathlib import Path
import re
import pandas as pd
from typing import Any
from email.utils import getaddresses
from bs4 import BeautifulSoup


CONTENT_TYPE_HTML = "text/html"
CONTENT_TYPE_PLAIN = "text/plain"

HTML = 'html'
PLAIN = 'plain'


RE_WHITESPACE = re.compile(r'\s')
RE_SPACES = re.compile(r'\s{2,}')


# https://docs.python.org/3/library/email.message.html

def load_email(file_path: Path) -> EmailMessage:
    with file_path.open('rb') as fp:
        return email.parser.BytesParser(policy=email.policy.default).parse(fp)


def _collapse_spaces(spaced_text: str) -> str:
    return RE_SPACES.sub(" ", spaced_text) # collapse multispace into single space


def _count_words(text: str) -> int:
    return len(text.split(" "))


def _is_whitespace(text: str) -> bool:
    return bool(RE_WHITESPACE.match(text))


def html_to_text(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        html_stripped = soup.get_text()
        return _collapse_spaces(html_stripped)
    except Exception as e:
        print("Failed to parse html, returning empty")
        return ""


class EmailContent:
    TYPE_HTML = 'html'
    TYPE_PLAIN = 'plain'
    TYPE_BOTH = 'both'

    def __init__(self, html: str, plain: str, content_types: dict[str, int], multipart: bool, non_main_count: int):
        self.html = html
        self.plain = plain
        self.plain_stripped = None if self.plain is None else _collapse_spaces(self.plain)
        self.content_types = content_types
        self.multipart = multipart
        self.html_text = None if self.html is None else html_to_text(self.html)
        self.non_main_count = non_main_count

    @property
    def has_both(self) -> bool:
        return self.html is not None and self.plain is not None

    @property
    def type(self) -> bool:
        if self.has_both:
            return EmailContent.TYPE_BOTH

        has_html: bool = self.html is not None

        return EmailContent.TYPE_HTML if has_html else EmailContent.TYPE_PLAIN

    def get_total_length(self):
        l = 0
        if self.html is not None:
            l += len(self.html)

        if self.plain is not None:
            l += len(self.plain)

        return l

    def get_word_count(self):
        count = 0

        if self.html_text is not None:
            # html_text is space-collapsed
            count += _count_words(self.html_text)

        if self.plain is not None:
            # plain text is not space-collapsed
            count += _count_words(_collapse_spaces(self.plain))

        return count

    def get_uppercase_ratio(self):
        total_lower = 0
        total_upper = 0

        process = []
        if self.html_text is not None:
            process.append(self.html_text)

        if self.plain is not None:
            process.append(self.plain)

        for text in process:
            for c in text:
                # this doens't even deal with ascii properly.
                if c.upper() == c:
                    total_upper += 1
                elif not _is_whitespace(c):
                    total_lower += 1

        divisor = max(1, total_upper + total_lower)

        return total_upper / divisor

    def get_explamation_count(self):
        exclamations = 0
        if self.html_text is not None:
            exclamations += self.html_text.count("!")

        if self.plain is not None:
            exclamations += self.plain.count("!")

        return exclamations



class EmailReader:
    @staticmethod
    def _convert_one(email: EmailMessage) -> dict[str, Any]:
        content: EmailContent = EmailReader._get_body(email)

        from_email = email.get("From")
        from_name_and_email = getaddresses([from_email])
        from_uses_freemail = from_name_and_email[0][1].split("@")[1].endswith((
            "gmail.com",
            "hotmail.com",
            "yahoo.com",
            "msn.com"
        ))

        to_emails = email.get("To")
        to_names_and_emails = getaddresses([to_emails])
        to_emails_count = len(to_names_and_emails)
        to_names = ",".join([e[0] for e in to_names_and_emails if len(e[0]) > 0])
        to_emails_only = ",".join([e[1] for e in to_names_and_emails if len(e[1]) > 0])

        reply_to = email.get("Reply-To")
        reply_to_names_and_emails = getaddresses([reply_to])

        to_is_reply_to = to_emails is not None and to_emails == reply_to

        list_unsub = email.get("List-Unsubscribe")
        has_list_unsub: bool = list_unsub is not None

        char_count: int = content.get_total_length()
        word_count: int = content.get_word_count()
        shoutiness: float = content.get_uppercase_ratio()
        exclamations: int = content.get_explamation_count()

        # Matches to output columns in DataFrame
        msg_data: dict[str, Any] = {
            "subject": email.get("Subject"),
            "from_raw": from_email,
            "from_name": from_name_and_email[0][0],
            "from_email": from_name_and_email[0][1],
            "from_uses_freemail": from_uses_freemail,
            "to_raw": to_emails,
            "to_names": to_names,
            "to_emails": to_emails_only,
            "to_emails_count": to_emails_count,
            "reply_to_raw": reply_to,
            "reply_to_name": reply_to_names_and_emails[0][0],
            "reply_to_email": reply_to_names_and_emails[0][1],
            "to_is_reply_to": to_is_reply_to,
            "cc": email.get("Cc"),
            "list_unsub": list_unsub,
            "has_list_unsub": has_list_unsub,
            "content_type_raw": email.get("Content-Type"),
            "date": email.get("Date"),
            "message_id": email.get("Message-ID"),
            "x_mailer": email.get("X-Mailer"),
            "user_agent": email.get("User-Agent"),
            "type": content.type,
            "html_body": content.html,
            "html_body_stripped": content.html_text,
            "plain_body": content.plain,
            "plain_body_stripped": content.plain_stripped,
            "content_types": json.dumps(content.content_types),
            "non_main_content": content.non_main_count,
            "multipart": content.multipart,
            "char_count": char_count,
            "word_count": word_count,
            "shoutiness": shoutiness,
            "exclamations": exclamations
        }

        return msg_data

    @staticmethod
    def _safe_get_content(part) -> str:
        charset = part.get_content_charset()

        if charset is None or charset.lower() in {"default_charset", "unknown-8bit"}:
            charset = "latin-1"

        try:
            return part.get_payload(decode=True).decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            # absolute worst case, fallback again
            return part.get_payload(decode=True).decode("latin-1", errors="replace")

    @staticmethod
    def _get_body(email: EmailMessage) -> EmailContent:
        try:
            if email.is_multipart():

                types_counter: dict[str, int] = {}
                non_main_types: int = 0
                parts: dict[str, list[str]] = defaultdict(list)

                for part in email.iter_parts(): # extract multipart parts

                    content_type = part.get_content_type()

                    # track # of content types
                    if content_type not in types_counter:
                        types_counter[content_type] = 0
                    types_counter[content_type] += 1

                    # Extract interesting bodies
                    if content_type == CONTENT_TYPE_HTML:
                        parts[HTML].append(EmailReader._safe_get_content(part))

                    elif content_type == CONTENT_TYPE_PLAIN:
                        parts[PLAIN].append(EmailReader._safe_get_content(part))

                    else:
                        non_main_types += 1
                        print(f"Ignoring content type '{content_type}'...")

                html_concat: str = None if HTML not in parts else "\n".join(parts[HTML])
                plain_concat: str = None if PLAIN not in parts else "\n".join(parts[PLAIN])

                return EmailContent(
                    html=html_concat,
                    plain=plain_concat,
                    content_types=types_counter,
                    multipart=True,
                    non_main_count=non_main_types
                )

            else:
                content_type = email.get_content_type().lower()
                types_counter: dict[str, int] = {content_type: 1}
                html_content: str = None
                plain_content: str = None

                if content_type == CONTENT_TYPE_HTML:
                    html_content = EmailReader._safe_get_content(email)

                elif content_type == CONTENT_TYPE_PLAIN:
                    plain_content = EmailReader._safe_get_content(email)

                elif content_type.startswith("multipart/"):
                    print("Email claims to be multipart but isn't. Skipping.")

                else:
                    print(f"Unhandled content type: {content_type}")

                return EmailContent(
                    html=html_content,
                    plain=plain_content,
                    content_types=types_counter,
                    multipart=False,
                    non_main_count=0
                )

        except Exception as e:
            print("Could not parse email body")
            raise e

    @staticmethod
    def read(emails: list[Path]) -> pd.DataFrame:

        dict_list: list[list[Any]] = []

        for path in emails:
            print(f"Now loading... '{path.absolute}'")
            converted = EmailReader._convert_one(load_email(path))
            dict_list.append(converted)

        return pd.DataFrame(dict_list)