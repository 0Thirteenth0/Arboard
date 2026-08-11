import threading


# PyMuPDF documents are processed on background threads to keep tkinter
# responsive, but library operations are serialized for process-wide safety.
PDF_OPERATION_LOCK = threading.RLock()
