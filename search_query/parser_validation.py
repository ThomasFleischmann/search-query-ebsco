#!/usr/bin/env python3
"""EBSCO query parser."""
from __future__ import annotations

import re
import typing


class QueryStringValidator:
    """Class for Query String Validation"""

    FAULTY_OPERATOR_REGEX = r"\b(?:[aA][nN][dD]|[oO][rR]|[nN][oO][tT])\b"
    PARENTHESIS_REGEX = r"[\(\)]"
    linter_messages: typing.List[dict] = []

    def __init__(
        self,
        query_str: str,
        search_field_general: str,
    ):
        self.query_str = query_str
        self.search_field_general = search_field_general

    def check_operator(self) -> None:
        """Check for operators written in not all capital letters."""
        self.linter_messages.clear()

        for match in re.finditer(
            self.FAULTY_OPERATOR_REGEX, self.query_str, flags=re.IGNORECASE
        ):
            operator = match.group()
            start, end = match.span()
            if operator != operator.upper():
                self.query_str = (
                    self.query_str[:start] + operator.upper() + self.query_str[end:]
                )

                self.linter_messages.append(
                    {
                        "level": "Warning",
                        "msg": f"Operator '{operator}' automatically capitalized",
                        "pos": (start, end),
                    }
                )

    def check_parenthesis(self) -> None:
        """Check if the string has the same amount of '(' as well as ')'."""
        self.linter_messages.clear()

        open_count = 0
        close_count = 0

        for match in re.finditer(self.PARENTHESIS_REGEX, self.query_str):
            parenthesis = match.group()

            if parenthesis == "(":
                open_count += 1

            if parenthesis == ")":
                close_count += 1

        if open_count != close_count:
            self.linter_messages.append(
                {
                    "level": "Fatal",
                    "msg": (
                        f"Unbalanced parentheses: open = {open_count},"
                        f" close = {close_count}"
                    ),
                    "pos": "",
                }
            )


class EBSCOQueryStringValidator:
    """Class for EBSCO Query String Validation"""

    UNSUPPORTED_SEARCH_FIELD_REGEX = r"\b(?!OR\b)\b(?!S\d+\b)[A-Z]{2}\b"
    linter_messages: typing.List[dict] = []

    def __init__(
        self,
        query_str: str,
        search_field_general: str,
    ):
        self.query_str = query_str
        self.search_field_general = search_field_general

    def check_search_field_general(self, strict: bool) -> None:
        """Check field 'Search Fields' in content."""
        self.linter_messages.clear()

        if self.search_field_general != "" and strict:
            self.linter_messages.append(
                {
                    "level": "Warning",
                    "msg": (
                        "Content in Search Fields: "
                        f"'{self.search_field_general}'\n"
                        "If content is applicable in search, "
                        "please add to search_terms "
                        "in the search-string"
                    ),
                    "pos": "",
                }
            )

    def filter_search_field(self, strict: bool) -> None:
        """
        Filter out unsupported search_fields.
        Depending on strictness, automatically change or ask user
        """
        self.linter_messages.clear()

        supported_fields = {
            "TI",
            "AU",
            "TX",
            "AB",
            "SO",
            "SU",
            "IS",
            "IB",
            "DE",
            "LA",
            "KW",
        }
        modified_query_list = list(
            self.query_str
        )  # Convert to list for direct modification
        unsupported_fields = []

        for match in re.finditer(self.UNSUPPORTED_SEARCH_FIELD_REGEX, self.query_str):
            field = match.group()
            field = field.strip()
            start, end = match.span()

            if field not in supported_fields:
                unsupported_fields.append(field)
                if strict:
                    while True:
                        # Prompt the user to enter a replacement field
                        replacement = input(
                            f"Unsupported field '{field}' found. "
                            "Please enter a replacement (e.g., 'AB'): "
                        ).strip()
                        if replacement in supported_fields:
                            # Replace directly in the modified query list
                            modified_query_list[start:end] = list(replacement)
                            print(f"Field '{field}' replaced with '{replacement}'.")
                            break
                        print(
                            f"'{replacement}' is not a supported field. "
                            "Please try again."
                        )
                else:
                    # Replace the unsupported field with 'AB' directly
                    modified_query_list[start:end] = list("AB")
                    self.linter_messages.append(
                        {
                            "level": "Error",
                            "msg": (
                                f"search-field-unsupported: '{field}' "
                                "automatically changed to Abstract AB."
                            ),
                            "pos": (start, end),
                        }
                    )

        # Convert the modified list back to a string
        self.query_str = "".join(modified_query_list)

    def validate_token_position(
        self,
        token_type: str,
        previous_token_type: typing.Optional[str],
        position: typing.Optional[tuple[int, int]],
    ) -> None:
        """
        Validate the position of the current token
        based on its type and the previous token type.
        """
        self.linter_messages.clear()

        if previous_token_type is None:
            # First token, no validation required
            return

        valid_transitions = {
            "FIELD": [
                "SEARCH_TERM",
                "PARENTHESIS_OPEN",
            ],  # After FIELD can be SEARCH_TERM; PARENTHESIS_OPEN
            "SEARCH_TERM": [
                "SEARCH_TERM",
                "LOGIC_OPERATOR",
                "PROXIMITY_OPERATOR",
                "PARENTHESIS_CLOSED",
            ],  # After SEARCH_TERM can be SEARCH_TERM (will get connected anyway);
            # LOGIC_OPERATOR; PROXIMITY_OPERATOR; PARENTHESIS_CLOSED
            "LOGIC_OPERATOR": [
                "SEARCH_TERM",
                "FIELD",
                "PARENTHESIS_OPEN",
            ],  # After LOGIC_OPERATOR can be SEARCH_TERM; FIELD; PARENTHESIS_OPEN
            "PROXIMITY_OPERATOR": [
                "SEARCH_TERM",
                "PARENTHESIS_OPEN",
                "FIELD",
            ],  # After PROXIMITY_OPERATOR can be SEARCH_TERM; PARENTHESIS_OPEN; FIELD
            "PARENTHESIS_OPEN": [
                "FIELD",
                "SEARCH_TERM",
                "PARENTHESIS_OPEN",
            ],  # After PARENTHESIS_OPEN can be FIELD; SEARCH_TERM; PARENTHESIS_OPEN
            "PARENTHESIS_CLOSED": [
                "PARENTHESIS_CLOSED",
                "LOGIC_OPERATOR",
                "PROXIMITY_OPERATOR",
            ],  # After PARENTHESIS_CLOSED can be PARENTHESIS_CLOSED;
            # LOGIC_OPERATOR; PROXIMITY_OPERATOR
        }

        if token_type not in valid_transitions.get(previous_token_type, []):
            self.linter_messages.append(
                {
                    "level": "Error",
                    "msg": (
                        f"Invalid token sequence: '{previous_token_type}' "
                        f"followed by '{token_type}'"
                    ),
                    "pos": position,
                }
            )


class QueryListValidator:
    """Class for Query List Validation"""

    linter_messages: typing.List[dict] = []

    def __init__(self, query_list: str, search_field_general: str):
        self.query_list = query_list
        self.search_field_general = search_field_general

    # Possible validations to be implemented in the future
    def check_string_connector(self) -> None:
        """Check string combination, e.g., replace #1 OR #2 -> S1 OR S2."""
        raise NotImplementedError("not yet implemented")

    def check_comments(self) -> None:
        """Check string for comments -> add to file comments"""
        raise NotImplementedError("not yet implemented")
