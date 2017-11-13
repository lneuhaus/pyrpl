class UnexpectedPyrplError(Exception):
    """Raise when an unexpected error occurs that should be reported"""
    # color codes
    STARTC = "\x1b[35m"  # purple
    ENDC = "\x1b[0m"  # normal
    pyrpl_error_message = STARTC + """\n\n
        An unexpected error occured in PyRPL. Please help us to improve the
        program by copy-pasting the full error message and optionally some
        additional information regarding your setup on
        https://www.github.com/lneuhaus/pyrpl/issues as a new issue. It is
        possible that we can help you to get rid of the error. If your error
        is related to improper usage of the PyRPL API, your report will
        help us improve the documentation. Thanks! """ + ENDC
    def __init__(self, message="", **kwargs):
        self.message = message + self.pyrpl_error_message
        super(UnexpectedPyrplError, self).__init__(self.message, **kwargs)


class ExpectedPyrplError(Exception):
    """Raise when an unexpected error occurs that should be reported"""
    # color codes
    STARTC = "\x1b[35m"  # purple
    ENDC = "\x1b[0m"  # normal
    pyrpl_error_message = STARTC + """\n\n
        An expected error occured in PyRPL. Please follow the instructions
        in this error message and retry! """ + ENDC
    def __init__(self, message="", **kwargs):
        self.message = message + self.pyrpl_error_message
        super(ExpectedPyrplError, self).__init__(self.message, **kwargs)

class NotReadyError(ValueError):
    pass
