from search_agent.page_labels import pdf_page_labels, resolve_printed_pages


def test_equal_numbering_from_pdf_metadata() -> None:
    assert resolve_printed_pages(["one", "two", "three"], ["1", "2", "3"]) == ["1", "2", "3"]


def test_introductory_pages_do_not_create_a_fixed_offset() -> None:
    texts = ["Cover", "Contents", "Chapter\n1", "Details\n2", "More\n3"]
    assert resolve_printed_pages(texts) == [None, None, "1", "2", "3"]


def test_roman_numeral_front_matter_and_numeric_body_are_detected_as_separate_runs() -> None:
    texts = ["Preface\ni", "Contents\nii", "Tables\niii", "Chapter\n1", "Details\n2"]
    assert resolve_printed_pages(texts) == ["i", "ii", "iii", "1", "2"]


def test_missing_or_isolated_printed_labels_remain_unknown() -> None:
    assert resolve_printed_pages(["Cover", "Only one page\n7", "Unnumbered appendix"]) == [None, None, None]


def test_non_numeric_pdf_metadata_labels_are_preserved_verbatim() -> None:
    assert resolve_printed_pages(["cover", "appendix", "appendix"], ["Cover", "A-1", "A-2"]) == [
        "Cover",
        "A-1",
        "A-2",
    ]


def test_pdf_labels_are_used_only_when_page_label_metadata_exists() -> None:
    class Root(dict[str, object]):
        def get_object(self) -> "Root":
            return self

    class Reader:
        def __init__(self, has_labels: bool) -> None:
            self.trailer = {"/Root": Root({"/PageLabels": object()} if has_labels else {})}
            self.page_labels = ["i", "1"]

    assert pdf_page_labels(Reader(True), 2) == ["i", "1"]
    assert pdf_page_labels(Reader(False), 2) is None
