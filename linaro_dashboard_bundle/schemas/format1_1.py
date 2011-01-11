"""
Partial document schema for Dashboard Bundle Format 1.1 documents

Useful for constructing objects with :class:`linaro_json.DocumentBuilder`
"""


from linaro_json import document


class Attributes(document.Object):
    """
    Container for additional attributes.

    May store any properties as long as they are strings.
    """

    class Meta:
        additionalProperties = document.Property(
            description = "Arbitrary properties that are defined by the particular test result",
            type = "string"
        )


class Attachment(document.Object):
    """
    Attachment
    """

    filename = document.Property(
        type = "string"
    )
    content = document.Property(
        type = "string",
        contentEncoding = "base64"
    )


class TestResult(document.Object):
    """
    TestResult object
    """

    test_case_id = document.Property(
        description = "Identifier of the TestCase this test result came from",
        type = "string",
        optional = True
    )
    result = document.Property(
        description = "Status code of this test result",
        type = "string",
        enum = ["pass", "fail", "skip", "unknown"]
    )
    message = document.Property(
        description = "Message scrubbed from the log file",
        type = "string",
        optional = "true",
    )
    measurement = document.Property(
        description = "Numerica measurement associated with the test result",
        type = "number",
        optional = True,
        requires = "test_case_id",
    )
    units = document.Property(
        description = "Units for measurement",
        type = "string",
        optional = True,
        requires = "measurement",
    )
    timestamp = document.Property(
        description = "Date and time when the test was performed",
        type = "string",
        optional = True,
        format = "date-time",
    )
    # TODO: convert to UTC-Miliseconds as defined in JSON schema format
    duration = document.Property(
        description = "Duration of the test case. Duration is stored in the following format '[DAYS]d [SECONDS]s [MICROSECONDS]us'",
        type = "string",
        optional = True
    )
    log_filename = document.Property(
        description = "Filename of the log file which this test result was scrubbed from",
        type = "string",
        optional = "true",
    )
    log_lineno = document.Property(
        description = "Precise location in the log file (line number)",
        type = "integer",
        optional = True,
        requires = "log_filename",
    )
    attributes = document.Property(
        description = "Container for additional attributes defined by the test result",
        type = Attributes,
        optional = True,
    )

    class Meta:
        additionalProperties = False


class SoftwareSource(document.Object):

    branch_vcs = document.Property(
        type = "string",
        enum = ["bzr", "git"]
    )
    branch_url = document.Property(
        type = "string"
    )
    project_name = document.Property(
        type = "string"
    )
    branch_revision = document.Property(
        type = ["string", "integer"]
    )
    commit_timestamp = document.Property(
        type = "string",
        format = "date-time",
        optional = True,
    )

    class Meta:
        additionalProperties = False


class SoftwarePackage(document.Object):

    name = document.Property(
        type = "string"
    )
    version = document.Property(
        type = "string"
    )

    class Meta:
        additionalProperties = False


class SoftwareImage(document.Object):

    name = document.Property(
        type = "string"
    )

    class Meta:
        additionalProperties = False


class SoftwareContext(document.Object):

    image = document.Property(
        type = SoftwareImage,
        optional = True,
    )
    packages = document.Property(
        type = "array",
        items = SoftwareSource,
        optional = True,
    )
    sources = document.Property(
        type = "array",
        items = SoftwareSource,
        optional = True,
    )

    class Meta:
        additionalProperties = False


class HardwareContext(document.Object):

    class Meta:
        additionalProperties = False


class TestRun(document.Object):
    """
    TestRun object.
    """

    analyzer_assigned_uuid = document.Property(
        description = "UUID that was assigned by the log analyzer during processing",
        type = "string",
    )
    analyzer_assigned_date = document.Property(
        description = "Time stamp in ISO 8601 format that was assigned by the log analyzer during processing. The exact format is YYYY-MM-DDThh:mm:ssZ",
        type = "string",
        format = "date-time",
    )
    time_check_performed = document.Property(
        description = "Indicator on whether the log analyzer had accurate time information",
        type = "boolean",
    )
    attributes = document.Property(
        description = "Container for additional attributes defined by the test and their values during this particular run",
        type = 'object',
        optional = True,
    )
    test_id = document.Property(
        description = "Test identifier. Must be a well-defined (in scope of the dashboard) name of the test",
        type = "string",
    )
    test_results = document.Property(
        description = "Array of TestResult objects",
        type = "array",
        items = 'TestResult'
    )
    software_context = document.Property(
        type = SoftwareContext,
        optional = True,
    )
    hardware_context = document.Property(
        type = HardwareContext,
        optional = True,
    )
    attachments = document.Property(
        type = "array",
        items = Attachment,
        optional = True,
    )

    class Meta:
        additionalProperties = False


class DashboardBundle(document.Object):
    """
    DashboardBundle object
    """

    format = document.Property(
        description = "Document format identifier",
        type = "string",
        enum = ["Dashboard Bundle Format 1.1"],
    )
    test_runs = document.Property(
        description = "Array of TestRun objects",
        type = "array",
        optional = True,
        items = TestRun
    )

    class Meta:
        additionalProperties = False
