from linaro_json.document import DocumentObject, DocumentProperty


class DashboardBundle(DocumentObject):
    """
    DashboardBundle object
    """

    format = DocumentProperty(
        description = "Document format identifier",
        type = "string",
        enum = ["Dashboard Bundle Format 1.0.1"],
    )

    test_runs = DocumentProperty(
        description = "Array of TestRun objects",
        type = "array",
        optional = True,
        items = 'TestRun'
    )


class TestRun(DocumentObject):
    """
    TestRun object.
    """

    analyzer_assigned_uuid = DocumentProperty(
        description = "UUID that was assigned by the log analyzer during processing",
        type = "string",
    )

    analyzer_assigned_date = DocumentProperty(
        description = "Time stamp in ISO 8601 format that was assigned by the log analyzer during processing. The exact format is YYYY-MM-DDThh:mm:ssZ",
        type = "string",
        format = "date-time",
    )

    time_check_performed = DocumentProperty(
        description = "Indicator on whether the log analyzer had accurate time information",
        type = "boolean",
    )

    attributes = DocumentProperty(
        description = "Container for additional attributes defined by the test and their values during this particular run",
        type =  "object",
        optional =  True,
        additionalProperties = DocumentProperty(
            description = "Arbitrary properties that are defined by the test",
            type =  "string",
        ),
    )

    test_id = DocumentProperty(
        description = "Test identifier. Must be a well-defined (in scope of the dashboard) name of the test",
        type = "string",
    )

    test_results = DocumentProperty(
        description = "Array of TestResult objects",
        type = "array",
        items = 'TestResult'
    )

    # TODO: attachments, hardware_context, software_context


class TestResult(DocumentObject):
    """
    TestResult object
    """

    test_case_id = DocumentProperty(
        description = "Identifier of the TestCase this test result came from",
        type = "string",
        optional = True
    )

    result = DocumentProperty(
        description = "Status code of this test result",
        type = "string",
        enum = ["pass", "fail", "skip", "unknown"]
    )

    message = DocumentProperty(
        description = "Message scrubbed from the log file",
        type = "string",
        optional = "true",
    )

    measurement = DocumentProperty(
        description = "Numerica measurement associated with the test result",
        type = "number",
        optional = True,
        requires = "test_case_id",
    )

    units = DocumentProperty(
        description = "Units for measurement",
        type = "string",
        optional = True,
        requires = "measurement",
    )

    timestamp = DocumentProperty(
        description = "Date and time when the test was performed",
        type = "string",
        optional = True,
        format = "date-time",
    )

    duration = DocumentProperty(
        description = "Duration of the test case. Duration is stored in the following format '[DAYS]d [SECONDS]s [MICROSECONDS]us'",
        type = "string",
        optional = True
    )

    log_filename = DocumentProperty(
        description = "Filename of the log file which this test result was scrubbed from",
        type = "string",
        optional = "true",
    )

    log_lineno = DocumentProperty(
        description = "Precise location in the log file (line number)",
        type = "integer",
        optional = True,
        requires = "log_filename",
    )

    attributes = DocumentProperty(
        description = "Container for additional attributes defined by the test result",
        type = "object",
        optional = True,
        additionalProperties = DocumentProperty(
            description = "Arbitrary properties that are defined by the particular test result",
            type = "string"
        )
    )
